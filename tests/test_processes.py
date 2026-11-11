"""Testes do registro/cancelamento de subprocessos e limpeza."""

import os

import pytest

from core import processes


class FakeProc:
    """Subprocesso fake para os testes de registro/cancelamento."""

    def __init__(self, alive=True):
        self._alive = alive
        self.killed = False

    def poll(self):
        return None if self._alive else 0

    def kill(self):
        self.killed = True
        self._alive = False


@pytest.fixture(autouse=True)
def _limpar_registro():
    processes.kill_all()
    yield
    processes.kill_all()


def test_register_e_unregister_controlam_o_conjunto():
    proc = FakeProc()

    processes.register(proc)
    assert proc in processes._active_procs

    processes.unregister(proc)
    assert proc not in processes._active_procs


def test_unregister_de_processo_desconhecido_nao_falha():
    processes.unregister(FakeProc())  # não deve levantar


def test_kill_all_encerra_processos_ativos():
    ativo = FakeProc(alive=True)
    terminado = FakeProc(alive=False)
    processes.register(ativo)
    processes.register(terminado)

    processes.kill_all()

    assert ativo.killed is True
    assert terminado.killed is False
    assert processes._active_procs == set()


def test_kill_ffmpeg_by_dir_ignora_token_vazio(monkeypatch):
    chamado = []
    monkeypatch.setattr(processes.subprocess, 'run', lambda *a, **k: chamado.append(a))

    processes.kill_ffmpeg_by_dir_quoted('')

    assert chamado == []


def test_kill_ffmpeg_by_dir_escapa_aspas(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        processes.subprocess, 'run', lambda args, **k: chamadas.append(args)
    )

    processes.kill_ffmpeg_by_dir_quoted("video'1")

    assert len(chamadas) == 1
    comando = chamadas[0][-1]
    assert "video''1" in comando


def test_kill_ffmpeg_by_dir_ignora_erros_do_powershell(monkeypatch):
    def _falha(*args, **kwargs):
        raise OSError('powershell ausente')

    monkeypatch.setattr(processes.subprocess, 'run', _falha)

    processes.kill_ffmpeg_by_dir_quoted('token')  # não deve levantar


def test_cleanup_for_dir_ignora_caminho_invalido(monkeypatch):
    chamou = []
    monkeypatch.setattr(processes, 'kill_all', lambda: chamou.append('kill_all'))

    processes.cleanup_for_dir('')
    processes.cleanup_for_dir(os.path.join('nao', 'existe'))

    assert chamou == []


def test_cleanup_for_dir_encerra_e_remove(tmp_path, monkeypatch):
    pasta = tmp_path / 'processando'
    pasta.mkdir()
    (pasta / 'parcial.mp4').write_bytes(b'x')
    chamou = []

    monkeypatch.setattr(processes, 'kill_all', lambda: chamou.append('kill_all'))
    monkeypatch.setattr(
        processes,
        'kill_ffmpeg_by_dir_quoted',
        lambda token: chamou.append(('token', token)),
    )

    processes.cleanup_for_dir(str(pasta))

    assert chamou == ['kill_all', ('token', 'processando')]
    assert not pasta.exists()
