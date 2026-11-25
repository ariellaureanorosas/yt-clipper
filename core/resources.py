"""Localização de recursos empacotados e do diretório de instalação.

Quando o aplicativo roda como executável (PyInstaller), os arquivos de dados
(ícones, ffmpeg) ficam em ``sys._MEIPASS``; rodando do código, ficam na raiz do
projeto. Este módulo centraliza essa diferença.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_path(*parts: str) -> str:
    """Retorna o caminho absoluto de um recurso empacotado com o aplicativo."""
    base = getattr(sys, '_MEIPASS', None)
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def is_frozen() -> bool:
    """``True`` quando rodando como executável empacotado pelo PyInstaller."""
    return bool(getattr(sys, 'frozen', False))


def executable_dir() -> Path:
    """Pasta onde o executável (ou o projeto, em modo dev) está localizado."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
