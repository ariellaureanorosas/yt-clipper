@echo off
setlocal EnableExtensions
chcp 65001 >nul

rem ============================================================
rem  Instalador do YouTube Clipper
rem  Instala o Python (se preciso), baixa dependencias, compila
rem  o app e cria o atalho na area de trabalho. Pode demorar.
rem ============================================================

title Instalador do YouTube Clipper

cd /d "%~dp0"

echo.
echo  ==============================================
echo    YouTube Clipper - Instalador
echo  ==============================================
echo.

rem ---------- 1. Localizar Python ----------
call :locate_python
if defined PYTHON_CMD goto :python_pronto

echo  Python nao foi encontrado no sistema.
echo  Vou instala-lo automaticamente agora (baixa ~25 MB).
echo.
echo    Tentando instalar pelo Windows Store (winget)...
winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements >nul 2>nul
call :locate_python
if defined PYTHON_CMD (
    echo    Python instalado pelo winget!
    goto :python_pronto
)

echo    Winget nao funcionou. Baixando instalador oficial...
set "PY_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
set "PY_FILE=%TEMP%\python-installer-yc.exe"
curl -L --fail --silent --show-error -o "%PY_FILE%" "%PY_URL%" >nul 2>nul
if errorlevel 1 (
    echo    Falha ao baixar o Python pelo site oficial.
    goto :python_falhou
)
echo    Instalando Python (aguarde, leva alguns minutos)...
"%PY_FILE%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
call :locate_python
if defined PYTHON_CMD (
    echo    Python instalado com sucesso!
    goto :python_pronto
)

:python_falhou
echo.
echo  [ERRO] Nao foi possivel instalar o Python automaticamente.
echo  Instale o Python 3.11 ou mais recente de forma manual:
echo  https://www.python.org/downloads/
echo  IMPORTANTE: na instalacao marque a opcao "Add python.exe to PATH".
echo  Depois rode este instalador novamente.
goto :fim

:python_pronto
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

goto :fim

:locate_python
rem Detecta o Python em: launcher (py) -> PATH (python) -> instalacao de
rem usuario (LocalAppData), usada pelo winget e pelo instalador oficial.
set "PYTHON_CMD="
py --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    exit /b 0
)
python --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)
if defined LOCALAPPDATA (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" (
            set "PYTHON_CMD=%%D\python.exe"
            exit /b 0
        )
    )
)
exit /b 1

:fim
echo.
pause
endlocal