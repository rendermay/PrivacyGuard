; SecureRedact Windows 安装程序配置
; Inno Setup 脚本
; 版本来源: 命令行 /DMyAppVersion 优先（由 3_build_with_setup.bat / 4_create_installer_only.bat
; 从项目根 version.txt 读出后传入），缺失时回落到下面的默认值。
; ⚠️ 默认值必须与项目根 version.txt 保持一致，否则安装包文件名 / AppVersion 会与
;    EXE 版本资源(version_info.txt)、应用内显示的版本号对不上。
;    当前 version.txt = 1.1.13

#define MyAppName "SecureRedact"
#define MyAppNameFull "SecureRedact 信息脱敏助手"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.13"
#endif
#define MyAppPublisher "SecureRedact Team"
#define MyAppURL "https://github.com/secureredact/secureredact"
#define MyAppExeName "SecureRedact.exe"

[Setup]
; AppId must be unique for each application
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppNameFull}
AppVerName={#MyAppNameFull} {#MyAppVersion}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=..\..\..\releases\windows
OutputBaseFilename=SecureRedact-{#MyAppVersion}-Setup
SetupIconFile=..\..\..\assets\logo\windows\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; GPL-3.0 要求分发时附带许可证副本：安装向导直接展示许可证全文。
; 该文件是项目根 LICENSE 的逐字节副本（GPL 原文不可改动），
; 随包分发的副本见下方 [Files] 段（源为项目根 LICENSE）。
LicenseFile=LICENSE.txt
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Code]
// Check if Visual C++ Redistributable is installed (with full DLL check)
function IsVCRedistInstalled(): Boolean;
var
  Version: String;
  HasVCR140, HasVCR140_1, HasMSVCP140: Boolean;
begin
  // Check for VC++ 2015-2022 x64 in registry
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Version', Version) then
  begin
    Result := True;
    Exit;
  end
  else if RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Version', Version) then
  begin
    Result := True;
    Exit;
  end;

  // Also check if required DLLs exist in System32
  HasVCR140 := FileExists('C:\Windows\System32\vcruntime140.dll');
  HasVCR140_1 := FileExists('C:\Windows\System32\vcruntime140_1.dll');
  HasMSVCP140 := FileExists('C:\Windows\System32\msvcp140.dll');

  // All three DLLs are required for onnxruntime
  if HasVCR140 and HasVCR140_1 and HasMSVCP140 then
  begin
    Result := True;
  end
  else
  begin
    Result := False;
  end;
end;

// Get missing DLL info for better error message
function GetMissingDLLInfo(): String;
begin
  Result := '';
  if not FileExists('C:\Windows\System32\vcruntime140.dll') then
    Result := Result + '  - vcruntime140.dll' + #13#10;
  if not FileExists('C:\Windows\System32\vcruntime140_1.dll') then
    Result := Result + '  - vcruntime140_1.dll (CRITICAL for OCR)' + #13#10;
  if not FileExists('C:\Windows\System32\msvcp140.dll') then
    Result := Result + '  - msvcp140.dll' + #13#10;
end;

function InitializeSetup(): Boolean;
var
  MissingDLLs: String;
begin
  if not IsVCRedistInstalled() then
  begin
    MissingDLLs := GetMissingDLLInfo();

    MsgBox('Visual C++ Redistributable is required but not detected.' + #13#10 + #13#10 +
           'Missing files:' + #13#10 + MissingDLLs + #13#10 +
           'Please download and install the latest VC++ Redistributable:' + #13#10 +
           'https://aka.ms/vs/17/release/vc_redist.x64.exe' + #13#10 + #13#10 +
           'Note: vcruntime140_1.dll is REQUIRED for OCR functionality.' + #13#10 +
           'After installation, please run this setup again.', mbInformation, MB_OK);

    // Continue anyway - DLLs might be bundled or user might install later
    Result := True;
  end
  else
  begin
    Result := True;
  end;
end;

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
Source: "..\..\..\dist\SecureRedact\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\..\dist\SecureRedact\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Launcher wrapper for DLL checking
Source: "..\scripts\launcher_wrapper.bat"; DestDir: "{app}"; Flags: ignoreversion
; GPL-3.0 分发要求：安装目录必须包含许可证全文。
; 源取项目根 LICENSE（唯一权威副本），落地名统一为 LICENSE.txt。
Source: "..\..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
; 注意: 不要在任何共享系统文件上使用 "Flags: ignoreversion"

[Icons]
; Use launcher wrapper to check DLLs before starting
Name: "{autoprograms}\{#MyAppNameFull}"; Filename: "{app}\launcher_wrapper.bat"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppNameFull}"; Filename: "{app}\launcher_wrapper.bat"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppNameFull}"; Filename: "{app}\launcher_wrapper.bat"; Tasks: quicklaunchicon; IconFilename: "{app}\{#MyAppExeName}"

[Run]
; Use launcher wrapper to check DLLs before starting
Filename: "{app}\launcher_wrapper.bat"; Description: "{cm:LaunchProgram,{#StringChange(MyAppNameFull, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
