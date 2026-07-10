$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = if ($env:CLYO_STOCK_VERSION) { $env:CLYO_STOCK_VERSION.Trim() } else { "9.0.0" }
$PortableDir = Join-Path $Root "dist\CLYO_Stock_PORTABLE"
$InstallerDir = Join-Path $Root "dist\installer"
$InstallerExe = Join-Path $InstallerDir "CLYO_Stock_Atelier_Setup_$Version.exe"

function Step($Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "La commande a échoué avec le code $LASTEXITCODE : $FilePath $($Arguments -join ' ')"
    }
}

Set-Location $Root
$env:CLYO_STOCK_VERSION = $Version
$Python = Join-Path $Root ".venv\Scripts\python.exe"

Step "Préparation de Python"
if (-not (Test-Path $Python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        Invoke-Native py "-3.12" "-m" "venv" (Join-Path $Root ".venv")
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        Invoke-Native python "-m" "venv" (Join-Path $Root ".venv")
    }
    else {
        throw "Python est introuvable."
    }
}

Step "Installation des outils de compilation"
Invoke-Native $Python "-m" "pip" "install" "--upgrade" "pip" "setuptools" "wheel"
Invoke-Native $Python "-m" "pip" "install" "-r" (Join-Path $Root "requirements.txt")
# Installation explicite pour éviter un environnement virtuel incomplet ou un cache défectueux.
Invoke-Native $Python "-m" "pip" "install" "--upgrade" "pyinstaller>=6.12,<7"

Step "Vérification de PyInstaller"
Invoke-Native $Python "-m" "PyInstaller" "--version"

Step "Validation de la version $Version"
Invoke-Native $Python (Join-Path $Root "validate_release.py") "--version" $Version "--phase" "source"

Step "Nettoyage des anciens installateurs"
if (Test-Path $InstallerDir) {
    Get-ChildItem $InstallerDir -Filter "CLYO_Stock_Atelier_Setup_*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force
}

Step "Build de l'application portable"
Invoke-Native $Python (Join-Path $Root "CLYO_Stock_Builder.py") "--app-dir" $Root

if (-not (Test-Path (Join-Path $PortableDir "CLYO_Stock.exe"))) {
    throw "L'exécutable portable n'a pas été généré : $PortableDir\CLYO_Stock.exe"
}

Step "Compilation Inno Setup"
$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "ISCC.exe est introuvable. Installe Inno Setup 6 avant de continuer."
}

New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null
Invoke-Native $iscc "/DMyAppVersion=$Version" (Join-Path $Root "CLYO_Stock_Installer.iss")

if (-not (Test-Path $InstallerExe)) {
    throw "Installateur non généré : $InstallerExe"
}

Step "Validation finale"
Invoke-Native $Python (Join-Path $Root "validate_release.py") "--version" $Version "--phase" "built" "--installer" $InstallerExe

Write-Host "`nInstallateur généré : $InstallerExe" -ForegroundColor Green
