"""
YouTube Clipper - Ponto de entrada.
Aplicativo desktop para download e corte de vídeos do YouTube.
"""

import os
import sys

# Garantir que o diretório do projeto está no path
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)


def main():
    from core.bootstrap import bootstrap_config
    from core.logging_config import get_logger, setup_logging
    from ui.app_window import AppWindow

    log_path = setup_logging()
    logger = get_logger(__name__)
    logger.info('Aplicativo iniciado. Log em: %s', log_path)

    # Detecta o hardware e aplica o perfil (encoder/download) antes de abrir a UI.
    bootstrap_config()

    app = AppWindow()
    app.mainloop()


if __name__ == '__main__':
    main()
