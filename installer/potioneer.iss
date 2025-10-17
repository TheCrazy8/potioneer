; Inno Setup script to build PotioneerInstaller.exe
; Requires: Inno Setup 6 (iscc)

#define MyAppName "Potioneer"
#define MyAppPublisher "Your Company or Name"
#define MyAppURL "https://github.com/TheCrazy8/potioneer"
#define MyAppExeName "Potioneer.exe" ; Built by PyInstaller --name=Potioneer
#define MyAppVersion GetEnv('APP_VERSION')
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{73A331F9-76C8-4D3E-832D-8F3B3B6D22D6}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputBaseFilename=PotioneerInstaller
OutputDir=out
WizardStyle=modern
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
DisableWelcomePage=no
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
CloseApplications=yes
; Uncomment and set if you have an icon for the installer itself
; SetupIconFile=icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Dirs]
; Create a shared data folder for assets writable by all users (optional)
Name: "{commonappdata}\Potioneer"; Flags: uninsalwaysuninstall
Name: "{commonappdata}\Potioneer\plugins"; Flags: uninsalwaysuninstall

[Files]
; Install the application binaries built by PyInstaller (adjust Source if folder name differs)
Source: "..\\dist\\Potioneer\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Optionally include default assets/configs into ProgramData (shared)
; Source: "assets\*"; DestDir: "{commonappdata}\Potioneer"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Optionally remove shared data on uninstall; we prompt the user at uninstall time.
Type: filesandordirs; Name: "{commonappdata}\Potioneer"; Check: ShouldRemoveUserData
Type: filesandordirs; Name: "{localappdata}\Potioneer"; Check: ShouldRemoveUserData
Type: filesandordirs; Name: "{userappdata}\Potioneer"; Check: ShouldRemoveUserData

[Code]
var
  RemoveUserData: Boolean;

function ShouldRemoveUserData(): Boolean;
begin
  Result := RemoveUserData;
end;

function InitializeUninstall(): Boolean;
begin
  RemoveUserData := False;
  if DirExists(ExpandConstant('{commonappdata}\\Potioneer')) or
     DirExists(ExpandConstant('{localappdata}\\Potioneer')) or
     DirExists(ExpandConstant('{userappdata}\\Potioneer')) then
  begin
    if MsgBox('Do you want to remove all Potioneer data (plugins, config, logs) from this machine?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      RemoveUserData := True;
    end;
  end;
  Result := True;  // Continue with uninstall
end;

// Notes:
// - Per-user data is best created by the application itself under {localappdata}\Potioneer
//   at first run. Installing to {userappdata} during an elevated install can target the admin
//   profile instead of the eventual end-user.
// - If your PyInstaller output folder is named differently, change Source and MyAppExeName above.
