<#
가벼운 PDF 뷰어 빌드 + 설치 파일 (onedir: 폴더 형태, 시작 속도 우선)

사용법:
  .\build.ps1    # -> dist\PDFViewer\PDFViewer.exe  + installer\PDFViewer-Setup-<버전>.exe

버전은 pdf_viewer.py 의 __version__ 을 단일 소스로 사용합니다.
#>

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "venv가 없습니다. 먼저 생성하세요:" -ForegroundColor Yellow
    Write-Host "  py -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller pyinstaller-hooks-contrib"
    exit 1
}

& $py -m pip install -r requirements.txt pyinstaller pyinstaller-hooks-contrib --quiet

$ver = (& $py -c "import pdf_viewer; print(pdf_viewer.__version__)").Trim()
if (-not $ver) {
    Write-Host "버전(pdf_viewer.__version__)을 확인하지 못했습니다." -ForegroundColor Red
    exit 1
}
Write-Host "버전: $ver" -ForegroundColor Cyan

Write-Host "onedir 빌드 중..." -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean pdf_viewer.spec

if (-not (Test-Path ".\dist\PDFViewer\PDFViewer.exe")) {
    Write-Host "빌드 실패!" -ForegroundColor Red
    exit 1
}
Write-Host "빌드 완료 -> dist\PDFViewer\PDFViewer.exe" -ForegroundColor Green

# --- 설치 파일(installer) 컴파일 ---
$isccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "Inno Setup(ISCC.exe)을 찾지 못해 설치 파일을 건너뜁니다." -ForegroundColor Yellow
    Write-Host "설치: winget install JRSoftware.InnoSetup  또는 https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    exit 0
}

Write-Host "설치 파일 컴파일 중... (버전 $ver)" -ForegroundColor Cyan
& $iscc "/DMyAppVersion=$ver" installer.iss

$setup = ".\installer\PDFViewer-Setup-$ver.exe"
if (Test-Path $setup) {
    Write-Host "설치 파일 완료 -> $setup" -ForegroundColor Green
} else {
    Write-Host "설치 파일 컴파일 실패!" -ForegroundColor Red
    exit 1
}
