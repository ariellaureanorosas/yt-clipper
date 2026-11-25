"""
Atualização automática do YouTube Clipper a partir das Releases do GitHub.

O aplicativo consulta a última release, baixa o instalador
(``YouTubeClipper-Setup-<versão>.exe``) e valida tamanho, cabeçalho ``MZ`` e
SHA-256. A aplicação é entregue a um supervisor externo
(``YouTubeClipperUpdater.exe``) que espera o app encerrar de verdade, faz backup
por renomeação, executa o Setup com ``/DIR`` explícito, confere a versão
instalada, restaura o backup em caso de falha e reabre o aplicativo. Assim não
é mais necessário o script PowerShell que trocava o ``.exe`` em uso.

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
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from core import __version__, update_state
from core.config import get_config
from core.logging_config import get_logger
from core.resources import executable_dir, is_frozen

logger = get_logger(__name__)

REPOSITORY = 'ariellaureanorosas/yt-clipper'
_API_LATEST_RELEASE = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
_INSTALLER_PREFIX = 'YouTubeClipper-Setup-'
_CHUNK_SIZE = 256 * 1024
_USER_AGENT = f'YouTubeClipper-Updater/{__version__}'
_VERSION_RE = re.compile(r'^[vV]?(\d+(?:\.\d+)*)(?:[-+].*)?$')
_UNINSTALLER_NAME = 'unins000.exe'
_HELPER_NAME = 'YouTubeClipperUpdater.exe'
_HANDSHAKE_TIMEOUT = 15.0


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


def get_install_dir() -> Path:
    """Pasta onde o aplicativo está instalado (ou o projeto, em modo dev)."""
    return executable_dir()


def is_installed() -> bool:
    """``True`` quando o aplicativo foi instalado pelo Setup (Inno Setup)."""
    return is_frozen() and (get_install_dir() / _UNINSTALLER_NAME).is_file()


def _updates_dir() -> Path:
    base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
    return Path(base) / 'YouTubeClipper' / 'updates'


def updates_dir() -> Path:
    """Pasta pública dos downloads de atualização (para mensagens de erro)."""
    return _updates_dir()


def helper_path() -> Path:
    """Caminho do supervisor instalado fora da pasta do aplicativo.

    Fica em ``%LOCALAPPDATA%\\YouTubeClipper\\updater`` para não ser
    sobrescrito/apagado enquanto está em execução durante a instalação.
    """
    base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
    return Path(base) / 'YouTubeClipper' / 'updater' / _HELPER_NAME


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


def _find_installer_asset(assets: list[dict], version: str) -> dict | None:
    """Localiza o ``YouTubeClipper-Setup-<versão>.exe`` da release.

    Só aceita nome diferente do padrão quando a versão embutida no nome é
    exatamente a versão da release. Isso evita baixar o asset errado (o bug da
    v1.2.1 escolhia qualquer ``YouTubeClipper-*.exe``, inclusive o Setup).
    """
    expected = f'{_INSTALLER_PREFIX}{version}.exe'
    for asset in assets:
        if asset.get('name') == expected:
            return asset

    wanted = parse_version(version)
    for asset in assets:
        name = str(asset.get('name', ''))
        if not (name.startswith(_INSTALLER_PREFIX) and name.endswith('.exe')):
            continue
        embedded = name[len(_INSTALLER_PREFIX) : -len('.exe')]
        if wanted and parse_version(embedded) == wanted:
            return asset
    return None


def _find_checksum_asset(assets: list[dict], installer_name: str) -> dict | None:
    expected = f'{installer_name}.sha256'
    for asset in assets:
        if asset.get('name') == expected:
            return asset
    return None


# ── Verificação ───────────────────────────────────────────────


def check_for_update(
    current_version: str | None = None,
    timeout: float | None = None,
    ignore_suppressed: bool = False,
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
    if not ignore_suppressed and update_state.is_version_suppressed(version):
        logger.info(
            'A versão %s falhou na última tentativa; não será oferecida '
            'automaticamente por enquanto (verificação manual continua).',
            version,
        )
        return None
    assets = release.get('assets') or []
    installer_asset = _find_installer_asset(assets, version)
    if not installer_asset:
        logger.warning(
            'Release %s não possui instalador (%s<versão>.exe) anexado.',
            tag,
            _INSTALLER_PREFIX,
        )
        return None

    installer_name = str(installer_asset.get('name'))
    checksum_asset = _find_checksum_asset(assets, installer_name)
    return UpdateInfo(
        version=version,
        tag=tag,
        notes=str(release.get('body') or ''),
        download_url=str(installer_asset.get('browser_download_url') or ''),
        checksum_url=(
            str(checksum_asset.get('browser_download_url') or '')
            if checksum_asset
            else None
        ),
        size=int(installer_asset.get('size') or 0),
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
    """Baixa e valida o instalador da atualização, retornando o caminho."""
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

        downloaded = part_path.stat().st_size
        if downloaded <= 0:
            raise UpdateError('O download da atualização ficou vazio.')
        if info.size and downloaded != info.size:
            raise UpdateError(
                f'Download incompleto: {downloaded} de {info.size} bytes.'
            )
        with open(part_path, 'rb') as handle:
            if handle.read(2) != b'MZ':
                raise UpdateError('O arquivo baixado não é um executável do Windows.')

        os.replace(part_path, final_path)
    except (UpdateCancelled, UpdateError):
        _safe_remove(part_path)
        raise
    except Exception as exc:
        _safe_remove(part_path)
        raise UpdateError(f'Falha ao baixar a atualização: {exc}') from exc

    return final_path


# ── Aplicação da atualização ──────────────────────────────────


def build_installer_command(
    installer: Path, log_path: Path, install_dir: Path | None = None
) -> list[str]:
    """Monta o comando do instalador para atualização silenciosa.

    ``/DIR`` fixa o destino na pasta onde o aplicativo está rodando; sem isso o
    Inno depende do registro/``UsePreviousAppDir`` e pode instalar uma segunda
    cópia em outro lugar.
    """
    command = [
        str(installer),
        '/SILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        '/CLOSEAPPLICATIONS',
        f'/LOG={log_path}',
    ]
    if install_dir is not None:
        command.append(f'/DIR={install_dir}')
    return command


def apply_update_and_restart(installer: Path, target_version: str) -> None:
    """Entrega a atualização ao supervisor externo e espera o handshake.

    O supervisor é quem espera o app encerrar, faz o backup, executa o Setup,
    valida o resultado, restaura em caso de falha e reabre o aplicativo. Aqui
    só gravamos o pedido e confirmamos que o supervisor realmente iniciou antes
    de o chamador fechar a janela.
    """
    if not is_frozen():
        raise UpdateError(
            'A atualização automática só está disponível no aplicativo '
            'instalado (.exe).'
        )
    if sys.platform != 'win32':
        raise UpdateError('A atualização automática está disponível só no Windows.')
    if not is_installed():
        raise UpdateError(
            'Esta cópia não foi instalada pelo Setup; baixe o instalador '
            'mais recente para atualizar.'
        )
    if not target_version:
        raise UpdateError('Versão de destino da atualização não informada.')

    installer_path = Path(installer).resolve()
    if not installer_path.is_file():
        raise UpdateError('Instalador da atualização não encontrado.')

    helper = helper_path()
    if not helper.is_file():
        raise UpdateError(
            f'O supervisor de atualização não foi encontrado em {helper}. '
            'Reinstale o aplicativo com o Setup mais recente.'
        )

    install_dir = get_install_dir()
    inno_log = _updates_dir() / f'install-{int(time.time())}.log'
    token = uuid.uuid4().hex
    pending = update_state.write_pending(
        {
            'token': token,
            'installer': str(installer_path),
            'install_dir': str(install_dir),
            'target_version': str(target_version),
            'current_version': __version__,
            'parent_pid': os.getpid(),
            'inno_log': str(inno_log),
            'created_at': time.time(),
        }
    )
    update_state.clear_started()

    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(
        subprocess, 'DETACHED_PROCESS', 0
    )
    try:
        process = subprocess.Popen(
            [str(helper), '--pending', str(pending)],
            close_fds=True,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        update_state.clear_pending()
        raise UpdateError(f'Não foi possível executar o supervisor: {exc}') from exc

    logger.info(
        'Supervisor %s iniciado (PID %s); aguardando confirmação.',
        helper.name,
        process.pid,
    )

    deadline = time.monotonic() + _HANDSHAKE_TIMEOUT
    while time.monotonic() < deadline:
        started = update_state.read_started()
        if started and started.get('token') == token:
            logger.info(
                'Supervisor confirmou o início; o aplicativo pode fechar. ' 'Log: %s',
                _updates_dir().parent / 'logs',
            )
            return
        if process.poll() is not None:
            break
        time.sleep(0.2)

    try:
        process.terminate()
    except OSError:
        pass
    update_state.clear_pending()
    raise UpdateError(
        'O supervisor de atualização não confirmou o início; a instalação '
        'NÃO foi aplicada. Consulte os logs em '
        f'{_updates_dir().parent / "logs"} e tente novamente.'
    )


def cleanup_update_cache(max_age_days: int = 7) -> None:
    """Remove downloads antigos/parciais e logs de instalação antigos.

    Arquivos ``.part``/``.tmp`` (download interrompido) são sempre removidos,
    independentemente da idade.
    """
    directory = _updates_dir()
    if not directory.is_dir():
        return

    cutoff = time.time() - max_age_days * 24 * 3600
    for entry in directory.iterdir():
        try:
            if entry.is_file():
                stale_partial = entry.suffix in ('.part', '.tmp')
                if stale_partial or entry.stat().st_mtime < cutoff:
                    entry.unlink()
        except OSError:
            pass
