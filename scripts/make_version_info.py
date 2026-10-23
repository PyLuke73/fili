"""Scrive i file di versione di Windows (nome prodotto, versione, editore) per fili.exe e fili-gui.exe.

Uso:  python -I scripts/make_version_info.py <cartella-di-uscita>
Il nome del prodotto e la versione sono gli stessi in ogni file e vengono da src/fili/__init__.py: la firma del codice
(SignPath) li controlla.
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'PyLuke73'),
      StringStruct('FileDescription', '{desc}'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 PyLuke73. GPL-3.0-or-later'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', 'fili'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main(out_dir: str) -> int:
    text = open(os.path.join(ROOT, "src", "fili", "__init__.py"), encoding="utf-8").read()
    ver = re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)
    nums = [int(x) for x in re.findall(r"\d+", ver)[:4]]
    nums += [0] * (4 - len(nums))
    os.makedirs(out_dir, exist_ok=True)
    for name, desc in (("fili", "fili - replace the driver of a USB device (command line)"),
                       ("fili-gui", "fili - replace the driver of a USB device (window)")):
        with open(os.path.join(out_dir, name + ".txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(TEMPLATE.format(v=", ".join(map(str, nums)), ver=ver, name=name, desc=desc))
    print("version info %s for fili, fili-gui in %s" % (ver, out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "version")))
