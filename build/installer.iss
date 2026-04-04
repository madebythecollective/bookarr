; Bookarr Windows Installer — Inno Setup Script
; Builds a standard Windows installer from the PyInstaller output.
;
; Prerequisites:
;   1. Run build-windows.bat first to create dist\Bookarr\
;   2. Install Inno Setup 6: https://jrsoftware.org/isinfo.php
;   3. Run this with ISCC.exe or open in Inno Setup Compiler

#define MyAppName "Bookarr"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "John Howrey"
#define MyAppURL "https://github.com/johnhowrey/bookarr-public"
#define MyAppExeName "Bookarr.exe"

[Setup]
AppId={{B00KARR-1234-5678-9ABC-DEF012345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output installer to dist/
OutputDir=..\dist
OutputBaseFilename=Bookarr-{#MyAppVersion}-windows-setup
SetupIconFile=..\static\favicon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
; Minimum Windows 10
MinVersion=10.0
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE
InfoBeforeFile=..\DISCLAIMER.md

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start Bookarr automatically when Windows starts"; GroupDescription: "Startup:"
Name: "firewallrule"; Description: "Add Windows Firewall rule for Bookarr (port 8585)"; GroupDescription: "Network:"

[Files]
; Copy the entire PyInstaller output directory
Source: "..\dist\Bookarr\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; Open browser after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
; Add firewall rule
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Bookarr"" dir=in action=allow protocol=TCP localport=8585"; Flags: runhidden; Tasks: firewallrule

[UninstallRun]
; Remove firewall rule on uninstall
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Bookarr"""; Flags: runhidden

[UninstallDelete]
; Clean up data directory (optional — user data in AppData)
; Uncomment to remove user data on uninstall:
; Type: filesandordirs; Name: "{userappdata}\Bookarr"

[Code]
// Kill Bookarr if running before install/uninstall
procedure TaskKill(FileName: String);
var
  ResultCode: Integer;
begin
  Exec('taskkill', '/f /im ' + FileName, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  TaskKill('Bookarr.exe');
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    TaskKill('Bookarr.exe');
end;
