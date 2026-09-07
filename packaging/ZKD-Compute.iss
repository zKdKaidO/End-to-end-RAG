; Per-user, on-demand ZKD Compute installer. Requires Inno Setup 6.
#define AppName "ZKD Compute"
#define AppVersion "1.0.0"
#define AppPublisher "ZKD"
#define AppExeName "ZKD-Compute.exe"
[Setup]
AppId={{C17E5B98-12E4-49BB-94DC-09E4B0D5B843}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\ZKD Compute
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\build\installer
OutputBaseFilename=ZKD-Compute-Setup
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\{#AppExeName}
[Files]
Source: "..\build\windows\ZKD-Compute\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\ZKD Compute"; Filename: "{app}\{#AppExeName}"
[Registry]
Root: HKCU; Subkey: "Software\Classes\zkd"; ValueType: string; ValueName: ""; ValueData: "URL:ZKD Compute Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\zkd"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\zkd\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Flags: uninsdeletekey
[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch ZKD Compute now"; Flags: nowait postinstall skipifsilent
; No HKCU Run key, no scheduled task, and no user data deletion are present.
