"""Testes da atualização automática (versões, assets, download e aplicação)."""

import hashlib
import os
import threading
import time

import pytest

import core.updater as updater
from core import update_state
from core.config import AppConfig, UpdateConfig


class FakeResponse:
    """Resposta HTTP falsa mínima, compatível com o context manager."""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self.headers = {'Content-Length': str(len(data))}

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._data) - self._pos
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


@pytest.fixture(autouse=True)
def _default_config(monkeypatch):
    monkeypatch.setattr(updater, 'get_config', lambda: AppConfig())


def _release(
    tag='v1.2.0',
    *,
    asset_name='YouTubeClipper-Setup-1.2.0.exe',
    with_checksum=True,
    draft=False,
    prerelease=False,
):
    assets = [
        {
            'name': asset_name,
            'browser_download_url': f'https://example.com/{asset_name}',
            'size': 123,
        }
    ]
    if with_checksum:
        assets.append(
            {
                'name': f'{asset_name}.sha256',
                'browser_download_url': f'https://example.com/{asset_name}.sha256',
            }
        )
    return {
        'tag_name': tag,
        'draft': draft,
        'prerelease': prerelease,
        'body': 'notas da versão',
        'assets': assets,
    }


@pytest.fixture
def update_info():
    return updater.UpdateInfo(
        version='1.2.0',
        tag='v1.2.0',
        notes='notas',
        download_url='https://example.com/YouTubeClipper-Setup-1.2.0.exe',
        checksum_url='https://example.com/YouTubeClipper-Setup-1.2.0.exe.sha256',
        size=4,
    )


# ── Versões ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    'value,expected',
    [
        ('v1.2.3', (1, 2, 3)),
        ('1.2', (1, 2)),
        ('V10', (10,)),
        ('1.2.0-beta', (1, 2, 0)),
        ('', ()),
        ('abc', ()),
    ],
)
def test_parse_version(value, expected):
    assert updater.parse_version(value) == expected


@pytest.mark.parametrize(
    'candidate,current,expected',
    [
        ('v1.2.0', '1.1.9', True),
        ('1.2.0', '1.2.0', False),
        ('1.1.0', '1.2.0', False),
        ('1.2', '1.2.0', False),
        ('1.2.1', '1.2', True),
        ('invalida', '1.2.0', False),
    ],
)
def test_is_newer(candidate, current, expected):
    assert updater.is_newer(candidate, current) is expected


# ── check_for_update ──────────────────────────────────────────


def test_check_for_update_retorna_release_mais_nova(monkeypatch):
    monkeypatch.setattr(updater, '_fetch_json', lambda url, timeout: _release())

    info = updater.check_for_update('1.1.0')

    assert info is not None
    assert info.version == '1.2.0'
    assert info.tag == 'v1.2.0'
    assert info.notes == 'notas da versão'
    assert info.checksum_url.endswith('.sha256')
    assert info.asset_name == 'YouTubeClipper-Setup-1.2.0.exe'


@pytest.mark.parametrize('current', ['1.2.0', '1.3.0'])
def test_check_for_update_sem_versao_nova(monkeypatch, current):
    monkeypatch.setattr(updater, '_fetch_json', lambda url, timeout: _release())

    assert updater.check_for_update(current) is None


def test_check_for_update_ignora_draft_e_prerelease(monkeypatch):
    monkeypatch.setattr(
        updater, '_fetch_json', lambda url, timeout: _release(draft=True)
    )
    assert updater.check_for_update('1.1.0') is None

    monkeypatch.setattr(
        updater, '_fetch_json', lambda url, timeout: _release(prerelease=True)
    )
    assert updater.check_for_update('1.1.0') is None


def test_check_for_update_sem_executavel(monkeypatch):
    release = _release()
    release['assets'] = []

    monkeypatch.setattr(updater, '_fetch_json', lambda url, timeout: release)

    assert updater.check_for_update('1.1.0') is None


def test_check_for_update_ignora_release_so_com_exe_antigo(monkeypatch):
    """A release precisa do Setup; o .exe portátil antigo não serve mais."""
    release = _release(asset_name='YouTubeClipper-1.1.0.exe')

    monkeypatch.setattr(updater, '_fetch_json', lambda url, timeout: release)

    assert updater.check_for_update('1.0.0') is None


