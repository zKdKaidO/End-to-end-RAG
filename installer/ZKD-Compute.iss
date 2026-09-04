; Per-user installer. Persistent data is intentionally outside {app}.
#define ProductName "ZKD Compute"
#define ProductVersion "0.1.0"
#define ProductPublisher "ZKD"
#define BuildRoot "..\build\windows\ZKD-Compute"

[Setup]
AppId={{C5B35A3E-5B03-4C4E-8408-3D6439C3B5A1}
AppName={#ProductName}
AppVersion={#ProductVersion}
AppPublisher={#ProductPublisher}
DefaultDirName={localappdata}\Programs\ZKD Compute
DefaultGroupName={#ProductName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\build\installer
OutputBaseFilename=ZKD-Compute-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayName={#ProductName}

[Files]
Source: "{#BuildRoot}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ZKD Compute"; ValueData: """{app}\ZKD-Compute.exe"" --background"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\zkd-compute"; ValueType: string; ValueName: ""; ValueData: "URL:ZKD Compute Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\zkd-compute"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\zkd-compute\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\ZKD-Compute.exe"" --pair-uri ""%1"""; Flags: uninsdeletekey

[Run]
Filename: "{app}\ZKD-Compute.exe"; Parameters: "--background"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Do not delete {localappdata}\ZKD\Compute. It contains user documents,
; indexes, DPAPI credentials, and models. A future explicit purge UI owns it.
