"""Genera dal set 1 i file che il programma usa davvero: assets/icons/fili.ico e src/fili/iconpack.py (PNG in base64).

Serve Microsoft Edge (rende gli SVG in PNG trasparenti, senza altre dipendenze) e Pillow solo per ritagliare.
Uso:  python assets/icons/build_assets.py      (dopo aver cambiato le icone del set 1)
"""
import base64
import io
import os
import struct
import subprocess
import sys
import tempfile
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SET = os.path.join(HERE, "set-1-filo")
EDGES = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
         r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
UI_SIZE = 20                                  # lato delle icone dei pulsanti
APP_SIZES = (16, 24, 32, 48, 64, 128, 256)    # dimensioni dentro fili.ico
NAMES = ["usb-device", "install", "reinstall", "restore", "diagnose", "certificates", "licenses", "save", "refresh",
         "help", "about", "support", "usb-reset", "hubs", "admin", "force", "twins", "filter"]


def render(html: str, width: int, height: int) -> Image.Image:
    edge = next(p for p in EDGES if os.path.exists(p))
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        page, out = os.path.join(tmp, "p.html"), os.path.join(tmp, "o.png")
        with open(page, "w", encoding="utf-8") as f:
            f.write("<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:transparent}"
                    "img{position:absolute;top:0}</style>" + html)
        subprocess.run([edge, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--default-background-color=00000000", "--user-data-dir=" + os.path.join(tmp, "profile"),
                        "--window-size=%d,%d" % (width, height), "--screenshot=" + out, "file:///" + page.replace("\\", "/")],
                       check=True, capture_output=True, timeout=120)
        for _ in range(100):                       # Edge puo' tornare prima di aver scritto il file
            if os.path.exists(out) and os.path.getsize(out) > 0:
                time.sleep(0.2)
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Edge non ha prodotto l'immagine")
        return Image.open(out).convert("RGBA").copy()


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def svg_url(name: str) -> str:
    return "file:///" + os.path.join(SET, name + ".svg").replace("\\", "/")


def main() -> int:
    # icone dei pulsanti: una riga di celle da 32 px, ciascuna ritagliata a UI_SIZE
    cell = 32
    html = "".join('<img src="%s" width="%d" height="%d" style="left:%dpx">' % (svg_url(n), UI_SIZE, UI_SIZE, i * cell)
                   for i, n in enumerate(NAMES))
    sheet = render(html, cell * len(NAMES), cell)
    ui = {n: sheet.crop((i * cell, 0, i * cell + UI_SIZE, UI_SIZE)) for i, n in enumerate(NAMES)}
    # icona dell'applicazione a piu' dimensioni
    app = {s: render('<img src="%s" width="%d" height="%d" style="left:0">' % (svg_url("app-icon"), s, s), s, s)
           for s in APP_SIZES}

    # fili.ico: intestazione + voci con immagini PNG (accettate da Windows Vista in poi)
    images = [png_bytes(app[s]) for s in APP_SIZES]
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for s, data in zip(APP_SIZES, images):
        entries += struct.pack("<BBBBHHII", 0 if s >= 256 else s, 0 if s >= 256 else s, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(os.path.join(HERE, "fili.ico"), "wb") as f:
        f.write(head + entries + b"".join(images))

    lines = ['"""Icone dell\'interfaccia (set 1) come PNG in base64: file generato da assets/icons/build_assets.py, non modificare."""',
             "", "UI = {"]
    for n in NAMES:
        lines.append('    "%s": "%s",' % (n, base64.b64encode(png_bytes(ui[n])).decode()))
    lines.append("}")
    lines.append("")
    lines.append("APP = {")
    for s in (32, 64):
        lines.append('    %d: "%s",' % (s, base64.b64encode(png_bytes(app[s])).decode()))
    lines.append("}")
    with open(os.path.join(ROOT, "src", "fili", "iconpack.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("fili.ico (%d dimensioni), iconpack.py (%d icone)" % (len(APP_SIZES), len(NAMES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
