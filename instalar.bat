@echo off
setlocal EnableExtensions
chcp 65001 >nul

rem ============================================================
rem  Instalador do YouTube Clipper
rem  Baixa dependencias, compila o app e cria o atalho na
rem  area de trabalho. Pode demorar alguns minutos.
rem ============================================================

title Instalador do YouTube Clipper

cd /d "%~dp0"

echo.
echo  ==============================================
echo    YouTube Clipper - Instalador
echo  ==============================================
echo.

rem ---------- 1. Localizar Python ----------
set "PYTHON_CMD="
py --version >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
    python --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo  [ERRO] Python nao foi encontrado no sistema.
    echo  Instale o Python 3.11 ou mais recente de:
    echo  https://www.python.org/downloads/
    echo  IMPORTANTE: marque a opcao "Add python.exe to PATH"
    echo  na tela de instalacao.
    goto :fim
)
echo  Python encontrado.
echo.

rem ---------- 2. Instalar dependencias ----------
echo  Instalando dependencias (primeira vez pode demorar)...
"%PYTHON_CMD%" -m pip install --disable-pip-version-check -r requirements.txt >nul 2>nul
if errorlevel 1 (
    echo  [ERRO] Falha ao instalar as dependencias.
    goto :fim
)
echo  Dependencias instaladas.

echo  Verificando PyInstaller...
"%PYTHON_CMD%" -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo  PyInstaller nao instalado. Instalando...
    "%PYTHON_CMD%" -m pip install --disable-pip-version-check pyinstaller >nul 2>nul
    if errorlevel 1 (
        echo  [ERRO] Falha ao instalar o PyInstaller.
        goto :fim
    )
)
echo  PyInstaller pronto.
echo.

rem ---------- 3. Compilar o executavel ----------
echo  Compilando o executavel (pode levar alguns minutos)...
"%PYTHON_CMD%" -m PyInstaller build.spec --noconfirm --clean >nul 2>nul
if errorlevel 1 (
    echo  [ERRO] Falha ao compilar o aplicativo.
    goto :fim
)
if not exist "dist\YouTubeClipper.exe" (
    echo  [ERRO] Executavel nao foi gerado em dist\.
    goto :fim
)
echo  Compilacao concluida.
echo.

rem ---------- 4. Copiar para a area de trabalho ----------
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%D"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"
copy /y "dist\YouTubeClipper.exe" "%DESKTOP%\YouTubeClipper.exe" >nul 2>nul
if errorlevel 1 (
    echo  [ERRO] Falha ao copiar o executavel para a area de trabalho.
    goto :fim
)
echo  Executavel copiado para a area de trabalho.

rem ---------- 5. Criar atalho ----------
powershell -NoProfile -Command "& { $Desk=[Environment]::GetFolderPath('Desktop'); $ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut(($Desk+'\YouTube Clipper.lnk')); $s.TargetPath=$Desk+'\YouTubeClipper.exe'; $s.WorkingDirectory=$Desk; $s.IconLocation=$Desk+'\YouTubeClipper.exe,0'; $s.Description='YouTube Clipper'; $s.Save() }"
if errorlevel 1 (
    echo  [AVISO] Nao foi possivel criar o atalho. O executavel ja esta na area de trabalho.
) else (
    echo  Atalho "YouTube Clipper" criado na area de trabalho.
)
echo.

echo  ==============================================
echo    Pronto! Abra o atalho "YouTube Clipper"
echo    na area de trabalho para usar o app.
echo  ==============================================
echo.

:fim
echo.
pause
endlocal