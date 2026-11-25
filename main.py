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


def _set_app_user_model_id() -> None:
    """Agrupa janela, barra de tarefas e atalhos sob o mesmo AppUserModelID.

    Sem isso o Windows usa o ícone/identidade do processo hospedeiro e o ícone
    do aplicativo não aparece corretamente na barra de tarefas.
    """
    if sys.platform != 'win32':
        return
    try:
        import ctypes

        from core import APP_ID

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:  # nunca impede a abertura do aplicativo
        pass


def main():
    # Modo de verificação usado pelo supervisor de atualização: grava a versão
    # embutida neste executável e sai, sem abrir a interface.
    if '--version-file' in sys.argv:
        from pathlib import Path

        from core import __version__

        index = sys.argv.index('--version-file')
        try:
            target = sys.argv[index + 1]
        except IndexError:
            print('uso: YouTubeClipper.exe --version-file <caminho>')
            return 2
        Path(target).write_text(__version__, encoding='utf-8')
        return 0

    from core.bootstrap import bootstrap_config
    from core.logging_config import get_logger, setup_logging
    from ui.app_window import AppWindow

    _set_app_user_model_id()

    log_path = setup_logging()
    logger = get_logger(__name__)
    logger.info('Aplicativo iniciado. Log em: %s', log_path)

    # Detecta o hardware e aplica o perfil (encoder/download) antes de abrir a UI.
    bootstrap_config()

    app = AppWindow()
    app.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
