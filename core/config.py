"""
Configuração centralizada e tipada do YouTube Clipper.
Baseado em 12-factor app: config via ambiente, defaults sensatos, validação.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


class HardwareProfile(str, Enum):
    """Perfis de hardware pré-definidos."""
    HIGH_END = "high_end"          # 32GB+ RAM, GPU dedicada NVIDIA/AMD
    MID_RANGE = "mid_range"        # 16GB RAM, GPU dedicada ou iGPU forte
    LOW_MEMORY = "low_memory"      # 8-12GB RAM, iGPU (ex: Ryzen 5600G)
    CI_CD = "ci_cd"                # Ambiente controlado, determinístico


class GPUVendor(str, Enum):
    """Fabricantes de GPU conhecidos."""
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    APPLE = "apple"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DownloadConfig:
    """Configuração de download via yt-dlp.
    
    Todos os timeouts em segundos. Valores baseados em benchmarks reais
    e recomendações do yt-dlp para redes instáveis.
    """
    socket_timeout: int = 60
    connect_timeout: int = 30
    retries: int = 5
    fragment_retries: int = 5
    extractor_retries: int = 3
    http_chunk_size: int = 10_485_760          # 10 MiB chunks
    concurrent_fragment_downloads: int = 3     # Paralelismo HLS/DASH
    throttled_rate: str | None = None          # ex: "1M", "500K"
    ignore_errors: bool = False
    no_check_certificate: bool = False
    
    # Computados
    @property
    def ydl_params(self) -> dict:
        """Gera parâmetros compatíveis com yt-dlp.YoutubeDL."""
        params = {
            'socket_timeout': self.socket_timeout,
            'retries': self.retries,
            'fragment_retries': self.fragment_retries,
            'extractor_retries': self.extractor_retries,
            'http_chunk_size': self.http_chunk_size,
            'concurrent_fragment_downloads': self.concurrent_fragment_downloads,
            'ignoreerrors': self.ignore_errors,
            'nocheckcertificate': self.no_check_certificate,
        }
        if self.throttled_rate:
            params['throttled_rate'] = self.throttled_rate
        return params
    
    @classmethod
    def for_profile(cls, profile: HardwareProfile) -> Self:
        """Presets por perfil de hardware/rede."""
        match profile:
            case HardwareProfile.LOW_MEMORY | HardwareProfile.CI_CD:
                return cls(
                    socket_timeout=90,
                    connect_timeout=45,
                    retries=8,
                    fragment_retries=8,
                    extractor_retries=5,
                    http_chunk_size=5_242_880,       # 5 MiB - menos pressão de memória
                    concurrent_fragment_downloads=1,  # Serial para baixa RAM
                )
            case HardwareProfile.HIGH_END:
                return cls(
                    socket_timeout=45,
                    connect_timeout=20,
                    retries=3,
                    fragment_retries=3,
                    extractor_retries=2,
                    http_chunk_size=20_971_520,       # 20 MiB - throughput máximo
                    concurrent_fragment_downloads=4,
                )
            case _:  # MID_RANGE
                return cls()


@dataclass(frozen=True, slots=True)
class EncoderConfig:
    """Configuração de encoding de vídeo (ffmpeg)."""
    # Codec de vídeo preferido
    prefer_hardware: bool = True
    allow_fallback: bool = True
    
    # Qualidade
    crf: int = 23                    # libx264
    cq: int = 23                     # NVENC/QuickSync/VAAPI
    preset_cpu: str = "veryfast"     # ultrafast, superfast, veryfast, faster, fast, medium
    preset_gpu: str = "p1"           # p1..p7 (NVENC), fast/medium/slow (outros)
    
    # Baixa memória
    low_memory_mode: bool = False
    max_threads: int = 0             # 0 = auto (ffmpeg decide)
    thread_queue_size: int = 1024
    max_muxing_queue_size: int = 1024
    
    # Pixel format
    pix_fmt: str = "yuv420p"         # Compatibilidade máxima
    
    # Áudio
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_copy_if_aac: bool = True
    
    # Container
    movflags: str = "+faststart"
    
    def __post_init__(self):
        if self.low_memory_mode:
            object.__setattr__(self, 'max_threads', 2)
            object.__setattr__(self, 'thread_queue_size', 256)
            object.__setattr__(self, 'max_muxing_queue_size', 512)
            object.__setattr__(self, 'preset_cpu', 'veryfast')
    
    @classmethod
    def for_profile(cls, profile: HardwareProfile, low_memory_override: bool = False) -> Self:
        """Presets por perfil."""
        low_mem = low_memory_override or profile == HardwareProfile.LOW_MEMORY
        
        match profile:
            case HardwareProfile.HIGH_END:
                return cls(
                    prefer_hardware=True,
                    preset_cpu="fast",
                    preset_gpu="p2",
                    low_memory_mode=low_mem,
                )
            case HardwareProfile.LOW_MEMORY | HardwareProfile.CI_CD:
                return cls(
                    prefer_hardware=False,   # Força CPU - mais previsível
                    preset_cpu="veryfast",
                    low_memory_mode=True,
                )
            case _:  # MID_RANGE
                return cls(
                    prefer_hardware=True,
                    preset_cpu="veryfast",
                    preset_gpu="p1",
                    low_memory_mode=low_mem,
                )


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Configuração global da aplicação."""
    # Perfil ativo (auto-detectado se não setado)
    hardware_profile: HardwareProfile | None = None
    force_low_memory: bool = False
    
    # Diretórios
    assets_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "assets")
    temp_dir: Path | None = None  # None = sistema default
    log_dir: Path | None = None
    
    # FFmpeg
    ffmpeg_timeout: int = 300        # 5 min max por corte
    ffprobe_timeout: int = 30
    
    # UI
    window_width: int = 760
    window_min_height: int = 520
    remember_window_size: bool = True
    
    # Download
    download: DownloadConfig = field(default_factory=DownloadConfig)
    
    # Encoder
    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    
    # Logging
    log_level: str = "INFO"
    log_max_files: int = 10
    log_max_bytes: int = 5_242_880  # 5 MiB
    
    @classmethod
    def load(cls) -> Self:
        """Carrega configuração do ambiente + defaults."""
        # Hardware profile via env
        profile_env = os.getenv("YTCLIPPER_PROFILE", "").lower()
        profile = None
        if profile_env in HardwareProfile.__members__.values():
            profile = HardwareProfile(profile_env)
        
        # Low memory override
        force_low_mem = os.getenv("YTCLIPPER_LOW_MEMORY", "").lower() in ("1", "true", "yes", "on")
        
        # Diretórios
        base_dir = Path(__file__).parent.parent
        assets_dir = Path(os.getenv("YTCLIPPER_ASSETS_DIR", base_dir / "assets"))
        temp_dir = Path(os.getenv("YTCLIPPER_TEMP_DIR")) if os.getenv("YTCLIPPER_TEMP_DIR") else None
        log_dir = Path(os.getenv("YTCLIPPER_LOG_DIR")) if os.getenv("YTCLIPPER_LOG_DIR") else None
        
        # Download config via env (para CI/CD tuning)
        download = DownloadConfig(
            socket_timeout=int(os.getenv("YTCLIPPER_DL_SOCKET_TIMEOUT", "60")),
            connect_timeout=int(os.getenv("YTCLIPPER_DL_CONNECT_TIMEOUT", "30")),
            retries=int(os.getenv("YTCLIPPER_DL_RETRIES", "5")),
            fragment_retries=int(os.getenv("YTCLIPPER_DL_FRAG_RETRIES", "5")),
            extractor_retries=int(os.getenv("YTCLIPPER_DL_EXTRACTOR_RETRIES", "3")),
            http_chunk_size=int(os.getenv("YTCLIPPER_DL_CHUNK_SIZE", str(10_485_760))),
            concurrent_fragment_downloads=int(os.getenv("YTCLIPPER_DL_CONCURRENT", "3")),
            throttled_rate=os.getenv("YTCLIPPER_DL_THROTTLE") or None,
        )
        
        # Encoder config
        encoder = EncoderConfig(
            prefer_hardware=os.getenv("YTCLIPPER_PREFER_HW", "true").lower() != "false",
            allow_fallback=os.getenv("YTCLIPPER_ALLOW_FALLBACK", "true").lower() != "false",
            crf=int(os.getenv("YTCLIPPER_CRF", "23")),
            cq=int(os.getenv("YTCLIPPER_CQ", "23")),
            preset_cpu=os.getenv("YTCLIPPER_PRESET_CPU", "veryfast"),
            preset_gpu=os.getenv("YTCLIPPER_PRESET_GPU", "p1"),
            low_memory_mode=force_low_mem,
            audio_bitrate=os.getenv("YTCLIPPER_AUDIO_BITRATE", "192k"),
        )
        
        return cls(
            hardware_profile=profile,
            force_low_memory=force_low_mem,
            assets_dir=assets_dir,
            temp_dir=temp_dir,
            log_dir=log_dir,
            download=download,
            encoder=encoder,
            log_level=os.getenv("YTCLIPPER_LOG_LEVEL", "INFO"),
        )
    
    def with_profile(self, profile: HardwareProfile) -> Self:
        """Retorna nova config com perfil aplicado (imutável)."""
        download = DownloadConfig.for_profile(profile)
        encoder = EncoderConfig.for_profile(profile, self.force_low_memory)
        return AppConfig(
            hardware_profile=profile,
            force_low_memory=self.force_low_memory,
            assets_dir=self.assets_dir,
            temp_dir=self.temp_dir,
            log_dir=self.log_dir,
            download=download,
            encoder=encoder,
            log_level=self.log_level,
        )


# Instância global singleton (carregada na primeira importação)
_CONFIG: AppConfig | None = None


def get_config() -> AppConfig:
    """Retorna configuração global (carrega na primeira chamada)."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = AppConfig.load()
    return _CONFIG


def set_config(config: AppConfig) -> None:
    """Define configuração global (útil para testes e CLI)."""
    global _CONFIG
    _CONFIG = config


def reset_config() -> None:
    """Reseta para recarregar do ambiente."""
    global _CONFIG
    _CONFIG = None