# -*- mode: python ; coding: utf-8 -*-
"""
Arquivo de especificação do PyInstaller para YouTube Clipper.
Gera um executável único (.exe) incluindo ffmpeg e ffprobe.
"""

import os
import sys

block_cipher = None

# SPECPATH é fornecido pelo PyInstaller e aponta para o diretório deste arquivo
base_dir = globals().get('SPECPATH') or os.path.abspath('.')

# Incluir ffmpeg e ffprobe como dados
datas = []
ffmpeg_path = os.path.join(base_dir, 'assets', 'ffmpeg.exe')
ffprobe_path = os.path.join(base_dir, 'assets', 'ffprobe.exe')

if os.path.isfile(ffmpeg_path):
    datas.append((ffmpeg_path, 'assets'))
if os.path.isfile(ffprobe_path):
    datas.append((ffprobe_path, 'assets'))

# Ícone do app
icon_path = os.path.join(base_dir, 'icons', 'app.ico')
if not os.path.isfile(icon_path):
    icon_path = None

a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'customtkinter',
        'PIL',
        'yt_dlp',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YouTubeClipper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
