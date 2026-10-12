; PDF Viewer 설치 파일 스크립트 (Inno Setup)
; 빌드: ISCC.exe installer.iss

#define MyAppName "PDF Viewer"
#ifndef MyAppVersion
  #define MyAppVersion "1.2.0"
#endif
#define MyAppPublisher "류호준"
#define MyAppExeName "PDFViewer.exe"

[Setup]
AppId={{B4E7C2A9-6F1D-4A83-9C5E-2D7B8F0A1E63}
AppName={#MyAppName}
AppVerName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ChangesAssociations=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=none
OutputDir=installer
OutputBaseFilename=PDFViewer-Setup-{#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "pdfassoc"; Description: "PDF 파일의 기본 프로그램으로 설정"; GroupDescription: "파일 연결:"; Flags: checkedonce

[Files]
Source: "dist\PDFViewer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; ProgID (연결 프로그램 정의)
Root: HKCU; Subkey: "Software\Classes\PDFViewer.pdf"; ValueType: string; ValueName: ""; ValueData: "PDF 문서"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\PDFViewer.pdf\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"",0"
Root: HKCU; Subkey: "Software\Classes\PDFViewer.pdf\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
; 실행 파일 단위 등록 (기본 앱/연결 프로그램 목록의 이름·아이콘)
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "PDF Viewer"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}"; ValueType: string; ValueName: "ApplicationCompany"; ValueData: "류호준"
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"",0"
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""
; '연결 프로그램' 목록에 추가
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFViewer.pdf"; ValueData: ""; Flags: uninsdeletevalue
; Windows '기본 앱' 목록에 표시
Root: HKCU; Subkey: "Software\PDFViewer\Capabilities"; ValueType: string; ValueName: ""; ValueData: "PDF Viewer"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\PDFViewer\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "PDF Viewer"
Root: HKCU; Subkey: "Software\PDFViewer\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "가벼운 PDF 뷰어"
Root: HKCU; Subkey: "Software\PDFViewer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "PDFViewer.pdf"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "PDFViewer"; ValueData: "Software\PDFViewer\Capabilities"; Flags: uninsdeletevalue

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure SHChangeNotify(wEventId: Integer; uFlags: Cardinal; dwItem1, dwItem2: Integer);
  external 'SHChangeNotify@shell32.dll stdcall';

procedure SetPdfDefault();
begin
  { 기존 사용자 선택(UserChoice)을 지워야 기본값 변경이 반영됨 }
  RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER,
    'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice');
  RegWriteStringValue(HKEY_CURRENT_USER, 'Software\Classes\.pdf', '', 'PDFViewer.pdf');
  SHChangeNotify($08000000, 0, 0, 0);
end;

procedure RemovePdfDefault();
var
  Cur: String;
begin
  { .pdf 기본값이 이 프로그램이면 제거 }
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Classes\.pdf', '', Cur) then
    if CompareText(Cur, 'PDFViewer.pdf') = 0 then
      RegDeleteValue(HKEY_CURRENT_USER, 'Software\Classes\.pdf', '');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if WizardIsTaskSelected('pdfassoc') then
      SetPdfDefault();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    RemovePdfDefault();
    SHChangeNotify($08000000, 0, 0, 0);
  end;
end;
