# -*- mode: python ; coding: utf-8 -*-
"""
Arquivo de especificação do PyInstaller para YouTube Clipper.

Gera uma pasta (``dist/YouTubeClipper``) com o executável, as dependências e o
ffmpeg/ffprobe embutidos. O instalador (``installer/ytclipper.iss``) empacota
essa pasta em um único ``Setup.exe``.

Modo *onedir* (em vez de ``--onefile``) evita extrair tudo para ``%TEMP%`` a
cada abertura, deixando a inicialização rápida mesmo com o ffmpeg embutido.
"""

import os
import re

block_cipher = None

# SPECPATH é fornecido pelo PyInstaller e aponta para o diretório deste arquivo
base_dir = globals().get('SPECPATH') or os.path.abspath('.')


def _app_version() -> str:
    init_path = os.path.join(base_dir, 'core', '__init__.py')
    try:
        with open(init_path, encoding='utf-8') as handle:
            match = re.search(r"__version__\s*=\s*'([^']+)'", handle.read())
    except OSError:
        match = None
    return match.group(1) if match else '0.0.0'


version = _app_version()
version_tuple = tuple(int(part) for part in re.findall(r'\d+', version))[:4]
version_tuple += (0,) * (4 - len(version_tuple))


def _write_version_info() -> str:
    """Gera o arquivo de metadados exibido nas Propriedades do .exe."""
    build_dir = os.path.join(base_dir, 'build')
    os.makedirs(build_dir, exist_ok=True)
    target = os.path.join(build_dir, 'version_info.txt')
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Ariel Laureano Rosas'),
            StringStruct('FileDescription', 'YouTube Clipper'),
            StringStruct('FileVersion', '{version}'),
            StringStruct('InternalName', 'YouTubeClipper'),
            StringStruct('OriginalFilename', 'YouTubeClipper.exe'),
            StringStruct('ProductName', 'YouTube Clipper'),
            StringStruct('ProductVersion', '{version}'),
          ],
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""
    with open(target, 'w', encoding='utf-8') as handle:
        handle.write(content)
    return target


# Incluir ffmpeg e ffprobe como dados (baixados no CI antes do build)
datas = []
for tool_name in ('ffmpeg.exe', 'ffprobe.exe'):
    tool_path = os.path.join(base_dir, 'assets', tool_name)
    if os.path.isfile(tool_path):
        datas.append((tool_path, 'assets'))

# Ícones disponíveis em tempo de execução (janela/barra de tarefas)
for icon_name in ('app.ico', 'app.png'):
    icon_path = os.path.join(base_dir, 'icons', icon_name)
    if os.path.isfile(icon_path):
        datas.append((icon_path, 'icons'))

exe_icon = os.path.join(base_dir, 'icons', 'app.ico')
if not os.path.isfile(exe_icon):
    exe_icon = None

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
    [],
    exclude_binaries=True,
    name='YouTubeClipper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
    version=_write_version_info(),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='YouTubeClipper',
)
