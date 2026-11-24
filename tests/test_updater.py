"""Testes da atualização automática (versões, assets, download e aplicação)."""

import hashlib
import os
import threading
import time
from pathlib import Path

import pytest

import core.updater as updater
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
    exe_name='YouTubeClipper-1.2.0.exe',
    with_checksum=True,
    draft=False,
    prerelease=False,
):
    assets = [
        {
            'name': exe_name,
            'browser_download_url': f'https://example.com/{exe_name}',
            'size': 123,
        }
    ]
    if with_checksum:
        assets.append(
            {
                'name': f'{exe_name}.sha256',
                'browser_download_url': f'https://example.com/{exe_name}.sha256',
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
        download_url='https://example.com/YouTubeClipper-1.2.0.exe',
        checksum_url='https://example.com/YouTubeClipper-1.2.0.exe.sha256',
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
    assert info.asset_name == 'YouTubeClipper-1.2.0.exe'


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


def test_check_for_update_usa_asset_por_prefixo(monkeypatch):
    monkeypatch.setattr(
        updater,
        '_fetch_json',
        lambda url, timeout: _release(exe_name='YouTubeClipper-custom.exe'),
    )

    info = updater.check_for_update('1.1.0')

    assert info is not None
    assert info.asset_name == 'YouTubeClipper-custom.exe'
    assert info.checksum_url == ('https://example.com/YouTubeClipper-custom.exe.sha256')


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


# ── download_update ───────────────────────────────────────────


def test_download_update_valida_checksum(monkeypatch, tmp_path, update_info):
    payload = b'exe!'
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
    assert path.name == 'YouTubeClipper-1.2.0.exe'
    assert progressed[-1][0] == 100


def test_download_update_checksum_invalido(monkeypatch, tmp_path, update_info):
    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(
        updater, '_http_open', lambda url, timeout: FakeResponse(b'exe!')
    )
    monkeypatch.setattr(updater, '_fetch_text', lambda url, timeout: '0' * 64)

    with pytest.raises(updater.UpdateError, match='Checksum'):
        updater.download_update(update_info)

    assert not (tmp_path / 'YouTubeClipper-1.2.0.exe').exists()
    assert not (tmp_path / 'YouTubeClipper-1.2.0.exe.part').exists()


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
        updater, '_http_open', lambda url, timeout: FakeResponse(b'exe!')
    )

    path = updater.download_update(info)

    assert path.read_bytes() == b'exe!'


def test_download_update_cancelado(monkeypatch, tmp_path, update_info):
    event = threading.Event()
    event.set()

    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(
        updater, '_http_open', lambda url, timeout: FakeResponse(b'exe!')
    )

    with pytest.raises(updater.UpdateCancelled):
        updater.download_update(update_info, cancel_event=event)

    assert not (tmp_path / 'YouTubeClipper-1.2.0.exe.part').exists()


def test_download_update_falha_de_rede(monkeypatch, tmp_path, update_info):
    def _boom(url, timeout):
        raise OSError('caiu')

    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path)
    monkeypatch.setattr(updater, '_http_open', _boom)

    with pytest.raises(updater.UpdateError, match='Falha ao baixar'):
        updater.download_update(update_info)


# ── apply_update_and_restart ──────────────────────────────────


def test_apply_recusa_modo_dev(monkeypatch):
    monkeypatch.setattr(updater, 'is_frozen', lambda: False)

    with pytest.raises(updater.UpdateError, match='executável'):
        updater.apply_update_and_restart(Path('novo.exe'))


def test_apply_recusa_fora_do_windows(monkeypatch, tmp_path):
    new_exe = tmp_path / 'novo.exe'
    new_exe.write_bytes(b'x')

    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    monkeypatch.setattr(updater.sys, 'platform', 'linux')

    with pytest.raises(updater.UpdateError, match='Windows'):
        updater.apply_update_and_restart(new_exe)


def test_apply_recusa_arquivo_inexistente(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    monkeypatch.setattr(updater.sys, 'platform', 'win32')

    with pytest.raises(updater.UpdateError, match='não encontrado'):
        updater.apply_update_and_restart(tmp_path / 'nao_existe.exe')


def test_apply_agenda_script_e_processo(monkeypatch, tmp_path):
    new_exe = tmp_path / 'YouTubeClipper-1.2.0.exe'
    new_exe.write_bytes(b'novo')

    monkeypatch.setattr(updater, 'is_frozen', lambda: True)
    monkeypatch.setattr(updater.sys, 'platform', 'win32')
    monkeypatch.setattr(updater.sys, 'executable', str(tmp_path / 'atual.exe'))
    monkeypatch.setattr(updater, '_updates_dir', lambda: tmp_path / 'updates')

    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured['args'] = args
            captured['kwargs'] = kwargs

    monkeypatch.setattr(updater.subprocess, 'Popen', FakePopen)

    updater.apply_update_and_restart(new_exe)

    script = tmp_path / 'updates' / f'update-{os.getpid()}.ps1'
    assert script.is_file()
    assert 'Move-Item' in script.read_text(encoding='utf-8')
    assert '-ProcessId' in captured['args']
    assert str(new_exe) in captured['args']
    assert captured['args'][0] == 'powershell.exe'


def test_build_update_script_contem_espera_pelo_processo():
    script = updater.build_update_script()

    assert 'Get-Process -Id $ProcessId' in script
    assert 'Start-Process -FilePath $CurrentExe' in script


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
