# Download and unpack, WITHOUT installing anything, what libwdi needs to embed drivers:
#   * WDK 8.0 redistributables (Microsoft MSI, WinUSB co-installers)  - extracted with "msiexec /a" (admin image,
#     writes only into the target directory; it does not install the product)
#   * libusb-win32 1.4.0.0 binaries and libusbK 3.1.0.0 binaries (the same releases libwdi's own CI uses)
# Everything goes under -Work (default build\wdi-work, ignored by git). Needs 7-Zip (7z.exe) for the .7z/.zip files.
# Status: PROVEN on a Windows 11 machine (see docs/building-wdi-simple.md). It changes nothing outside -Work.
param(
  [string]$Work = (Join-Path $PSScriptRoot '..\build\wdi-work'),
  [string]$SevenZip = 'C:\Program Files\7-Zip\7z.exe'
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Work | Out-Null
$Work = (Resolve-Path $Work).Path
$dl = Join-Path $Work 'dl'
New-Item -ItemType Directory -Force $dl | Out-Null
if (-not (Test-Path $SevenZip)) { throw "7-Zip not found: $SevenZip (pass -SevenZip)" }

$files = @(
  @{ Name = 'wdk-redist.msi'; Url = 'https://go.microsoft.com/fwlink/p/?LinkID=253170' },
  @{ Name = 'libusb0.zip';    Url = 'https://github.com/mcuee/libusb-win32/releases/download/release_1.4.0.0/libusb-win32-bin-1.4.0.0.zip' },
  @{ Name = 'libusbk.7z';     Url = 'https://github.com/mcuee/libusbk/releases/download/V3.1.0.0/libusbK-3.1.0.0-bin.7z' }
)
foreach ($f in $files) {
  $p = Join-Path $dl $f.Name
  if (-not (Test-Path $p)) { curl.exe -sSL --fail --max-time 300 -o $p $f.Url; if ($LASTEXITCODE) { throw "download failed: $($f.Url)" } }
  '{0}  {1}' -f (Get-FileHash $p -Algorithm SHA256).Hash, $f.Name
}
$sig = Get-AuthenticodeSignature (Join-Path $dl 'wdk-redist.msi')
"wdk-redist.msi signature: $($sig.Status), $($sig.SignerCertificate.Subject)"
if ($sig.Status -ne 'Valid') { throw 'the WDK redist MSI is not validly signed by Microsoft: stop' }

New-Item -ItemType Directory -Force (Join-Path $Work 'wdk'), (Join-Path $Work 'libusb0x'), (Join-Path $Work 'libusbkx') | Out-Null
$p = Start-Process msiexec.exe -ArgumentList '/a', (Join-Path $dl 'wdk-redist.msi'), '/qn', ('TARGETDIR=' + (Join-Path $Work 'wdk')) -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "msiexec /a failed: $($p.ExitCode)" }
& $SevenZip x -y ('-o' + (Join-Path $Work 'libusb0x')) (Join-Path $dl 'libusb0.zip') | Out-Null
& $SevenZip x -y ('-o' + (Join-Path $Work 'libusbkx')) (Join-Path $dl 'libusbk.7z') | Out-Null
foreach ($need in 'wdk\Windows Kits\8.0\redist\wdf\x64\WdfCoInstaller01011.dll',
                  'wdk\Windows Kits\8.0\redist\wdf\x64\winusbcoinstaller2.dll',
                  'libusb0x\libusb-win32-bin-1.4.0.0\bin\amd64\libusb0.sys',
                  'libusbkx\libusbK-3.1.0.0-bin\bin\sys\amd64\libusbK.sys') {
  if (-not (Test-Path (Join-Path $Work $need))) { throw "missing after unpacking: $need" }
}
"ready: $Work"
