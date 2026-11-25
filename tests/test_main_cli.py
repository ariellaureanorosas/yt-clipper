"""Teste do modo ``--version-file`` usado pelo supervisor de atualização."""

import subprocess
import sys

from core import __version__


def test_version_file_grava_versao_embutida(tmp_path):
    target = tmp_path / 'versao.txt'

    completed = subprocess.run(
        [sys.executable, 'main.py', '--version-file', str(target)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert target.read_text(encoding='utf-8') == __version__


def test_version_file_sem_argumento_retorna_erro(tmp_path):
    completed = subprocess.run(
        [sys.executable, 'main.py', '--version-file'],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 2
