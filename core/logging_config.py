"""
Configuração de logging do YouTube Clipper.

Grava um arquivo de log rotativo para diagnóstico. Por padrão o arquivo fica em
%LOCALAPPDATA%\\YouTubeClipper\\logs\\app.log no Windows, com fallback para
~/.youtube-clipper/logs/app.log quando LOCALAPPDATA não existir.

O logging é idempotente: chamar setup_logging() mais de uma vez não duplica
handlers (importante para os workers e para o modo frozen do PyInstaller).
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_LOGGER_NAME = 'ytclipper'
_configured = False

_MAX_BYTES = 1_000_000  # ~1 MB por arquivo
_BACKUP_COUNT = 3


def get_log_dir() -> str:
    """Retorna o diretório onde os logs são gravados."""
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(base, 'YouTubeClipper', 'logs')


def get_log_path() -> str:
    """Retorna o caminho completo do arquivo de log."""
    return os.path.join(get_log_dir(), 'app.log')


def setup_logging(level: int = logging.INFO) -> str:
    """
    Configura o logger raiz da aplicação (arquivo rotativo + stderr).

    Retorna o caminho do arquivo de log. É seguro chamar várias vezes.
    """
    global _configured

    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return get_log_path()

    logger.setLevel(level)
    logger.propagate = False
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    try:
        os.makedirs(get_log_dir(), exist_ok=True)
        file_handler = RotatingFileHandler(
            get_log_path(),
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding='utf-8',
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        # Sem permissão/ espaço para gravar o arquivo: segue apenas com stderr.
        pass

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    logger.addHandler(console)

    _configured = True
    logger.info('Logging iniciado. Arquivo: %s', get_log_path())
    return get_log_path()


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Retorna um logger que herda os handlers configurados em setup_logging()."""
    return logging.getLogger(name)
