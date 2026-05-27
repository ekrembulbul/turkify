# Turkify motorunu (turkify-engine.exe) PyInstaller ile bagimsiz bir ikiliye dondurur.
# Cikti: windows\packaging\dist\turkify-engine\turkify-engine.exe  (bkz. ADR 0009)
#
# Kullanim (repo kokunden veya herhangi bir yerden):
#   windows\packaging\build_engine.ps1
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..')).Path
$buildVenv = Join-Path $here '.build-venv'
$venvPy = Join-Path $buildVenv 'Scripts\python.exe'

Write-Host "==> Temiz build venv: $buildVenv"
if (Test-Path $buildVenv) { Remove-Item -Recurse -Force $buildVenv }
python -m venv $buildVenv
& $venvPy -m pip install --upgrade pip wheel | Out-Null

Write-Host "==> Bagimliliklar: turkify + Tier 2 (zeyrek) + pyinstaller"
& $venvPy -m pip install "$repo[morphology]" pyinstaller

Write-Host "==> PyInstaller (onedir)"
Push-Location $here
try {
    if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
    if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' }
    & $venvPy -m PyInstaller --clean --noconfirm 'turkify-engine.spec'
}
finally {
    Pop-Location
}

$engine = Join-Path $here 'dist\turkify-engine\turkify-engine.exe'
Write-Host "==> Hizli kontrol"
'{"id":1,"text":"bugun gorusme yapacagiz"}' | & $engine serve --stdio

Write-Host ""
Write-Host "==> Tamam: $engine"
Write-Host "    Uygulamaya gommek icin: windows\packaging\build_app.ps1"
