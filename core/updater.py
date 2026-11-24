"""
Atualização automática do YouTube Clipper a partir das Releases do GitHub.

O executável consulta a última release, baixa o novo ``.exe``, confere o
SHA-256 e agenda a troca do arquivo em execução por um script auxiliar do
PowerShell — o Windows não permite sobrescrever um ``.exe`` aberto.

Ao rodar direto do código (``python main.py``) nada é aplicado: o módulo
apenas expõe as funções usadas pela interface.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from core import __version__
from core.config import get_config
from core.logging_config import get_logger

logger = get_logger(__name__)

REPOSITORY = 'ariellaureanorosas/yt-clipper'
_API_LATEST_RELEASE = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
_ASSET_PREFIX = 'YouTubeClipper-'
_CHUNK_SIZE = 256 * 1024
_USER_AGENT = f'YouTubeClipper-Updater/{__version__}'
_VERSION_RE = re.compile(r'^[vV]?(\d+(?:\.\d+)*)(?:[-+].*)?$')


class UpdateError(RuntimeError):
    """Falha ao verificar, baixar ou aplicar uma atualização."""


class UpdateCancelled(Exception):
    """Atualização cancelada pelo usuário."""


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """Dados da release mais recente disponível."""

    version: str
    tag: str
    notes: str
    download_url: str
    checksum_url: str | None
    size: int = 0

    @property
    def asset_name(self) -> str:
        return Path(self.download_url).name


# ── Versões ───────────────────────────────────────────────────


def parse_version(value: str) -> tuple[int, ...]:
    """Converte ``v1.2.3``/``1.2`` em uma tupla comparável de inteiros."""
    match = _VERSION_RE.match(str(value).strip())
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split('.'))


def is_newer(candidate: str, current: str) -> bool:
    """Indica se ``candidate`` é uma versão mais nova que ``current``."""
    candidate_parts = parse_version(candidate)
    current_parts = parse_version(current)
    if not candidate_parts or not current_parts:
        return False

    length = max(len(candidate_parts), len(current_parts))
    candidate_parts += (0,) * (length - len(candidate_parts))
    current_parts += (0,) * (length - len(current_parts))
    return candidate_parts > current_parts


# ── Ambiente ──────────────────────────────────────────────────


def is_frozen() -> bool:
    """``True`` quando rodando como executável empacotado pelo PyInstaller."""
    return bool(getattr(sys, 'frozen', False))


def _updates_dir() -> Path:
    base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
    return Path(base) / 'YouTubeClipper' / 'updates'


def _request_timeout(download: bool = False) -> float:
    timeout = get_config().update.timeout
    return max(timeout, 30) if download else timeout


# ── HTTP ──────────────────────────────────────────────────────


def _http_open(url: str, timeout: float):
    request = Request(
        url,
        headers={
            'User-Agent': _USER_AGENT,
            'Accept': 'application/vnd.github+json',
        },
    )
    return urlopen(request, timeout=timeout)


def _fetch_json(url: str, timeout: float) -> dict:
    with _http_open(url, timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _fetch_text(url: str, timeout: float) -> str:
    with _http_open(url, timeout) as response:
        return response.read().decode('utf-8', errors='replace')


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_remove(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


# ── Seleção de assets ─────────────────────────────────────────


def _find_exe_asset(assets: list[dict], version: str) -> dict | None:
    expected = f'{_ASSET_PREFIX}{version}.exe'
    for asset in assets:
        if asset.get('name') == expected:
            return asset
    for asset in assets:
        name = str(asset.get('name', ''))
        if name.startswith(_ASSET_PREFIX) and name.endswith('.exe'):
            return asset
    return None


def _find_checksum_asset(assets: list[dict], exe_name: str) -> dict | None:
    expected = f'{exe_name}.sha256'
    for asset in assets:
        if asset.get('name') == expected:
            return asset
    return None


# ── Verificação ───────────────────────────────────────────────


def check_for_update(
    current_version: str | None = None,
    timeout: float | None = None,
) -> UpdateInfo | None:
    """Retorna a release mais nova ou ``None`` se não houver atualização.

    Falhas de rede são registradas no log e tratadas como "sem atualização",
    para nunca impedir o uso normal do aplicativo.
    """
    if not get_config().update.enabled:
        logger.debug('Verificação de atualizações desativada por configuração.')
        return None

    current = current_version or __version__
    request_timeout = timeout or get_config().update.timeout

    try:
        release = _fetch_json(_API_LATEST_RELEASE, request_timeout)
    except Exception as exc:  # rede, timeout, JSON inválido
        logger.info('Não foi possível verificar atualizações: %s', exc)
        return None

    if release.get('draft') or release.get('prerelease'):
        logger.debug('Última release é rascunho/pré-release; ignorando.')
        return None

    tag = str(release.get('tag_name') or '')
    if not is_newer(tag, current):
        logger.debug('Aplicativo já está atualizado (v%s).', current)
        return None

    version = tag.lstrip('vV').strip()
    assets = release.get('assets') or []
    exe_asset = _find_exe_asset(assets, version)
    if not exe_asset:
        logger.warning('Release %s não possui executável anexado.', tag)
        return None

    checksum_asset = _find_checksum_asset(assets, str(exe_asset.get('name')))
    return UpdateInfo(
        version=version,
        tag=tag,
        notes=str(release.get('body') or ''),
        download_url=str(exe_asset.get('browser_download_url') or ''),
        checksum_url=(
            str(checksum_asset.get('browser_download_url') or '')
            if checksum_asset
            else None
        ),
        size=int(exe_asset.get('size') or 0),
    )


# ── Download ──────────────────────────────────────────────────


def _download_file(
    url: str,
    destination: Path,
    total_size: int,
    progress_callback=None,
    cancel_event=None,
    version: str = '',
) -> None:
    timeout = _request_timeout(download=True)
    with _http_open(url, timeout) as response:
        total = int(response.headers.get('Content-Length') or total_size or 0)
        downloaded = 0
        with open(destination, 'wb') as handle:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise UpdateCancelled('Atualização cancelada')
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    mb = downloaded / 1_000_000
                    total_mb = total / 1_000_000
                    pct = min(downloaded * 100 / total, 99)
                    progress_callback(
                        pct,
                        f'Baixando atualização {version}... {mb:.1f}/{total_mb:.1f} MB',
                    )
    if progress_callback:
        progress_callback(100, 'Download da atualização concluído.')


def _expected_sha256(url: str, timeout: float) -> str:
    try:
        text = _fetch_text(url, timeout)
    except Exception as exc:
        raise UpdateError(f'Não foi possível ler o checksum: {exc}') from exc

    first = text.strip().split()[0] if text.strip() else ''
    if not re.fullmatch(r'[0-9a-fA-F]{64}', first):
        raise UpdateError('Arquivo de checksum inválido.')
    return first.lower()


def download_update(
    info: UpdateInfo,
    progress_callback=None,
    cancel_event=None,
) -> Path:
    """Baixa e valida o executável da atualização, retornando o caminho."""
    target_dir = _updates_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    final_path = target_dir / info.asset_name
    part_path = final_path.with_suffix(final_path.suffix + '.part')
    _safe_remove(part_path)

    try:
        _download_file(
            info.download_url,
            part_path,
            info.size,
            progress_callback,
            cancel_event,
            info.version,
        )

        if info.checksum_url:
            expected = _expected_sha256(info.checksum_url, _request_timeout())
            actual = _sha256(part_path)
            if actual != expected:
                raise UpdateError('Checksum SHA-256 não confere; download corrompido.')
        else:
            logger.warning(
                'Release %s sem checksum; seguindo sem verificação.',
                info.version,
            )

        os.replace(part_path, final_path)
    except (UpdateCancelled, UpdateError):
        _safe_remove(part_path)
        raise
    except Exception as exc:
        _safe_remove(part_path)
        raise UpdateError(f'Falha ao baixar a atualização: {exc}') from exc

    return final_path


# ── Aplicação da atualização ──────────────────────────────────

_UPDATE_SCRIPT = """param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$CurrentExe,
    [Parameter(Mandatory = $true)][string]$NewExe
)

