#!/usr/bin/env bash
# Build wdi-simple.exe (libwdi) with MSYS2/MinGW. NOT TESTED to completion on the author's machine:
# it stops at the prerequisites check (no WDK redistributables, no autotools). See docs/building-wdi-simple.md.
#
# Usage:  WDK_DIR='C:/Program Files (x86)/Windows Kits/10' scripts/build_wdi_simple.sh
# The result is build/wdi-simple.exe. This script changes nothing outside this repository.
set -euo pipefail
cd "$(dirname "$0")/.."

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing tool: $1 (see docs/building-wdi-simple.md)" >&2; exit 1; }; }
for t in git gcc make autoconf automake libtool; do need "$t"; done

: "${WDK_DIR:?set WDK_DIR to a Windows Kits directory that contains redist/wdf and redist/winusb (or edit the configure line to use --with-libusbk / --with-libusb0 / --with-userdir)}"
for f in "redist/wdf/x64/WdfCoInstaller01011.dll" "redist/winusb/x64/winusbcoinstaller2.dll"; do
  [ -f "$WDK_DIR/$f" ] || { echo "WDK file not found: $WDK_DIR/$f" >&2; exit 1; }
done

REF="${LIBWDI_REF:-v1.5.1}"
[ -d third_party/libwdi ] || git clone --depth 1 --branch "$REF" https://github.com/pbatard/libwdi.git third_party/libwdi
cd third_party/libwdi
./autogen.sh --enable-examples-build --with-wdkdir="$WDK_DIR" --disable-32bit
make -j"$(nproc)"
cd ../..
mkdir -p build
cp third_party/libwdi/examples/wdi-simple.exe build/
echo "built build/wdi-simple.exe"
