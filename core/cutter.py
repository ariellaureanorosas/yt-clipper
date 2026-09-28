"""
Módulo de corte e redimensionamento de vídeo via ffmpeg.
Usa subprocess para chamar ffmpeg diretamente.
Otimizado para máxima velocidade com stream copy quando possível.
"""

import os
import re
import subprocess
import sys
import threading

from core.processes import ProcessingCancelled, register, unregister


def _base_dir() -> str:
    """
    Diretório base do app (pasta do .exe quando compilado, ou raiz do projeto
    no modo desenvolvimento).
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_ffmpeg_tool(name: str) -> str:
    """
    Retorna o caminho de um binário (.exe) do ffmpeg.
    Prioridade: assets/ local (ao lado do app) → embutido no .exe (PyInstaller
    onefile extrai para sys._MEIPASS) → PATH do sistema → 'ffmpeg'/'ffprobe'.
    """
    # 1) Pasta assets/ ao lado do app (modo dev ou instalado solto)
    bundled = os.path.join(_base_dir(), 'assets', name)
    if os.path.isfile(bundled):
        return bundled

    # 2) Binário embutido no executável onefile (extraído para _MEIPASS)
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        embedded = os.path.join(meipass, 'assets', name)
        if os.path.isfile(embedded):
            return embedded

    # 3) PATH do sistema
    for dir_entry in os.environ.get('PATH', '').split(os.pathsep):
        candidate = os.path.join(dir_entry, name)
        if os.path.isfile(candidate):
            return candidate

    # 4) Fallback: depende da resolução pelo PATH do sistema
    return name


def get_ffmpeg_path() -> str:
    """Retorna o caminho do ffmpeg (assets/ → embutido → PATH)."""
    return _find_ffmpeg_tool('ffmpeg.exe')


def get_ffprobe_path() -> str:
    """Retorna o caminho do ffprobe (mesma lógica do ffmpeg)."""
    return _find_ffmpeg_tool('ffprobe.exe')


def check_ffmpeg_available() -> bool:
    """Verifica se o ffmpeg está acessível no sistema."""
    ffmpeg = get_ffmpeg_path()
    try:
        result = subprocess.run(
            [ffmpeg, '-version'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_assets_dir() -> str:
    """Retorna o caminho da pasta assets/ (onde baixar o ffmpeg)."""
    return os.path.join(_base_dir(), 'assets')


_FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'


def download_ffmpeg(progress_callback=None) -> bool:
    """
    Baixa ffmpeg automaticamente para a pasta assets/.
    Retorna True se sucesso, False se falha.
    """
    import urllib.request
    import zipfile
    import tempfile

    assets_dir = _get_assets_dir()
    os.makedirs(assets_dir, exist_ok=True)

    # Verificar se já existe
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

        # Extrair apenas ffmpeg.exe e ffprobe.exe
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                basename = os.path.basename(member)
                if basename in ('ffmpeg.exe', 'ffprobe.exe'):
                    data = zf.read(member)
                    out_path = os.path.join(assets_dir, basename)
                    with open(out_path, 'wb') as f:
                        f.write(data)

        # Limpar zip temporário
        try:
            os.remove(zip_path)
        except OSError:
            pass

        # Verificar se funcionou
        if os.path.isfile(os.path.join(assets_dir, 'ffmpeg.exe')):
            if progress_callback:
                progress_callback(100, 'FFmpeg instalado com sucesso!')
            return True

        if progress_callback:
            progress_callback(100, 'Falha ao extrair ffmpeg do zip.')
        return False

    except Exception as e:
        # Limpar zip em caso de erro
        try:
            os.remove(zip_path)
        except OSError:
            pass
        if progress_callback:
            progress_callback(0, f'Erro ao baixar ffmpeg: {str(e)[:80]}')
        return False


def _format_time(seconds: float) -> str:
    """Converte segundos para HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def _get_video_resolution(input_path: str) -> tuple:
    """
    Retorna (width, height) do vídeo via ffprobe.
    Retorna (0, 0) se falhar.
    """
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe,
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=p=0',
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
    """
    Retorna o codec de vídeo via ffprobe.
    Retorna '' se falhar.
    """
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe,
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'csv=p=0',
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
    """
    Retorna o codec de áudio do vídeo via ffprobe.
    Retorna '' se falhar.
    """
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe,
                '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'csv=p=0',
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
) -> str:
    """
    Retorna o filtro ffmpeg para crop + scale mantendo proporção (crop-first).
    Primeiro recorta a região central com a proporção ALVO direto da fonte e
    depois escala para o tamanho final — evita o frame intermediário gigante
    que o scale-then-crop cria (ex.: 1080x1920 passava por 3413x1920).
    """
    tw, th = target_w, target_h
    ow, oh = orig_w, orig_h

    def clamp_even(v: int, cap: int) -> int:
        v = min(v, cap)
        return v if v % 2 == 0 else v - 1

    src_ratio = ow / oh
    tgt_ratio = tw / th

    if src_ratio > tgt_ratio:
        # Fonte mais "larga": recortar laterais, manter altura total
        crop_h = oh
        crop_w = clamp_even(round(oh * tw / th), ow)
        x = (ow - crop_w) // 2
        y = 0
    elif src_ratio < tgt_ratio:
        # Fonte mais "estreita": recortar topo/base, manter largura total
        crop_w = ow
        crop_h = clamp_even(round(ow * th / tw), oh)
        x = 0
        y = (oh - crop_h) // 2
    else:
        # Mesma proporção: não precisa crop, só scale
        return f'scale={tw}:{th}'

    return f'crop={crop_w}:{crop_h}:{x}:{y},scale={tw}:{th}'


