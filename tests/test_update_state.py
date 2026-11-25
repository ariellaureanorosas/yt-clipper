"""Testes do estado persistente da atualização."""

import json
import time

import pytest

from core import update_state


@pytest.fixture(autouse=True)
def _tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(update_state, 'state_dir', lambda: tmp_path)


def test_pending_roundtrip():
    update_state.write_pending({'installer': 'x.exe', 'target_version': '1.2.0'})

    assert update_state.read_pending()['target_version'] == '1.2.0'
    update_state.clear_pending()
    assert update_state.read_pending() is None


def test_escrita_atomica_nao_deixa_tmp(tmp_path):
    update_state.write_pending({'a': 1})

    assert not list(tmp_path.glob('*.tmp'))
    assert json.loads((tmp_path / 'pending.json').read_text(encoding='utf-8')) == {
        'a': 1
    }


def test_started_roundtrip():
    update_state.write_started({'token': 'abc', 'pid': 10})

    assert update_state.read_started()['token'] == 'abc'
    update_state.clear_started()
    assert update_state.read_started() is None


def test_resultado_consumido_uma_vez():
    update_state.write_result({'status': 'success'})

    assert update_state.consume_result()['status'] == 'success'
    assert update_state.consume_result() is None


def test_supressao_de_versao_que_falhou():
    update_state.record_failed_version('1.2.0', {'step': 'install'})

    assert update_state.is_version_suppressed('1.2.0')
    assert not update_state.is_version_suppressed('1.3.0')


def test_supressao_expira():
    update_state.record_failed_version('1.2.0')
    data = json.loads(
        (update_state.state_dir() / 'failed-version.json').read_text(encoding='utf-8')
    )
    data['failed_at'] = time.time() - 25 * 3600
    (update_state.state_dir() / 'failed-version.json').write_text(
        json.dumps(data), encoding='utf-8'
    )

    assert not update_state.is_version_suppressed('1.2.0')


def test_json_corrompido_nao_quebra():
    (update_state.state_dir() / 'last-result.json').write_text('{', encoding='utf-8')

    assert update_state.read_result() is None
    assert update_state.consume_result() is None