def test_check_for_update_rejeita_asset_de_outra_versao(monkeypatch):
    """Nome fora do padrão só é aceito se a versão embutida for a da release."""
    monkeypatch.setattr(
        updater,
        '_fetch_json',
        lambda url, timeout: _release(asset_name='YouTubeClipper-Setup-custom.exe'),
    )

    assert updater.check_for_update('1.1.0') is None


def test_check_for_update_aceita_asset_com_v_no_nome(monkeypatch):
    monkeypatch.setattr(
        updater,
        '_fetch_json',
        lambda url, timeout: _release(asset_name='YouTubeClipper-Setup-v1.2.0.exe'),
    )

    info = updater.check_for_update('1.1.0')

    assert info is not None
    assert info.asset_name == 'YouTubeClipper-Setup-v1.2.0.exe'


def test_check_for_update_disponivel_mesmo_sem_checksum(monkeypatch):
    monkeypatch.setattr(
        updater,
        '_fetch_json',
        lambda url, timeout: _release(with_checksum=False),
    )

    info = updater.check_for_update('1.1.0')

    assert info is not None
    assert info.checksum_url is None


def test_check_for_update_desativado(monkeypatch):
    monkeypatch.setattr(
        updater,
        'get_config',
        lambda: AppConfig(update=UpdateConfig(enabled=False)),
    )
    monkeypatch.setattr(updater, '_fetch_json', lambda url, timeout: _release())

    assert updater.check_for_update('1.1.0') is None


def test_check_for_update_falha_de_rede_nao_quebra(monkeypatch):
    def _boom(url, timeout):
        raise OSError('sem internet')

    monkeypatch.setattr(updater, '_fetch_json', _boom)

    assert updater.check_for_update('1.1.0') is None


def test_check_for_update_suprime_versao_que_falhou(monkeypatch, tmp_path):
    monkeypatch.setattr(update_state, 'state_dir', lambda: tmp_path)
    update_state.record_failed_version('1.2.0')
    monkeypatch.setattr(updater, '_fetch_json', lambda url, timeout: _release())

    # Automático: não oferece de novo a versão que acabou de falhar.
    assert updater.check_for_update('1.1.0') is None
    # Manual: o usuário ainda pode tentar.
    assert updater.check_for_update('1.1.0', ignore_suppressed=True) is not None


# ── download_update ───────────────────────────────────────────


def test_download_update_valida_checksum(monkeypatch, tmp_path, update_info):
    payload = b'MZ\x90\x00'
    sha = hashlib.sha256(payload).hexdigest()
    progressed = []

    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(
        updater, '_http_open', lambda url, timeout: FakeResponse(payload)
    )
    monkeypatch.setattr(
        updater, '_fetch_text', lambda url, timeout: f'{sha}  arquivo.exe\n'
    )

    path = updater.download_update(
        update_info, lambda pct, msg: progressed.append((pct, msg))
    )

    assert path.read_bytes() == payload
    assert path.name == 'YouTubeClipper-Setup-1.2.0.exe'
    assert progressed[-1][0] == 100


def test_download_update_checksum_invalido(monkeypatch, tmp_path, update_info):
    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(
        updater, '_http_open', lambda url, timeout: FakeResponse(b'MZ\x90\x00')
    )
    monkeypatch.setattr(updater, '_fetch_text', lambda url, timeout: '0' * 64)

    with pytest.raises(updater.UpdateError, match='Checksum'):
        updater.download_update(update_info)

    assert not (tmp_path / 'YouTubeClipper-Setup-1.2.0.exe').exists()
    assert not (tmp_path / 'YouTubeClipper-Setup-1.2.0.exe.part').exists()


def test_download_update_sem_checksum(monkeypatch, tmp_path, update_info):
    info = updater.UpdateInfo(
        version=update_info.version,
        tag=update_info.tag,
        notes='',
        download_url=update_info.download_url,
        checksum_url=None,
    )
    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(
        updater, '_http_open', lambda url, timeout: FakeResponse(b'MZ\x90\x00')
    )

    path = updater.download_update(info)

    assert path.read_bytes() == b'MZ\x90\x00'


def test_download_update_rejeita_arquivo_vazio(monkeypatch, tmp_path):
    info = updater.UpdateInfo(
        version='1.2.0',
        tag='v1.2.0',
        notes='',
        download_url='https://example.com/setup.exe',
        checksum_url=None,
        size=0,
    )
    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(updater, '_http_open', lambda url, timeout: FakeResponse(b''))

    with pytest.raises(updater.UpdateError, match='vazio'):
        updater.download_update(info)

    assert not (tmp_path / 'setup.exe').exists()


