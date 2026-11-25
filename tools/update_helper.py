#!/usr/bin/env python3
"""
Supervisor da atualização do YouTube Clipper.

Este executável é iniciado pelo aplicativo **antes** de ele fechar e é
responsável por todo o processo de troca:

1. grava um handshake (``started.json``) para o app saber que pode fechar;
2. espera o processo principal terminar de verdade (por PID);
3. renomeia a instalação atual para ``.bak`` (backup barato, sem copiar 260 MB);
4. executa o Setup do Inno em modo silencioso, com ``/DIR`` explícito;
5. valida o resultado (código de saída, exe presente, versão instalada);
6. em caso de sucesso: apaga o backup e o instalador baixado e reabre o app;
7. em caso de falha: restaura o backup, grava o motivo e reabre a versão antiga.

Todo o processo é registrado em ``%LOCALAPPDATA%\\YouTubeClipper\\logs`` e o
resultado fica em ``...\\state\\last-result.json`` para o app mostrar ao usuário
na próxima abertura.

Roda como executável próprio (``YouTubeClipperUpdater.exe``), sem console, para
não depender de política de execução do PowerShell.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP_EXE = 'YouTubeClipper.exe'
UNINSTALLER = 'unins000.exe'
UNINSTALLER_DATA = 'unins000.dat'
INTERNAL_DIR = '_internal'
BACKUP_SUFFIX = '.bak'
SKIP_RELAUNCH_ENV = 'YTCLIPPER_SKIP_RELAUNCH'

WAIT_APP_EXIT_SECONDS = 60.0
INSTALL_TIMEOUT_SECONDS = 900.0
VERSION_TIMEOUT_SECONDS = 60.0

_LOG = logging.getLogger('ytclipper.updater_helper')


class UpdateFailure(RuntimeError):
    """Falha em um passo específico da atualização."""

    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step


# ── Caminhos ──────────────────────────────────────────────────


def local_app_data() -> Path:
    base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
    return Path(base) / 'YouTubeClipper'


def state_dir() -> Path:
    return local_app_data() / 'state'


def log_dir() -> Path:
    return local_app_data() / 'logs'


def default_pending_path() -> Path:
    return state_dir() / 'pending.json'


def setup_logging(now: float | None = None) -> Path:
    """Configura o log do helper e devolve o caminho do arquivo."""
    existing = getattr(_LOG, '_ytclipper_log_path', None)
    if existing and _LOG.handlers:
        return Path(existing)
    log_dir().mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S', time.localtime(now))
    path = log_dir() / f'update-{stamp}.log'
    handler = logging.FileHandler(path, encoding='utf-8')
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
    )
    _LOG.setLevel(logging.INFO)
    _LOG.propagate = False
    _LOG.addHandler(handler)
    _LOG._ytclipper_log_path = str(path)  # type: ignore[attr-defined]
    _LOG.info('Helper de atualização iniciado (PID %s).', os.getpid())
    return path


# ── Estado ────────────────────────────────────────────────────


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with open(temporary, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def _read_json(path: Path) -> dict:
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError('JSON inválido')
    return data


def read_pending(path: Path) -> dict:
    pending = _read_json(path)
    for key in ('installer', 'install_dir', 'target_version'):
        if not pending.get(key):
            raise ValueError(f'Campo obrigatório ausente: {key}')
    return pending


def write_started(pending: dict) -> None:
    _write_json(
        state_dir() / 'started.json',
        {
            'token': pending.get('token'),
            'pid': os.getpid(),
            'started_at': time.time(),
        },
    )


def _record_failed_version(version: str, detail: dict) -> None:
    try:
        _write_json(
            state_dir() / 'failed-version.json',
            {'version': version, 'failed_at': time.time(), 'detail': detail},
        )
    except OSError:
        _LOG.exception('Não foi possível registrar a versão que falhou.')


# ── Espera e troca de arquivos ────────────────────────────────


def wait_for_process_exit(pid: int, timeout: float = WAIT_APP_EXIT_SECONDS) -> bool:
    """Espera o PID terminar. Retorna ``True`` se ele não existe mais."""
    if pid <= 0:
        return True
    if sys.platform != 'win32':
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return True
            time.sleep(0.2)
        return False

    import ctypes

    kernel32 = ctypes.windll.kernel32
    synchronize = 0x00100000
    handle = kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return True  # processo já não existe
    try:
        remaining = int(max(timeout, 0) * 1000)
        return kernel32.WaitForSingleObject(handle, remaining) == 0
    finally:
        kernel32.CloseHandle(handle)


def _rename_with_retry(source: Path, target: Path, timeout: float = 60.0) -> None:
    """Renomeia com novas tentativas (antivírus/indexador podem segurar o arquivo)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise UpdateFailure(
                    'backup',
                    f'Não foi possível mover {source.name}: {exc}',
                ) from exc
            _LOG.warning('Tentando novamente mover %s: %s', source.name, exc)
            time.sleep(0.5)


