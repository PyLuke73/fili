"""La logica dietro la GUI, senza tkinter: si limita a pilotare la CLI.

Ogni azione passa da cli.main(--json), quindi la GUI ha esattamente le stesse regole di sicurezza della riga di
comando (classi protette, --yes, controllo dell'amministratore, verifica dopo l'installazione). Qui dentro nulla
esegue direttamente un comando di sistema.
"""

import ctypes
import io
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional

from . import cli


@dataclass
class Result:
    code: int
    ok: bool
    error: Optional[str]
    data: object
    messages: List[str]

    @property
    def meaning(self) -> str:
        return cli.EXIT_CODES.get(self.code, "?")


def call(argv: List[str], main: Callable = cli.main, **kw) -> Result:
    """Esegue un comando della CLI nello stesso processo e ne restituisce il risultato JSON."""
    out, err = io.StringIO(), io.StringIO()
    code = main(["--json"] + list(argv), out=out, err=err, **kw)
    try:
        doc = json.loads(out.getvalue())
    except ValueError:
        return Result(code or cli.EXIT_ERROR, False, (err.getvalue() or out.getvalue()).strip() or "no output",
                      None, [])
    return Result(code, bool(doc.get("ok")), doc.get("error"), doc.get("data"), doc.get("messages") or [])


def target_args(dev: dict) -> List[str]:
    """Seleziona esattamente questo dispositivo/interfaccia (l'instance ID è univoco)."""
    return ["--vid", "%04X" % dev["vid"], "--pid", "%04X" % dev["pid"], "--instance", dev["instance_id"]]


def install_args(action: str, dev: dict, driver: str = "winusb", *, force: bool = False, name: str = "",
                 wcid: bool = False, filter_driver: bool = False, all_matching: bool = False) -> List[str]:
    if action not in ("install", "reinstall", "restore"):
        raise ValueError("unknown action '%s'" % action)
    argv = [action] + target_args(dev)
    if action == "install":
        argv += ["--driver", driver]
    if action in ("install", "reinstall"):
        if name.strip():
            argv += ["--name", name.strip()]
        if wcid:
            argv.append("--wcid")
        if filter_driver:
            argv.append("--filter")
    if all_matching and action in ("install", "reinstall", "restore"):
        argv.append("--all-matching")
    if force:
        argv.append("--force")
    return argv


def list_devices(main: Callable = cli.main, hubs: bool = False, **kw) -> Result:
    return call(["list"] + (["--hubs"] if hubs else []), main, **kw)


def preview(argv: List[str], main: Callable = cli.main, **kw) -> Result:
    """Prova (dry-run): mostra il piano, non cambia nulla."""
    return call(argv + ["--dry-run"], main, **kw)


def apply(argv: List[str], main: Callable = cli.main, **kw) -> Result:
    """L'esecuzione vera. Chi chiama deve aver mostrato l'anteprima e ottenuto la conferma dell'utente."""
    return call(argv + ["--yes"], main, **kw)


def progress_label(done: int, total: int, text: str, seconds: float) -> str:
    """Riga sopra la barra: 'Step 2 of 4: testo (12 s)'."""
    return "Step %d of %d: %s (%d s)" % (done, total, text, int(seconds))


HELP_TEXT = """\
fili - what each part of the window does

DEVICE LIST
  Shows the USB devices and interfaces present now: VID:PID, interface (MI_xx, for composite devices), class,
  the driver (Windows service) in use, the status and the name. 'Refresh' reads the list again; 'Show hubs'
  also lists USB hubs. Select ONE row before using a button.

OPTIONS
  Driver        Driver to install: winusb (generic access, recommended), libusbk or libusb-win32 (libusb
                applications), usbser (serial/CDC port; only for devices that really are CDC).
  Name          Device name written in the driver package (optional).
  WCID          Match the device by its WCID compatible ID. Works only on devices that advertise it.
  Filter driver Attach libusb-win32 as a FILTER on top of the current driver (use with libusb-win32).
                Some devices stop working with it: 'Restore' removes it.
  All matching  With several identical devices (same VID:PID) change ALL of them at once. Without it only the
                selected one is changed; 'Filter driver' needs it.
  Force         Allow changing devices in protected classes (keyboard, mouse, disk, Bluetooth...). Replacing
                their driver can disable them: use it only if you are sure.

BUTTONS
  Install       Replaces the driver of the selected device/interface with the chosen one. The window first shows
                the plan (nothing is changed), then asks you to confirm. Needs Administrator.
  Reinstall     Installs again the same kind of driver the device already uses (WinUSB, libusbK...).
  Restore       Undoes the change: removes the driver package created by fili (and the libusb-win32 filter)
                so that Windows binds the original driver again.
  Diagnose      Explains why the driver of the selected device fails: problem code, setupapi.dev.log excerpt and
                recent events. With no device selected it lists all devices that report a problem. Read-only.
  Certificates  Lists the self-signed certificates created by libwdi in this PC's trusted stores (Root,
                TrustedPublisher). Read-only. To remove one use the command line: fili cert-remove.
  Licenses      Shows the third-party components and their licenses. Read-only.
  Save output   Saves the text of the lower box (plan, diagnosis, certificates, licenses) to a file.
  Help / About  This text / version, license and credits.
  Ko-fi (cup)   Opens the Ko-fi page to support the project with a donation (optional).

PROGRESS BAR
  While Install, Reinstall or Restore run, a bar shows "Step 2 of 4", what the step is and the seconds spent in it.
  The installation of the package (the first step) can take up to a minute with no change of the bar: that is normal,
  the tool does not report a percentage.

THE TEXT BOX
  Shows the result of the last action, with the exit code. Right-click for Copy / Select all. Scroll bars
  appear for long lines and long texts.

GOOD TO KNOW
  * Changes need Administrator. Without it the window is read-only; use 'Restart as Administrator'.
  * Installing adds a SELF-SIGNED certificate to this PC's trusted stores. Remove it when you no longer
    need the driver (fili cert-remove).
  * While a WinUSB/libusb driver is active, a storage device or camera is not available to Windows
    until you press Restore.
  * The same operations are available on the command line: run 'fili --help'.
"""


KOFI_URL = "https://ko-fi.com/lucacolombo35186"


def about_text() -> str:
    """Versione, licenza e crediti (i componenti di terze parti vengono da fili.licenses)."""
    from . import __version__, licenses
    lines = ["fili %s" % __version__,
             "Replace the driver of a USB device or interface (Windows), from the command line or this window.",
             "",
             "Copyright (c) 2026 PyLuke73. Released under the GNU GPL v3 or later (see LICENSE).",
             "Free software: if it is useful to you, you can support it with a donation on Ko-fi: " + KOFI_URL,
             "",
             "Credits and third-party components",
             "  fili is inspired by Zadig (https://zadig.akeo.ie). No Zadig code was used (clean-room).",
             "  The driver is installed by libwdi (https://libwdi.akeo.ie), run as a separate program."]
    for c in licenses.COMPONENTS[1:]:
        lines.append("  - %s: %s (%s)" % (c["name"], c["license"], c["role"]))
    lines += ["", licenses.NOTE]
    return "\n".join(lines)


def is_admin() -> bool:
    return cli._default_is_admin()


def relaunch_elevated(argv: Optional[List[str]] = None) -> bool:
    """Chiede a Windows (UAC) di riavviare questo programma come amministratore. True se la richiesta è stata accettata."""
    rest = list(argv if argv is not None else sys.argv[1:])
    if not getattr(sys, "frozen", False):
        rest = ["-m", "fili.gui"] + rest
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, subprocess.list2cmdline(rest),
                                               None, 1) > 32
