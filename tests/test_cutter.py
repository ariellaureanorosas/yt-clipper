"""Testes das funções puras do módulo de corte (ffmpeg)."""

import pytest

import core.cutter as cutter
from core.config import AppConfig, EncoderConfig, GPUVendor, HardwareProfile
from core.cutter import (
    _build_crop_filter,
    _can_stream_copy,
    _format_time,
    _select_strategies,
)
from core.hardware import HardwareCapabilities


@pytest.mark.parametrize(
    'seconds,expected',
    [
        (0, '00:00:00.000'),
        (59.5, '00:00:59.500'),
        (60, '00:01:00.000'),
        (3661.25, '01:01:01.250'),
    ],
)
def test_format_time(seconds, expected):
    assert _format_time(seconds) == expected


def test_mesma_proporcao_apenas_escala():
    # 1920x1080 -> 1920x1080 não precisa de crop
    result = _build_crop_filter(1920, 1080, 1920, 1080)
    assert result == ['-vf', 'scale=1920:1080']


def test_fonte_larga_recorta_laterais():
    # 16:9 -> 9:16: recorta as laterais e mantém a altura
    filtro = _build_crop_filter(1920, 1080, 1080, 1920)
    assert filtro[0] == '-vf'
    assert filtro[1].startswith('crop=')
    assert filtro[1].endswith('scale=1080:1920')


def test_fonte_estreita_recorta_topo_base():
    # 9:16 -> 16:9: recorta topo/base e mantém a largura
    filtro = _build_crop_filter(1080, 1920, 1920, 1080)
    assert filtro[0] == '-vf'
    assert filtro[1].startswith('crop=')
    assert filtro[1].endswith('scale=1920:1080')


@pytest.mark.parametrize(
    'ow,oh,tw,th',
    [
        (1920, 1081, 1080, 1920),  # fonte com altura ímpar
        (1001, 1080, 1080, 1920),  # fonte com largura ímpar
        (1001, 1920, 1920, 1080),  # fonte estreita com largura ímpar
        (3840, 2160, 1080, 1920),  # 4K -> vertical
    ],
)
def test_dimensoes_de_crop_sao_pares(ow, oh, tw, th):
    # ffmpeg exige largura/altura pares no filtro de crop
    filtro = _build_crop_filter(ow, oh, tw, th)
    assert filtro[0] == '-vf'
    filter_str = filtro[1]
    if filter_str.startswith('crop='):
        crop = filter_str.split(',')[0]  # crop=w:h:x:y
        w, h = crop.split('=')[1].split(':')[:2]
        assert int(w) % 2 == 0
        assert int(h) % 2 == 0


@pytest.mark.parametrize(
    'needs_scale,codec,expected',
    [
        (False, 'h264', True),  # mesma resolução + H.264: stream copy
        (True, 'h264', False),  # precisa redimensionar: re-encode
        (False, 'vp9', False),  # codec incompatível com mp4/H.264
        (False, 'av1', False),
        (True, 'vp9', False),
    ],
)
def test_can_stream_copy(needs_scale, codec, expected):
    assert _can_stream_copy(needs_scale, codec) is expected


# ── Seleção de estratégias (Strategy Pattern) ─────────────────


def _caps(**overrides):
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


def test_seleciona_hardware_na_ordem_e_cpu_por_ultimo():
    caps = _caps(
        has_nvenc=True,
        has_quicksync=True,
        has_vaapi=True,
        has_videotoolbox=True,
    )

    estrategias = _select_strategies(
        caps, EncoderConfig(prefer_hardware=True, allow_fallback=True)
    )
    labels = [s.label for s in estrategias]

    assert len(estrategias) == 5
    assert labels[0].startswith('NVENC')
    assert labels[1].startswith('QuickSync')
    assert labels[2].startswith('VAAPI')
    assert labels[3].startswith('VideoToolbox')
    assert labels[4].startswith('CPU libx264')


def test_sem_preferencia_por_hardware_usa_somente_cpu():
    caps = _caps(has_nvenc=True)

    estrategias = _select_strategies(
        caps, EncoderConfig(prefer_hardware=False, allow_fallback=True)
    )

    assert len(estrategias) == 1
    assert estrategias[0].label.startswith('CPU libx264')


def test_sem_fallback_nao_inclui_cpu():
    caps = _caps(has_nvenc=True)

    estrategias = _select_strategies(
        caps, EncoderConfig(prefer_hardware=True, allow_fallback=False)
    )

    assert len(estrategias) == 1
    assert estrategias[0].label.startswith('NVENC')


def test_cpu_low_memory_marca_o_perfil():
    caps = _caps()

    estrategias = _select_strategies(
        caps, EncoderConfig(prefer_hardware=False, low_memory_mode=True)
    )

    assert '[LOW MEM]' in estrategias[0].label


