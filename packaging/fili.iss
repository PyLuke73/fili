; Installer di fili (Inno Setup 6). Si compila con scripts\build_installer.ps1, che passa /DAppVersion=...
; Installa SOLO file: nessun driver cambiato, nessun certificato aggiunto, né all'installazione né alla rimozione.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1B7C52-3A4E-4D8B-9E0A-5C2D71F0A3B9}
AppName=fili
AppVersion={#AppVersion}
AppPublisher=PyLuke73
AppPublisherURL=https://github.com/PyLuke73
DefaultDirName={autopf}\fili
DefaultGroupName=fili
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
SetupIconFile=..\assets\icons\fili.ico
UninstallDisplayIcon={app}\fili-gui.exe
InfoBeforeFile=INSTALLER_NOTICE.txt
OutputDir=..\dist\installer
OutputBaseFilename=fili-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=fili {#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoProductName=fili
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany=PyLuke73
VersionInfoDescription=fili setup
ChangesEnvironment=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "addpath"; Description: "Add fili to the PATH (use ""fili"" from any terminal) / Aggiungi fili al PATH"; GroupDescription: "Command line / Riga di comando:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\fili.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\fili-gui.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\wdi-bundle\wdi-simple.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\wdi-bundle\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\wdi-bundle\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\wdi-bundle\SHA256SUMS"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\wdi-bundle\LICENSES\*"; DestDir: "{app}\LICENSES"; Flags: ignoreversion
Source: "..\dist\wdi-bundle\THIRD_PARTY\*"; DestDir: "{app}\THIRD_PARTY"; Flags: ignoreversion
Source: "..\dist\wdi-bundle\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALLER_NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\fili"; Filename: "{app}\fili-gui.exe"; WorkingDir: "{app}"
Name: "{group}\fili - command line"; Filename: "{sys}\cmd.exe"; Parameters: "/k ""cd /d ""{app}"" && fili --version"""; WorkingDir: "{app}"
Name: "{group}\Licenses and notices"; Filename: "{app}\INSTALLER_NOTICE.txt"
Name: "{group}\Uninstall fili"; Filename: "{uninstallexe}"
Name: "{autodesktop}\fili"; Filename: "{app}\fili-gui.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\fili-gui.exe"; Description: "{cm:LaunchProgram,fili}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
const
  EnvKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

function PathContains(Dir: string): Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKLM, EnvKey, 'Path', Paths) then
    Paths := '';
  Result := Pos(';' + Lowercase(Dir) + ';', ';' + Lowercase(Paths) + ';') > 0;
end;

function PathKindWrite(Paths: string): Boolean;
begin
  { mantiene il tipo di valore: REG_EXPAND_SZ solo se il Path contiene già riferimenti %VAR% }
  if Pos('%', Paths) > 0 then
    Result := RegWriteExpandStringValue(HKLM, EnvKey, 'Path', Paths)
  else
    Result := RegWriteStringValue(HKLM, EnvKey, 'Path', Paths);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Paths: string;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addpath') and not PathContains(ExpandConstant('{app}')) then
  begin
    if not RegQueryStringValue(HKLM, EnvKey, 'Path', Paths) then
      Paths := '';
    if (Paths <> '') and (Paths[Length(Paths)] <> ';') then
      Paths := Paths + ';';
    PathKindWrite(Paths + ExpandConstant('{app}'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Paths, Dir: string;
  P: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Dir := ExpandConstant('{app}');
    if RegQueryStringValue(HKLM, EnvKey, 'Path', Paths) then
    begin
      P := Pos(';' + Lowercase(Dir) + ';', ';' + Lowercase(Paths) + ';');
      if P > 0 then
      begin
        Paths := ';' + Paths + ';';
        Delete(Paths, P, Length(Dir) + 1);
        if (Paths <> '') and (Paths[1] = ';') then Delete(Paths, 1, 1);
        if (Paths <> '') and (Paths[Length(Paths)] = ';') then Delete(Paths, Length(Paths), 1);
        PathKindWrite(Paths);
      end;
    end;
  end;
end;
