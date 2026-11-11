"""Testes da detecção de hardware e da seleção de encoders."""

import types

import pytest

import core.hardware as hw
from core.config import GPUVendor, HardwareProfile
from core.hardware import HardwareCapabilities, _classify_gpu_vendor

GB = 1024**3


@pytest.fixture(autouse=True)
def _limpar_cache():
    hw.invalidate_hardware_cache()
    yield
    hw.invalidate_hardware_cache()


def _caps(**overrides) -> HardwareCapabilities:
    """Cria capacidades de hardware com valores padrão sobrescrevíveis."""
    defaults = {
        'has_nvenc': False,
        'has_cuda': False,
        'has_quicksync': False,
        'has_vaapi': False,
        'has_videotoolbox': False,
        'total_ram_gb': 16.0,
        'available_ram_gb': 8.0,
        'gpu_vendor': GPUVendor.UNKNOWN,
        'gpu_name': 'Test GPU',
        'cpu_cores': 4,
        'cpu_threads': 8,
        'is_low_memory': False,
        'profile': HardwareProfile.MID_RANGE,
    }
    defaults.update(overrides)
    return HardwareCapabilities(**defaults)


# ── Classificação de vendor ───────────────────────────────────


@pytest.mark.parametrize(
    'name,vendor',
    [
        ('NVIDIA GeForce RTX 4070', GPUVendor.NVIDIA),
        ('Quadro P2000', GPUVendor.NVIDIA),
        ('AMD Radeon RX 6600', GPUVendor.AMD),
        ('Radeon Vega 7', GPUVendor.AMD),
        ('Intel(R) UHD Graphics 630', GPUVendor.INTEL),
        ('Intel Iris Xe Graphics', GPUVendor.INTEL),
        ('Apple M2', GPUVendor.APPLE),
        ('Dispositivo Desconhecido', GPUVendor.UNKNOWN),
    ],
)
def test_classify_gpu_vendor(name, vendor):
    assert _classify_gpu_vendor(name) == vendor


# ── Ordem de encoders ─────────────────────────────────────────


def test_ordem_de_encoders_com_todas_as_aceleracoes():
    caps = _caps(
        has_nvenc=True,
        has_quicksync=True,
        has_vaapi=True,
        has_videotoolbox=True,
    )

    assert caps.best_encoder_order() == [
        'h264_nvenc',
        'h264_qsv',
        'h264_vaapi',
        'h264_videotoolbox',
        'libx264',
    ]


def test_ordem_de_encoders_sem_aceleracao_cai_para_cpu():
    assert _caps().best_encoder_order() == ['libx264']


# ── Resumo ────────────────────────────────────────────────────


def test_summary_descreve_hardware_e_aceleracao():
    caps = _caps(
        has_nvenc=True,
        gpu_vendor=GPUVendor.NVIDIA,
        gpu_name='RTX 4070',
        total_ram_gb=32.0,
        available_ram_gb=20.0,
        cpu_cores=8,
        cpu_threads=16,
        profile=HardwareProfile.HIGH_END,
    )

    resumo = caps.summary()

    assert 'RTX 4070' in resumo
    assert 'NVENC' in resumo
    assert '32.0GB' in resumo
    assert 'high_end' in resumo
    assert '8C/16T' in resumo


def test_summary_sem_gpu_mostra_cpu_only():
    assert 'Nenhum (CPU only)' in _caps().summary()


# ── detect_hardware (psutil/ffmpeg mockados) ──────────────────


def _mock_hardware(monkeypatch, *, total_gb, available_gb, vendor, name):
    monkeypatch.setattr(hw.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(hw, '_detect_gpu_windows', lambda: (vendor, name))
    monkeypatch.setattr(hw, '_get_ffmpeg_path', lambda: 'ffmpeg')
    monkeypatch.setattr(
        hw.psutil,
        'virtual_memory',
        lambda: types.SimpleNamespace(total=total_gb * GB, available=available_gb * GB),
    )
    monkeypatch.setattr(
        hw.psutil, 'cpu_count', lambda logical=True: 8 if logical else 4
    )


def test_detect_hardware_perfil_low_memory(monkeypatch):
    _mock_hardware(
        monkeypatch,
        total_gb=8,
        available_gb=3,
        vendor=GPUVendor.AMD,
        name='Radeon Vega 7',
    )
    monkeypatch.setattr(hw, '_check_ffmpeg_encoder', lambda *a: False)

    caps = hw.detect_hardware(force_refresh=True)

    assert caps.profile is HardwareProfile.LOW_MEMORY
    assert caps.is_low_memory is True
    assert caps.total_ram_gb == pytest.approx(8.0)
    assert caps.available_ram_gb == pytest.approx(3.0)


def test_detect_hardware_perfil_high_end_com_nvenc(monkeypatch):
    _mock_hardware(
        monkeypatch,
        total_gb=32,
        available_gb=24,
        vendor=GPUVendor.NVIDIA,
        name='RTX 4070',
    )
    monkeypatch.setattr(hw, '_check_ffmpeg_encoder', lambda *a: True)
    monkeypatch.setattr(hw, '_check_ffmpeg_filter', lambda *a: True)
    monkeypatch.setattr(hw, '_check_ffmpeg_hwaccel', lambda *a: True)

    caps = hw.detect_hardware(force_refresh=True)

    assert caps.profile is HardwareProfile.HIGH_END
    assert caps.has_nvenc is True
    assert caps.has_cuda is True
    assert caps.best_encoder_order()[0] == 'h264_nvenc'


def test_detect_hardware_usa_cache(monkeypatch):
    _mock_hardware(
        monkeypatch,
        total_gb=16,
        available_gb=10,
        vendor=GPUVendor.INTEL,
        name='Intel UHD',
    )
    monkeypatch.setattr(hw, '_check_ffmpeg_encoder', lambda *a: False)

    first = hw.detect_hardware(force_refresh=True)
    second = hw.detect_hardware()

    assert first is second
    assert hw.get_cached_capabilities() is first


def test_invalidate_hardware_cache_redetecta(monkeypatch):
    _mock_hardware(
        monkeypatch,
        total_gb=16,
        available_gb=10,
        vendor=GPUVendor.INTEL,
        name='Intel UHD',
    )
    monkeypatch.setattr(hw, '_check_ffmpeg_encoder', lambda *a: False)

    first = hw.get_cached_capabilities()
    hw.invalidate_hardware_cache()
    second = hw.get_cached_capabilities()

    assert first is not second
