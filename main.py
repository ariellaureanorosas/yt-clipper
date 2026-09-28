"""
YouTube Clipper - Ponto de entrada.
Aplicativo desktop para download e corte de vídeos do YouTube.
"""

import sys
import os

# Garantir que o diretório do projeto está no path
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)


def main():
    from ui.app_window import AppWindow

    app = AppWindow()
    app.mainloop()


if __name__ == '__main__':
    main()
