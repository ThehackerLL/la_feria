; Instalador de Sistema POS (La Feria) - Inno Setup 6
; Antes de compilar, ejecuta construir.bat (crea dist\SistemaPOS).
; Resultado: instalador\Instalar_LaFeria.exe

#define NombrePrograma "Sistema POS"
#define Version "1.0"
#define Exe "SistemaPOS.exe"

[Setup]
AppId={{7C1D2E4A-5B3F-4E8A-9A61-1A2F3E4D5C6B}
AppName={#NombrePrograma}
AppVersion={#Version}
DefaultDirName={autopf}\{#NombrePrograma}
DefaultGroupName={#NombrePrograma}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir=instalador
OutputBaseFilename=Instalar_LaFeria
SetupIconFile=recursos\icono.ico
UninstallDisplayIcon={app}\{#Exe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\SistemaPOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Datos del negocio: fuera del programa, con permiso de escritura para todos.
; Al desinstalar NO se borran (uninsneveruninstall).
Name: "C:\LaFeria"; Permissions: users-modify; Flags: uninsneveruninstall

[Icons]
Name: "{autodesktop}\{#NombrePrograma}"; Filename: "{app}\{#Exe}"; IconFilename: "{app}\{#Exe}"; Tasks: escritorio
Name: "{autoprograms}\{#NombrePrograma}"; Filename: "{app}\{#Exe}"; IconFilename: "{app}\{#Exe}"

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir {#NombrePrograma} ahora"; Flags: nowait postinstall skipifsilent