def test_download_update_rejeita_tamanho_diferente(monkeypatch, tmp_path, update_info):
    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(updater, '_http_open', lambda url, timeout: FakeResponse(b'MZ'))
    monkeypatch.setattr(updater, '_fetch_text', lambda url, timeout: '0' * 64)
    # Sem checksum para chegar à validação de tamanho.
    info = updater.UpdateInfo(
        version='1.2.0',
        tag='v1.2.0',
        notes='',
        download_url='https://example.com/setup.exe',
        checksum_url=None,
        size=4,
    )

    with pytest.raises(updater.UpdateError, match='incompleto'):
        updater.download_update(info)


def test_download_update_rejeita_nao_executavel(monkeypatch, tmp_path):
    payload = b'data'
    sha = hashlib.sha256(payload).hexdigest()
    info = updater.UpdateInfo(
        version='1.2.0',
        tag='v1.2.0',
        notes='',
        download_url='https://example.com/setup.exe',
        checksum_url='https://example.com/setup.exe.sha256',
        size=len(payload),
    )
    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(
        updater, '_http_open', lambda url, timeout: FakeResponse(payload)
    )
    monkeypatch.setattr(
        updater, '_fetch_text', lambda url, timeout: f'{sha}  setup.exe\n'
    )

    with pytest.raises(updater.UpdateError, match='executável'):
        updater.download_update(info)

    assert not (tmp_path / 'setup.exe').exists()


def test_download_update_cancelado(monkeypatch, tmp_path, update_info):
    event = threading.Event()
    event.set()

    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(
        updater, '_http_open', lambda url, timeout: FakeResponse(b'MZ\x90\x00')
    )

    with pytest.raises(updater.UpdateCancelled):
        updater.download_update(update_info, cancel_event=event)

    assert not (tmp_path / 'YouTubeClipper-Setup-1.2.0.exe.part').exists()


def test_download_update_falha_de_rede(monkeypatch, tmp_path, update_info):
    def _boom(url, timeout):
        raise OSError('caiu')

    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(updater, '_http_open', _boom)

    with pytest.raises(updater.UpdateError, match='Falha ao baixar'):
        updater.download_update(update_info)


# ── apply_update_and_restart ──────────────────────────────────


def _prepared_install(monkeypatch, tmp_path, *, helper=True, installed=True):
    installer = tmp_path / 'YouTubeClipper-Setup-1.2.0.exe'
    installer.write_bytes(b'MZ installer')
    install_dir = tmp_path / 'app'
    install_dir.mkdir()
    (install_dir / 'YouTubeClipper.exe').write_bytes(b'MZ old')
    (install_dir / 'unins000.exe').write_bytes(b'MZ uninstaller')
    helper_file = tmp_path / 'updater' / 'YouTubeClipperUpdater.exe'
    helper_file.parent.mkdir()
    if helper:
        helper_file.write_bytes(b'MZ helper')

    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    monkeypatch.setattr(updater.sys, 'platform', 'win32')
    monkeypatch.setattr(updater, 'is_installed', lambda: installed)
    monkeypatch.setattr(updater, 'get_install_dir', lambda: install_dir)
    monkeypatch.setattr(updater, 'helper_path', lambda: helper_file)
    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path / 'updates')
    (tmp_path / 'updates').mkdir()
    monkeypatch.setattr(update_state, 'state_dir', lambda: tmp_path / 'state')
    return installer, install_dir


class FakeSupervisor:
    pid = 4242

    def __init__(self, args, handshake=True, token=None, **kwargs):
        self.args = args
        self.handshake = handshake
        self.token = token
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def write_started(self):
        if self.handshake:
            update_state.write_started({'token': self.token, 'pid': self.pid})


def test_apply_recusa_modo_dev(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, 'is_frozen', lambda: False)

    with pytest.raises(updater.UpdateError, match='instalado'):
        updater.apply_update_and_restart(tmp_path / 'novo.exe', '1.2.0')


def test_apply_recusa_fora_do_windows(monkeypatch, tmp_path):
    installer = tmp_path / 'novo.exe'
    installer.write_bytes(b'MZ')

    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    monkeypatch.setattr(updater.sys, 'platform', 'linux')

    with pytest.raises(updater.UpdateError, match='Windows'):
        updater.apply_update_and_restart(installer, '1.2.0')


