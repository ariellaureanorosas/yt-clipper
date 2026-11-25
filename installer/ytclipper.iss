; Instalador do YouTube Clipper (Inno Setup 6).
;
; Uso:
;   ISCC.exe /DAppVersion=1.3.0 installer\ytclipper.iss
;
; Gera dist\installer\YouTubeClipper-Setup-<versão>.exe a partir da pasta
; dist\YouTubeClipper (PyInstaller em modo onedir). O ffmpeg/ffprobe já vão
; embutidos, então o aplicativo não baixa nada na primeira execução.

#define AppName "YouTube Clipper"
#define AppExeName "YouTubeClipper.exe"
#define AppPublisher "Ariel Laureano Rosas"
#define AppURL "https://github.com/ariellaureanorosas/yt-clipper"
#define AppId "{{52F44799-F8A4-431E-B57F-A5579594F74F}"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\YouTubeClipper
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=YouTubeClipper-Setup-{#AppVersion}
SetupIconFile=..\icons\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousTasks=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\YouTubeClipper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Garante upgrade limpo: remove a instalação anterior antes de copiar.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\{#AppExeName}"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; AppUserModelID: "ArielRosas.YouTubeClipper"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; AppUserModelID: "ArielRosas.YouTubeClipper"

[Run]
; Interativo: abre o app na tela final (checkbox "Executar YouTube Clipper").
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Silencioso (atualização automática): reabre o app assim que a instalação termina.
Filename: "{app}\{#AppExeName}"; Flags: nowait; Check: WizardSilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
