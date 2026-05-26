[Setup]
AppId={{8E2D8C2A-8F8D-4A2F-8A2F-8D2F8A2F8D2F}}
AppName=School Management System
AppVersion=1.0
AppPublisher=JSLY
DefaultDirName={pf}\SchoolManagementSystem
DefaultGroupName=School Management System
AllowNoIcons=yes
OutputDir=installer
OutputBaseFilename=SchoolManagementSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\SchoolManagement.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create desktop icon"; GroupDescription: "Additional icons:"
Name: "startmenuicon"; Description: "Create start menu icon"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\SchoolManagement.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "templates\*.html"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs
Source: "static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\School Management System"; Filename: "{app}\SchoolManagement.exe"
Name: "{group}\Uninstall School Management"; Filename: "{uninstallexe}"
Name: "{autodesktop}\School Management System"; Filename: "{app}\SchoolManagement.exe"; Tasks: desktopicon
Name: "{userstartmenu}\School Management System"; Filename: "{app}\SchoolManagement.exe"; Tasks: startmenuicon

[Run]
Filename: "{app}\SchoolManagement.exe"; Description: "Launch School Management System"; Flags: nowait postinstall skipifsilent