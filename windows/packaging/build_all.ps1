# Turkify — Windows kurulum paketini (TurkifySetup.exe) TEK ADIMDA uretir.
#
# Sirasiyla:  motoru dondur (PyInstaller)  ->  uygulamayi yayinla + motoru gom (dotnet)
#             ->  installer derle (Inno Setup)
# Cikti:      windows\packaging\dist\TurkifySetup.exe
#
# Kullanim (repo kokunden veya herhangi bir yerden):
#   .\windows\packaging\build_all.ps1
#   .\windows\packaging\build_all.ps1 -SkipEngine        # motoru yeniden dondurme (hizli)
#   .\windows\packaging\build_all.ps1 -IsccPath "C:\...\ISCC.exe"
#
# On kosul: .NET 8 SDK, Python 3, Inno Setup (https://jrsoftware.org/isdl.php).
# Script izni gerekirse:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
[CmdletBinding()]
param(
    [switch]$SkipEngine,
    [string]$IsccPath
)
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$engineExe = Join-Path $here 'dist\turkify-engine\turkify-engine.exe'
$setupExe = Join-Path $here 'dist\TurkifySetup.exe'

function Find-Iscc {
    param([string]$Explicit)
    if ($Explicit) {
        if (Test-Path $Explicit) { return $Explicit }
        throw "Belirtilen ISCC bulunamadi: $Explicit"
    }
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 5\ISCC.exe"
    )
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    return $null
}

# Inno Setup'i en basta dogrula: uzun motor/uygulama derlemesinden SONRA
# "ISCC yok" surpriziyle karsilasilmasin (fail fast).
$iscc = Find-Iscc -Explicit $IsccPath
if (-not $iscc) {
    throw ("Inno Setup (ISCC.exe) bulunamadi. Kur: https://jrsoftware.org/isdl.php " +
           "veya -IsccPath ile tam yolu ver.")
}
Write-Host "Inno Setup: $iscc"

$sw = [System.Diagnostics.Stopwatch]::StartNew()

if ($SkipEngine) {
    Write-Host "==> [1/3] Motor atlandi (-SkipEngine); mevcut donmus motor kullanilacak." -ForegroundColor Yellow
    if (-not (Test-Path $engineExe)) {
        throw "Donmus motor yok: $engineExe. -SkipEngine'siz calistirip motoru bir kez uret."
    }
}
else {
    Write-Host "==> [1/3] Motor donduruluyor (PyInstaller)..." -ForegroundColor Cyan
    & (Join-Path $here 'build_engine.ps1')
}

Write-Host "==> [2/3] Uygulama yayinlaniyor + motor gomuluyor (dotnet)..." -ForegroundColor Cyan
& (Join-Path $here 'build_app.ps1')

Write-Host "==> [3/3] Installer derleniyor (Inno Setup)..." -ForegroundColor Cyan
& $iscc (Join-Path $here 'turkify.iss')
if ($LASTEXITCODE -ne 0) { throw "ISCC basarisiz (cikis kodu $LASTEXITCODE)." }

if (-not (Test-Path $setupExe)) { throw "Installer uretilemedi: $setupExe" }
$sw.Stop()
$sizeMb = [math]::Round((Get-Item $setupExe).Length / 1MB, 1)
Write-Host ""
Write-Host "==> TAMAM ($([int]$sw.Elapsed.TotalSeconds) sn): $setupExe  ($sizeMb MB)" -ForegroundColor Green
Write-Host "    Dagitmaya hazir. Imzasiz oldugundan kullanici SmartScreen'de 'Yine de calistir' der."
