# Costruisce l'installer dist\installer\fili-setup-<versione>.exe con Inno Setup 6.
# Prerequisiti (nell'ordine): scripts\build_wdi_simple.sh (build\wdi-simple.exe), scripts\build_exe.ps1 (dist\fili*.exe),
# scripts\package_wdi_bundle.py (dist\wdi-bundle). Questo script aggiunge il sorgente di libusb-win32 (libusb0.sys è GPL),
# poi compila l'installer e scrive dist\SHA256SUMS. Non installa nulla e non tocca driver o certificati.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup 6 non trovato (winget install JRSoftware.InnoSetup).' }
foreach ($f in 'dist\fili.exe', 'dist\fili-gui.exe', 'dist\wdi-bundle\wdi-simple.exe', 'dist\wdi-bundle\SHA256SUMS') {
    if (-not (Test-Path $f)) { throw "manca ${f}: vedi i prerequisiti in testa a questo script." }
}

# sorgente corrispondente di libusb-win32 1.4.0.0 (obbligo della GPL per libusb0.sys incorporato)
$zip = 'dist\wdi-bundle\THIRD_PARTY\libusb-win32-release_1.4.0.0-source.zip'
$sha = '7c041cbdcd47a9ad6fe7ef20605c94480454d6d768946f133fc7d9db38e22de6'
if (-not (Test-Path $zip)) {
    Invoke-WebRequest 'https://github.com/mcuee/libusb-win32/archive/refs/tags/release_1.4.0.0.zip' -OutFile $zip -UseBasicParsing
}
if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $sha) { throw "SHA-256 inatteso per $zip" }
@"
libusb-win32 1.4.0.0 - corresponding source
===========================================
wdi-simple.exe embeds libusb0.sys from libusb-win32 1.4.0.0 (driver: GNU GPL; library and installer: GNU LGPL).
The corresponding source is the file libusb-win32-release_1.4.0.0-source.zip in this folder.
Origin : https://github.com/mcuee/libusb-win32/archive/refs/tags/release_1.4.0.0.zip (tag release_1.4.0.0)
SHA-256: $sha
Licence texts: LICENSES\GPL-3.0.txt, LICENSES\LGPL-3.0.txt.
"@ | Set-Content 'dist\wdi-bundle\THIRD_PARTY\libusb-win32-SOURCE.txt' -Encoding utf8

# SHA256SUMS del bundle (finisce in {app}): aggiunge i file di libusb-win32 e quelli che l'installer copia da fuori dal
# bundle (fili.exe, fili-gui.exe, README.md, INSTALLER_NOTICE.txt), con i nomi che avranno nella cartella installata.
# Prima toglie le righe di un'esecuzione precedente. Verifica dopo l'installazione: sha256sum -c SHA256SUMS
$sums = 'dist\wdi-bundle\SHA256SUMS'
$extra = [ordered]@{
    'THIRD_PARTY/libusb-win32-release_1.4.0.0-source.zip' = 'dist\wdi-bundle\THIRD_PARTY\libusb-win32-release_1.4.0.0-source.zip'
    'THIRD_PARTY/libusb-win32-SOURCE.txt'                 = 'dist\wdi-bundle\THIRD_PARTY\libusb-win32-SOURCE.txt'
    'fili.exe'                                            = 'dist\fili.exe'
    'fili-gui.exe'                                        = 'dist\fili-gui.exe'
    'README.md'                                           = 'README.md'
    'INSTALLER_NOTICE.txt'                                = 'packaging\INSTALLER_NOTICE.txt'
}
$keep = Get-Content $sums | Where-Object { -not $extra.Contains(($_ -split '  ', 2)[1]) }
$new = $extra.GetEnumerator() | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.Value -Algorithm SHA256).Hash.ToLower(), $_.Key }
[IO.File]::WriteAllText((Join-Path $root $sums), ((@($keep) + $new) -join "`n") + "`n")

$version = (Select-String -Path 'src\fili\__init__.py' -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
& $iscc "/DAppVersion=$version" packaging\fili.iss
if ($LASTEXITCODE -ne 0) { throw "ISCC ha restituito $LASTEXITCODE" }

# SHA256SUMS da pubblicare accanto ai file: installer, eseguibili e wdi-simple.exe (formato di 'sha256sum -c', percorsi relativi a dist\)
$release = @("installer\fili-setup-$version.exe", 'fili.exe', 'fili-gui.exe', 'wdi-bundle\wdi-simple.exe')
$lines = $release | ForEach-Object { "{0}  {1}" -f (Get-FileHash "dist\$_" -Algorithm SHA256).Hash.ToLower(), $_.Replace('\', '/') }
[IO.File]::WriteAllText((Join-Path $root 'dist\SHA256SUMS'), ($lines -join "`n") + "`n")
$lines
