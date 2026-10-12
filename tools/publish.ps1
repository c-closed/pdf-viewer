<#
로컬에서 이미 빌드된 설치 파일을 GitHub Release에 올리고 latest.json 자산까지 등록한다.
(CI 없이 수동 릴리스할 때. 평소에는 태그 푸시로 GitHub Actions의 Release 워크플로가 자동 수행)

사전 준비(1회):
  gh auth login
  git remote add origin https://github.com/<사용자>/pdf-viewer.git   # 아직 없으면

사용법:
  .\tools\publish.ps1                    # pdf_viewer.__version__ 기준 (태그 v<버전>)
  .\tools\publish.ps1 -Version 1.2.0
  .\tools\publish.ps1 -Tag v1.2.0
#>
param([string]$Version = "", [string]$Tag = "")

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"

if (-not $Version) {
    $Version = (& $py -c "import pdf_viewer; print(pdf_viewer.__version__)").Trim()
}
if (-not $Tag) { $Tag = "v$Version" }

$asset = ".\installer\PDFViewer-Setup-$Version.exe"
if (-not (Test-Path $asset)) {
    Write-Host "설치 파일 없음: $asset (먼저 .\build.ps1 실행)" -ForegroundColor Red
    exit 1
}

$repo = (gh repo view --json nameWithOwner --jq ".nameWithOwner")
if (-not $repo) { Write-Host "gh repo view 실패 (gh auth login 확인)" -ForegroundColor Red; exit 1 }

$sha = (Get-FileHash $asset -Algorithm SHA256).Hash.ToLower()
$json = [ordered]@{
    version  = $Version
    url      = "https://github.com/$repo/releases/download/$Tag/PDFViewer-Setup-$Version.exe"
    sha256   = $sha
    size     = (Get-Item $asset).Length
    pub_date = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Compress
Set-Content -Path latest.json -Value $json -Encoding utf8

$notes = "PDF Viewer $Version"
gh release create $Tag $asset latest.json --title "PDF Viewer $Version" --notes $notes
if (-not $?) { Write-Host "릴리스 생성 실패(이미 존재하는 태그일 수 있음)" -ForegroundColor Red; exit 1 }

Write-Host "완료: $Version -> https://github.com/$repo/releases/tag/$Tag" -ForegroundColor Green