def _remove_with_retry(path: Path, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while path.exists():
        try:
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
            else:
                path.unlink()
            return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise UpdateFailure(
                    'cleanup',
                    f'Não foi possível remover {path.name}: {exc}',
                ) from exc
            time.sleep(0.5)


def recover_leftovers(install_dir: Path) -> None:
    """Recupera uma troca interrompida no meio (backup presente, original ausente)."""
    for name in (INTERNAL_DIR, APP_EXE, UNINSTALLER, UNINSTALLER_DATA):
        original = install_dir / name
        backup = install_dir / f'{name}{BACKUP_SUFFIX}'
        if backup.exists() and not original.exists():
            _LOG.warning('Recuperando %s da tentativa anterior.', name)
            os.replace(backup, original)


def backup_installation(install_dir: Path) -> list[tuple[Path, Path]]:
    """Renomeia a instalação atual para ``.bak`` (backup sem copiar dados)."""
    pairs: list[tuple[Path, Path]] = []
    try:
        for name in (INTERNAL_DIR, APP_EXE, UNINSTALLER, UNINSTALLER_DATA):
            original = install_dir / name
            if not original.exists():
                continue
            backup = install_dir / f'{name}{BACKUP_SUFFIX}'
            if backup.exists():
                _remove_with_retry(backup)
            _rename_with_retry(original, backup)
            pairs.append((original, backup))
            _LOG.info('Backup: %s -> %s', original.name, backup.name)
    except Exception:
        restore_installation(pairs)
        raise
    return pairs


def restore_installation(pairs: list[tuple[Path, Path]]) -> None:
    """Restaura o backup, apagando o que a instalação nova deixou."""
    for original, _ in pairs:
        if original.exists():
            _remove_with_retry(original)
    for original, backup in pairs:
        if backup.exists():
            _rename_with_retry(backup, original)
            _LOG.info('Restaurado: %s', original.name)


def discard_backups(pairs: list[tuple[Path, Path]]) -> None:
    for _, backup in pairs:
        if backup.exists():
            _remove_with_retry(backup)
    _LOG.info('Backup removido após sucesso.')


# ── Instalação ────────────────────────────────────────────────


def build_install_command(
    installer: Path, install_dir: Path, log_file: Path
) -> list[str]:
    """Comando do Inno Setup com destino explícito (não depende do registro)."""
    return [
        str(installer),
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        '/CLOSEAPPLICATIONS',
        f'/DIR={install_dir}',
        f'/LOG={log_file}',
    ]


def run_installer(
    installer: Path,
    install_dir: Path,
    log_file: Path,
    timeout: float = INSTALL_TIMEOUT_SECONDS,
) -> int:
    """Executa o Setup e devolve o código de saída (sem disparar e esquecer)."""
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    environment = os.environ.copy()
    # O helper relança o app; evita que o Inno abra uma segunda instância.
    environment[SKIP_RELAUNCH_ENV] = '1'
    command = build_install_command(installer, install_dir, log_file)
    _LOG.info('Executando instalador: %s', ' '.join(command))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
            env=environment,
            cwd=str(install_dir),
        )
    except subprocess.TimeoutExpired as exc:
        raise UpdateFailure(
            'install', f'Instalador excedeu {timeout:.0f}s e foi abandonado.'
        ) from exc
    except OSError as exc:
        raise UpdateFailure(
            'install', f'Não foi possível executar o Setup: {exc}'
        ) from exc
    if completed.stdout:
        _LOG.info('Setup stdout: %s', completed.stdout.strip()[:2000])
    if completed.stderr:
        _LOG.warning('Setup stderr: %s', completed.stderr.strip()[:2000])
    _LOG.info('Instalador terminou com código %s.', completed.returncode)
    return completed.returncode


