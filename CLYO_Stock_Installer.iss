#define MyAppName "CLYO Stock Atelier"
#define MyAppVersion "9.0.0"
#define MyAppPublisher "CLYO Systems"
#define MyAppExeName "CLYO_Stock.exe"

[Setup]
AppId={{D7B0E350-5C64-4CB9-9E8F-2B4E706D6D73}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CLYO Stock Atelier
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename=CLYO_Stock_Atelier_Setup_{#MyAppVersion}
SetupIconFile=assets\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\CLYO Stock Atelier"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{commonappdata}\CLYO Stock Atelier\NexVandal"; Permissions: users-modify; Flags: uninsneveruninstall

[Files]
Source: "dist\CLYO_Stock_PORTABLE\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait shellexec skipifdoesntexist

[UninstallRun]
; V8.2.9 : une désinstallation volontaire marque la prochaine installation comme nouvelle.
; Les données métier sont conservées, mais le choix de base sera redemandé.
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$p=Join-Path $env:ProgramData 'CLYO Stock Atelier'; New-Item -ItemType Directory -Force -Path $p | Out-Null; Set-Content -Path (Join-Path $p 'fresh_install_required.flag') -Value 'uninstalled' -Encoding UTF8"""; Flags: runhidden; RunOnceId: "CLYOStockMarkFreshInstall"

[UninstallDelete]
; V8.2.9 : supprimer uniquement les fichiers qui mémorisent le choix de base.
; Les données métier dans ProgramData ne sont volontairement pas supprimées.
; Elles restent en place pour éviter toute perte de référentiel, Excel, SQLite, documents ou historique.
Type: files; Name: "{commonappdata}\CLYO Stock Atelier\nexvandal_active_data.json"
Type: files; Name: "{commonappdata}\CLYO Stock Atelier\nexvandal_active_data_preserved_before_update.json"
Type: files; Name: "{commonappdata}\CLYO Stock Atelier\sql_database_config.json"
Type: files; Name: "{commonappdata}\CLYO Stock Atelier\NexVandal\setup_choice.json"
Type: files; Name: "{localappdata}\CLYO Stock Atelier\nexvandal_active_data.json"
Type: files; Name: "{localappdata}\CLYO Stock Atelier\nexvandal_active_data_preserved_before_update.json"
Type: files; Name: "{localappdata}\CLYO Stock Atelier\sql_database_config.json"
Type: files; Name: "{userappdata}\CLYO Stock Atelier\nexvandal_active_data.json"
Type: files; Name: "{userappdata}\CLYO Stock Atelier\nexvandal_active_data_preserved_before_update.json"
Type: files; Name: "{userappdata}\CLYO Stock Atelier\sql_database_config.json"
