"""Testes das funções puras do módulo de corte (ffmpeg)."""

import pytest

from core.cutter import _build_crop_filter, _format_time


@pytest.mark.parametrize(
    'seconds,expected',
    [
        (0, '00:00:00.000'),
        (59.5, '00:00:59.500'),
        (60, '00:01:00.000'),
        (3661.25, '01:01:01.250'),
    ],
)
def test_format_time(seconds, expected):
    assert _format_time(seconds) == expected


def test_mesma_proporcao_apenas_escala():
    # 1920x1080 -> 1920x1080 não precisa de crop
    result = _build_crop_filter(1920, 1080, 1920, 1080)
    assert result == ['-vf', 'scale=1920:1080']


def test_fonte_larga_recorta_laterais():
    # 16:9 -> 9:16: recorta as laterais e mantém a altura
    filtro = _build_crop_filter(1920, 1080, 1080, 1920)
    assert filtro[0] == '-vf'
    assert filtro[1].startswith('crop=')
    assert filtro[1].endswith('scale=1080:1920')


def test_fonte_estreita_recorta_topo_base():
    # 9:16 -> 16:9: recorta topo/base e mantém a largura
    filtro = _build_crop_filter(1080, 1920, 1920, 1080)
    assert filtro[0] == '-vf'
    assert filtro[1].startswith('crop=')
    assert filtro[1].endswith('scale=1920:1080')


@pytest.mark.parametrize(
    'ow,oh,tw,th',
    [
        (1920, 1081, 1080, 1920),  # fonte com altura ímpar
        (1001, 1080, 1080, 1920),  # fonte com largura ímpar
        (1001, 1920, 1920, 1080),  # fonte estreita com largura ímpar
        (3840, 2160, 1080, 1920),  # 4K -> vertical
    ],
)
def test_dimensoes_de_crop_sao_pares(ow, oh, tw, th):
    # ffmpeg exige largura/altura pares no filtro de crop
    filtro = _build_crop_filter(ow, oh, tw, th)
    assert filtro[0] == '-vf'
    filter_str = filtro[1]
    if filter_str.startswith('crop='):
        crop = filter_str.split(',')[0]  # crop=w:h:x:y
        w, h = crop.split('=')[1].split(':')[:2]
        assert int(w) % 2 == 0
        assert int(h) % 2 == 0