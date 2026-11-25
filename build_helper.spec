# -*- mode: python ; coding: utf-8 -*-
"""
Especificação do PyInstaller para o supervisor de atualização.

Gera ``dist/YouTubeClipperUpdater.exe`` (arquivo único, sem console). O
instalador copia esse executável para
``%LOCALAPPDATA%\\YouTubeClipper\\updater``, fora da pasta do aplicativo, para
que ele continue vivo enquanto o Setup substitui os arquivos.
"""

import os

base_dir = globals().get('SPECPATH') or os.path.abspath('.')

exe_icon = os.path.join(base_dir, 'icons', 'app.ico')
if not os.path.isfile(exe_icon):
    exe_icon = None

a = Analysis(
    ['tools/update_helper.py'],
    pathex=[base_dir],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='YouTubeClipperUpdater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)
