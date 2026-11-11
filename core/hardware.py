"""
Detecção de hardware robusta, cacheada e cross-platform.
Suporta: Windows (WMI), Linux (/proc, lspci, clinfo), macOS (system_profiler).
"""

from __future__ import annotations

import functools
import platform
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Final

import psutil

from core.config import GPUVendor, HardwareProfile
from core.logging_config import get_logger

logger = get_logger(__name__)

# Cache com TTL (segundos)
_HARDWARE_CACHE: dict = {}
_CACHE_TTL = 300  # 5 min
_CACHE_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class HardwareCapabilities:
    """Capacidades de hardware detectadas."""
    has_nvenc: bool
    has_cuda: bool
    has_quicksync: bool
    has_vaapi: bool
    has_videotoolbox: bool
    total_ram_gb: float
    available_ram_gb: float
    gpu_vendor: GPUVendor
    gpu_name: str
    cpu_cores: int
    cpu_threads: int
    is_low_memory: bool
    profile: HardwareProfile
    
    def best_encoder_order(self) -> list[str]:
        """Ordem de preferência de encoders baseada no hardware."""
        order = []
        if self.has_nvenc:
            order.append("h264_nvenc")
        if self.has_quicksync:
            order.append("h264_qsv")
        if self.has_vaapi:
            order.append("h264_vaapi")
        if self.has_videotoolbox:
            order.append("h264_videotoolbox")
        order.append("libx264")  # Sempre disponível como fallback
        return order
    
    def summary(self) -> str:
        parts = [
            f"GPU: {self.gpu_name} ({self.gpu_vendor.value})",
            f"RAM: {self.total_ram_gb:.1f}GB total / {self.available_ram_gb:.1f}GB livre",
            f"CPU: {self.cpu_cores}C/{self.cpu_threads}T",
            f"Profile: {self.profile.value}",
        ]
        hw_accel = []
        if self.has_nvenc: hw_accel.append("NVENC")
        if self.has_quicksync: hw_accel.append("QuickSync")
        if self.has_vaapi: hw_accel.append("VAAPI")
        if self.has_videotoolbox: hw_accel.append("VideoToolbox")
        if hw_accel:
            parts.append(f"HW Accel: {', '.join(hw_accel)}")
        else:
            parts.append("HW Accel: Nenhum (CPU only)")
        return " | ".join(parts)


