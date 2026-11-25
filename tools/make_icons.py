"""Gera os ícones do aplicativo (``icons/app.png`` e ``icons/app.ico``).

O desenho original era um quadrado com fundo preto opaco. Este script remove
esse fundo (mantendo o miolo da arte intacto) e regera todos os tamanhos do
``.ico`` a partir de um master 256x256, para ficar nítido na barra de tarefas,
no Explorer e no instalador.

Uso::

    python tools/make_icons.py [origem.png]

Sem argumentos, usa ``icons/app.png`` como origem. A origem pode ter fundo
preto (o fundo é removido automaticamente) ou já ser transparente.
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT / 'icons'
MASTER_SIZE = (256, 256)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
# Pixels mais escuros que isso são considerados fundo (o fundo original é
# preto puro; o miolo da arte nunca chega a ser preto puro e não é alcançado
# pelo preenchimento, que parte apenas das bordas).
BLACK_THRESHOLD = 8
FEATHER_RADIUS = 0.6


def _is_background(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    if alpha < 8:
        return True
    return (
        red <= BLACK_THRESHOLD and green <= BLACK_THRESHOLD and blue <= BLACK_THRESHOLD
    )


def strip_background(image: Image.Image) -> Image.Image:
    """Torna transparente o fundo escuro conectado às bordas da imagem."""
    image = image.convert('RGBA')
    width, height = image.size
    pixels = image.load()
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if visited[index]:
            continue
        visited[index] = 1
        if not _is_background(pixels[x, y]):
            continue

        pixels[x, y] = (0, 0, 0, 0)
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    # Suaviza a borda para não ficar serrilhada em telas com escala.
    alpha = image.getchannel('A').filter(ImageFilter.GaussianBlur(FEATHER_RADIUS))
    image.putalpha(alpha)
    return image


def build_master(source: Path) -> Image.Image:
    with Image.open(source) as opened:
        image = opened.convert('RGBA')
    if image.size != MASTER_SIZE:
        image = image.resize(MASTER_SIZE, Image.LANCZOS)
    return strip_background(image)


def main(argv: list[str]) -> int:
    source = Path(argv[1]) if len(argv) > 1 else ICONS_DIR / 'app.png'
    if not source.is_file():
        print(f'Origem não encontrada: {source}')
        return 1

    master = build_master(source)
    png_path = ICONS_DIR / 'app.png'
    ico_path = ICONS_DIR / 'app.ico'

    master.save(png_path, format='PNG')
    master.save(ico_path, format='ICO', sizes=[(size, size) for size in ICO_SIZES])

    print(f'Gerado {png_path.relative_to(ROOT)} ({master.width}x{master.height})')
    print(f'Gerado {ico_path.relative_to(ROOT)} ({len(ICO_SIZES)} tamanhos)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
