"""Testes dos utilitários de recursos e do ícone empacotado."""

from pathlib import Path

from PIL import Image

from core.resources import executable_dir, is_frozen, resource_path

ROOT = Path(__file__).resolve().parent.parent


def test_resource_path_modo_dev_aponta_para_o_projeto():
    path = Path(resource_path('icons', 'app.ico'))

    assert path.is_file()
    assert path.parent == ROOT / 'icons'


def test_executable_dir_modo_dev_e_a_raiz_do_projeto():
    assert is_frozen() is False
    assert (executable_dir() / 'main.py').is_file()


def test_icone_png_tem_cantos_transparentes():
    with Image.open(ROOT / 'icons' / 'app.png') as image:
        assert image.mode == 'RGBA'
        for corner in ((0, 0), (255, 0), (0, 255), (255, 255)):
            assert image.getpixel(corner)[3] == 0


def test_icone_ico_tem_os_tamanhos_esperados():
    with Image.open(ROOT / 'icons' / 'app.ico') as image:
        sizes = set(image.info.get('sizes', set()))

    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes
