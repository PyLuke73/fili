"""Prova ogni driver su UN dispositivo reale e lo rimette a posto; stampa una tabella e tiene un log.

Pensato per le prove di piattaforma (Integrità della memoria attiva, Secure Boot attivo, Windows 10, ...): va eseguito
in un terminale con privilegi di AMMINISTRATORE, dalla radice del repository, con un dispositivo che si può permettere
di cambiare per un minuto (non tastiera, mouse o disco di avvio):

    python scripts/driver_matrix.py --vid 0E8D --pid 201C [--iface N] [--instance ID]

Per ogni driver (winusb, libusbk, libusb-win32) esegue install --yes, legge lo stato, poi restore --yes.
Alla fine rimuove solo i certificati libwdi che non esistevano quando è partito.
Stampa anche i dati di piattaforma che contano (Integrità della memoria, Secure Boot, build di Windows).
"""

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fili import cli  # noqa: E402

DRIVERS = ("winusb", "libusbk", "libusb-win32")


def fili(argv, log):
    """Esegue la CLI nello stesso processo con --json; restituisce (codice di uscita, documento)."""
    import io
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["--json", "--log-file", log] + argv, out=out, err=err)
    try:
        return code, json.loads(out.getvalue())
    except ValueError:
        return code, {"error": (err.getvalue() or out.getvalue()).strip(), "data": None, "messages": []}


def ps(script):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def platform_facts():
    return {
        "windows": ps("(Get-CimInstance Win32_OperatingSystem | % { $_.Caption + ' build ' + $_.BuildNumber + ' ' + $_.OSArchitecture })"),
        "secure_boot": ps("try { Confirm-SecureBootUEFI } catch { 'not available (legacy BIOS or no access)' }"),
        "memory_integrity_running": ps(
            "(Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\\Microsoft\\Windows\\DeviceGuard)"
            ".SecurityServicesRunning -contains 2"),
        "uac_enabled": ps("(Get-ItemProperty HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System).EnableLUA"),
    }


def ci_events(since):
    """Eventi di Code Integrity (driver bloccati) da un dato istante in poi."""
    script = ("Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-CodeIntegrity/Operational'; "
              "StartTime=[datetime]'@SINCE@'} -ErrorAction SilentlyContinue | Where-Object { $_.Id -in 3023,3033,3034,3076,3077 } | "
              "ForEach-Object { '{0} id={1} {2}' -f $_.TimeCreated, $_.Id, ($_.Message -split \"`n\")[0] }")
    return ps(script.replace("@SINCE@", since))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vid", required=True)
    ap.add_argument("--pid", required=True)
    ap.add_argument("--iface")
    ap.add_argument("--instance")
    ap.add_argument("--force", action="store_true", help="allow a protected device class")
    ap.add_argument("--log", default=os.path.join(ROOT, "logs", "driver_matrix.log"))
    a = ap.parse_args()

    if not cli._default_is_admin():
        print("Open an ELEVATED terminal (Administrator) and run this again.")
        return 3
    os.makedirs(os.path.dirname(a.log), exist_ok=True)

    target = ["--vid", a.vid, "--pid", a.pid]
    if a.iface is not None:
        target += ["--iface", a.iface]
    if a.instance:
        target += ["--instance", a.instance]
    force = ["--force"] if a.force else []

    facts = platform_facts()
    print(json.dumps(facts, indent=2))
    start = ps("(Get-Date).ToString('s')")
    certs_before = {(c["store"], c["thumbprint"]) for c in (fili(["cert-remove"], a.log)[1].get("data") or [])}

    code, doc = fili(["status"] + target, a.log)
    if code != 0:
        print("Device not usable:", doc.get("error"))
        return code
    first = doc["data"]["device"]
    print("Start: %s / %s / %s" % (first["service"], first["inf_path"], first["provider"]))

    rows, failed = [], False
    for drv in DRIVERS:
        c1, d1 = fili(["install", "--driver", drv, "--yes"] + target + force, a.log)
        now = (d1.get("data") or {}).get("after") or {}
        c2, d2 = fili(["restore", "--yes"] + target + force, a.log)
        back = (d2.get("data") or {}).get("after") or {}
        ok = c1 == 0 and c2 == 0 and back.get("service", "").lower() == first["service"].lower()
        failed |= not ok
        rows.append((drv, c1, now.get("service", "-"), now.get("problem_code", "-"), c2, back.get("service", "-"),
                     "PASS" if ok else "CHECK", (d1.get("error") or d2.get("error") or "")[:90]))

    print("\n%-13s %-8s %-10s %-8s %-8s %-10s %-6s %s" % ("driver", "inst.rc", "service", "problem", "rest.rc",
                                                           "back to", "result", "note"))
    for r in rows:
        print("%-13s %-8s %-10s %-8s %-8s %-10s %-6s %s" % r)

    events = ci_events(start)
    print("\nCode Integrity events during the run:\n" + (events or "  none"))

    # rimuove solo i certificati creati da questa esecuzione
    for c in (fili(["cert-remove"], a.log)[1].get("data") or []):
        if (c["store"], c["thumbprint"]) not in certs_before:
            fili(["cert-remove", "--thumbprint", c["thumbprint"], "--yes"], a.log)
            print("removed certificate %s (%s)" % (c["thumbprint"], c["subject"]))
    code, doc = fili(["status"] + target, a.log)
    end = (doc.get("data") or {}).get("device") or {}
    print("End: %s / %s / %s   (log: %s)" % (end.get("service"), end.get("inf_path"), end.get("provider"), a.log))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
