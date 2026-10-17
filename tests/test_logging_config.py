"""Testes da configuração de logging em arquivo."""

import logging
import os

from core import logging_config


def test_log_path_com_termina_em_app_log():
    assert logging_config.get_log_path().endswith('app.log')


def test_log_dir_respeita_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    esperado = os.path.join(str(tmp_path), 'YouTubeClipper', 'logs')
    assert logging_config.get_log_dir() == esperado


def test_setup_logging_cria_arquivo_e_nao_duplica_handlers(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

    # Estado limpo: a configuração é um global de módulo (idempotente).
    logging_config._configured = False
    logger = logging.getLogger('ytclipper')
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    path = logging_config.setup_logging()
    total_handlers = len(logger.handlers)

    # Segunda chamada não deve adicionar handlers nem mudar o caminho.
    path2 = logging_config.setup_logging()
    assert path2 == path
    assert len(logger.handlers) == total_handlers

    logger.info('mensagem de teste')
    for handler in logger.handlers:
        handler.flush()
    assert os.path.isfile(path)
    with open(path, encoding='utf-8') as handle:
        assert 'mensagem de teste' in handle.read()
