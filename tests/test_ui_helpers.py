"""Testes dos helpers de tempo e de nome de arquivo da interface."""

import pytest

from ui.app_window import _format_duration, _parse_time, _sanitize_filename


@pytest.mark.parametrize(
    'text,expected',
    [
        ('00:00:00', 0.0),
        ('00:01:30', 90.0),
        ('01:00:00', 3600.0),
        ('00:00:05.250', 5.25),
        (' 00:02:00 ', 120.0),
        ('02:30', 150.0),
        ('45', 45.0),
    ],
)
def test_parse_time(text, expected):
    assert _parse_time(text) == pytest.approx(expected)


@pytest.mark.parametrize('text', ['', 'abc', 'aa:bb'])
def test_parse_time_invalido(text):
    with pytest.raises((ValueError, IndexError)):
        _parse_time(text)


@pytest.mark.parametrize(
    'seconds,expected',
    [
        (0, '00:00'),
        (59, '00:59'),
        (60, '01:00'),
        (3599, '59:59'),
        (3600, '01:00:00'),
        (3725, '01:02:05'),
    ],
)
def test_format_duration(seconds, expected):
    assert _format_duration(seconds) == expected


@pytest.mark.parametrize(
    'name,expected',
    [
        ('video normal', 'video normal'),
        ('a<b>:c?.mp4', 'abc.mp4'),
        ('...', 'video'),
        ('', 'video'),
    ],
)
def test_sanitize_filename(name, expected):
    assert _sanitize_filename(name) == expected


def test_sanitize_filename_limita_tamanho():
    assert len(_sanitize_filename('x' * 500)) == 200
