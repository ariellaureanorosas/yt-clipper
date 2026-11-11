"""Testes do bootstrap de configuração (aplicação do perfil detectado)."""

import types

import pytest

from core.bootstrap import bootstrap_config
from core.config import HardwareProfile, get_config, reset_config


@pytest.fixture(autouse=True)
def _reset_config():
    reset_config()
    yield
    reset_config()


def _fake_caps(profile=HardwareProfile.LOW_MEMORY, total_ram_gb=8.0):
    return types.SimpleNamespace(profile=profile, total_ram_gb=total_ram_gb)


def test_bootstrap_aplica_perfil_detectado(monkeypatch):
    monkeypatch.delenv('YTCLIPPER_PROFILE', raising=False)
    monkeypatch.setattr('core.bootstrap.get_cached_capabilities', lambda: _fake_caps())

    cfg = bootstrap_config()

    assert cfg.hardware_profile is HardwareProfile.LOW_MEMORY
    assert cfg.encoder.low_memory_mode is True
    assert cfg.download.retries == 8
    assert get_config().hardware_profile is HardwareProfile.LOW_MEMORY


def test_bootstrap_e_idempotente(monkeypatch):
    monkeypatch.delenv('YTCLIPPER_PROFILE', raising=False)
    monkeypatch.setattr('core.bootstrap.get_cached_capabilities', lambda: _fake_caps())

    primeira = bootstrap_config()
    segunda = bootstrap_config()

    assert primeira is segunda


def test_bootstrap_respeita_perfil_explicito_do_ambiente(monkeypatch):
    monkeypatch.setenv('YTCLIPPER_PROFILE', 'high_end')
    reset_config()
    monkeypatch.setattr('core.bootstrap.get_cached_capabilities', lambda: _fake_caps())

    cfg = bootstrap_config()

    assert cfg.hardware_profile is HardwareProfile.HIGH_END
    assert cfg.download.retries == 3


def test_bootstrap_force_refresh_redetecta(monkeypatch):
    monkeypatch.setenv('YTCLIPPER_PROFILE', 'high_end')
    reset_config()
    monkeypatch.setattr('core.bootstrap.get_cached_capabilities', lambda: _fake_caps())

    cfg = bootstrap_config(force_refresh=True)

    assert cfg.hardware_profile is HardwareProfile.LOW_MEMORY