def test_estrategia_cpu_monta_comando_com_limites_de_memoria():
    caps = _caps()
    estrategias = _select_strategies(
        caps,
        EncoderConfig(
            prefer_hardware=False,
            low_memory_mode=True,
            max_threads=2,
            thread_queue_size=256,
            max_muxing_queue_size=512,
        ),
    )

    cmd = estrategias[0].build_cmd(
        ['ffmpeg', '-y'],
        ['-vf', 'scale=1920:1080'],
        ['-c:a', 'copy'],
        'out.mp4',
        'in.mp4',
    )

    assert 'libx264' in cmd
    assert cmd[cmd.index('-threads') + 1] == '2'
    assert '256' in cmd
    assert '512' in cmd


# ── Pipeline cut_video (subprocess mockado) ──────────────────


class FakeProc:
    def __init__(self, returncode=0, stderr_lines=None):
        self.returncode = returncode
        self.stderr = list(stderr_lines or [])
        self.killed = False

    def wait(self):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True


def _setup_cut(monkeypatch, caps, procs, *, resolution=(1920, 1080), codec='h264'):
    """Configura cut_video com ffprobe/subprocess falsos."""
    monkeypatch.setattr(cutter, 'get_config', lambda: AppConfig())
    monkeypatch.setattr(cutter, 'get_cached_capabilities', lambda: caps)
    monkeypatch.setattr(cutter, 'get_ffmpeg_path', lambda: 'ffmpeg')
    monkeypatch.setattr(cutter, '_get_video_resolution', lambda _p: resolution)
    monkeypatch.setattr(cutter, '_get_video_codec', lambda _p: codec)
    monkeypatch.setattr(cutter, '_get_audio_codec', lambda _p: 'aac')
    monkeypatch.setattr(cutter, '_verify_output', lambda _p: True)
    monkeypatch.setattr(cutter.os, 'replace', lambda a, b: None)

    restantes = list(procs)

    # Guarda o comando executado em cada chamada.
    comandos = []

    def _popen(cmd, **kwargs):
        comandos.append(cmd)
        return restantes.pop(0)

    monkeypatch.setattr(cutter.subprocess, 'Popen', _popen)
    return comandos


def test_cut_video_faz_stream_copy_quando_resolucao_igual_e_h264(monkeypatch):
    comandos = _setup_cut(monkeypatch, _caps(), [FakeProc(0)])

    cutter.cut_video('in.mp4', 'out', 0, 10, 'horizontal')

    cmd = comandos[0]
    assert cmd[cmd.index('-c:v') + 1] == 'copy'


def test_cut_video_reencoda_quando_precisa_converter_para_vertical(monkeypatch):
    caps = _caps()
    comandos = _setup_cut(monkeypatch, caps, [FakeProc(0)])

    cutter.cut_video('in.mp4', 'out', 0, 10, 'vertical')

    cmd = comandos[0]
    assert cmd[cmd.index('-c:v') + 1] == 'libx264'
    assert 'crop=' in ' '.join(cmd)


def test_cut_video_tenta_proxima_estrategia_quando_a_primeira_falha(monkeypatch):
    caps = _caps(has_nvenc=True)
    comandos = _setup_cut(
        monkeypatch,
        caps,
        [FakeProc(1, ['falhou\n']), FakeProc(0)],
    )

    cutter.cut_video('in.mp4', 'out', 0, 10, 'vertical')

    assert len(comandos) == 2
    assert 'h264_nvenc' in comandos[0]
    assert 'libx264' in comandos[1]


def test_cut_video_levanta_erro_quando_todas_falham(monkeypatch):
    caps = _caps(has_nvenc=True)
    _setup_cut(
        monkeypatch,
        caps,
        [FakeProc(1, ['erro grave\n']), FakeProc(1, ['erro grave\n'])],
    )

    with pytest.raises(RuntimeError, match='erro grave'):
        cutter.cut_video('in.mp4', 'out', 0, 10, 'vertical')


def test_cut_video_respeita_cancelamento(monkeypatch):
    caps = _caps()
    _setup_cut(monkeypatch, caps, [FakeProc(0, ['frame=1\n'])])
    evento = cutter.threading.Event()
    evento.set()

    with pytest.raises(cutter.ProcessingCancelled):
        cutter.cut_video('in.mp4', 'out', 0, 10, 'vertical', cancel_event=evento)


def test_cut_video_reporta_progresso_final(monkeypatch):
    _setup_cut(monkeypatch, _caps(), [FakeProc(0)])
    eventos = []

    cutter.cut_video(
        'in.mp4',
        'out',
        0,
        10,
        'vertical',
        progress_callback=lambda p, m: eventos.append((p, m)),
    )

    assert eventos[-1] == (100, 'Corte concluído!')
