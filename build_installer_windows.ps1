$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = if ($env:CLYO_STOCK_VERSION) { $env:CLYO_STOCK_VERSION.Trim() } else { "8.3.11" }
$PortableDir = Join-Path $Root "dist\CLYO_Stock_PORTABLE"
$InstallerDir = Join-Path $Root "dist\installer"
$InstallerExe = Join-Path $InstallerDir "CLYO_Stock_Atelier_Setup_$Version.exe"
function Step($m){ Write-Host "`n=== $m ===" -ForegroundColor Cyan }
Set-Location $Root
Step "Validation de la version $Version"
$env:CLYO_STOCK_VERSION=$Version
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv (Join-Path $Root ".venv") }
  else { & python -m venv (Join-Path $Root ".venv") }
}
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
& $Python validate_release.py --version $Version --phase source
if ($LASTEXITCODE -ne 0) { throw "Validation source échouée" }
Step "Build de l'application portable"
& $Python CLYO_Stock_Builder.py --app-dir $Root
if ($LASTEXITCODE -ne 0) { throw "Build portable échoué" }
Step "Compilation Inno Setup"
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (!(Test-Path $iscc)) { throw "ISCC.exe introuvable : $iscc" }
New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null
Get-ChildItem $InstallerDir -Filter "CLYO_Stock_Atelier_Setup_*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force
& $iscc "/DMyAppVersion=$Version" ".\CLYO_Stock_Installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Compilation Inno Setup échouée" }
if (-not (Test-Path $InstallerExe)) { throw "Installateur non généré : $InstallerExe" }
& $Python validate_release.py --version $Version --phase built --installer $InstallerExe
if ($LASTEXITCODE -ne 0) { throw "Validation finale échouée" }
Write-Host "`nInstallateur généré : $InstallerExe" -ForegroundColor Green
