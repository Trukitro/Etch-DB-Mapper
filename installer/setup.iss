; Inno Setup script for Etch-DB-Mapper
; Build with: tools\build_windows.ps1 -Installer
;   (o a mano: ISCC.exe /DMyAppVersion=2.3.0 installer\setup.iss)

#define MyAppName "Etch-DB-Mapper"
#ifndef MyAppVersion
  #define MyAppVersion "2.3.0"
#endif
#define MyAppPublisher "Etch"
#define MyAppURL "https://github.com/Trukitro/Etch-DB-Mapper"
#define MyAppExeName "Etch-DB-Mapper.exe"

[Setup]
AppId={{FC4225AF-51D7-4432-89BC-B1B7885CDD5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=Etch-DB-Mapper-Setup-v{#MyAppVersion}
SetupIconFile=..\favicon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// La interfaz usa Microsoft Edge WebView2 (viene con Windows 11 y Windows 10 actualizado).
function WebView2Installed(): Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(HKLM32, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
  if Result then
    Result := (Version <> '') and (Version <> '0.0.0.0');
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if (not WizardSilent) and (not WebView2Installed()) then
    Result := MsgBox(
      'Etch-DB-Mapper necesita el runtime "Microsoft Edge WebView2", que no se detecto en este equipo.' + #13#10 +
      'Puedes descargarlo desde https://developer.microsoft.com/microsoft-edge/webview2/' + #13#10 +
      '(Etch-DB-Mapper no abrira hasta que este instalado).' + #13#10#13#10 +
      'Quieres continuar con la instalacion de todos modos?',
      mbConfirmation, MB_YESNO) = IDYES;
end;