_NVENC_CACHE: dict = {}


def _nvenc_available() -> bool:
    """Verifica se o encoder NVENC (GPU NVIDIA) está disponível no ffmpeg."""
    if _NVENC_CACHE:
        return _NVENC_CACHE['value']
    ffmpeg = get_ffmpeg_path()
    try:
        result = subprocess.run(
            [ffmpeg, '-hide_banner', '-encoders'],
            capture_output=True,
            text=True,
            timeout=15,
        )
        value = 'h264_nvenc' in result.stdout and result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        value = False
    _NVENC_CACHE['value'] = value
    return value


_CUDA_CACHE: dict = {}


def _cuda_available() -> bool:
    """
    Verifica se o decode/scale via CUDA estão disponíveis no ffmpeg.
    Requer: h264_nvenc + scale_cuda (filtro GPU) + hwaccel cuda.
    """
    if _CUDA_CACHE:
        return _CUDA_CACHE['value']
    ffmpeg = get_ffmpeg_path()
    value = False
    try:
        enc = subprocess.run(
            [ffmpeg, '-hide_banner', '-encoders'],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if 'h264_nvenc' not in enc.stdout or enc.returncode != 0:
            _CUDA_CACHE['value'] = False
            return False
        flt = subprocess.run(
            [ffmpeg, '-hide_banner', '-filters'],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if 'scale_cuda' not in flt.stdout:
            _CUDA_CACHE['value'] = False
            return False
        hw = subprocess.run(
            [ffmpeg, '-hide_banner', '-hwaccels'],
            capture_output=True,
            text=True,
            timeout=15,
        )
        value = 'cuda' in hw.stdout and hw.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        value = False
    _CUDA_CACHE['value'] = value
    return value


def _get_best_video_encoder():
    """
    Retorna a lista de argumentos de codec mais rápida disponível.
    Prefere NVENC (GPU) se disponível; senão cai para libx264 ultrafast.
    Formato: ([codec args], [rate/quality args]).
    """
    if _nvenc_available():
        # NVENC: preset p1 (ultra-rápido) + CQ 23 (qualidade similar ao crf 23)
        return (['-c:v', 'h264_nvenc', '-preset', 'p1'], ['-cq', '23'])
    else:
        # Fallback: libx264 com preset ultrafast
        return (['-c:v', 'libx264', '-preset', 'ultrafast'], ['-crf', '23'])


def _verify_output(path: str) -> bool:
    """
    Confirma que o arquivo de saída tem pelo menos 1 stream de vídeo válido.
    Usado para nunca deixar um arquivo "com cara de pronto" e quebrado.
    """
    if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
        return False
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe,
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'csv=p=0',
                path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def cut_video(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    target_format: str,
    progress_callback=None,
    cancel_event: threading.Event = None,
) -> str:
    """
    Corta e redimensiona o vídeo.
    Usa stream copy quando a resolução já é a alvo (corte instantâneo).
    target_format: 'vertical' (1080x1920) ou 'horizontal' (1920x1080)
    Retorna o caminho do arquivo de saída.
    """
    ffmpeg = get_ffmpeg_path()

    if target_format == 'vertical':
        target_w, target_h = 1080, 1920
    else:
        target_w, target_h = 1920, 1080

    if not output_path.endswith('.mp4'):
        output_path += '.mp4'
    # Grava em arquivo temporário e renomeia no final: nunca deixa um
    # arquivo "com cara de pronto" e corrompido se algo der errado.
    part_path = output_path + '.part.mp4'

    orig_w, orig_h = _get_video_resolution(input_path)
    needs_scale = orig_w != target_w or orig_h != target_h
    audio_codec = _get_audio_codec(input_path)
    audio_copy = audio_codec == 'aac'

    if audio_copy:
        audio_args = ['-c:a', 'copy']
    else:
        audio_args = ['-c:a', 'aac', '-b:a', '192k']

    # Lista de comandos candidatos. A maioria dos casos prepara GPU (CUDA) com
    # fallback CPU: se o comando CUDA falhar (ex.: driver indisponível no
    # momento), tenta automaticamente o pipeline por CPU.
    candidates = []  # (label, cmd)

    if needs_scale:
        # Resolução difere do alvo: re-encode com crop-first (mantém proporção).
        use_copy = False
        crop_filter = _build_crop_filter(orig_w, orig_h, target_w, target_h)
        no_crop = crop_filter.startswith('scale=')
        base = [
            ffmpeg, '-y',
            '-ss', _format_time(start_time),
            '-to', _format_time(end_time),
        ]
        tail = [
            *audio_args,
            '-movflags', '+faststart',
            '-max_muxing_queue_size', '1024',
            part_path,
        ]
        # Sem crop (mesma proporção): scale_cuda na GPU dá ~1,6x de ganho.
        if no_crop and _cuda_available():
            gpu_cmd = [
                *base,
                '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda',
                '-i', input_path,
                '-vf', f'scale_cuda={target_w}:{target_h}',
                '-c:v', 'h264_nvenc', '-preset', 'p1', '-cq', '23',
                *tail,
            ]
            candidates.append(('Re-encode (CUDA)', gpu_cmd))
        cpu_codec, _ = _get_best_video_encoder()
        cpu_cmd = [
            *base,
            '-i', input_path,
            *cpu_codec,
            '-vf', crop_filter, '-pix_fmt', 'yuv420p',
            *tail,
        ]
        candidates.append(('Re-encode', cpu_cmd))
    elif _get_video_codec(input_path) == 'h264':
        # Stream copy: corte instantâneo, sem re-encode. Início exato com
        # -noaccurate_seek + make_zero (evita o "travamento" de ~1s no início).
        use_copy = True
        cmd = [
            ffmpeg, '-y',
            '-ss', _format_time(start_time),
            '-to', _format_time(end_time),
            '-noaccurate_seek',
            '-i', input_path,
            '-c:v', 'copy',
            *audio_args,
            '-avoid_negative_ts', 'make_zero',
            '-movflags', '+faststart',
            '-max_muxing_queue_size', '1024',
            part_path,
        ]
        candidates.append(('Stream copy', cmd))
    else:
        # Codec incompatível (AV1/VP9/HEVC): re-encode para H.264 + yuv420p.
        use_copy = False
        codec_args, _ = _get_best_video_encoder()
        cmd = [
            ffmpeg, '-y',
            '-ss', _format_time(start_time),
            '-to', _format_time(end_time),
            '-i', input_path,
            *codec_args,
            '-pix_fmt', 'yuv420p',
            *audio_args,
            '-movflags', '+faststart',
            '-max_muxing_queue_size', '1024',
            part_path,
        ]
        candidates.append(('Re-encode', cmd))

    def _remove_part():
        try:
            if os.path.exists(part_path):
                os.remove(part_path)
        except OSError:
            pass

    last_error = None
    for mode_label, cmd in candidates:
        if progress_callback:
            progress_callback(0, f'Iniciando corte ({mode_label})...')

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
                    h, m, s, ms = int(match[1]), int(match[2]), int(match[3]), int(match[4])
                    current = h * 3600 + m * 60 + s + ms / 100
                    if duration > 0:
                        pct = min((current / duration) * 100, 99)
                        progress_callback(pct, f'Cortando... {pct:.1f}%')

        process.wait()
        unregister(process)

        if process.returncode == 0:
            last_error = None
            break
        # Pipeline (GPU) falhou → tenta o próximo candidato (CPU)
        last_error = ''.join(stderr_lines[-20:])
        _remove_part()

    if last_error:
        if cancel_event.is_set():
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
