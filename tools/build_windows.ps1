<#
.SYNOPSIS
  Compila Etch-DB-Mapper para Windows: pruebas -> .exe (PyInstaller) -> instalador (Inno Setup).

.EXAMPLE
  .\tools\build_windows.ps1                 # solo el .exe en dist\
  .\tools\build_windows.ps1 -Installer      # .exe + instalador en installer\output\
  .\tools\build_windows.ps1 -SkipTests      # sin correr las pruebas
#>
param(
    [switch]$Installer,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (python -c "from core.version import __version__; print(__version__)").Trim()
Write-Host "== Etch-DB-Mapper $version ==" -ForegroundColor Cyan

Write-Host "-- Comprobando sintaxis" -ForegroundColor Cyan
python -m py_compile db_manager_app.py core\api.py core\scanner.py core\storage.py core\paths.py core\demo.py core\version.py
if ($LASTEXITCODE -ne 0) { throw "py_compile fallo" }

if (-not $SkipTests) {
    Write-Host "-- Corriendo pruebas" -ForegroundColor Cyan
    python -m unittest discover -s tests -t .
    if ($LASTEXITCODE -ne 0) { throw "Las pruebas fallaron" }
}

Write-Host "-- Compilando el .exe (PyInstaller)" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name "Etch-DB-Mapper" --icon "$root\favicon.ico" `
    --specpath build --workpath build\pyinstaller --distpath dist `
    --add-data "$root\webui;webui" `
    --add-data "$root\CHANGELOG.md;." `
    --add-data "$root\HELP.md;." `
    --add-data "$root\THIRD_PARTY_NOTICES.md;." `
    --hidden-import psycopg2 --hidden-import pyodbc --hidden-import pymysql `
    db_manager_app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo" }

$exe = Join-Path $root "dist\Etch-DB-Mapper.exe"
if (-not (Test-Path $exe)) { throw "No se genero $exe" }
$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "OK: $exe ($sizeMb MB)" -ForegroundColor Green

if ($Installer) {
    Write-Host "-- Generando el instalador (Inno Setup)" -ForegroundColor Cyan
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    $iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) { throw "No se encontro ISCC.exe. Instala Inno Setup 6 (https://jrsoftware.org/isinfo.php)." }
    & $iscc "/DMyAppVersion=$version" "installer\setup.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup fallo" }
    $setup = Get-ChildItem "installer\output\Etch-DB-Mapper-Setup-v$version.exe" -ErrorAction Stop
    Write-Host ("OK: {0} ({1} MB)" -f $setup.FullName, [math]::Round($setup.Length / 1MB, 1)) -ForegroundColor Green
}
