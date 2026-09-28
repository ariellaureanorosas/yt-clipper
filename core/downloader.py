"""
Módulo de download e extração de informações de vídeos do YouTube.
Usa yt-dlp como biblioteca Python.
"""

import os
import re
import threading
import time
import yt_dlp

from yt_dlp.utils import DownloadCancelled

from core.cutter import get_ffmpeg_path


# Regex para validação de URLs do YouTube
_YT_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+'
)


def is_valid_youtube_url(url: str) -> bool:
    """Verifica se a URL é um link válido do YouTube."""
    return bool(_YT_REGEX.match(url.strip()))


_FORMAT_ERROR = 'Requested format is not available'


def _format_download_error(e: Exception) -> str:
    """Converte erros comuns de download em mensagens orientativas em pt-BR."""
    msg = str(e)
    # Remove prefixo 'ERROR: ' duplicado que o yt-dlp já inclui na mensagem
    if msg.startswith('ERROR: '):
        msg = msg[len('ERROR: '):]
    if _FORMAT_ERROR in msg:
        return (
            'Este video exige login do YouTube (formatos bloqueados). '
            'Tente novamente ou escolha outro video.'
        )
    if 'bots' in msg or 'bot' in msg or 'Sign in to confirm' in msg:
        return (
            'O YouTube bloqueou o acesso (anti-bot). '
            'Tente novamente mais tarde ou escolha outro video.'
        )
    return msg[:100]


def fetch_video_info(url: str) -> dict:
    """
    Busca informações do vídeo sem baixar.
    Retorna dict com: title, duration, thumbnail_url, id
    """
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        'title': info.get('title', 'Sem título'),
        'duration': info.get('duration', 0),
        'thumbnail_url': info.get('thumbnail', ''),
        'id': info.get('id', ''),
    }


