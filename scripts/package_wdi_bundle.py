"""Costruisce un pacchetto di ridistribuzione per un wdi-simple.exe compilato da te, con la documentazione LGPL.

fili in se' non distribuisce wdi-simple.exe. Se VUOI consegnare un binario a qualcun altro, esegui questo
script: rifiuta di produrre il pacchetto se il materiale legale non è a posto, e aggiunge
  * i testi LGPL-3.0 e GPL-3.0 (LICENSES/),
  * NOTICE e un THIRD_PARTY/libwdi-SOURCE.txt con la versione esatta, il copyright e un'offerta scritta,
  * l'archivio dei sorgenti corrispondente di libwdi (scaricato da GitHub, o indicato con --source-archive),
  * le istruzioni di compilazione (docs/building-wdi-simple.md),
  * l'elenco dei driver incorporati e delle loro licenze (da fornire con --drivers-file),
  * SHA256SUMS per ogni file.
Non installa nulla e non tocca il sistema. Non è una consulenza legale.

Usage:
  python -I scripts/package_wdi_bundle.py --exe path/to/wdi-simple.exe --out dist/wdi-bundle \
      --drivers-file drivers.txt [--libwdi-tag v1.5.1] [--source-archive libwdi-1.5.1.tar.gz]
"""

import argparse
import hashlib
import os
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TAG = "v1.5.1"
DEFAULT_COMMIT = "9b23b82a2dd1cbffc16d46c212f92c6bf8c0c602"   # commit del tag v1.5.1 (verificato su GitHub)
REPO = "https://github.com/pbatard/libwdi"

REQUIRED = ["LICENSES/LGPL-3.0.txt", "LICENSES/GPL-3.0.txt", "NOTICE", "LICENSE",
            "docs/building-wdi-simple.md"]


