"""Toglie da un albero sorgente di libwdi i co-installer Microsoft (WdfCoInstaller01011.dll, winusbcoinstaller2.dll).

Servono solo a Windows XP/Vista: da Windows 10 il framework WDF e winusb.sys sono già nel sistema. Senza di loro il
binario non ridistribuisce codice Microsoft soggetto alla manleva del WDK (docs/licenza.md). Modifica soltanto:
  libwdi/embedder_files.h   (non incorpora più i due file del WDK)
  libwdi/winusb.inf.in      (niente sezioni CoInstallers, niente righe dei co-installer)
  libwdi/libusbk.inf.in     (idem)
  libwdi/winusb.cat.in, libwdi/libusbk.cat.in   (elenchi dei file del catalogo: niente co-installer)
Uso: python strip_coinstallers.py <cartella-sorgente-libwdi>. È idempotente solo su file appena ripristinati
(lo script di build li ripristina con git checkout prima di chiamarlo).
"""
import os
import re
import sys

COINSTALLER_RE = re.compile(r"coinstaller", re.I)
SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]")


def strip_inf(text):
    out, skip = [], False
    for line in text.splitlines(keepends=True):
        m = SECTION_RE.match(line)
        if m:
            skip = bool(COINSTALLER_RE.search(m.group("name")))
        if skip or COINSTALLER_RE.search(line):
            continue
        out.append(line)
    return "".join(out)


def strip_embedder(text):
    # il blocco "// WinUSB" ... "#endif	// WDK_DIR" elenca soltanto i file del WDK
    new, n = re.subn(r"// WinUSB\r?\n#if defined\(WDK_DIR\).*?#endif[ \t]*// WDK_DIR\r?\n", "// WinUSB: nessun co-installer\n",
                     text, flags=re.S)
    if n != 1:
        raise SystemExit("embedder_files.h: blocco WinUSB non trovato (versione di libwdi diversa?)")
    return new


def patch(path, fn):
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as f:
        text = f.read()
    new = fn(text)
    if new == text:
        raise SystemExit("nessuna modifica in %s: già patchato o formato inatteso" % path)
    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(new)


def main(src):
    d = os.path.join(src, "libwdi")
    patch(os.path.join(d, "embedder_files.h"), strip_embedder)
    patch(os.path.join(d, "winusb.inf.in"), strip_inf)
    patch(os.path.join(d, "libusbk.inf.in"), strip_inf)
    for name in ("winusb.cat.in", "libusbk.cat.in"):
        patch(os.path.join(d, name), strip_inf)  # senza sezioni: toglie solo le righe dei co-installer


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
