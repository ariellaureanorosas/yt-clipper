"""
Estado persistente do fluxo de atualização.

Guarda, em ``%LOCALAPPDATA%\\YouTubeClipper\\state``, os arquivos usados para
supervisionar uma atualização:

- ``pending.json``: o que está sendo instalado e qual helper foi iniciado;
- ``last-result.json``: resultado da última tentativa (sucesso/falha, passo,
  código de saída e caminho do log);
- ``failed-version.json``: versão que falhou recentemente, para não oferecer a
  mesma atualização em loop.

A escrita é atômica (arquivo temporário + ``os.replace``) para que um
encerramento no meio da gravação nunca deixe JSON truncado.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

# Tempo durante o qual uma versão que falhou não é oferecida de novo no check
# automático. O usuário ainda pode verificar manualmente.
SUPPRESSION_HOURS = 24.0

_PENDING_NAME = 'pending.json'
_STARTED_NAME = 'started.json'
_RESULT_NAME = 'last-result.json'
_FAILED_NAME = 'failed-version.json'


def state_dir() -> Path:
    """Pasta de estado do atualizador (gravável pelo usuário)."""
    base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
    return Path(base) / 'YouTubeClipper' / 'state'


def _path(name: str) -> Path:
    return state_dir() / name


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f'{path.stem}-', suffix='.tmp', dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return path


def _read_json(path: Path) -> dict | None:
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


# ── Atualização pendente ──────────────────────────────────────


def write_pending(payload: dict) -> Path:
    """Registra a atualização que está sendo aplicada."""
    return _write_json(_path(_PENDING_NAME), payload)


def read_pending() -> dict | None:
    return _read_json(_path(_PENDING_NAME))


def clear_pending() -> None:
    _remove(_path(_PENDING_NAME))


# ── Handshake com o supervisor ────────────────────────────────


def write_started(payload: dict) -> Path:
    return _write_json(_path(_STARTED_NAME), payload)


def read_started() -> dict | None:
    return _read_json(_path(_STARTED_NAME))


def clear_started() -> None:
    _remove(_path(_STARTED_NAME))


# ── Resultado da última tentativa ─────────────────────────────


def write_result(payload: dict) -> Path:
    """Grava o resultado final da atualização (lido na próxima abertura)."""
    return _write_json(_path(_RESULT_NAME), payload)


def read_result() -> dict | None:
    return _read_json(_path(_RESULT_NAME))


def consume_result() -> dict | None:
    """Lê e apaga o resultado, para a mensagem aparecer uma única vez."""
    result = read_result()
    if result is not None:
        _remove(_path(_RESULT_NAME))
    return result


# ── Supressão de versão que falhou ────────────────────────────


def record_failed_version(version: str, detail: dict | None = None) -> None:
    """Marca uma versão como falha recente (evita loop de prompt)."""
    _write_json(
        _path(_FAILED_NAME),
        {
            'version': str(version),
            'failed_at': time.time(),
            'detail': detail or {},
        },
    )


def clear_failed_version() -> None:
    _remove(_path(_FAILED_NAME))


def is_version_suppressed(version: str, hours: float = SUPPRESSION_HOURS) -> bool:
    """``True`` se ``version`` falhou nas últimas ``hours`` horas."""
    data = _read_json(_path(_FAILED_NAME))
    if not data:
        return False
    if str(data.get('version') or '') != str(version):
        return False
    try:
        failed_at = float(data.get('failed_at') or 0)
    except (TypeError, ValueError):
        return False
    age = time.time() - failed_at
    return 0 <= age < hours * 3600
