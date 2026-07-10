$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = if ($env:CLYO_STOCK_VERSION) { $env:CLYO_STOCK_VERSION.Trim() } else { "9.0.0" }
$PortableDir = Join-Path $Root "dist\CLYO_Stock_PORTABLE"
$InstallerDir = Join-Path $Root "dist\installer"
$InstallerExe = Join-Path $InstallerDir "CLYO_Stock_Atelier_Setup_$Version.exe"

function Write-Step($Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

Set-Location $Root

Write-Step "Nettoyage des anciens installateurs"
if (-not (Test-Path $InstallerDir)) {
    New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null
} else {
    Get-ChildItem $InstallerDir -Filter "CLYO_Stock_Atelier_Setup_*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

Write-Step "Build de l'application portable"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) { & py -3 -m venv (Join-Path $Root ".venv") }
    else { & python -m venv (Join-Path $Root ".venv") }
}

& $Python CLYO_Stock_Builder.py --app-dir $Root
if ($LASTEXITCODE -ne 0) {
    throw "Build portable echoue, code retour : $LASTEXITCODE"
}

if (-not (Test-Path (Join-Path $PortableDir "CLYO_Stock.exe"))) {
    throw "Build portable introuvable : $PortableDir"
}

Write-Step "Compilation Inno Setup"
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if (!(Test-Path $iscc)) {
    throw "ISCC.exe introuvable : $iscc"
}

& $iscc ".\CLYO_Stock_Installer.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Compilation Inno Setup echouee, code retour : $LASTEXITCODE"
}

if (-not (Test-Path $InstallerExe)) {
    $Generated = Get-ChildItem $InstallerDir -Filter "CLYO_Stock_Atelier_Setup_*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $Generated) {
        throw "Aucun installateur genere dans : $InstallerDir"
    }
    Rename-Item -Path $Generated.FullName -NewName (Split-Path $InstallerExe -Leaf) -Force
}

if (-not (Test-Path $InstallerExe)) {
    throw "Installateur non genere : $InstallerExe"
}

Write-Host "`nInstallateur genere :" -ForegroundColor Green
Write-Host $InstallerExe -ForegroundColor Yellow
Write-Host "`nTu peux distribuer ce fichier a tes utilisateurs." -ForegroundColor Green
