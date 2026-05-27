# WPF uygulamasini self-contained yayinlar ve donmus motoru icine gomer.
# Cikti: windows\packaging\dist\Turkify\  (Turkify.exe + turkify-engine\)
#
# On kosul: once windows\packaging\build_engine.ps1 calistirilmis olmali.
# Kullanim:
#   windows\packaging\build_app.ps1
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..')).Path
$csproj = Join-Path $repo 'windows\Turkify\Turkify.csproj'
$engineSrc = Join-Path $here 'dist\turkify-engine'
$appOut = Join-Path $here 'dist\Turkify'

if (-not (Test-Path (Join-Path $engineSrc 'turkify-engine.exe'))) {
    throw "Donmus motor yok: $engineSrc. Once build_engine.ps1 calistir."
}

Write-Host "==> dotnet publish (self-contained, win-x64)"
if (Test-Path $appOut) { Remove-Item -Recurse -Force $appOut }
dotnet publish $csproj -c Release -r win-x64 --self-contained true `
    -p:PublishSingleFile=false -o $appOut

Write-Host "==> Donmus motoru gom: $appOut\turkify-engine"
$engineDst = Join-Path $appOut 'turkify-engine'
Copy-Item -Recurse -Force $engineSrc $engineDst

Write-Host ""
Write-Host "==> Tamam: $appOut\Turkify.exe (gomulu motor ile; Python/venv gerekmez)"
Write-Host "    Installer icin: windows\packaging\turkify.iss (Inno Setup)"
