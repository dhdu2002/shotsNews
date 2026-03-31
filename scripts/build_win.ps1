# Windows MVP 빌드 스크립트

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$SpecPath = Join-Path $Root "packaging\app.spec"

Write-Host "[build] PyInstaller 빌드를 시작합니다."
python -m PyInstaller --noconfirm "$SpecPath"

Write-Host "[build] 완료: dist\shotsNews"