def read_app_version(exe: Path, timeout: float = VERSION_TIMEOUT_SECONDS) -> str:
    """Pergunta a versão ao próprio executável novo (``--version-file``)."""
    handle, temp_name = tempfile.mkstemp(prefix='ytclipper-version-', suffix='.txt')
    os.close(handle)
    target = Path(temp_name)
    try:
        completed = subprocess.run(
            [str(exe), '--version-file', str(target)],
            timeout=timeout,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            cwd=str(exe.parent),
            capture_output=True,
        )
        if completed.returncode != 0:
            raise UpdateFailure(
                'verify',
                f'O executável novo não iniciou (código {completed.returncode}).',
            )
        try:
            version = target.read_text(encoding='utf-8').strip()
        except OSError as exc:
            raise UpdateFailure('verify', f'O executável não informou a versão: {exc}')
        if not version:
            raise UpdateFailure('verify', 'O executável novo informou versão vazia.')
        return version
    except subprocess.TimeoutExpired as exc:
        raise UpdateFailure(
            'verify', 'O executável novo não respondeu a tempo.'
        ) from exc
    finally:
        try:
            target.unlink()
        except OSError:
            pass


def verify_installation(install_dir: Path, target_version: str) -> None:
    """Confere se a instalação nova está realmente no lugar e funciona."""
    exe = install_dir / APP_EXE
    if not exe.is_file():
        raise UpdateFailure('verify', f'{APP_EXE} não existe após a instalação.')
    if not (install_dir / INTERNAL_DIR).is_dir():
        raise UpdateFailure('verify', 'A pasta _internal não foi instalada.')
    installed = read_app_version(exe)
    if installed != str(target_version):
        raise UpdateFailure(
            'verify',
            f'Versão instalada ({installed}) diferente da esperada ({target_version}).',
        )
    _LOG.info('Instalação validada: versão %s.', installed)


