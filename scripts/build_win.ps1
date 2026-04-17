# Windows MVP 빌드 스크립트

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$SpecPath = Join-Path $Root "packaging\app.spec"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
} else {
    $PythonExe = "python"
}

Write-Host "[build] PyInstaller 빌드를 시작합니다."
& $PythonExe -m PyInstaller --noconfirm "$SpecPath"

Write-Host "[build] 완료: dist\shotsNews"
