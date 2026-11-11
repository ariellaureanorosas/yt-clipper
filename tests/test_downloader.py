"""Testes da validação de links e do tratamento de erros de download."""

import pytest

from core.downloader import _format_download_error, is_valid_youtube_url


@pytest.mark.parametrize(
    'url',
    [
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'http://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123&index=2',
        'https://www.youtube.com/watch?app=desktop&v=dQw4w9WgXcQ',
        'https://youtu.be/dQw4w9WgXcQ',
        'https://youtu.be/dQw4w9WgXcQ?si=gO0PK97d_4qib2Vv',
        'https://www.youtube.com/shorts/dQw4w9WgXcQ',
        'https://www.youtube.com/live/HkzxcAwEobM?si=gO0PK97d_4qib2Vv',
        'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://music.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://www.youtube.com/embed/dQw4w9WgXcQ',
        'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ',
        'www.youtube.com/watch?v=dQw4w9WgXcQ',
    ],
)
def test_aceita_links_validos(url):
    assert is_valid_youtube_url(url) is True


@pytest.mark.parametrize(
    'url',
    [
        '',
        '   ',
        'não é um link',
        'https://vimeo.com/123456',
        'https://www.google.com',
        'youtube.com',
        'https://www.youtube.com/',
        'https://www.youtube.com/results?search_query=teste',
        'ftp://youtube.com/watch?v=dQw4w9WgXcQ',
    ],
)
def test_rejeita_links_invalidos(url):
    assert is_valid_youtube_url(url) is False


def test_ignora_espacos_ao_redor():
    assert is_valid_youtube_url('  https://youtu.be/dQw4w9WgXcQ  ') is True


def test_erro_de_formato_vira_mensagem_orientativa():
    msg = _format_download_error(Exception('Requested format is not available'))
    assert 'login' in msg.lower()


def test_erro_anti_bot_vira_mensagem_orientativa():
    msg = _format_download_error(Exception('Sign in to confirm you are not a bot'))
    assert 'bloqueou' in msg.lower() or 'tente novamente' in msg.lower()


def test_remove_prefixo_error_duplicado():
    msg = _format_download_error(Exception('ERROR: algo deu errado'))
    assert not msg.startswith('ERROR:')


# ── fetch_video_info / download_video (yt-dlp mockado) ────────


class _FakeYDL:
    """Substitui yt_dlp.YoutubeDL nos testes."""

    info = {
        'title': 'Meu vídeo',
        'duration': 120,
        'thumbnail': 'http://img',
        'id': 'abc123',
    }
    erro = None
    ultimo_opts = None

    def __init__(self, opts):
        type(self).ultimo_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        if type(self).erro:
            raise type(self).erro
        if type(self).info is None:
            return None
        return dict(type(self).info)

    def download(self, urls):
        if type(self).erro:
            raise type(self).erro


@pytest.fixture
def fake_ydl(monkeypatch):
    import core.downloader as downloader

    _FakeYDL.erro = None
    _FakeYDL.ultimo_opts = None
    _FakeYDL.info = {
        'title': 'Meu vídeo',
        'duration': 120,
        'thumbnail': 'http://img',
        'id': 'abc123',
    }
    monkeypatch.setattr(downloader.yt_dlp, 'YoutubeDL', _FakeYDL)
    return _FakeYDL


def test_fetch_video_info_normaliza_campos(monkeypatch, fake_ydl):
    import core.downloader as downloader
    from core.config import AppConfig

    monkeypatch.setattr(downloader, 'get_config', lambda: AppConfig())

    info = downloader.fetch_video_info('https://youtu.be/abc123')

    assert info == {
        'title': 'Meu vídeo',
        'duration': 120,
        'thumbnail_url': 'http://img',
        'id': 'abc123',
    }
    assert fake_ydl.ultimo_opts['socket_timeout'] == 60


def test_fetch_video_info_trata_live_sem_duracao(monkeypatch, fake_ydl):
    import core.downloader as downloader
    from core.config import AppConfig

    monkeypatch.setattr(downloader, 'get_config', lambda: AppConfig())
    monkeypatch.setattr(
        _FakeYDL, 'info', {'title': None, 'duration': None, 'id': 'live'}
    )

    info = downloader.fetch_video_info('https://youtu.be/live')

    assert info['title'] == 'Sem título'
    assert info['duration'] == 0


def test_fetch_video_info_erro_quando_sem_dados(monkeypatch, fake_ydl):
    import core.downloader as downloader
    from core.config import AppConfig

    monkeypatch.setattr(downloader, 'get_config', lambda: AppConfig())
    monkeypatch.setattr(_FakeYDL, 'info', None)

    with pytest.raises(ValueError):
        downloader.fetch_video_info('https://youtu.be/abc')


def test_download_video_retorna_arquivo_baixado(monkeypatch, tmp_path, fake_ydl):
    import core.downloader as downloader
    from core.config import AppConfig

    monkeypatch.setattr(downloader, 'get_config', lambda: AppConfig())
    monkeypatch.setattr(downloader, 'get_ffmpeg_path', lambda: 'ffmpeg')
    (tmp_path / 'video.mp4').write_bytes(b'x')

    caminho = downloader.download_video('https://youtu.be/abc', str(tmp_path), 'video')

    assert caminho.endswith('video.mp4')


def test_download_video_erro_quando_arquivo_nao_existe(monkeypatch, tmp_path, fake_ydl):
    import core.downloader as downloader
    from core.config import AppConfig

    monkeypatch.setattr(downloader, 'get_config', lambda: AppConfig())
    monkeypatch.setattr(downloader, 'get_ffmpeg_path', lambda: 'ffmpeg')

    with pytest.raises(FileNotFoundError):
        downloader.download_video('https://youtu.be/abc', str(tmp_path), 'sumiu')


def test_download_video_converte_erro_em_cancelamento(monkeypatch, tmp_path, fake_ydl):
    import threading

    from yt_dlp.utils import DownloadCancelled

    import core.downloader as downloader
    from core.config import AppConfig

    monkeypatch.setattr(downloader, 'get_config', lambda: AppConfig())
    monkeypatch.setattr(downloader, 'get_ffmpeg_path', lambda: 'ffmpeg')

    evento = threading.Event()
    evento.set()
    fake_ydl.erro = RuntimeError('interrompido')

    with pytest.raises(DownloadCancelled):
        downloader.download_video(
            'https://youtu.be/abc', str(tmp_path), 'video', cancel_event=evento
        )


def test_erro_de_timeout_vira_mensagem_orientativa():
    msg = _format_download_error(Exception('The read operation timed out'))
    assert 'internet' in msg.lower() or 'conexão' in msg.lower()