def test_apply_recusa_arquivo_inexistente(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    monkeypatch.setattr(updater.sys, 'platform', 'win32')
    monkeypatch.setattr(updater, 'is_installed', lambda: True)

    with pytest.raises(updater.UpdateError, match='não encontrado'):
        updater.apply_update_and_restart(tmp_path / 'nao_existe.exe', '1.2.0')


def test_apply_recusa_copia_portatil(monkeypatch, tmp_path):
    installer = tmp_path / 'setup.exe'
    installer.write_bytes(b'MZ')
    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    monkeypatch.setattr(updater.sys, 'platform', 'win32')
    monkeypatch.setattr(updater, 'is_installed', lambda: False)

    with pytest.raises(updater.UpdateError, match='Setup'):
        updater.apply_update_and_restart(installer, '1.2.0')


def test_apply_exige_supervisor(monkeypatch, tmp_path):
    installer, _ = _prepared_install(monkeypatch, tmp_path, helper=False)

    with pytest.raises(updater.UpdateError, match='supervisor'):
        updater.apply_update_and_restart(installer, '1.2.0')


def test_apply_inicia_supervisor_e_aguarda_handshake(monkeypatch, tmp_path):
    installer, _ = _prepared_install(monkeypatch, tmp_path)
    captured = {}

    def fake_popen(args, **kwargs):
        captured['args'] = args
        pending = update_state.read_pending()
        process = FakeSupervisor(args, token=pending['token'])
        process.write_started()
        return process

    monkeypatch.setattr(updater.subprocess, 'Popen', fake_popen)

    updater.apply_update_and_restart(installer, '1.2.0')

    assert captured['args'][0].endswith('YouTubeClipperUpdater.exe')
    assert captured['args'][1] == '--pending'
    pending = update_state.read_pending()
    assert pending['installer'] == str(installer)
    assert pending['target_version'] == '1.2.0'
    assert pending['parent_pid'] == os.getpid()
    assert pending['inno_log'].endswith('.log')


def test_apply_falha_se_supervisor_nao_confirmar(monkeypatch, tmp_path):
    installer, _ = _prepared_install(monkeypatch, tmp_path)
    monkeypatch.setattr(updater, '_HANDSHAKE_TIMEOUT', 0.2)

    def fake_popen(args, **kwargs):
        return FakeSupervisor(args, handshake=False)

    monkeypatch.setattr(updater.subprocess, 'Popen', fake_popen)

    with pytest.raises(updater.UpdateError, match='não confirmou'):
        updater.apply_update_and_restart(installer, '1.2.0')

    assert update_state.read_pending() is None


def test_apply_falha_ao_iniciar_supervisor(monkeypatch, tmp_path):
    installer, _ = _prepared_install(monkeypatch, tmp_path)

    def _boom(*args, **kwargs):
        raise OSError('sem permissão')

    monkeypatch.setattr(updater.subprocess, 'Popen', _boom)

    with pytest.raises(updater.UpdateError, match='supervisor'):
        updater.apply_update_and_restart(installer, '1.2.0')


def test_build_installer_command_inclui_dir(tmp_path):
    command = updater.build_installer_command(
        tmp_path / 'setup.exe', tmp_path / 'install.log', tmp_path / 'app'
    )

    assert command[0] == str(tmp_path / 'setup.exe')
    assert f'/LOG={tmp_path / "install.log"}' in command
    assert f'/DIR={tmp_path / "app"}' in command
    assert '/NORESTART' in command


# ── Detecção de instalação ────────────────────────────────────


def test_is_installed_detecta_desinstalador(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    monkeypatch.setattr(updater, 'get_install_dir', lambda: tmp_path)

    assert updater.is_installed() is False

    (tmp_path / 'unins000.exe').write_bytes(b'x')
    assert updater.is_installed() is True


def test_is_installed_falso_em_modo_dev(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, 'is_frozen', lambda: False)
    monkeypatch.setattr(updater, 'get_install_dir', lambda: tmp_path)
    (tmp_path / 'unins000.exe').write_bytes(b'x')

    assert updater.is_installed() is False


# ── Cache ─────────────────────────────────────────────────────


def test_cleanup_update_cache_remove_arquivos_antigos(monkeypatch, tmp_path):
    old_file = tmp_path / 'antigo.exe'
    recent_file = tmp_path / 'recente.exe'
    old_file.write_bytes(b'x')
    recent_file.write_bytes(b'x')

    old_time = time.time() - 8 * 24 * 3600
    os.utime(old_file, (old_time, old_time))

    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)

    updater.cleanup_update_cache(max_age_days=7)

    assert not old_file.exists()
    assert recent_file.exists()