while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 1
}

$staged = "$CurrentExe.new"
$deadline = (Get-Date).AddSeconds(60)
$installed = $false

while ((Get-Date) -lt $deadline) {
    try {
        Copy-Item -LiteralPath $NewExe -Destination $staged -Force
        if ((Get-Item -LiteralPath $staged).Length -eq (Get-Item -LiteralPath $NewExe).Length) {
            Move-Item -LiteralPath $staged -Destination $CurrentExe -Force
            $installed = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($installed) {
    Start-Process -FilePath $CurrentExe
    Start-Sleep -Seconds 2
}

Remove-Item -LiteralPath $NewExe -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $staged -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
"""


def build_update_script() -> str:
    """Retorna o script PowerShell que troca o executável em uso."""
    return _UPDATE_SCRIPT


def apply_update_and_restart(new_exe: Path) -> None:
    """Agenda a troca do executável e encerra para o script assumir.

    O chamador deve fechar a janela logo depois (o script espera o processo
    atual terminar antes de substituir o arquivo).
    """
    if not is_frozen():
        raise UpdateError(
            'A atualização automática só está disponível no executável (.exe).'
        )
    if sys.platform != 'win32':
        raise UpdateError('A atualização automática está disponível só no Windows.')

    current_exe = Path(sys.executable).resolve()
    new_exe = Path(new_exe).resolve()
    if not new_exe.is_file():
        raise UpdateError('Arquivo de atualização não encontrado.')

    script_dir = _updates_dir()
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / f'update-{os.getpid()}.ps1'
    script_path.write_text(build_update_script(), encoding='utf-8')

    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(
        subprocess, 'DETACHED_PROCESS', 0
    )
    subprocess.Popen(
        [
            'powershell.exe',
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-WindowStyle',
            'Hidden',
            '-File',
            str(script_path),
            '-ProcessId',
            str(os.getpid()),
            '-CurrentExe',
            str(current_exe),
            '-NewExe',
            str(new_exe),
        ],
        close_fds=True,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info('Atualização agendada; o aplicativo será reiniciado.')


def cleanup_update_cache(max_age_days: int = 7) -> None:
    """Remove downloads antigos/parciais da pasta de atualizações."""
    directory = _updates_dir()
    if not directory.is_dir():
        return

    cutoff = time.time() - max_age_days * 24 * 3600
    for entry in directory.iterdir():
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink()
        except OSError:
            pass
