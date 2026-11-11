"""Testes da configuração centralizada (perfis, ambiente e imutabilidade)."""

from dataclasses import replace

import pytest

from core.config import (
    AppConfig,
    DownloadConfig,
    EncoderConfig,
    HardwareProfile,
    get_config,
    reset_config,
    set_config,
)


@pytest.fixture(autouse=True)
def _reset_config():
    reset_config()
    yield
    reset_config()


# ── DownloadConfig ────────────────────────────────────────────


@pytest.mark.parametrize(
    'profile,timeout,retries,chunk,concurrent',
    [
        (HardwareProfile.HIGH_END, 45, 3, 20_971_520, 4),
        (HardwareProfile.MID_RANGE, 60, 5, 10_485_760, 3),
        (HardwareProfile.LOW_MEMORY, 90, 8, 5_242_880, 1),
        (HardwareProfile.CI_CD, 90, 8, 5_242_880, 1),
    ],
)
def test_download_presets_por_perfil(profile, timeout, retries, chunk, concurrent):
    cfg = DownloadConfig.for_profile(profile)
    assert cfg.socket_timeout == timeout
    assert cfg.retries == retries
    assert cfg.http_chunk_size == chunk
    assert cfg.concurrent_fragment_downloads == concurrent


def test_ydl_params_contem_timeouts_e_retries():
    params = DownloadConfig().ydl_params

    assert params['socket_timeout'] == 60
    assert params['retries'] == 5
    assert params['fragment_retries'] == 5
    assert params['http_chunk_size'] == 10_485_760
    assert params['ignoreerrors'] is False


def test_ydl_params_inclui_throttle_apenas_quando_definido():
    assert 'throttled_rate' not in DownloadConfig().ydl_params
    assert DownloadConfig(throttled_rate='1M').ydl_params['throttled_rate'] == '1M'


# ── EncoderConfig ─────────────────────────────────────────────


def test_low_memory_aplica_limites_agressivos():
    cfg = EncoderConfig(low_memory_mode=True)

    assert cfg.max_threads == 2
    assert cfg.thread_queue_size == 256
    assert cfg.max_muxing_queue_size == 512
    assert cfg.preset_cpu == 'veryfast'


def test_low_memory_nao_altera_config_padrao():
    cfg = EncoderConfig()

    assert cfg.max_threads == 0
    assert cfg.thread_queue_size == 1024
    assert cfg.low_memory_mode is False


def test_perfil_low_memory_forca_cpu():
    cfg = EncoderConfig.for_profile(HardwareProfile.LOW_MEMORY)

    assert cfg.prefer_hardware is False
    assert cfg.low_memory_mode is True


def test_perfil_high_end_usa_gpu_e_preset_rapido():
    cfg = EncoderConfig.for_profile(HardwareProfile.HIGH_END)

    assert cfg.prefer_hardware is True
    assert cfg.preset_cpu == 'fast'
    assert cfg.preset_gpu == 'p2'


def test_override_de_low_memory_vale_para_mid_range():
    cfg = EncoderConfig.for_profile(HardwareProfile.MID_RANGE, low_memory_override=True)

    assert cfg.low_memory_mode is True
    assert cfg.max_threads == 2


# ── AppConfig.load / ambiente ─────────────────────────────────


def test_load_sem_env_nao_aplica_perfil(monkeypatch):
    for var in (
        'YTCLIPPER_PROFILE',
        'YTCLIPPER_LOW_MEMORY',
        'YTCLIPPER_PREFER_HW',
    ):
        monkeypatch.delenv(var, raising=False)

    cfg = AppConfig.load()

    assert cfg.hardware_profile is None
    assert cfg.force_low_memory is False
    assert cfg.encoder.low_memory_mode is False


def test_load_aplica_perfil_do_ambiente_no_download(monkeypatch):
    monkeypatch.setenv('YTCLIPPER_PROFILE', 'low_memory')

    cfg = AppConfig.load()

    assert cfg.hardware_profile is HardwareProfile.LOW_MEMORY
    assert cfg.download.retries == 8
    assert cfg.download.http_chunk_size == 5_242_880
    assert cfg.download.concurrent_fragment_downloads == 1
    assert cfg.encoder.prefer_hardware is False
    assert cfg.encoder.low_memory_mode is True


def test_load_ignora_perfil_invalido(monkeypatch):
    monkeypatch.setenv('YTCLIPPER_PROFILE', 'nao_existe')

    cfg = AppConfig.load()

    assert cfg.hardware_profile is None


def test_load_respeita_low_memory_por_ambiente(monkeypatch):
    monkeypatch.setenv('YTCLIPPER_LOW_MEMORY', 'true')

    cfg = AppConfig.load()

    assert cfg.force_low_memory is True
    assert cfg.encoder.low_memory_mode is True
    assert cfg.encoder.max_threads == 2


def test_prefer_hw_ambiente_tem_prioridade_sobre_perfil(monkeypatch):
    monkeypatch.setenv('YTCLIPPER_PROFILE', 'low_memory')
    monkeypatch.setenv('YTCLIPPER_PREFER_HW', 'true')

    cfg = AppConfig.load()

    assert cfg.encoder.prefer_hardware is True


def test_with_profile_preserva_opcoes_nao_relacionadas():
    base = AppConfig(log_level='DEBUG', ffmpeg_timeout=123)
    novo = base.with_profile(HardwareProfile.HIGH_END)

    # Imutabilidade: a instância original não muda.
    assert base.hardware_profile is None
    assert novo.hardware_profile is HardwareProfile.HIGH_END
    assert novo.log_level == 'DEBUG'
    assert novo.ffmpeg_timeout == 123
    assert novo.download.retries == 3


def test_with_profile_respeita_force_low_memory():
    base = AppConfig(force_low_memory=True)
    novo = base.with_profile(HardwareProfile.HIGH_END)

    assert novo.force_low_memory is True
    assert novo.encoder.low_memory_mode is True


# ── Singleton ─────────────────────────────────────────────────


def test_get_config_retorna_sempre_a_mesma_instancia():
    assert get_config() is get_config()


def test_set_config_substitui_a_instancia_global():
    custom = replace(get_config(), log_level='ERROR')
    set_config(custom)

    assert get_config().log_level == 'ERROR'


def test_reset_config_recarrega_do_ambiente(monkeypatch):
    original = get_config()
    monkeypatch.setenv('YTCLIPPER_LOG_LEVEL', 'DEBUG')

    reset_config()

    assert get_config() is not original
    assert get_config().log_level == 'DEBUG'
