#!/usr/bin/env bash
# Build wdi-simple.exe (libwdi v1.5.1, x64) with MSYS2 MinGW-w64, WITHOUT autotools and WITHOUT make.
# Status: PROVEN on a Windows 11 machine (gcc 14.2.0 ucrt64). See docs/building-wdi-simple.md.
#
# Steps:  1) powershell -File scripts/fetch_wdi_deps.ps1      (download + unpack the driver files, installs nothing)
#         2) scripts/build_wdi_simple.sh                       (this script; run it from an MSYS2/Git Bash shell)
# Result: build/wdi-simple.exe   (git-ignored). Nothing is installed or run: the exe is only compiled.
#
# Co-installer Microsoft (WdfCoInstaller01011.dll, winusbcoinstaller2.dll): per default NON sono incorporati. Servono solo a
# Windows XP/Vista e ridistribuirli impone la manleva del WDK (docs/licenza.md). WITH_COINSTALLERS=1 riporta la build
# precedente (richiede fetch_wdi_deps.ps1 -WithCoInstallers; chi pubblica quel binario si assume le condizioni Microsoft).
#
# Why not ./configure: the MSYS2 package mirrors failed TLS verification on the build PC, so autoconf/automake could
# not be installed (verification was not disabled). The build is the one in libwdi/Makefile.am, written out by hand.
set -euo pipefail
export PATH=/c/msys64/ucrt64/bin:/c/msys64/usr/bin:$PATH

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${WDI_WORK:-$ROOT/build/wdi-work}"
REF="${LIBWDI_REF:-v1.5.1}"
REF_COMMIT="${LIBWDI_COMMIT:-9b23b82a2dd1cbffc16d46c212f92c6bf8c0c602}"

for t in git gcc windres ar cygpath sha256sum; do
  command -v "$t" >/dev/null 2>&1 || { echo "missing tool: $t (MSYS2 ucrt64 gcc/binutils + Git, see docs/building-wdi-simple.md)" >&2; exit 1; }
done
WW="$(cygpath -m "$WORK")"
WITH_COINSTALLERS="${WITH_COINSTALLERS:-0}"
WDK_DIR="$WW/wdk/Windows Kits/8.0"
LIBUSB0_DIR="$WW/libusb0x/libusb-win32-bin-1.4.0.0"
LIBUSBK_DIR="$WW/libusbkx/libusbK-3.1.0.0-bin/bin"
NEEDED=("$LIBUSB0_DIR/bin/amd64/libusb0.sys" "$LIBUSBK_DIR/sys/amd64/libusbK.sys")
# i co-installer Microsoft servono solo con WITH_COINSTALLERS=1
if [ "$WITH_COINSTALLERS" = 1 ]; then
  NEEDED+=("$WDK_DIR/redist/wdf/x64/WdfCoInstaller01011.dll" "$WDK_DIR/redist/wdf/x64/winusbcoinstaller2.dll")
fi
for f in "${NEEDED[@]}"; do
  [ -f "$f" ] || { echo "driver file not found: $f -- run scripts/fetch_wdi_deps.ps1 first" >&2; exit 1; }
done

SRC="$WORK/libwdi"
if [ ! -d "$SRC" ]; then git clone -q --depth 1 --branch "$REF" https://github.com/pbatard/libwdi.git "$SRC"; fi
HEAD="$(git -C "$SRC" rev-parse HEAD)"
[ "$HEAD" = "$REF_COMMIT" ] || { echo "libwdi is at $HEAD, expected $REF_COMMIT (set LIBWDI_COMMIT if you changed LIBWDI_REF on purpose)" >&2; exit 1; }

if [ "$WITH_COINSTALLERS" != 1 ]; then
  # ripristina i file toccati dalla patch (build ripetibili) e toglie i co-installer
  git -C "$SRC" checkout -q -- libwdi/embedder_files.h libwdi/winusb.inf.in libwdi/libusbk.inf.in \
    libwdi/winusb.cat.in libwdi/libusbk.cat.in
  python -I "$ROOT/scripts/strip_coinstallers.py" "$(cygpath -m "$SRC")"
  # WDK_DIR resta definito (senza file): libwdi considera WinUSB supportato e non prende il co-installer dal pacchetto libusbK
  WDK_DIR="$WW/unused-wdk-no-coinstallers"
fi

INC="$WORK/inc"; mkdir -p "$INC"
cat > "$INC/config.h" <<EOF
/* hand-written config.h for an x64 MinGW-w64 build of libwdi $REF */
#define WDK_DIR "$WDK_DIR"
#define WDF_VER 1011
#define COINSTALLER_DIR "wdf"
#define X64_DIR "x64"
#define LIBUSB0_DIR "$LIBUSB0_DIR"
#define LIBUSBK_DIR "$LIBUSBK_DIR"
#define OPT_M64
#define ENABLE_LOGGING 1
EOF

cd "$SRC/libwdi"
CF="-O2 -m64 -D_WIN64 -I$INC -I$SRC -I$SRC/libwdi"

echo "[1/5] installer_x64.exe";            gcc $CF installer.c -o installer_x64.exe -static -lsetupapi -lnewdev -lole32
echo "[2/5] embedder and embedded.h";      gcc $CF embedder.c -o embedder.exe; ./embedder.exe embedded.h >/dev/null
echo "[3/5] libwdi.a"
windres -i libwdi.rc -o libwdi_rc.o
for f in logging tokenizer vid_data pki libwdi_dlg libwdi; do gcc $CF -c $f.c -o $f.o; done
ar rcs libwdi.a logging.o tokenizer.o vid_data.o pki.o libwdi_dlg.o libwdi.o libwdi_rc.o
echo "[4/5] wdi-simple resources";         cd "$SRC/examples"; windres -i wdi-simple.rc -o wdi-simple_rc.o
echo "[5/5] wdi-simple.exe"
gcc $CF -I../libwdi wdi-simple.c wdi-simple_rc.o -o wdi-simple.exe -static -L../libwdi -lwdi -lsetupapi -lole32 -lntdll

mkdir -p "$ROOT/build"
cp wdi-simple.exe "$ROOT/build/wdi-simple.exe"
echo "built $ROOT/build/wdi-simple.exe (libwdi $REF, commit $HEAD)"
sha256sum "$ROOT/build/wdi-simple.exe"