class BundleError(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_offer(tag, commit):
    return (
        "libwdi / wdi-simple.exe - corresponding source and written offer\n"
        "=================================================================\n\n"
        "The program wdi-simple.exe in this bundle is built from libwdi\n"
        "  Copyright (c) 2010-2023 Pete Batard <pete@akeo.ie> and other contributors (see AUTHORS in the source),\n"
        "  licensed under the GNU Lesser General Public License, version 3 or later (LICENSES/LGPL-3.0.txt,\n"
        "  which refers to LICENSES/GPL-3.0.txt).\n\n"
        "Version : %s\n"
        "Commit  : %s\n"
        "Source  : %s/tree/%s\n"
        "Archive : %s/archive/refs/tags/%s.tar.gz\n\n"
        "The complete corresponding source of that version is included in this bundle\n"
        "(THIRD_PARTY/%s), together with the build instructions (docs/building-wdi-simple.md).\n"
        "You may modify and rebuild the program and replace the wdi-simple.exe in this bundle\n"
        "with your own build. Any local modification made by whoever assembled this bundle must be\n"
        "listed in THIRD_PARTY/MODIFICATIONS.txt (if the file is missing, none were declared).\n\n"
        "Written offer: for three years from the date of distribution, whoever distributes this bundle\n"
        "will provide, on request, the complete corresponding source of wdi-simple.exe on a durable medium\n"
        "or by download, at no charge beyond the cost of the medium.\n\n"
        "fili (the front end that runs wdi-simple.exe as a separate process) is under the MIT License\n"
        "(LICENSE). fili does not link libwdi.\n"
    ) % (tag, commit, REPO, tag, REPO, tag, "libwdi-%s.tar.gz" % tag.lstrip("v"))


def build_bundle(exe, out, drivers_file, tag=DEFAULT_TAG, commit=DEFAULT_COMMIT,
                 source_archive=None, download=True, root=ROOT):
    if not os.path.isfile(exe):
        raise BundleError("wdi-simple.exe not found: %s" % exe)
    if os.path.basename(exe).lower() != "wdi-simple.exe":
        raise BundleError("the executable must be named wdi-simple.exe")
    for rel in REQUIRED:
        if not os.path.isfile(os.path.join(root, rel)):
            raise BundleError("missing legal/build file in the repository: %s" % rel)
    if not drivers_file or not os.path.isfile(drivers_file):
        raise BundleError("--drivers-file is required: a text file that lists every driver embedded in "
                          "your wdi-simple.exe (WinUSB co-installers, libusb0, libusbK, ...) with its "
                          "license and where you verified it")
    with open(drivers_file, encoding="utf-8") as f:
        if len(f.read().strip()) < 20:
            raise BundleError("--drivers-file is empty or too short to be a real list")
    if os.path.exists(out) and os.listdir(out):
        raise BundleError("output directory is not empty: %s" % out)

    # Costruisce in una cartella temporanea accanto e rinomina solo alla fine, così un errore non lascia mai
    # un pacchetto a metà (ad esempio un exe senza i suoi sorgenti) nella cartella di destinazione.
    final = os.path.abspath(out)
    out = final + ".partial"
    if os.path.exists(out):
        shutil.rmtree(out)
    try:
        _fill(exe, out, drivers_file, tag, commit, source_archive, download, root)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    if os.path.isdir(final):
        os.rmdir(final)                      # era vuota (verificato sopra)
    os.replace(out, final)
    return final


def _fill(exe, out, drivers_file, tag, commit, source_archive, download, root):
    third = os.path.join(out, "THIRD_PARTY")
    os.makedirs(third, exist_ok=True)
    os.makedirs(os.path.join(out, "LICENSES"), exist_ok=True)
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)

    shutil.copy2(exe, os.path.join(out, "wdi-simple.exe"))
    # ogni testo di licenza del repository (LGPL, GPL e il testo BSD di libusbK) accompagna il binario
    lic_dir = os.path.join(root, "LICENSES")
    for name in sorted(os.listdir(lic_dir)):
        if os.path.isfile(os.path.join(lic_dir, name)):
            shutil.copy2(os.path.join(lic_dir, name), os.path.join(out, "LICENSES", name))
    for rel in ("NOTICE", "LICENSE"):
        shutil.copy2(os.path.join(root, rel), os.path.join(out, rel))
    shutil.copy2(os.path.join(root, "docs", "building-wdi-simple.md"),
                 os.path.join(out, "docs", "building-wdi-simple.md"))
    shutil.copy2(drivers_file, os.path.join(third, "embedded-drivers.txt"))
    with open(os.path.join(third, "libwdi-SOURCE.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(source_offer(tag, commit))

    archive_name = "libwdi-%s.tar.gz" % tag.lstrip("v")
    dest = os.path.join(third, archive_name)
    if source_archive:
        if not os.path.isfile(source_archive):
            raise BundleError("source archive not found: %s" % source_archive)
        shutil.copy2(source_archive, dest)
    elif download:
        url = "%s/archive/refs/tags/%s.tar.gz" % (REPO, tag)
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
        except OSError as e:
            raise BundleError("could not download the libwdi source (%s): pass --source-archive" % e)
    else:
        raise BundleError("no source archive: the LGPL requires the corresponding source. Pass "
                          "--source-archive or allow the download")

    lines = []
    for dirpath, _, files in os.walk(out):
        for name in sorted(files):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, out).replace(os.sep, "/")
            if rel == "SHA256SUMS":
                continue
            lines.append("%s  %s" % (sha256(full), rel))
    with open(os.path.join(out, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sorted(lines, key=lambda l: l.split("  ", 1)[1])) + "\n")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--drivers-file")
    ap.add_argument("--libwdi-tag", default=DEFAULT_TAG)
    ap.add_argument("--libwdi-commit", default=DEFAULT_COMMIT,
                    help="commit of the tag you built (default: the one checked for v1.5.1)")
    ap.add_argument("--source-archive")
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args(argv)
    if a.libwdi_tag != DEFAULT_TAG and a.libwdi_commit == DEFAULT_COMMIT:
        print("error: with a tag other than %s pass --libwdi-commit with the commit you built" % DEFAULT_TAG,
              file=sys.stderr)
        return 2
    try:
        out = build_bundle(a.exe, a.out, a.drivers_file, a.libwdi_tag, a.libwdi_commit,
                           a.source_archive, not a.no_download)
    except BundleError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print("bundle written to %s (nothing was installed)" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
