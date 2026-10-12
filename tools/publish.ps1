<#
로컬에서 이미 빌드된 설치 파일을 Cloudflare R2에 올리고 latest.json을 갱신한다.
(CI 없이 수동 릴리스할 때. 평소에는 GitHub Actions의 Release 워크플로가 자동 수행)

사전 준비(1회):
  npx wrangler login                       # 또는 CLOUDFLARE_API_TOKEN/CLOUDFLARE_ACCOUNT_ID
  npx wrangler r2 bucket create pdf-viewer
  cd updates-worker; npx wrangler deploy; cd ..

사용법:
  .\tools\publish.ps1                       # pdf_viewer.__version__ 기준
  .\tools\publish.ps1 -Version 1.2.0 -WorkerBase https://pdf-viewer-updates.xxx.workers.dev
#>
param([string]$Version = "", [string]$WorkerBase = "")

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"

if (-not $Version) {
    $Version = (& $py -c "import pdf_viewer; print(pdf_viewer.__version__)").Trim()
}
if (-not $WorkerBase) {
    $WorkerBase = $env:WORKER_BASE_URL
}
if (-not $WorkerBase) {
    Write-Host "WorkerBase(또는 환경변수 WORKER_BASE_URL)를 지정하세요. 예: https://pdf-viewer-updates.xxx.workers.dev" -ForegroundColor Yellow
    exit 1
}
$base = $WorkerBase.Trim().TrimEnd('/')

$asset = ".\installer\PDFViewer-Setup-$Version.exe"
if (-not (Test-Path $asset)) {
    Write-Host "설치 파일 없음: $asset (먼저 .\build.ps1 실행)" -ForegroundColor Red
    exit 1
}

$sha = (Get-FileHash $asset -Algorithm SHA256).Hash.ToLower()
$json = [ordered]@{
    version = $Version
    url     = "$base/download/PDFViewer-Setup-$Version.exe"
    sha256  = $sha
    size    = (Get-Item $asset).Length
    pub_date = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Compress
Set-Content -Path latest.json -Value $json -Encoding utf8

npx --yes wrangler@latest r2 object put "pdf-viewer/releases/PDFViewer-Setup-$Version.exe" --file $asset --remote
npx --yes wrangler@latest r2 object put "pdf-viewer/latest.json" --file latest.json --remote

Write-Host "완료: $Version -> $base" -ForegroundColor Green