def download_video(
    url: str,
    output_path: str,
    filename: str,
    progress_callback=None,
    start_time: float = None,
    end_time: float = None,
    cancel_event: threading.Event = None,
) -> str:
    """
    Baixa o vídeo e retorna o caminho do arquivo salvo.
    progress_callback(percentual: float, status_msg: str) é chamado durante o download.
    percentual = -1 indica modo indeterminado (barra pulsante — usado quando o total
    não é conhecido, ex.: download via FFmpegFD/subprocesso do yt-dlp).
    cancel_event: se setado, o download aborta (matando o ffmpeg interno se preciso).
    start_time/end_time são aceitos por compatibilidade, mas o download é sempre
    do vídeo inteiro (download por trecho via yt-dlp é ~120x mais lento); o
    recorte exato é feito depois pelo cut_video.
    """
    output_template = os.path.join(output_path, f'{filename}.%(ext)s')

    # Garantir que o yt-dlp encontre o ffmpeg (necessário para o merge das streams
    # e para o download parcial via download_ranges). O yt-dlp verifica a
    # disponibilidade via FFmpegFD.available(), que só respeita a ContextVar
    # _ffmpeg_location (setada pela CLI com --ffmpeg-location) ou o PATH do processo.
    ffmpeg_path = get_ffmpeg_path()
    ffmpeg_dir = os.path.dirname(ffmpeg_path) if ffmpeg_path != 'ffmpeg' else ''
    if ffmpeg_dir and ffmpeg_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

    # Fix o download parcial: faz FFmpegFD.available() retornar True.
    # Definir a ContextVar com o caminho COMPLETO do ffmpeg.exe (a versão CLI,
    # --ffmpeg-location, usa exatamente isso). Sem isso, o yt-dlp reporta
    # "ffmpeg is not installed" para download parcial, mesmo com o binário local.
    if ffmpeg_path != 'ffmpeg':
        try:
            from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
            FFmpegPostProcessor._ffmpeg_location.set(ffmpeg_path)
        except Exception:
            pass

    # Estado compartilhado entre o hook e o monitor
    _state = {
        'last_hook': 0.0,
        'finished_mb': 0.0,  # streams já concluídas (em MB)
        'stop': threading.Event(),  # sinaliza o fim do download p/ o monitor
    }
    if cancel_event is None:
        cancel_event = threading.Event()

    def _progress_hook(d):
        status = d.get('status')
        if cancel_event.is_set():
            raise DownloadCancelled('Cancelado pelo usuário')
        if status == 'downloading' and progress_callback:
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            _state['last_hook'] = time.time()
            speed = d.get('speed')
            speed_str = ''
            if speed:
                if speed > 1_000_000:
                    speed_str = f' ({speed / 1_000_000:.1f} MB/s)'
                else:
                    speed_str = f' ({speed / 1_000:.0f} KB/s)'
            if total and total > 0:
                pct = (downloaded / total) * 100
                progress_callback(pct, f'Baixando... {pct:.1f}%{speed_str}')
            else:
                progress_callback(-1, f'Baixando... {downloaded / 1_000_000:.1f} MB{speed_str}')
        elif status == 'finished' and progress_callback:
            _state['finished_mb'] += (d.get('total_bytes') or d.get('downloaded_bytes', 0)) / 1_000_000
            progress_callback(100, 'Download concluído, processando...')

    def _monitor():
        # Cobre o download via FFmpegFD (subprocesso ffmpeg): o hook não é chamado,
        # então medimos os MB gravados na pasta e, no cancelamento, matamos o ffmpeg.
        token = os.path.basename(output_path)
        while not _state['stop'].wait(0.5):
            if cancel_event.is_set():
                from core.processes import kill_ffmpeg_by_dir_quoted
                kill_ffmpeg_by_dir_quoted(token)
                return
            if progress_callback and (time.time() - _state['last_hook']) > 2.5:
                try:
                    total = sum(
                        os.path.getsize(os.path.join(output_path, f))
                        for f in os.listdir(output_path)
                        if not f.endswith('.mp4')
                    ) / 1_000_000
                except Exception:
                    total = 0.0
                base = _state['finished_mb'] + total
                if base > 1:
                    progress_callback(-1, f'Baixando... {base:.0f} MB (pode demorar)')
                else:
                    progress_callback(-1, 'Baixando... (aguarde)')

    # Download SEMPRE do vídeo inteiro (formato nativo HttpFD, ~20 MB/s).
    # O download do trecho via download_ranges força o ffmpeg (FFmpegFD) e ficou
    # comprovadamente lento (~0,2 MB/s vs ~20 MB/s do nativo): um corte de 50 min
    # levava de 1,5 a 3,5 horas só baixando. Como o cut_video recorta com
    # -ss/-to exatos (re-encode NVENC), fazemos o recorte local sobre o arquivo
    # completo — mais rápido e preciso.
    # Seletor de formato robusto: em 2026 o YouTube parou de oferecer formatos
    # "combinados" (best/best[ext=mp4]) em vários vídeos, e o yt-dlp falha com
    # "Requested format is not available". Cadeia que sempre resolve:
    #   1. H.264 (avc1) + AAC (mp4 + m4a) — compatível com qualquer player,
    #      inclusive Windows Media Player (que NÃO decodifica AV1/VP9/HEVC)
    #   2. H.264 (avc1) + melhor áudio (fallback de áudio)
    #   3. Qualquer mp4 + melhor áudio (pode ser AV1 — o cortador re-encoda)
    #   4. Qualquer bestvideo+bestaudio (merge_output_format garante o .mp4)
    #   5. Formato combinado mp4 (fallback final)
    opts = {
        'format': (
            'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]'
            '/bestvideo[ext=mp4][vcodec^=avc1]+bestaudio'
            '/bestvideo[ext=mp4]+bestaudio[ext=m4a]'
            '/bestvideo[ext=mp4]+bestaudio'
            '/bestvideo+bestaudio'
            '/best[ext=mp4]'
        ),
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'progress_hooks': [_progress_hook],
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
    }

    # Informar ao yt-dlp onde está o ffmpeg (diretório de assets/ ou do PATH)
    if ffmpeg_dir:
        opts['ffmpeg_location'] = ffmpeg_dir

    monitor = threading.Thread(target=_monitor, daemon=True)
    monitor.start()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except DownloadCancelled:
        raise
    except Exception:
        if cancel_event.is_set():
            raise DownloadCancelled('Cancelado pelo usuário')
        raise
    finally:
        cancel_event.clear()
        _state['stop'].set()

    # Encontrar o arquivo baixado
    for ext in ['mp4', 'webm', 'mkv']:
        candidate = os.path.join(output_path, f'{filename}.{ext}')
        if os.path.exists(candidate):
            return candidate

    # Fallback: procurar qualquer arquivo com o nome
    for f in os.listdir(output_path):
        if f.startswith(filename) and os.path.isfile(os.path.join(output_path, f)):
            return os.path.join(output_path, f)

    raise FileNotFoundError(f'Arquivo baixado não encontrado em {output_path}')
