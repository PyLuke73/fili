# Building wdi-simple.exe

`fili install/reinstall` runs **wdi-simple.exe** from [libwdi](https://github.com/pbatard/libwdi) (LGPL-3.0-or-later).
It is not shipped here: you build it (or provide your own) and tell fili where it is: `--wdi PATH`, `[tool] wdi_path`
in `fili.toml`, `%FILI_WDI%`, a copy on `PATH`, or `build\wdi-simple.exe`.

> **Status: the build below is PROVEN on the build machine** (Windows 11 Pro, MSYS2 ucrt64 gcc 14.2.0, libwdi v1.5.1,
> commit `9b23b82a2dd1cbffc16d46c212f92c6bf8c0c602`), twice, from scratch. **The resulting exe was compiled and inspected
> statically** (`file`, `objdump -p`, `strings`) and then **run for real inside a Windows Server 2022 VM** to install WinUSB,
> libusbK and libusb-win32 on a virtual USB device (see `risultati-prove-installazione.md`); other systems and physical
> devices are untested (see `piano-prove-installazione.md`).

## Two scripts, nothing installed on the PC

```powershell
powershell -File scripts\fetch_wdi_deps.ps1     # downloads + unpacks the driver files into build\wdi-work (git-ignored)
```
```bash
scripts/build_wdi_simple.sh                      # from an MSYS2 / Git Bash shell: clones libwdi, compiles, copies build/wdi-simple.exe
```
Requirements: 7-Zip (`C:\Program Files\7-Zip\7z.exe`), Git, MSYS2 with the ucrt64 `gcc` and binutils (`windres`, `ar`),
and the Windows `curl.exe`. Neither `make` nor autotools are needed.

`fetch_wdi_deps.ps1` fetches the same support files that libwdi's own CI uses (`.github/workflows/mingw.yml`):

| File | Source | SHA-256 (as downloaded on 2026-10-11) |
|---|---|---|
| `wdk-redist.msi` (WDK 8.0 redistributables: WinUSB / WDF co-installers) | `https://go.microsoft.com/fwlink/p/?LinkID=253170` | `29314207814CE9D5D73695F7E9239539CF37C79E750B9D5EA5A5EF5487A583D6` |
| `libusb0.zip` (libusb-win32 1.4.0.0) | `github.com/mcuee/libusb-win32/releases/download/release_1.4.0.0/` | `9950B7A226E3EA387365C046D13B68BD0B0B18C015C034363601FF601C5B5585` |
| `libusbk.7z` (libusbK 3.1.0.0) | `github.com/mcuee/libusbk/releases/download/V3.1.0.0/` | `38605D8D5A86F408A4B7BEC60F6D4A096050EEE72F89A63A8D5BE125252D3FE7` |

The script prints the hashes and **stops unless the MSI has a valid Microsoft Authenticode signature** (it has:
`CN=Microsoft Corporation`). The two GitHub archives have no signature to check: compare the hashes with yours.
The MSI is unpacked with `msiexec /a` (an *administrative image*: it only writes into the target directory, it does **not**
install anything).

## What the build does (the same as `libwdi/Makefile.am`, written out by hand)

1. `installer_x64.exe` from `libwdi/installer.c` (the helper that libwdi embeds and runs elevated).
2. `embedder.exe` generates `embedded.h`, which embeds in the library: the WinUSB co-installers, libusb0 and libusbK
   driver files, the helper and the INF/CAT templates.
3. `libwdi.a`, then `wdi-simple.exe` (static, x64, console). It imports only system DLLs (`KERNEL32`, `SETUPAPI`, `ole32`,
   `ntdll`, the Universal CRT `api-ms-win-crt-*`, ...): runs on Windows 10/11 x64.
4. The `config.h` is written by the script: `WDK_DIR`, `WDF_VER 1011`, `COINSTALLER_DIR "wdf"`, `X64_DIR "x64"`,
   `LIBUSB0_DIR`, `LIBUSBK_DIR`, `OPT_M64`, `ENABLE_LOGGING 1`. **x64 only** (no 32-bit, no ARM64).

Result of the reference build: `build/wdi-simple.exe`, about 4.1 MB, PE32+ x86-64 console. The SHA-256 is **not
reproducible** between builds (timestamps are embedded); the second build was
`3cae635b8a6dfb603525e51d113c9d5fcdde72911c381709cb6214a8d3f19af9`.

### Choices and compromises

* **WinUSB uses the co-installers of the WDK 8.0 redistributables** (2012 files). libwdi v1.5.1 offers WinUSB **only** when
  `WDK_DIR` is defined (`wdi_is_driver_supported` in `libwdi.c`), so a build without them has no WinUSB. The WDK 10 NuGet
  package (`Microsoft.Windows.WDK.x64`) has no `redist` directory. The co-installers are legacy files; whether they matter on
  Windows 10/11 is exactly what the installation test has to show.
* **Licences of what is embedded:** the WDK redistributables are under Microsoft's redistribution terms; libusb-win32 and
  libusbK have their own licences. Verify and list them in `NOTICE` and `THIRD_PARTY/embedded-drivers.txt` before giving a
  binary to anyone (`docs/licenza.md`, `scripts/package_wdi_bundle.py`).
* **Why not `./configure`:** the MSYS2 package mirrors all failed with `SSL certificate problem: unable to get local issuer
  certificate` on this PC (every mirror, not one), so `autoconf`/`automake` could not be installed. The certificate check
  was **not** bypassed; the hand-written build avoids the need.

## How fili calls it (from `examples/wdi-simple.c`)

`wdi-simple -n NAME -f fili.inf -v 0xVID -p 0xPID [-i MI] -t TYPE -d DIR [-w] [--filter] [-s] [-o MS] -l LEVEL`
where `TYPE` is 0 WinUSB, 1 libusb-win32, 2 libusbK, 3 usbser. It extracts the package into `DIR`, **self-signs the catalog,
adds the certificate to the Root and TrustedPublisher stores** (`SelfSignFile` in libwdi's `pki.c`) and installs the driver.
`-x` (extract only) performs the same signing, so fili does not use it: `fili extract` writes an unsigned INF itself.
Certificates are named `CN=<hardware id> (libwdi autogenerated)`; `fili cert-remove` finds them by that suffix.

## Other option: Visual Studio

Open `libwdi.sln` (see libwdi's wiki, "Install") and build `wdi-simple`. Not tried here.
