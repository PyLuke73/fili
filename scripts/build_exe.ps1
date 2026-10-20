# Compila fili.exe (CLI) e fili-gui.exe (GUI) con PyInstaller, in dist/. Non installa e non esegue nulla del sistema.
# Uso (dalla radice del repository):  powershell -File scripts\build_exe.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$common = @('--noconfirm', '--clean', '--onefile', '--paths', 'src', '--distpath', 'dist', '--workpath', 'build\pyinstaller',
            '--specpath', 'build\pyinstaller')
python -m PyInstaller @common --console --name fili packaging\fili_cli.py
python -m PyInstaller @common --windowed --name fili-gui packaging\fili_gui.py
Get-ChildItem dist\fili.exe, dist\fili-gui.exe | Get-FileHash -Algorithm SHA256 | ForEach-Object { "{0}  {1}" -f $_.Hash.ToLower(), (Split-Path $_.Path -Leaf) }
