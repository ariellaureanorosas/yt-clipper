"""Testes do supervisor de atualização (backup, troca, rollback e relançamento)."""

import json
from pathlib import Path

import pytest

from tools import update_helper as helper


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setattr(helper, 'state_dir', lambda: tmp_path / 'state')
    (tmp_path / 'state').mkdir()


def _make_installation(tmp_path) -> Path:
    install = tmp_path / 'app'
    install.mkdir()
    (install / 'YouTubeClipper.exe').write_bytes(b'MZ OLD')
    (install / 'unins000.exe').write_bytes(b'MZ UNINST')
    (install / 'unins000.dat').write_bytes(b'OLD DAT')
    internal = install / '_internal'
    internal.mkdir()
    (internal / 'old.dll').write_bytes(b'OLD DLL')
    return install


def _make_pending(tmp_path, install_dir: Path, **overrides) -> tuple[Path, Path]:
    installer = tmp_path / 'YouTubeClipper-Setup-1.2.0.exe'
    installer.write_bytes(b'MZ SETUP')
    pending = {
        'token': 'tok',
        'installer': str(installer),
        'install_dir': str(install_dir),
        'target_version': '1.2.0',
        'current_version': '1.1.0',
        'parent_pid': 0,
        'inno_log': str(tmp_path / 'inno.log'),
        'created_at': 0,
    }
    pending.update(overrides)
    path = tmp_path / 'pending.json'
    path.write_text(json.dumps(pending), encoding='utf-8')
    return path, installer


def _fake_install(install_dir: Path, exit_code=0):
    def _run(installer, target_dir, log_file, timeout=0):
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / 'YouTubeClipper.exe').write_bytes(b'MZ NEW')
        internal = target_dir / '_internal'
        internal.mkdir(exist_ok=True)
        (internal / 'new.dll').write_bytes(b'NEW DLL')
        return exit_code

    return _run


def test_comando_do_instalador_inclui_dir(tmp_path):
    command = helper.build_install_command(
        tmp_path / 'setup.exe', tmp_path / 'app', tmp_path / 'log.txt'
    )

    assert f'/DIR={tmp_path / "app"}' in command
    assert f'/LOG={tmp_path / "log.txt"}' in command
    assert '/VERYSILENT' in command
    assert '/NORESTART' in command


def test_atualizacao_bem_sucedida(monkeypatch, tmp_path):
    install = _make_installation(tmp_path)
    pending, installer = _make_pending(tmp_path, install)
    launched = {}

    monkeypatch.setattr(helper, 'wait_for_process_exit', lambda pid, timeout=60: True)
    monkeypatch.setattr(helper, 'run_installer', _fake_install(install))
    monkeypatch.setattr(helper, 'read_app_version', lambda exe, timeout=60: '1.2.0')
    monkeypatch.setattr(
        helper, 'launch_app', lambda path: launched.setdefault('dir', path) or object()
    )

    result = helper.run_update(pending, log_file=tmp_path / 'helper.log')

    assert result['status'] == 'success'
    assert (install / 'YouTubeClipper.exe').read_bytes() == b'MZ NEW'
    assert (install / '_internal' / 'new.dll').exists()
    # Backup e instalador apagados após o sucesso.
    assert not list(install.glob('*.bak'))
    assert not installer.exists()
    assert not pending.exists()
    assert launched['dir'] == install
    assert (tmp_path / 'state' / 'last-result.json').exists()
    assert (tmp_path / 'state' / 'started.json').exists()


def test_instalador_falha_restaura_backup(monkeypatch, tmp_path):
    install = _make_installation(tmp_path)
    pending, installer = _make_pending(tmp_path, install)
    launched = {}

    monkeypatch.setattr(helper, 'wait_for_process_exit', lambda pid, timeout=60: True)
    monkeypatch.setattr(helper, 'run_installer', _fake_install(install, exit_code=1))
    monkeypatch.setattr(
        helper, 'launch_app', lambda path: launched.setdefault('dir', path) or object()
    )

    result = helper.run_update(pending, log_file=tmp_path / 'helper.log')

    assert result['status'] == 'failed'
    assert result['step'] == 'install'
    assert result['rolled_back'] is True
    assert (install / 'YouTubeClipper.exe').read_bytes() == b'MZ OLD'
    assert (install / '_internal' / 'old.dll').read_bytes() == b'OLD DLL'
    assert not list(install.glob('*.bak'))
    # O instalador é mantido em caso de falha (permite nova tentativa).
    assert installer.exists()
    assert launched['dir'] == install
    assert (tmp_path / 'state' / 'failed-version.json').exists()


def test_versao_errada_restaura_backup(monkeypatch, tmp_path):
    install = _make_installation(tmp_path)
    pending, _ = _make_pending(tmp_path, install)

    monkeypatch.setattr(helper, 'wait_for_process_exit', lambda pid, timeout=60: True)
    monkeypatch.setattr(helper, 'run_installer', _fake_install(install))
    monkeypatch.setattr(helper, 'read_app_version', lambda exe, timeout=60: '9.9.9')
    monkeypatch.setattr(helper, 'launch_app', lambda path: object())

    result = helper.run_update(pending, log_file=tmp_path / 'helper.log')

    assert result['status'] == 'failed'
    assert result['step'] == 'verify'
    assert (install / 'YouTubeClipper.exe').read_bytes() == b'MZ OLD'


def test_app_que_nao_encerra_cancela_sem_apagar_nada(monkeypatch, tmp_path):
    install = _make_installation(tmp_path)
    pending, installer = _make_pending(tmp_path, install)

    monkeypatch.setattr(helper, 'wait_for_process_exit', lambda pid, timeout=60: False)
    monkeypatch.setattr(
        helper, 'launch_app', lambda path: pytest.fail('não deveria relançar')
    )

    result = helper.run_update(pending, log_file=tmp_path / 'helper.log')

    assert result['status'] == 'failed'
    assert result['step'] == 'wait'
    assert result['rolled_back'] is False
    assert (install / 'YouTubeClipper.exe').read_bytes() == b'MZ OLD'
    assert installer.exists()
    # Falha de espera não suprime a versão (o app pode estar só demorando).
    assert not (tmp_path / 'state' / 'failed-version.json').exists()


def test_handshake_gravado_antes_da_troca(monkeypatch, tmp_path):
    install = _make_installation(tmp_path)
    pending, _ = _make_pending(tmp_path, install)
    seen = {}

    def _wait(pid, timeout=60):
        seen['started'] = helper.state_dir() / 'started.json'
        seen['exists'] = seen['started'].exists()
        return True

    monkeypatch.setattr(helper, 'wait_for_process_exit', _wait)
    monkeypatch.setattr(helper, 'run_installer', _fake_install(install))
    monkeypatch.setattr(helper, 'read_app_version', lambda exe, timeout=60: '1.2.0')
    monkeypatch.setattr(helper, 'launch_app', lambda path: object())

    helper.run_update(pending, log_file=tmp_path / 'helper.log')

    assert seen['exists'] is True
    data = json.loads(seen['started'].read_text(encoding='utf-8'))
    assert data['token'] == 'tok'


def test_recupera_backup_de_tentativa_anterior(tmp_path):
    install = tmp_path / 'app'
    install.mkdir()
    (install / '_internal.bak').mkdir()
    (install / '_internal.bak' / 'old.dll').write_bytes(b'OLD')

    helper.recover_leftovers(install)

    assert (install / '_internal' / 'old.dll').read_bytes() == b'OLD'
    assert not (install / '_internal.bak').exists()
