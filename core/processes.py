"""
Registro central de subprocessos e utilitários de cancelamento/limpeza.
Garante que nenhum ffmpeg/processo órfão fique rodando após cancelamento
ou fechamento da janela.
"""

import os
import subprocess
import threading

_lock = threading.Lock()
_active_procs = set()


class ProcessingCancelled(Exception):
    """Levantada quando o usuário cancela o processamento."""


def register(proc: subprocess.Popen) -> None:
    """Registra um Popen para ser encerrado no cancelamento/limpeza."""
    with _lock:
        _active_procs.add(proc)


def unregister(proc: subprocess.Popen) -> None:
    """Remove um Popen do registro (após terminar normalmente)."""
    with _lock:
        _active_procs.discard(proc)


def kill_all() -> None:
    """Encerra todos os subprocessos registrados que ainda estão ativos."""
    with _lock:
        procs = list(_active_procs)
    for proc in procs:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
    with _lock:
        _active_procs.clear()


def kill_ffmpeg_by_dir_quoted(token: str) -> None:
    """Versão que trata token com caracteres especiais (quoted no PowerShell)."""
    if not token:
        return
    safe_token = token.replace("'", "''")
    ps_cmd = (
        "Get-CimInstance Win32_Process -Filter \"Name='ffmpeg.exe'\" "
        "| Where-Object { $_.CommandLine.Contains('" + safe_token + "') } "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            [
                'powershell', '-NoProfile', '-NonInteractive', '-Command', ps_cmd,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        pass


def cleanup_for_dir(dir_path: str) -> None:
    """
    Encerra processos relacionados à pasta informada (ffmpeg órfãos) e
    remove a pasta com todos os arquivos parciais.
    """
    if not dir_path or not os.path.isdir(dir_path):
        return
    token = os.path.basename(dir_path)
    kill_all()
    kill_ffmpeg_by_dir_quoted(token)
    try:
        import shutil
        shutil.rmtree(dir_path, ignore_errors=True)
    except Exception:
        pass