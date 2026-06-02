; Turkify — Inno Setup kurulum betigi (Windows installer)
; On kosul: once build_engine.ps1 + build_app.ps1 calistirilmis olmali
;   (dist\Turkify\ icinde Turkify.exe + turkify-engine\ hazir olmali).
; Derleme: Inno Setup kurulu olmali (https://jrsoftware.org/isdl.php), sonra:
;   iscc windows\packaging\turkify.iss
; Cikti: windows\packaging\dist\TurkifySetup-<surum>.exe

#define AppName "Turkify"
#define AppVersion "1.3.0"
#define AppPublisher "Turkify"
#define AppExeName "Turkify.exe"

[Setup]
AppId={{B7A1F3C2-8E4D-4A6B-9C1E-TURKIFY000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=TurkifySetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Self-contained .NET + gomulu motor: 64-bit
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaustu simgesi olustur"; GroupDescription: "Ek simgeler:"; Flags: unchecked
Name: "startup"; Description: "Windows ile baslat"; GroupDescription: "Baslangic:"; Flags: unchecked

[Files]
; build_app.ps1 ciktisinin tamami (Turkify.exe + bagimliliklar + turkify-engine\)
Source: "dist\Turkify\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; "Windows ile baslat" gorevi secildiyse oturum acilisinda tray'de baslat
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "Turkify"; ValueData: """{app}\{#AppExeName}"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Turkify'i simdi baslat"; Flags: nowait postinstall skipifsilent