def _run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Executa comando com timeout, retorna (code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -1, "", "not found"
    except Exception as e:
        return -1, "", str(e)


def _detect_gpu_windows() -> tuple[GPUVendor, str]:
    """Detecta GPU no Windows via WMI."""
    # Tentar wmic (legado mas confiável)
    code, out, _ = _run_cmd([
        'wmic', 'path', 'win32_VideoController', 'get', 'name', '/format:csv'
    ], timeout=15)
    
    if code == 0 and out:
        # Output CSV: Node,Name
        lines = out.strip().split('\n')
        for line in lines[1:]:  # Pular header
            parts = line.split(',')
            if len(parts) >= 2:
                name = parts[1].strip()
                if name and name.lower() != 'name':
                    vendor = _classify_gpu_vendor(name)
                    return vendor, name
    
    # Fallback: PowerShell Get-CimInstance
    code, out, _ = _run_cmd([
        'powershell', '-NoProfile', '-Command',
        "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
    ], timeout=15)
    
    if code == 0 and out.strip():
        name = out.strip().split('\n')[0].strip()
        vendor = _classify_gpu_vendor(name)
        return vendor, name
    
    return GPUVendor.UNKNOWN, "Unknown"


def _detect_gpu_linux() -> tuple[GPUVendor, str]:
    """Detecta GPU no Linux via lspci / /proc."""
    # lspci -nn (mais confiável)
    code, out, _ = _run_cmd(['lspci', '-nn'], timeout=10)
    if code == 0:
        for line in out.split('\n'):
            if 'VGA' in line or '3D' in line or 'Display' in line:
                vendor = _classify_gpu_vendor(line)
                return vendor, line.strip()
    
    # Fallback: /proc/driver/nvidia/version
    try:
        with open('/proc/driver/nvidia/version', 'r') as f:
            content = f.read()
            if 'NVIDIA' in content:
                return GPUVendor.NVIDIA, "NVIDIA GPU (detected via /proc)"
    except Exception:
        pass
    
    return GPUVendor.UNKNOWN, "Unknown"


def _detect_gpu_macos() -> tuple[GPUVendor, str]:
    """Detecta GPU no macOS via system_profiler."""
    code, out, _ = _run_cmd([
        'system_profiler', 'SPDisplaysDataType'
    ], timeout=15)
    
    if code == 0:
        # Procurar por Chipset/Model
        for line in out.split('\n'):
            line = line.strip()
            if 'Chipset Model' in line or 'Model' in line:
                name = line.split(':', 1)[1].strip() if ':' in line else line
                if name:
                    vendor = _classify_gpu_vendor(name)
                    return vendor, name
    
    # Apple Silicon detection
    if platform.processor() == 'arm' or platform.machine() == 'arm64':
        return GPUVendor.APPLE, f"Apple Silicon ({platform.machine()})"
    
    return GPUVendor.UNKNOWN, "Unknown"


def _classify_gpu_vendor(name: str) -> GPUVendor:
    """Classifica vendor pelo nome da GPU."""
    name_lower = name.lower()
    
    nvidia_patterns = ['nvidia', 'geforce', 'quadro', 'tesla', 'rtx', 'gtx', 'titan']
    amd_patterns = ['amd', 'radeon', 'rx ', 'vega', 'fury', 'pro ', 'instinct']
    intel_patterns = ['intel', 'uhd', 'iris', 'hd graphics', 'xe graphics', 'arc ']
    apple_patterns = ['apple', 'm1', 'm2', 'm3', 'm4']
    
    for pattern in nvidia_patterns:
        if pattern in name_lower:
            return GPUVendor.NVIDIA
    for pattern in amd_patterns:
        if pattern in name_lower:
            return GPUVendor.AMD
    for pattern in intel_patterns:
        if pattern in name_lower:
            return GPUVendor.INTEL
    for pattern in apple_patterns:
        if pattern in name_lower:
            return GPUVendor.APPLE
    
    return GPUVendor.UNKNOWN


def _check_ffmpeg_encoder(ffmpeg: str, encoder: str) -> bool:
    """Verifica se encoder específico está disponível no ffmpeg."""
    code, out, _ = _run_cmd([ffmpeg, '-hide_banner', '-encoders'], timeout=15)
    return code == 0 and encoder in out


def _check_ffmpeg_filter(ffmpeg: str, filter_name: str) -> bool:
    """Verifica se filtro está disponível no ffmpeg."""
    code, out, _ = _run_cmd([ffmpeg, '-hide_banner', '-filters'], timeout=15)
    return code == 0 and filter_name in out


def _check_ffmpeg_hwaccel(ffmpeg: str, hwaccel: str) -> bool:
    """Verifica se hwaccel está disponível no ffmpeg."""
    code, out, _ = _run_cmd([ffmpeg, '-hide_banner', '-hwaccels'], timeout=15)
    return code == 0 and hwaccel in out


def _get_ffmpeg_path() -> str:
    """Obtém caminho do ffmpeg (reutiliza lógica do cutter)."""
    import os
    import sys
    
    def base_dir() -> str:
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1) assets/ local
    bundled = os.path.join(base_dir(), 'assets', 'ffmpeg.exe')
    if os.path.isfile(bundled):
        return bundled
    
    # 2) PyInstaller _MEIPASS
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        embedded = os.path.join(meipass, 'assets', 'ffmpeg.exe')
        if os.path.isfile(embedded):
            return embedded
    
    # 3) PATH
    return 'ffmpeg'