def launch_app(install_dir: Path) -> subprocess.Popen | None:
    """Reabre o aplicativo com o diretório de trabalho correto."""
    exe = install_dir / APP_EXE
    if not exe.is_file():
        _LOG.error('Não foi possível reabrir: %s não existe.', exe)
        return None
    creationflags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(
        subprocess, 'CREATE_NEW_PROCESS_GROUP', 0
    )
    try:
        process = subprocess.Popen(
            [str(exe)],
            cwd=str(install_dir),
            close_fds=True,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        _LOG.exception('Falha ao reabrir o aplicativo.')
        return None
    _LOG.info('Aplicativo reaberto (PID %s) em %s.', process.pid, install_dir)
    return process


# ── Fluxo completo ────────────────────────────────────────────


def _result_payload(
    pending: dict,
    status: str,
    *,
    step: str = '',
    message: str = '',
    exit_code: int | None = None,
    log_file: Path | None = None,
    inno_log: Path | None = None,
    rolled_back: bool = False,
    relaunched: bool = False,
    started_at: float,
) -> dict:
    return {
        'status': status,
        'target_version': str(pending.get('target_version') or ''),
        'from_version': str(pending.get('current_version') or ''),
        'installer_exit_code': exit_code,
        'step': step,
        'message': message,
        'install_dir': str(pending.get('install_dir') or ''),
        'log_file': str(log_file) if log_file else '',
        'inno_log': str(inno_log) if inno_log else '',
        'rolled_back': rolled_back,
        'relaunched': relaunched,
        'started_at': started_at,
        'finished_at': time.time(),
    }


def run_update(
    pending_path: Path,
    *,
    log_file: Path | None = None,
    wait_exit: bool = True,
) -> dict:
    """Executa a atualização supervisionada e devolve o resultado."""
    started_at = time.time()
    pending = read_pending(pending_path)
    write_started(pending)

    if log_file is None:
        log_file = setup_logging()
    _LOG.info(
        'Atualização %s -> %s',
        pending.get('current_version'),
        pending.get('target_version'),
    )

    install_dir = Path(str(pending['install_dir']))
    installer = Path(str(pending['installer']))
    target_version = str(pending['target_version'])
    inno_log = Path(
        str(pending.get('inno_log') or log_file.with_name(log_file.stem + '-inno.log'))
    )
    parent_pid = int(pending.get('parent_pid') or 0)

    backups: list[tuple[Path, Path]] = []
    exit_code: int | None = None
    app_exited = not wait_exit

    try:
        if wait_exit:
            app_exited = wait_for_process_exit(parent_pid)
            if not app_exited:
                raise UpdateFailure(
                    'wait',
                    'O aplicativo não encerrou a tempo; a atualização foi cancelada.',
                )

        _LOG.info('Aplicativo encerrado; iniciando troca de arquivos.')
        if not installer.is_file():
            raise UpdateFailure('prepare', 'O instalador baixado não existe mais.')
        if not install_dir.is_dir():
            raise UpdateFailure('prepare', 'A pasta de instalação não existe.')

        recover_leftovers(install_dir)
        backups = backup_installation(install_dir)

        exit_code = run_installer(installer, install_dir, inno_log)
        if exit_code != 0:
            raise UpdateFailure(
                'install', f'O instalador terminou com código {exit_code}.'
            )

        verify_installation(install_dir, target_version)

        discard_backups(backups)
        backups = []
        try:
            installer.unlink()
            _LOG.info('Instalador baixado removido.')
        except OSError as exc:
            _LOG.warning('Não foi possível apagar o instalador: %s', exc)

        relaunched = launch_app(install_dir) is not None
        result = _result_payload(
            pending,
            'success',
            message=f'Atualização para {target_version} concluída.',
            exit_code=exit_code,
            log_file=log_file,
            inno_log=inno_log,
            relaunched=relaunched,
            started_at=started_at,
        )
    except UpdateFailure as exc:
        _LOG.error('Falha no passo %s: %s', exc.step, exc)
        rolled_back = False
        if backups:
            try:
                restore_installation(backups)
                rolled_back = True
            except UpdateFailure:
                _LOG.exception('Falha ao restaurar o backup!')
        # Só relança se o app realmente fechou; senão abriria uma segunda cópia.
        recovered = app_exited and launch_app(install_dir) is not None
        result = _result_payload(
            pending,
            'failed',
            step=exc.step,
            message=str(exc),
            exit_code=exit_code,
            log_file=log_file,
            inno_log=inno_log,
            rolled_back=rolled_back,
            relaunched=recovered,
            started_at=started_at,
        )
        # Falha de espera não é problema da versão: não suprime o update.
        if target_version and exc.step != 'wait':
            _record_failed_version(target_version, result)
    except Exception as exc:  # nunca deixar o usuário sem resultado
        _LOG.exception('Erro inesperado no atualizador.')
        result = _result_payload(
            pending,
            'failed',
            step='unexpected',
            message=f'Erro inesperado: {exc}',
            exit_code=exit_code,
            log_file=log_file,
            inno_log=inno_log,
            started_at=started_at,
        )
        if backups:
            try:
                restore_installation(backups)
                result['rolled_back'] = True
            except Exception:
                _LOG.exception('Falha ao restaurar o backup!')
        result['relaunched'] = app_exited and launch_app(install_dir) is not None
        if target_version:
            _record_failed_version(target_version, result)

    _write_json(state_dir() / 'last-result.json', result)
    try:
        pending_path.unlink()
    except OSError:
        pass
    _LOG.info('Resultado da atualização: %s', result['status'])
    if _LOG.handlers:
        for handler in list(_LOG.handlers):
            handler.flush()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Supervisor de atualização.')
    parser.add_argument('--pending', default=str(default_pending_path()))
    parser.add_argument('--no-wait', action='store_true', help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)

    try:
        result = run_update(Path(arguments.pending), wait_exit=not arguments.no_wait)
    except Exception as exc:
        logging.basicConfig(level=logging.INFO)
        _LOG.exception('Falha ao processar a atualização: %s', exc)
        return 1
    return 0 if result.get('status') == 'success' else 1


if __name__ == '__main__':
    sys.exit(main())
