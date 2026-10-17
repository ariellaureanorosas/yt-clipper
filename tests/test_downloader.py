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