def detect_hardware(force_refresh: bool = False) -> HardwareCapabilities:
    """Detecta capacidades de hardware (com cache TTL)."""
    global _HARDWARE_CACHE
    
    with _CACHE_LOCK:
        if not force_refresh and 'data' in _HARDWARE_CACHE:
            if time.time() - _HARDWARE_CACHE.get('timestamp', 0) < _CACHE_TTL:
                return _HARDWARE_CACHE['data']
    
    logger.info("Detectando hardware do sistema...")
    
    # RAM
    mem = psutil.virtual_memory()
    total_ram_gb = mem.total / (1024 ** 3)
    available_ram_gb = mem.available / (1024 ** 3)
    
    # CPU
    cpu_cores = psutil.cpu_count(logical=False) or 1
    cpu_threads = psutil.cpu_count(logical=True) or 1
    
    # GPU
    system = platform.system().lower()
    if system == 'windows':
        gpu_vendor, gpu_name = _detect_gpu_windows()
    elif system == 'linux':
        gpu_vendor, gpu_name = _detect_gpu_linux()
    elif system == 'darwin':
        gpu_vendor, gpu_name = _detect_gpu_macos()
    else:
        gpu_vendor, gpu_name = GPUVendor.UNKNOWN, "Unknown"
    
    logger.info("GPU detectada: %s (%s)", gpu_name, gpu_vendor.value)
    
    # FFmpeg capabilities
    ffmpeg = _get_ffmpeg_path()
    
    has_nvenc = False
    has_cuda = False
    has_quicksync = False
    has_vaapi = False
    has_videotoolbox = False
    
    if gpu_vendor == GPUVendor.NVIDIA:
        has_nvenc = _check_ffmpeg_encoder(ffmpeg, 'h264_nvenc')
        has_cuda = (has_nvenc and 
                   _check_ffmpeg_filter(ffmpeg, 'scale_cuda') and
                   _check_ffmpeg_hwaccel(ffmpeg, 'cuda'))
    elif gpu_vendor == GPUVendor.INTEL:
        has_quicksync = _check_ffmpeg_encoder(ffmpeg, 'h264_qsv')
        has_vaapi = _check_ffmpeg_encoder(ffmpeg, 'h264_vaapi')
    elif gpu_vendor == GPUVendor.AMD:
        has_vaapi = _check_ffmpeg_encoder(ffmpeg, 'h264_vaapi')
        # AMF (Windows) - verificar se disponível
        has_amf = _check_ffmpeg_encoder(ffmpeg, 'h264_amf')
    elif gpu_vendor == GPUVendor.APPLE:
        has_videotoolbox = _check_ffmpeg_encoder(ffmpeg, 'h264_videotoolbox')
    
    # Determinar profile
    is_low_memory = available_ram_gb < 10.0  # Menos de 10GB livre
    if total_ram_gb >= 32 and gpu_vendor in (GPUVendor.NVIDIA, GPUVendor.AMD):
        profile = HardwareProfile.HIGH_END
    elif total_ram_gb >= 16:
        profile = HardwareProfile.MID_RANGE
    else:
        profile = HardwareProfile.LOW_MEMORY
    
    caps = HardwareCapabilities(
        has_nvenc=has_nvenc,
        has_cuda=has_cuda,
        has_quicksync=has_quicksync,
        has_vaapi=has_vaapi,
        has_videotoolbox=has_videotoolbox,
        total_ram_gb=total_ram_gb,
        available_ram_gb=available_ram_gb,
        gpu_vendor=gpu_vendor,
        gpu_name=gpu_name,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        is_low_memory=is_low_memory,
        profile=profile,
    )
    
    with _CACHE_LOCK:
        _HARDWARE_CACHE = {'data': caps, 'timestamp': time.time()}
    
    logger.info("Hardware detectado: %s", caps.summary())
    return caps


def get_hardware_capabilities() -> HardwareCapabilities:
    """Interface pública - usa cache."""
    return detect_hardware()


def invalidate_hardware_cache() -> None:
    """Invalida cache (útil após instalação de drivers)."""
    global _HARDWARE_CACHE
    with _CACHE_LOCK:
        _HARDWARE_CACHE.clear()


# Auto-detectar na importação (lazy)
_capabilities: HardwareCapabilities | None = None


def get_cached_capabilities() -> HardwareCapabilities:
    """Retorna capacidades cached (detecta na primeira chamada)."""
    global _capabilities
    if _capabilities is None:
        _capabilities = detect_hardware()
    return _capabilities