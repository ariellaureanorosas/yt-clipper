"""
Módulo de corte com Strategy Pattern para encoders, detecção de hardware
e modo baixa memória automático.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Protocol

from core.config import EncoderConfig, get_config
from core.hardware import HardwareCapabilities, get_cached_capabilities
from core.logging_config import get_logger
from core.processes import ProcessingCancelled, register, unregister

logger = get_logger(__name__)


def _base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_ffmpeg_tool(name: str) -> str:
    bundled = os.path.join(_base_dir(), 'assets', name)
    if os.path.isfile(bundled):
        return bundled
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        embedded = os.path.join(meipass, 'assets', name)
        if os.path.isfile(embedded):
            return embedded
    for dir_entry in os.environ.get('PATH', '').split(os.pathsep):
        candidate = os.path.join(dir_entry, name)
        if os.path.isfile(candidate):
            return candidate
    return name


def get_ffmpeg_path() -> str:
    return _find_ffmpeg_tool('ffmpeg.exe')


def get_ffprobe_path() -> str:
    return _find_ffmpeg_tool('ffprobe.exe')


def check_ffmpeg_available() -> bool:
    ffmpeg = get_ffmpeg_path()
    try:
        result = subprocess.run(
            [ffmpeg, '-version'], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ============================================================
# ENCODER STRATEGIES (Strategy Pattern)
# ============================================================


class EncoderStrategy(Protocol):
    """Protocol para estratégias de encoding."""

    def build_cmd(
        self,
        base: list[str],
        filter_args: list[str],
        audio_args: list[str],
        output: str,
        input_path: str,
    ) -> list[str]: ...

    @property
    def label(self) -> str: ...

    @property
    def requires_hwaccel(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class NVENCStrategy:
    """NVIDIA NVENC (requires CUDA)."""

    preset: str = "p1"
    cq: int = 23
    max_threads: int = 0

    @property
    def label(self) -> str:
        return f"NVENC (preset={self.preset}, cq={self.cq})"

    @property
    def requires_hwaccel(self) -> bool:
        return True

    def build_cmd(self, base, filter_args, audio_args, output, input_path):
        cmd = [
            *base,
            '-hwaccel',
            'cuda',
            '-hwaccel_output_format',
            'cuda',
            '-i',
            input_path,
            '-vf',
            filter_args[1] if len(filter_args) > 1 else f'scale_cuda={1920}:{1080}',
            '-c:v',
            'h264_nvenc',
            '-preset',
            self.preset,
            '-cq',
            str(self.cq),
        ]
        if self.max_threads > 0:
            cmd.extend(['-threads', str(self.max_threads)])
        cmd.extend(audio_args)
        cmd.extend(
            ['-movflags', '+faststart', '-max_muxing_queue_size', '1024', output]
        )
        return cmd


@dataclass(frozen=True, slots=True)
class QuickSyncStrategy:
    """Intel QuickSync (QSV)."""

    preset: str = "veryfast"
    cq: int = 23
    max_threads: int = 0

    @property
    def label(self) -> str:
        return f"QuickSync (preset={self.preset}, cq={self.cq})"

    @property
    def requires_hwaccel(self) -> bool:
        return True

    def build_cmd(self, base, filter_args, audio_args, output, input_path):
        cmd = [
            *base,
            '-init_hw_device',
            'qsv=hw',
            '-filter_hw_device',
            'hw',
            '-i',
            input_path,
            '-vf',
            f'hwupload=extra_hw_frames=64,{filter_args[1] if len(filter_args) > 1 else "scale_qsv=1920:1080"}',
            '-c:v',
            'h264_qsv',
            '-preset',
            self.preset,
            '-global_quality',
            str(self.cq),
        ]
        if self.max_threads > 0:
            cmd.extend(['-threads', str(self.max_threads)])
        cmd.extend(audio_args)
        cmd.extend(
            ['-movflags', '+faststart', '-max_muxing_queue_size', '1024', output]
        )
        return cmd


@dataclass(frozen=True, slots=True)
class VAAPIStrategy:
    """VAAPI (AMD/Intel no Linux)."""

    preset: str = "veryfast"
    cq: int = 23
    max_threads: int = 0

    @property
    def label(self) -> str:
        return f"VAAPI (preset={self.preset}, cq={self.cq})"

    @property
    def requires_hwaccel(self) -> bool:
        return True

    def build_cmd(self, base, filter_args, audio_args, output, input_path):
        cmd = [
            *base,
            '-hwaccel',
            'vaapi',
            '-hwaccel_output_format',
            'vaapi',
            '-vaapi_device',
            '/dev/dri/renderD128',
            '-i',
            input_path,
            '-vf',
            f'hwupload,{filter_args[1] if len(filter_args) > 1 else "scale_vaapi=1920:1080"}',
            '-c:v',
            'h264_vaapi',
            '-qp',
            str(self.cq),
        ]
        if self.max_threads > 0:
            cmd.extend(['-threads', str(self.max_threads)])
        cmd.extend(audio_args)
        cmd.extend(
            ['-movflags', '+faststart', '-max_muxing_queue_size', '1024', output]
        )
        return cmd


@dataclass(frozen=True, slots=True)
class VideoToolboxStrategy:
    """Apple VideoToolbox (macOS)."""

    preset: str = "fast"
    cq: int = 23
    max_threads: int = 0

    @property
    def label(self) -> str:
        return f"VideoToolbox (preset={self.preset}, cq={self.cq})"

    @property
    def requires_hwaccel(self) -> bool:
        return True

    def build_cmd(self, base, filter_args, audio_args, output, input_path):
        cmd = [
            *base,
            '-hwaccel',
            'videotoolbox',
            '-i',
            input_path,
            '-vf',
            filter_args[1] if len(filter_args) > 1 else 'scale=1920:1080',
            '-c:v',
            'h264_videotoolbox',
            '-q:v',
            str(self.cq),
        ]
        if self.max_threads > 0:
            cmd.extend(['-threads', str(self.max_threads)])
        cmd.extend(audio_args)
        cmd.extend(
            ['-movflags', '+faststart', '-max_muxing_queue_size', '1024', output]
        )
        return cmd


@dataclass(frozen=True, slots=True)
class CPUStrategy:
    """Software encoding libx264 (fallback universal)."""

    preset: str = "veryfast"
    crf: int = 23
    max_threads: int = 0
    thread_queue_size: int = 1024
    max_muxing_queue_size: int = 1024
    low_memory: bool = False

    @property
    def label(self) -> str:
        mem_suffix = " [LOW MEM]" if self.low_memory else ""
        return f"CPU libx264 (preset={self.preset}, crf={self.crf}){mem_suffix}"

    @property
    def requires_hwaccel(self) -> bool:
        return False

    def build_cmd(self, base, filter_args, audio_args, output, input_path):
        cmd = [
            *base,
            '-i',
            input_path,
            *filter_args,
            '-c:v',
            'libx264',
            '-preset',
            self.preset,
            '-crf',
            str(self.crf),
            '-pix_fmt',
            'yuv420p',
        ]
        if self.max_threads > 0:
            cmd.extend(['-threads', str(self.max_threads)])
        if self.low_memory:
            cmd.extend(
                [
                    '-thread_queue_size',
                    str(self.thread_queue_size),
                    '-max_muxing_queue_size',
                    str(self.max_muxing_queue_size),
                    '-fflags',
                    '+nobuffer',
                ]
            )
        cmd.extend(audio_args)
        cmd.extend(['-movflags', '+faststart', output])
        return cmd


def _select_strategies(
    caps: HardwareCapabilities, encoder_cfg: EncoderConfig
) -> list[EncoderStrategy]:
    """Seleciona e ordena estratégias baseadas no hardware e config."""
    strategies: list[EncoderStrategy] = []

    # Hardware encoders (ordem de preferência)
    if encoder_cfg.prefer_hardware:
        if caps.has_nvenc:
            strategies.append(
                NVENCStrategy(
                    preset=encoder_cfg.preset_gpu,
                    cq=encoder_cfg.cq,
                    max_threads=encoder_cfg.max_threads,
                )
            )
        if caps.has_quicksync:
            strategies.append(
                QuickSyncStrategy(
                    preset=encoder_cfg.preset_gpu,
                    cq=encoder_cfg.cq,
                    max_threads=encoder_cfg.max_threads,
                )
            )
        if caps.has_vaapi:
            strategies.append(
                VAAPIStrategy(
                    preset=encoder_cfg.preset_gpu,
                    cq=encoder_cfg.cq,
                    max_threads=encoder_cfg.max_threads,
                )
            )
        if caps.has_videotoolbox:
            strategies.append(
                VideoToolboxStrategy(
                    preset=encoder_cfg.preset_gpu,
                    cq=encoder_cfg.cq,
                    max_threads=encoder_cfg.max_threads,
                )
            )

    # CPU fallback (sempre por último se allow_fallback)
    if encoder_cfg.allow_fallback:
        strategies.append(
            CPUStrategy(
                preset=encoder_cfg.preset_cpu,
                crf=encoder_cfg.crf,
                max_threads=encoder_cfg.max_threads,
                thread_queue_size=encoder_cfg.thread_queue_size,
                max_muxing_queue_size=encoder_cfg.max_muxing_queue_size,
                low_memory=encoder_cfg.low_memory_mode,
            )
        )

    return strategies


# ============================================================
# UTILITÁRIOS DE VÍDEO
# ============================================================


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def _get_video_resolution(input_path: str) -> tuple[int, int]:
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe,
                '-v',
                'error',
                '-select_streams',
                'v:0',
                '-show_entries',
                'stream=width,height',
                '-of',
                'csv=p=0',
                input_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(',')
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return (0, 0)


def _get_video_codec(input_path: str) -> str:
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe,
                '-v',
                'error',
                '-select_streams',
                'v:0',
                '-show_entries',
                'stream=codec_name',
                '-of',
                'csv=p=0',
                input_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split(',')[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ''


def _get_audio_codec(input_path: str) -> str:
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe,
                '-v',
                'error',
                '-select_streams',
                'a:0',
                '-show_entries',
                'stream=codec_name',
                '-of',
                'csv=p=0',
                input_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split(',')[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ''


def _build_crop_filter(
    orig_w: int, orig_h: int, target_w: int, target_h: int
) -> list[str]:
    """Retorna args de filtro: ['-vf', 'crop=...:scale=...'] ou ['-vf', 'scale=...']"""
    tw, th = target_w, target_h
    ow, oh = orig_w, orig_h

    def clamp_even(v: int, cap: int) -> int:
        v = min(v, cap)
        return v if v % 2 == 0 else v - 1

    src_ratio = ow / oh
    tgt_ratio = tw / th

    if src_ratio > tgt_ratio:
        crop_h = clamp_even(oh, oh)
        crop_w = clamp_even(round(oh * tw / th), ow)
        x = (ow - crop_w) // 2
        y = 0
        filter_str = f'crop={crop_w}:{crop_h}:{x}:{y},scale={tw}:{th}'
    elif src_ratio < tgt_ratio:
        crop_w = clamp_even(ow, ow)
        crop_h = clamp_even(round(ow * th / tw), oh)
        x = 0
        y = (oh - crop_h) // 2
        filter_str = f'crop={crop_w}:{crop_h}:{x}:{y},scale={tw}:{th}'
    else:
        filter_str = f'scale={tw}:{th}'

    return ['-vf', filter_str]


def _verify_output(path: str) -> bool:
    if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
        return False
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe,
                '-v',
                'error',
                '-select_streams',
                'v:0',
                '-show_entries',
                'stream=codec_name',
                '-of',
                'csv=p=0',
                path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ============================================================
# CUT_VIDEO - PIPELINE PRINCIPAL
# ============================================================


def cut_video(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    target_format: str,
    progress_callback=None,
    cancel_event: threading.Event = None,
) -> str:
    config = get_config()
    caps = get_cached_capabilities()
    encoder_cfg = config.encoder

    ffmpeg = get_ffmpeg_path()

    if target_format == 'vertical':
        target_w, target_h = 1080, 1920
    else:
        target_w, target_h = 1920, 1080

    if not output_path.endswith('.mp4'):
        output_path += '.mp4'

    part_path = output_path + '.part.mp4'

    orig_w, orig_h = _get_video_resolution(input_path)
    needs_scale = orig_w != target_w or orig_h != target_h
    audio_codec = _get_audio_codec(input_path)
    audio_copy = audio_codec == 'aac' and encoder_cfg.audio_copy_if_aac

    if audio_copy:
        audio_args = ['-c:a', 'copy']
    else:
        audio_args = [
            '-c:a',
            encoder_cfg.audio_codec,
            '-b:a',
            encoder_cfg.audio_bitrate,
        ]

    # Base args comuns
    base = [
        ffmpeg,
        '-y',
        '-ss',
        _format_time(start_time),
        '-to',
        _format_time(end_time),
    ]

    # Filtro de vídeo
    if needs_scale:
        filter_args = _build_crop_filter(orig_w, orig_h, target_w, target_h)
    else:
        filter_args = []

    # Stream copy se possível (mesma resolução + H.264)
    video_codec = _get_video_codec(input_path)
    can_stream_copy = (
        not needs_scale
        and video_codec == 'h264'
        and not encoder_cfg.prefer_hardware  # Força re-encode se preferir HW
    )

    if can_stream_copy:
        logger.info('Usando stream copy (corte instantâneo)')
        strategies = [CPUStrategy(label='Stream copy', requires_hwaccel=False)]
    else:
        logger.info(
            'Re-encode necessário: needs_scale=%s, codec=%s', needs_scale, video_codec
        )
        strategies = _select_strategies(caps, encoder_cfg)

    def _remove_part():
        try:
            if os.path.exists(part_path):
                os.remove(part_path)
        except OSError:
            pass

    last_error = None
    for strategy in strategies:
        if progress_callback:
            progress_callback(0, f'Iniciando corte ({strategy.label})...')
        logger.info('Corte: tentando estratégia "%s"', strategy.label)

        if can_stream_copy:
            cmd = [
                *base,
                '-noaccurate_seek',
                '-i',
                input_path,
                '-c:v',
                'copy',
                *audio_args,
                '-avoid_negative_ts',
                'make_zero',
                '-movflags',
                '+faststart',
                '-max_muxing_queue_size',
                '1024',
                part_path,
            ]
        else:
            cmd = strategy.build_cmd(
                base, filter_args, audio_args, part_path, input_path
            )

        logger.debug('FFmpeg cmd: %s', ' '.join(cmd))

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        if cancel_event is None:
            cancel_event = threading.Event()
        register(process)

        duration = end_time - start_time
        time_pattern = re.compile(r'time=(\d+):(\d+):(\d+)\.(\d+)')

        stderr_lines = []
        for line in process.stderr:
            if cancel_event.is_set():
                process.kill()
                process.wait()
                unregister(process)
                _remove_part()
                raise ProcessingCancelled('Corte cancelado')
            stderr_lines.append(line)
            if progress_callback:
                match = time_pattern.search(line)
                if match:
                    h, m, s, ms = map(int, match.groups())
                    current = h * 3600 + m * 60 + s + ms / 100
                    if duration > 0:
                        pct = min((current / duration) * 100, 99)
                        progress_callback(pct, f'Cortando... {pct:.1f}%')

        process.wait()
        unregister(process)

        if process.returncode == 0:
            last_error = None
            logger.info('Corte bem-sucedido com: %s', strategy.label)
            break

        # Falhou - tentar próxima estratégia
        last_error = ''.join(stderr_lines[-30:])
        logger.warning(
            'Corte: estratégia "%s" falhou (código %s): %s',
            strategy.label,
            process.returncode,
            last_error.strip()[:500],
        )
        _remove_part()

        if not encoder_cfg.allow_fallback:
            break

    if last_error:
        if cancel_event and cancel_event.is_set():
            raise ProcessingCancelled('Corte cancelado')
        raise RuntimeError(
            f'Erro ao cortar vídeo (ffmpeg code {process.returncode}):\n{last_error}'
        )

    if not _verify_output(part_path):
        _remove_part()
        raise RuntimeError(
            'Corte gerou arquivo inválido/incompleto (verificação ffprobe falhou). '
            'Tente novamente.'
        )

    os.replace(part_path, output_path)

    if progress_callback:
        progress_callback(100, 'Corte concluído!')

    return output_path


# ============================================================
# FFMPEG AUTO-DOWNLOAD (mantido do original)
# ============================================================

_FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'


def download_ffmpeg(progress_callback=None) -> bool:
    import tempfile
    import urllib.request
    import zipfile

    assets_dir = os.path.join(_base_dir(), 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    if os.path.isfile(os.path.join(assets_dir, 'ffmpeg.exe')):
        return True

    zip_path = os.path.join(tempfile.gettempdir(), 'ffmpeg-download.zip')

    try:
        if progress_callback:
            progress_callback(0, 'Baixando ffmpeg (pode demorar)...')

        def _reporthook(block_num, block_size, total_size):
            if progress_callback and total_size > 0:
                downloaded = block_num * block_size
                pct = min((downloaded / total_size) * 80, 80)
                mb = downloaded / (1024 * 1024)
                total_mb = total_size / (1024 * 1024)
                progress_callback(pct, f'Baixando ffmpeg... {mb:.1f}/{total_mb:.1f} MB')

        urllib.request.urlretrieve(_FFMPEG_URL, zip_path, _reporthook)

        if progress_callback:
            progress_callback(80, 'Extraindo arquivos...')

        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                basename = os.path.basename(member)
                if basename in ('ffmpeg.exe', 'ffprobe.exe'):
                    data = zf.read(member)
                    out_path = os.path.join(assets_dir, basename)
                    with open(out_path, 'wb') as f:
                        f.write(data)

        try:
            os.remove(zip_path)
        except OSError:
            pass

        if os.path.isfile(os.path.join(assets_dir, 'ffmpeg.exe')):
            if progress_callback:
                progress_callback(100, 'FFmpeg instalado com sucesso!')
            return True

        if progress_callback:
            progress_callback(100, 'Falha ao extrair ffmpeg do zip.')
        return False

    except Exception as e:
        try:
            os.remove(zip_path)
        except OSError:
            pass
        if progress_callback:
            progress_callback(0, f'Erro ao baixar ffmpeg: {str(e)[:80]}')
        return False
