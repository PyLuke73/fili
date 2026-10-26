"""Riga di comando di fili.

Codici di uscita
  0 ok            1 errore imprevisto     2 argomenti non validi / rifiutato da una regola di sicurezza
  3 non admin     4 dispositivo non trovato   5 dispositivo ambiguo (più di uno / composito)
  6 errore driver  7 annullato (senza --yes)
"""

import argparse
import ctypes
import json
import logging
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import Callable, List, Optional

from . import __version__, diagnose, extract, licenses, ops, updates
from .config import SAMPLE, ConfigError, load_config
from .devices import (AmbiguousError, NotFoundError, SelectionError, UsbDevice, filter_devices,
                      list_devices, parse_hex_id, select_target)
from .logsetup import LOGGER_NAME, clip, log_fields, parse_level, setup_logging

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_NOT_ADMIN = 0, 1, 2, 3
EXIT_NOT_FOUND, EXIT_AMBIGUOUS, EXIT_DRIVER, EXIT_CANCELLED = 4, 5, 6, 7

EXIT_CODES = {
    EXIT_OK: "ok", EXIT_ERROR: "unexpected error", EXIT_USAGE: "invalid arguments or refused by a safety rule",
    EXIT_NOT_ADMIN: "Administrator rights required", EXIT_NOT_FOUND: "device not found",
    EXIT_AMBIGUOUS: "ambiguous device (several matches or composite without --iface)",
    EXIT_DRIVER: "driver error (command failed or driver not in the expected state)",
    EXIT_CANCELLED: "cancelled (confirmation missing)",
}

EXPECTED_SERVICE = {"winusb": "winusb", "libusb-win32": "libusb0", "libusbk": "libusbk", "usbser": "usbser"}

INSTALL_WARNING = """\
WARNING - read before continuing
  * This REPLACES the driver of the single interface/device shown above.
  * libwdi builds a driver package signed with a SELF-SIGNED certificate and adds that
    certificate to this PC's trusted stores (Root and TrustedPublisher). Anything signed
    with it is then trusted by this machine. Remove it later with 'fili cert-remove'.
  * Needs Administrator rights. Use only on devices you own and understand.
  * Undo the driver change with 'fili restore'."""


RESTORE_MAX_PASSES = 5

# libwdi restituisce WDI_ERROR_NEEDS_ADMIN (-15) quando non riesce ad avviare il proprio processo di installazione. Oltre a
# una mancata elevazione, è successo una volta su un PC con un antivirus di terze parti, alla primissima esecuzione di un
# installer appena estratto; non si è ripetuto.
WDI_NEEDS_ADMIN = (-15, 0xFFFFFFF1)
# libwdi restituisce WDI_ERROR_EXISTS (-13) quando Windows non trova nessun driver da aggiornare per il dispositivo; con --wcid
# succede su un dispositivo che non dichiara il compatible ID WCID.
WDI_EXISTS = (-13, 0xFFFFFFF3)

TIMEOUT_HELP = ("note: the command did not finish and was stopped. The device or the USB stack may be stuck. Run\n"
                "'fili usb-reset' on the same device (add --dry-run to preview); if it keeps failing, unplug and\n"
                "replug the device.")

ADMIN_HELP = """Administrator rights are required. Open an elevated terminal and run the same command again:
  Start menu -> right-click 'Windows Terminal' or 'PowerShell' -> Run as administrator
  (or press Win+X and choose 'Terminal (Admin)')."""


def _oem_codec() -> str:
    """Code page usata dai programmi console (pnputil, powershell) quando il loro output viene rediretto."""
    try:
        return "cp%d" % ctypes.windll.kernel32.GetOEMCP()
    except Exception:
        return "cp437"


def decode_output(data: bytes) -> str:
    """Decodifica l'output di un processo figlio: UTF-8 se valido, altrimenti la code page OEM
    (pnputil stampa il testo localizzato, ad esempio le lettere accentate, in cp850), senza mai fallire."""
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode(_oem_codec(), errors="replace")
    except LookupError:
        return data.decode("latin-1", errors="replace")


# Codice di uscita che fili assegna a un comando esterno fermato perché non finiva (nessun programma lo restituisce).
RC_TIMEOUT = 124
# Tempo massimo, in secondi, per i programmi che possono restare appesi per sempre quando la pila USB di Windows non
# risponde ('pnputil /restart-device' è rimasto fermo oltre 15 minuti; 'install --filter' si è fermato in wdi-simple).
COMMAND_TIMEOUTS = {"pnputil": 180, "wdi-simple": 300}


def _default_run(cmd: List[str]):
    return run_command(cmd)


def run_command(cmd: List[str]):
    """Esegue un programma esterno, con il tempo massimo di COMMAND_TIMEOUTS se ce n'è uno per quel programma."""
    name = os.path.splitext(os.path.basename(cmd[0]))[0].lower() if cmd else ""
    limit = COMMAND_TIMEOUTS.get(name)
    try:
        # CREATE_NO_WINDOW: senza, nell'exe a finestre (fili-gui) ogni PowerShell/pnputil apre una console vuota
        res = subprocess.run(cmd, capture_output=True, timeout=limit,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as e:
        note = ("timed out after %d s and was stopped" % limit).encode()
        res = subprocess.CompletedProcess(cmd, RC_TIMEOUT, e.stdout or b"", (e.stderr or b"") + note)
    res.stdout = decode_output(res.stdout)
    res.stderr = decode_output(res.stderr)
    return res


def _safe_streams(*streams) -> None:
    """Uno stdout/stderr rediretto può avere una code page (cp1252, cp850...) che non sa codificare tutti i
    caratteri dei messaggi che stampiamo (anche il testo che arriva dagli strumenti di Windows): sostituisce, non va mai in crash."""
    for s in streams:
        try:
            s.reconfigure(errors="replace")
        except Exception:
            pass


def _default_is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _project_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _q(cmd: List[str]) -> str:
    return subprocess.list2cmdline(cmd)


def _fmt_dev(d: UsbDevice) -> str:
    mi = "MI_%02X" % d.mi if d.mi is not None else "-"
    return "%04X:%04X  %-6s %-12s %-10s %-8s %s" % (
        d.vid, d.pid, mi, d.cls or "-", d.service or "-", d.status or "-", d.name or "-")


class Out:
    """Raccoglie i messaggi per l'utente e i dati strutturati; stampa testo oppure un solo oggetto JSON."""

    def __init__(self, stream, err, json_mode: bool, silent: bool):
        self.stream, self.err, self.json_mode, self.silent = stream, err, json_mode, silent
        self.messages: List[str] = []
        self.data = None
        self.error: Optional[str] = None
        self.last_rc: Optional[int] = None
        self.progress: Optional[Callable[[int, int, str], None]] = None  # (passo corrente, passi totali, testo)
        self.fetch: Optional[Callable] = None     # le Release da leggere per 'update' (nei test: dati finti)
        self._done = self._total = 0

    def begin(self, total: int) -> None:
        """Avvia il contatore di avanzamento: 'total' passi noti prima di cominciare."""
        self._done, self._total = 0, total

    def extend(self, more: int) -> None:
        self._total += more

    def advance(self, text: str) -> None:
        """Annuncia il passo che inizia. Con una funzione 'progress' la chiama (la GUI); altrimenti stampa '[2/4] testo'
        su stderr, tranne con --json o --silent, così l'output da leggere con uno script resta intatto."""
        self._done += 1
        if self.progress:
            self.progress(self._done, self._total, text)
        elif not self.json_mode and not self.silent:
            print("[%d/%d] %s" % (self._done, self._total, text), file=self.err, flush=True)

    def say(self, *parts) -> None:
        text = " ".join(str(p) for p in parts)
        self.messages.append(text)
        if not self.json_mode and not self.silent:
            print(text, file=self.stream)

    def fail(self, msg: str) -> None:
        self.error = msg
        if not self.json_mode:
            print("error: " + msg, file=self.err)

    def finish(self, cmd: str, code: int) -> int:
        if self.json_mode:
            print(json.dumps({"command": cmd, "ok": code == EXIT_OK, "exit_code": code,
                              "exit_meaning": EXIT_CODES.get(code, "?"), "error": self.error,
                              "data": self.data, "messages": self.messages}, indent=2, ensure_ascii=False),
                  file=self.stream)
        return code


def _common(p: argparse.ArgumentParser) -> None:
    S = argparse.SUPPRESS
    p.add_argument("--config", default=S, help="path of fili.toml")
    p.add_argument("--log-file", default=S, help="write a timestamped log here")
    p.add_argument("--log-level", default=S, help="DEBUG, INFO, WARN, ERROR (default INFO)")
    p.add_argument("--log-format", default=S, choices=["text", "json"], help="log file format")
    p.add_argument("-v", "--verbose", action="store_true", default=S, help="DEBUG level, echoed on stderr")
    p.add_argument("--json", action="store_true", default=S, help="machine-readable output")
    p.add_argument("--silent", action="store_true", default=S, help="no informational output (errors still shown)")


def _target(p: argparse.ArgumentParser, required: bool = True) -> None:
    p.add_argument("--vid", required=required, help="vendor ID, hex (e.g. 1234)")
    p.add_argument("--pid", required=required, help="product ID, hex (e.g. 5678)")
    p.add_argument("--iface", type=int, help="interface number (MI_xx) for composite devices")
    p.add_argument("--instance", help="exact instance ID, to pick one of several identical devices")


_EXAMPLES = {
    "main": """\
Examples (1234:5678 stands for the VID:PID of your device):
  fili list                                   show the USB devices and their drivers
  fili status --vid 1234 --pid 5678           show the driver bound to a device
  fili install --vid 1234 --pid 5678 --driver winusb --dry-run
                                                show what would be done, run nothing
  fili install --vid 1234 --pid 5678 --driver winusb --yes
                                                replace the driver (Administrator)
  fili diagnose --vid 1234 --pid 5678         why does the driver fail to start?

Run 'fili <command> --help' for the options and examples of each command.
""",
    "update": """\
Examples:
  fili update                        is a newer version published? (one anonymous request to GitHub)
  fili update --json                 machine-readable: data.update_available, data.latest, data.url

fili never checks by itself. This command only reads the public list of releases; it downloads and installs nothing.
""",
    "list": """\
Examples:
  fili list                          devices that are present now
  fili list --only-no-driver         only devices that have no driver
  fili list --hubs --parents         include hubs and composite parents
  fili list --json                   machine-readable output
""",
    "status": """\
Examples:
  fili status --vid 1234 --pid 5678
  fili status --vid 1234 --pid 5678 --iface 1          one interface of a composite device
  fili status --vid 1234 --pid 5678 --instance "USB\\VID_1234&PID_5678\\SERIAL1"
                                                         one of several identical devices
""",
    "install": """\
Examples:
  fili install --vid 1234 --pid 5678 --driver winusb --dry-run
      print the plan and the command, execute nothing (start here)
  fili install --vid 1234 --pid 5678 --driver winusb --yes
      replace the driver (needs Administrator and --yes)
  fili install --vid 1234 --pid 5678 --iface 1 --driver libusbk --yes
      replace the driver of interface 1 only
  fili install --vid 1234 --pid 5678 --driver winusb --name "My device" --yes
      set the device name written in the INF
  fili --log-file fili.log -v install --vid 1234 --pid 5678 --driver winusb --yes
      keep a timestamped log of the run

The driver is signed with a self-signed certificate that is added to this PC's trusted
stores: see 'fili cert-remove --help' to list and remove it.
""",
    "reinstall": """\
Examples:
  fili reinstall --vid 1234 --pid 5678 --dry-run
  fili reinstall --vid 1234 --pid 5678 --iface 1 --yes

With a driver fili installed (WinUSB, libusbK, libusb-win32, usbser) it installs the same one again. With the
manufacturer's or Windows' own driver it removes the device and lets Windows detect it again with the best
driver in its store (no certificate is added).
""",
    "restore": """\
Examples:
  fili restore --vid 1234 --pid 5678 --dry-run         show what would be removed
  fili restore --vid 1234 --pid 5678 --yes             go back to the original driver
  fili restore --vid 1234 --pid 5678 --iface 1 --yes   one interface only
  fili restore --vid 1234 --pid 5678 --instance ID --all-matching --yes   undo 'install --all-matching'
""",
    "restart": """\
Examples:
  fili restart --vid 1234 --pid 5678 --dry-run              show what would be done
  fili restart --vid 1234 --pid 5678 --yes                  enable it if Windows shows it as disabled, otherwise restart it
  fili restart --vid 1234 --pid 5678 --instance ID --yes    one of several identical devices
  (no driver is changed; for a device that hangs use 'fili usb-reset')
""",
    "usb-reset": """\
Examples:
  fili usb-reset --vid 1234 --pid 5678 --dry-run            show what would be done (stuck commands, plan)
  fili usb-reset --vid 1234 --pid 5678 --yes                stop stuck pnputil, disable and enable the device
  fili usb-reset --vid 1234 --pid 5678 --hub --yes          restart the external hub the device is plugged into
  (the USB controller and its root hub are never restarted: that would drop keyboard and mouse too)
""",
    "extract": """\
Examples:
  fili extract --vid 1234 --pid 5678 --out pkg          write pkg\\fili.inf (unsigned)
  fili extract --vid 1234 --pid 5678 --iface 1 --out pkg
  fili extract --vid 1234 --pid 5678 --wcid --out pkg   match the WCID compatible ID

Nothing is installed and no certificate is created: the INF is only for inspection.
""",
    "diagnose": """\
Examples:
  fili diagnose                                    all devices that report a problem
  fili diagnose --vid 1234 --pid 5678              one device
  fili diagnose --vid 1234 --pid 5678 --since 2h   only events of the last 2 hours
  fili diagnose --vid 1234 --pid 5678 --last 10 --no-events
  fili --json diagnose --vid 1234 --pid 5678       machine-readable output
""",
    "cert-remove": """\
Examples:
  fili cert-remove                                  list the certificates (changes nothing)
  fili cert-remove --thumbprint <40 hex> --dry-run  show what would be removed
  fili cert-remove --thumbprint <40 hex> --yes      remove it (Administrator)
""",
    "licenses": """\
Examples:
  fili licenses                       components and licenses (changes nothing)
  fili licenses --json                machine-readable output
""",
    "sample-config": """\
Examples:
  fili sample-config > fili.toml
  fili --config fili.toml list
""",
}


def _build_parser() -> argparse.ArgumentParser:
    raw = argparse.RawDescriptionHelpFormatter
    p = argparse.ArgumentParser(
        prog="fili", formatter_class=raw,
        epilog=_EXAMPLES["main"] + "\n" + textwrap.fill(
            "Exit codes: " + "; ".join("%d %s" % kv for kv in EXIT_CODES.items()), width=78),
        description="Replace the driver of a USB device/interface from the command line (Windows).\n"
                    "Read-only commands: list, status, diagnose, extract, sample-config and --dry-run.")
    p.add_argument("--version", action="version", version="fili " + __version__)
    p.add_argument("--skill", "--skil", action="store_true",
                   help="print a complete guide for an AI agent that has to drive this tool (rules, workflow, "
                        "commands, JSON output, exit codes, recovery) and exit; with --json the text is in data.markdown")
    _common(p)
    p.set_defaults(config=None, log_file=None, log_level=None, log_format=None, verbose=False,
                   json=False, silent=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, **kw):
        sp = sub.add_parser(name, formatter_class=raw, epilog=_EXAMPLES.get("restore" if name == "uninstall" else name), **kw)
        _common(sp)
        return sp

    s = add("list", help="list present USB devices/interfaces (read-only)")
    B = argparse.BooleanOptionalAction
    s.add_argument("--only-no-driver", action=B, default=None, help="only devices without a driver")
    s.add_argument("--hubs", action=B, default=None, help="include USB hubs")
    s.add_argument("--parents", action=B, default=None, help="include composite parents")
    s.add_argument("--trim", action=B, default=None, help="trim whitespace in names")

    s = add("status", help="show the current driver of a device (read-only)")
    _target(s)

    for name, hlp in (("install", "replace the driver (needs --yes and Administrator)"),
                      ("reinstall", "reinstall the driver currently bound, also a manufacturer's driver (needs --yes and Administrator)")):
        s = add(name, help=hlp)
        _target(s)
        if name == "install":
            s.add_argument("--driver", choices=sorted(ops.DRIVERS), help="driver to install (default from config)")
        s.add_argument("--name", help="device name to put in the INF (Zadig 'Edit')")
        s.add_argument("--wcid", action="store_true", default=None, help="WCID driver (match the compatible ID)")
        s.add_argument("--filter", dest="filter_driver", action="store_true", help="libusb-win32 filter driver")
        s.add_argument("--timeout", type=int, dest="timeout_ms", help="ms to wait for pending installations")
        s.add_argument("--wdi", help="path to wdi-simple.exe (default: config, $FILI_WDI, PATH, build/)")
        s.add_argument("--yes", action="store_true", help="confirm; without it nothing is executed")
        s.add_argument("--dry-run", action="store_true", help="print the plan and the command, execute nothing")
        s.add_argument("--force", action="store_true", help="allow protected classes (HID, storage, Bluetooth)")
        s.add_argument("--all-matching", action="store_true",
                       help="with several identical devices, change ALL of them with one wdi-simple run "
                            "(default: only the selected instance)")

    for name in ("restore", "uninstall"):
        s = add(name, help="remove the OEM driver package of a device and re-detect it"
                           + (" (same as restore)" if name == "uninstall" else ""))
        _target(s)
        s.add_argument("--yes", action="store_true")
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--force", action="store_true", help="remove even if the service is not WinUSB/libusbK/libusb0")
        s.add_argument("--all-matching", action="store_true",
                       help="undo 'install --all-matching': remove a package shared with identical devices "
                            "(they go back to their original driver too)")

    s = add("restart", help="enable a disabled device, or restart it; changes no driver (needs --yes and Administrator)")
    _target(s)
    s.add_argument("--yes", action="store_true")
    s.add_argument("--dry-run", action="store_true")

    s = add("usb-reset", help="recover a device (or its hub) that does not respond; needs --yes and Administrator")
    _target(s)
    s.add_argument("--hub", action="store_true",
                   help="restart the external USB hub the device is plugged into instead of the device itself")
    s.add_argument("--stuck-after", type=int, default=ops.STUCK_AFTER_S, metavar="SECONDS",
                   help="a pnputil command working on the device for longer than this is stopped (default %d)"
                        % ops.STUCK_AFTER_S)
    s.add_argument("--yes", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--force", action="store_true",
                   help="allow protected classes, and a hub with keyboards, mice, disks or Bluetooth behind it")

    s = add("extract", help="write an UNSIGNED INF for inspection; changes nothing on the system")
    _target(s)
    s.add_argument("--out", help="output directory (default from config)")
    s.add_argument("--driver", choices=sorted(ops.DRIVERS), help="only winusb is supported")
    s.add_argument("--name")
    s.add_argument("--wcid", action="store_true", default=None)

    s = add("diagnose", help="explain why a device's driver fails (read-only)")
    _target(s, required=False)
    s.add_argument("--since", help="only log sections/events newer than this (2h, 7d, YYYY-MM-DD)")
    s.add_argument("--last", type=int, default=5, help="how many setupapi.dev.log sections to show (default 5)")
    s.add_argument("--no-events", action="store_true", help="skip the Windows event logs")
    s.add_argument("--max-events", type=int, default=10, help="how many Windows events to show (default 10)")
    s.add_argument("--setupapi", help="path of setupapi.dev.log (default C:\\Windows\\INF\\setupapi.dev.log)")

    s = add("cert-remove", help="list/remove the self-signed certificates created by libwdi")
    s.add_argument("--thumbprint", help="40-hex thumbprint to remove (omit to just list)")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--dry-run", action="store_true")

    s = add("update", help="check whether a newer version is published on GitHub (downloads and installs nothing)")
    s.add_argument("--check", action="store_true",
                   help="accepted for clarity: checking is all this command does")

    add("licenses", help="list third-party components and their licenses (read-only)")
    add("sample-config", help="print a sample fili.toml")
    return p


def _print_skill(stream, as_json: bool) -> int:
    """'fili --skill': la guida per un'AI (vedi skill.py). Non legge né modifica nulla del sistema."""
    from . import skill
    text = skill.build(__version__, EXIT_CODES)
    if as_json:
        print(json.dumps({"command": "skill", "ok": True, "exit_code": EXIT_OK, "exit_meaning": EXIT_CODES[EXIT_OK],
                          "error": None, "data": {"markdown": text}, "messages": []}, indent=2, ensure_ascii=False),
              file=stream)
    else:
        print(text, file=stream)
    return EXIT_OK


def _logged_run(run: Callable, logger: logging.Logger) -> Callable:
    def wrapped(cmd: List[str]):
        label = ("powershell <script %d chars>" % len(cmd[-1])) if cmd and cmd[0] == "powershell" and len(cmd[-1]) > 120 \
            else " ".join(cmd)
        log_fields(logger, logging.DEBUG, "exec: " + label, command=label)
        res = run(cmd)
        ok = res.returncode == 0
        log_fields(logger, logging.DEBUG if ok else logging.ERROR, "exit %d: %s" % (res.returncode, label),
                   command=label, exit_code=res.returncode)
        if res.stdout:
            log_fields(logger, logging.DEBUG if ok else logging.ERROR, "stdout: " + clip(res.stdout), stream="stdout")
        if res.stderr:
            log_fields(logger, logging.DEBUG if ok else logging.ERROR, "stderr: " + clip(res.stderr), stream="stderr")
        return res
    return wrapped


def main(argv: Optional[List[str]] = None, *, run: Optional[Callable] = None,
         is_admin: Optional[Callable[[], bool]] = None, env: Optional[dict] = None,
         out=None, err=None, setupapi_text: Optional[str] = None,
         progress: Optional[Callable[[int, int, str], None]] = None, fetch: Optional[Callable] = None) -> int:
    stream = out or sys.stdout
    errs = err or sys.stderr
    _safe_streams(stream, errs)
    words = list(sys.argv[1:] if argv is None else argv)
    if "--skill" in words or "--skil" in words:         # prima di tutto: funziona anche senza sottocomando
        return _print_skill(stream, "--json" in words)
    env = os.environ if env is None else env
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code else EXIT_OK

    o = Out(stream, errs, args.json, False)
    o.progress = progress
    o.fetch = fetch
    try:
        cfg = load_config(args.config, env)
        level = args.log_level or cfg["general"]["log_level"]
        parse_level(level)
        logger = setup_logging(level, args.log_file or cfg["general"]["log_file"],
                               args.log_format or cfg["general"]["log_format"], args.verbose, errs)
        o.silent = bool(args.silent if args.silent is not None else cfg["general"]["silent"])
    except (ConfigError, ValueError, OSError) as e:
        o.fail(str(e))
        return o.finish(args.cmd, EXIT_USAGE)

    if run is None:
        if sys.platform != "win32" and args.cmd not in ("sample-config", "licenses", "update"):
            o.fail("fili works on Windows only.")
            return o.finish(args.cmd, EXIT_ERROR)
        run = _default_run
    run = _logged_run(run, logger)
    admin = is_admin or _default_is_admin
    log_fields(logger, logging.INFO, "fili %s: %s" % (__version__, args.cmd), command=args.cmd)

    try:
        code = _dispatch(args, cfg, run, admin, env, o, logger, setupapi_text)
    except NotFoundError as e:
        o.fail(str(e))
        code = EXIT_NOT_FOUND
    except AmbiguousError as e:
        o.fail(str(e))
        code = EXIT_AMBIGUOUS
    except (ValueError, SelectionError) as e:
        o.fail(str(e))
        code = EXIT_USAGE
    except (RuntimeError, json.JSONDecodeError, OSError) as e:
        o.fail(str(e))
        code = EXIT_ERROR
    if o.error:
        log_fields(logger, logging.ERROR, "failed (exit %d): %s" % (code, o.error), exit_code=code)
    else:
        log_fields(logger, logging.INFO, "done (exit %d)" % code, exit_code=code)
    return o.finish(args.cmd, code)


def _dispatch(args, cfg, run, admin, env, o: Out, logger, setupapi_text) -> int:
    cmd = args.cmd
    if cmd == "sample-config":
        o.say(SAMPLE.rstrip())
        return EXIT_OK

    if cmd == "update":
        try:
            o.data = updates.check(__version__, o.fetch)
        except updates.UpdateError as e:
            o.fail(str(e))
            return EXIT_ERROR
        for line in updates.describe(o.data):
            o.say(line)
        return EXIT_OK

    if cmd == "licenses":
        o.data = licenses.COMPONENTS
        for c in licenses.COMPONENTS:
            o.say("%-42s %-52s %s" % (c["name"], c["license"], c["role"]))
        o.say("")
        o.say(licenses.NOTE)
        return EXIT_OK

    if cmd == "list":
        dcfg = cfg["device"]
        pick = lambda v, k: dcfg[k] if v is None else v
        devs = filter_devices(list_devices(run), only_no_driver=pick(args.only_no_driver, "only_no_driver"),
                              include_hubs=pick(args.hubs, "include_hubs"),
                              include_parents=pick(args.parents, "include_parents"),
                              trim=pick(args.trim, "trim_whitespaces"))
        o.data = [d.to_dict() for d in devs]
        o.say("VID:PID    IFACE  CLASS        DRIVER     STATUS   NAME")
        for d in devs:
            o.say(_fmt_dev(d))
        return EXIT_OK

    if cmd == "cert-remove":
        return _cmd_cert(args, run, admin, o)

    if cmd == "diagnose" and args.vid is None:
        devs = list_devices(run)
        bad = [d for d in devs if d.problem_code != 0 or not d.has_driver]
        o.data = [diagnose.build_report(d, None, [], None, 0) for d in bad]
        if not bad:
            o.say("No USB device reports a driver problem.")
        for d in bad:
            o.say("%s  %s\n    problem %d: %s\n    status  : %s" % (
                d.instance_id, d.name, d.problem_code, diagnose.describe_cm_code(d.problem_code),
                diagnose.describe_ntstatus(d.problem_status)))
        return EXIT_OK

    vid = parse_hex_id(args.vid, "VID")
    pid = parse_hex_id(args.pid, "PID")
    devs = list_devices(run)
    dev = select_target(devs, vid, pid, args.iface, args.instance)
    o.data = {"device": dev.to_dict()}

    if cmd == "status":
        o.say(_fmt_dev(dev))
        o.say("instance      : " + dev.instance_id)
        o.say("driver package: %s  version %s (%s)  provider %s" % (
            dev.inf_path or "-", dev.driver_version or "-", dev.driver_date or "-", dev.provider or "-"))
        if dev.problem_code:
            o.say("problem       : %d - %s" % (dev.problem_code, diagnose.describe_cm_code(dev.problem_code)))
        return EXIT_OK

    if cmd == "diagnose":
        return _cmd_diagnose(args, dev, run, o, setupapi_text)
    if cmd == "extract":
        return _cmd_extract(args, cfg, dev, o)
    if cmd in ("install", "reinstall"):
        return _cmd_install(args, cfg, dev, devs, run, admin, env, o)
    if cmd == "usb-reset":
        return _cmd_usb_reset(args, dev, run, admin, o)
    if cmd == "restart":
        return _cmd_restart(args, dev, run, admin, o)
    return _cmd_restore(args, dev, devs, run, admin, o)


def _gate(args, admin, o: Out) -> Optional[int]:
    """Controlli comuni prima di eseguire qualsiasi cosa che modifichi il sistema. None = si può procedere."""
    if args.dry_run:
        o.say("\n[dry-run] nothing executed.")
        if not admin():
            o.say("note: this terminal is NOT elevated; the real run needs Administrator.\n" + ADMIN_HELP)
        o.data = dict(o.data or {}, dry_run=True)
        return EXIT_OK
    if not args.yes:
        o.fail("confirmation missing: re-run with --yes to proceed (or --dry-run to preview).")
        return EXIT_CANCELLED
    if not admin():
        o.fail(ADMIN_HELP)
        return EXIT_NOT_ADMIN
    return None


def _execute(cmds: List[List[str]], run, o: Out, steps: bool = False) -> int:
    """Esegue i comandi in ordine; con steps=True ognuno è un passo del contatore (il chiamante ha fatto begin/extend)."""
    for c in cmds:
        if steps:
            o.advance("running %s" % os.path.basename(c[0]))
        o.say("running: " + _q(c))
        res = run(c)
        o.last_rc = res.returncode
        if res.stdout:
            o.say(res.stdout.rstrip())
        if res.returncode != 0:
            o.fail("command failed (exit %d): %s %s" % (res.returncode, _q(c), (res.stderr or "").strip()))
            if res.returncode == RC_TIMEOUT:
                o.say(TIMEOUT_HELP)
            return EXIT_DRIVER
    return EXIT_OK


def _post_check(dev: UsbDevice, expected_service: Optional[str], run, o: Out) -> int:
    """Rilegge il dispositivo dopo una modifica e riporta lo stato del driver; spiega i fallimenti."""
    now = [d for d in list_devices(run) if d.instance_id.lower() == dev.instance_id.lower()]
    if not now:
        o.say("note: the device is no longer listed (it may be re-enumerating). If it does not come back within "
              "a few seconds, unplug and replug it: some devices (e.g. firmware bootloaders) do not survive a "
              "driver change and Windows then reports 'device descriptor request failed'.")
        return EXIT_OK
    d = now[0]
    o.say("after: driver '%s', status %s, problem %d (%s)" % (
        d.service or "-", d.status or "-", d.problem_code, diagnose.describe_cm_code(d.problem_code)))
    o.data = dict(o.data or {}, after=d.to_dict())
    if d.problem_code:
        o.fail("the device reports a driver problem after the change: %d %s. Run 'fili diagnose'."
               % (d.problem_code, diagnose.describe_cm_code(d.problem_code)))
        return EXIT_DRIVER
    if expected_service and d.service.lower() != expected_service:
        o.fail("the device uses '%s', expected '%s'. Run 'fili diagnose'." % (d.service or "-", expected_service))
        return EXIT_DRIVER
    return EXIT_OK


WDI_STEP = "installing the driver with wdi-simple (can take up to a minute)"


def _run_wdi(build, wcid: bool, run, o: Out):
    """Esegue wdi-simple (con un secondo tentativo per l'errore -15) e spiega i fallimenti noti.
    Restituisce (codice, cartella in cui ha estratto il pacchetto)."""
    dest = tempfile.mkdtemp(prefix="fili_")
    code = _execute([build(dest)], run, o)
    if code != EXIT_OK and o.last_rc in WDI_NEEDS_ADMIN:
        o.error = None
        o.say("note: libwdi could not start its installer (exit -15). Retrying once; if the terminal is elevated, "
              "an antivirus scanning the new file is the likely cause.")
        dest = tempfile.mkdtemp(prefix="fili_")
        code = _execute([build(dest)], run, o)
        if code != EXIT_OK and o.last_rc in WDI_NEEDS_ADMIN:
            o.fail("libwdi reports it cannot run its installer with administrative privileges. Check that "
                   "the terminal is elevated, then retry; if it still fails, allow the temporary installer in "
                   "your antivirus.")
    if code != EXIT_OK and o.last_rc in WDI_EXISTS:
        o.fail("libwdi found no driver to install for this device (WDI_ERROR_EXISTS)."
               + (" --wcid only works on devices that advertise the WCID compatible ID: try without it." if wcid else ""))
    return code, dest


def _cmd_install(args, cfg, dev, devs, run, admin, env, o: Out) -> int:
    dcfg = cfg["driver"]
    if args.cmd == "reinstall" and dev.service and not ops.is_own_driver(dev):
        return _cmd_reinstall_original(args, dev, run, admin, o)
    if args.cmd == "reinstall":
        driver = ops.driver_for_reinstall(dev)
    else:
        driver = args.driver or dcfg["default_driver"]
        if driver not in ops.DRIVERS:
            raise ValueError("invalid driver '%s'" % driver)
    msg = ops.check_protected(dev)
    if msg and not args.force:
        o.fail(msg)
        return EXIT_USAGE
    # wdi-simple installa su TUTTI i dispositivi con lo stesso VID/PID: con dei gemelli si installa per singola istanza
    twins = ops.siblings(dev, devs)
    single = bool(twins) and not args.all_matching
    if single and args.filter_driver:
        o.fail("--filter changes every device with this VID:PID; with identical devices present add --all-matching "
               "(%d others: %s)." % (len(twins), ", ".join(t.instance_id for t in twins)))
        return EXIT_USAGE
    wdi = ops.find_wdi(args.wdi or cfg["tool"]["wdi_path"], env, _project_dir())
    wcid = dcfg["wcid"] if args.wcid is None else args.wcid
    timeout = args.timeout_ms if args.timeout_ms is not None else dcfg["timeout_ms"]
    silent = bool(o.silent)
    o.say("Target  : " + _fmt_dev(dev))
    o.say("Instance: " + dev.instance_id)
    o.say("Driver  : %s %s -> %s%s" % (dev.service or "none", "(%s)" % dev.driver_version if dev.driver_version else "",
                                      driver, " (WCID)" if wcid else ""))
    o.say("Tool    : " + (wdi or "wdi-simple.exe NOT FOUND (see docs/building-wdi-simple.md)"))
    o.say("")
    o.say(INSTALL_WARNING)
    if twins and not single:
        o.say("  * --all-matching: %d identical device(s) will be changed TOO: %s"
              % (len(twins), ", ".join(t.instance_id for t in twins)))

    def build(dest, extract_only=False):
        return ops.install_command(wdi or "wdi-simple.exe", dev, driver, dest, name=args.name, wcid=wcid,
                                   silent=silent, timeout_ms=timeout, filter_driver=args.filter_driver,
                                   extract_only=extract_only)

    windir = env.get("SystemRoot") or env.get("windir") or "C:\\Windows"
    if single:
        o.say("\n%d other identical device(s) are connected (%s): the driver is installed on this instance only."
              % (len(twins), ", ".join(t.instance_id for t in twins)))
        o.say("Plan:")
        o.say("  1. " + _q(build("<temp dir>", True)) + "      (signs the package; the certificate is still added)")
        o.say("  2. " + _q(ops.stage_command("<temp dir>\\fili.inf")) + "      (driver store only, binds nothing)")
        o.say("  3. DiInstallDevice on " + dev.instance_id + "      (the package, on this device only)")
    else:
        o.say("\nCommand: " + _q(build("<temp dir>")))
    gate = _gate(args, admin, o)
    if gate is not None:
        return gate
    if not wdi:
        o.fail("wdi-simple.exe not found: build it (docs/building-wdi-simple.md) or pass --wdi.")
        return EXIT_ERROR
    if single:
        o.begin(4)
        code = _install_one(build, dev, wcid, windir, run, o)
    else:
        o.begin(2)
        o.advance(WDI_STEP)
        code, _ = _run_wdi(build, wcid, run, o)
    if code != EXIT_OK:
        return code
    o.advance("checking the result")
    # con --filter il driver resta quello originale: libusb0 è solo un filtro superiore, non il servizio del dispositivo
    return _post_check(dev, None if args.filter_driver else EXPECTED_SERVICE[driver], run, o)


def _install_one(build, dev, wcid: bool, windir: str, run, o: Out) -> int:
    """Installa il driver su UNA istanza: wdi-simple -x prepara e firma il pacchetto, pnputil lo mette nell'archivio
    driver senza associarlo, DiInstallDevice lo associa a questo solo dispositivo."""
    o.advance(WDI_STEP + " (prepares and signs the package)")
    code, dest = _run_wdi(lambda d: build(d, True), wcid, run, o)
    if code != EXIT_OK:
        return code
    inf = os.path.join(dest, "fili.inf")
    o.advance("adding the package to the driver store (pnputil)")
    stage = ops.stage_command(inf)
    o.say("running: " + _q(stage))
    res = run(stage)
    if res.stdout:
        o.say(res.stdout.rstrip())
    published = ops.published_name(res.stdout) if res.returncode == 0 else None
    if res.returncode != 0 or not published:
        o.fail("pnputil could not add the package to the driver store (exit %d): %s"
               % (res.returncode, ((res.stderr or "") + (res.stdout or "")).strip()))
        return EXIT_DRIVER
    bind = ops.bind_command(dev, published, windir)
    o.advance("installing the driver on this device only")
    o.say("running: DiInstallDevice %s with %s" % (dev.instance_id, published))
    res = run(bind)
    if res.stdout:
        o.say(res.stdout.rstrip())
    if res.returncode != 0:
        o.fail("installing %s on %s failed: %s. The package stays in the driver store: remove it with "
               "'pnputil /delete-driver %s /uninstall'." % (published, dev.instance_id, (res.stderr or "").strip(),
                                                           published))
        return EXIT_DRIVER
    return EXIT_OK


def _cmd_restore(args, dev, devs, run, admin, o: Out) -> int:
    # 'install --filter' lascia libusb0 come filtro superiore sul driver ORIGINALE: nessun pacchetto OEM da rimuovere
    filt = [f for f in ops.upper_filters(run, dev) if f.lower() == ops.FILTER_SERVICE]
    try:
        cmds = ops.restore_plan(dev, devs, args.force, args.all_matching)
    except ValueError:
        if not filt:
            raise
        cmds = []
    if filt:
        o.say("note: the libusb-win32 filter driver (libusb0) is attached to this device: it will be removed.")
        cmds = ops.filter_removal_commands(dev, ops.upper_filters(run, dev)) + cmds
    o.say("Target : " + _fmt_dev(dev))
    o.say("Package: " + dev.inf_path)
    if args.all_matching:
        shared = [d.instance_id for d in devs if d.instance_id != dev.instance_id
                  and d.inf_path.lower() == (dev.inf_path or "").lower()]
        if shared:
            o.say("--all-matching: %d identical device(s) sharing this package will go back to their original driver TOO: %s"
                  % (len(shared), ", ".join(shared)))
    o.say("Plan:")
    for c in cmds:
        o.say("  " + _q(c))
    gate = _gate(args, admin, o)
    if gate is not None:
        return gate
    o.begin(len(cmds) + 1)
    code = _execute(cmds, run, o, steps=True)
    if code != EXIT_OK:
        return code
    # Dopo un 'reinstall' (o un'installazione ripetuta) il driver store può contenere PIÙ pacchetti libwdi per lo
    # stesso dispositivo. Rimuovere quello associato fa associare a Windows il successivo, quindi il dispositivo non
    # tornerebbe sul driver originale: rimuove anche gli avanzi, al massimo in qualche passata.
    for _ in range(RESTORE_MAX_PASSES):
        now = [d for d in list_devices(run) if d.instance_id.lower() == dev.instance_id.lower()]
        if not now or not ops.is_libwdi_package(now[0]):
            break
        left = now[0]
        o.say("note: the device is now bound to another libwdi package (%s): removing it too." % left.inf_path)
        try:
            more = ops.restore_plan(left, list_devices(run), args.force, args.all_matching)
        except ValueError as e:
            o.fail(str(e))
            return EXIT_DRIVER
        for c in more:
            o.say("  " + _q(c))
        o.extend(len(more))
        code = _execute(more, run, o, steps=True)
        if code != EXIT_OK:
            return code
    else:
        o.fail("the device is still bound to a libwdi package after %d passes. Run 'fili diagnose'."
               % RESTORE_MAX_PASSES)
        return EXIT_DRIVER
    o.advance("checking the result")
    return _post_check(dev, None, run, o)


RESET_WAIT = (5, 3)   # (tentativi, secondi tra l'uno e l'altro) per veder tornare il dispositivo dopo il ripristino


def _cmd_reinstall_original(args, dev, run, admin, o: Out) -> int:
    """'reinstall' di un dispositivo che usa il driver del produttore (o di Windows): non c'è nulla da compilare né
    certificati da aggiungere; si toglie il dispositivo e Windows lo rileva di nuovo con il driver migliore dell'archivio."""
    msg = ops.check_protected(dev)
    if msg and not args.force:
        o.fail(msg)
        return EXIT_USAGE
    cmds = ops.reinstall_original_plan(dev)
    o.say("Target  : " + _fmt_dev(dev))
    o.say("Instance: " + dev.instance_id)
    o.say("Driver  : %s %s is not a driver installed by fili. No driver is built and no certificate is added: Windows "
          "will detect the device again and bind the best driver in its driver store (normally the same one)."
          % (dev.service, "(%s)" % dev.driver_version if dev.driver_version else ""))
    o.say("The device disappears for a few seconds. Settings stored for this device instance (for example it being "
          "disabled) are reset.")
    o.say("Plan:")
    for c in cmds:
        o.say("  " + _q(c))
    gate = _gate(args, admin, o)
    if gate is not None:
        return gate
    o.begin(len(cmds) + 2)
    code = _execute(cmds, run, o, steps=True)
    if code != EXIT_OK:
        return code
    o.advance("waiting for the device to come back")
    tries, pause = RESET_WAIT
    for i in range(tries):
        if [d for d in list_devices(run) if d.instance_id.lower() == dev.instance_id.lower()]:
            break
        if i + 1 < tries:
            time.sleep(pause)
    else:
        o.fail("the device is not listed after the reinstallation. Unplug it and plug it in again; if it does not "
               "come back, try another port or run 'fili diagnose'.")
        return EXIT_DRIVER
    return _post_check(dev, None, run, o)


def _cmd_restart(args, dev, run, admin, o: Out) -> int:
    """Riattiva un dispositivo disattivato (problema 22) o lo riavvia. Non cambia driver: per questo non vale il blocco
    delle classi protette (riattivare un mouse disattivato è proprio il caso d'uso)."""
    cmds = ops.restart_plan(dev)
    o.say("Target  : " + _fmt_dev(dev))
    o.say("Instance: " + dev.instance_id)
    if dev.problem_code == ops.CM_PROB_DISABLED:
        o.say("Windows shows this device as disabled: it will be enabled.")
    o.say("Plan:")
    for c in cmds:
        o.say("  " + _q(c))
    gate = _gate(args, admin, o)
    if gate is not None:
        return gate
    o.begin(len(cmds) + 1)
    code = _execute(cmds, run, o, steps=True)
    if code != EXIT_OK:
        return code
    o.advance("checking the result")
    return _post_check(dev, None, run, o)


def _cmd_usb_reset(args, dev, run, admin, o: Out) -> int:
    """Recupero di un dispositivo (o del suo hub) che non risponde: ferma i pnputil appesi su di lui, poi lo disattiva e
    lo riattiva. Il controller USB e l'hub radice non si toccano mai."""
    msg = ops.check_protected(dev)
    if msg and not args.force:
        o.fail(msg)
        return EXIT_USAGE
    stuck = ops.find_stuck(run, dev)
    hub = kids = None
    if args.hub:
        hub = ops.parent_hub(ops.ancestors(run, dev))
        if hub is None:
            o.fail("this device is not behind an external USB hub (it is on a root port), so --hub does not apply. "
                   "fili never restarts the USB controller or its root hub: that would also drop keyboard and mouse.")
            return EXIT_USAGE
        kids = ops.descendants(run, hub["InstanceId"])
        risky = ops.protected_below(kids)
        if risky and not args.force:
            o.fail("restarting the hub %s would also disconnect: %s. Use --force only if you are sure."
                   % (hub["InstanceId"], ", ".join("%s (%s)" % (k["Name"] or k["InstanceId"], k["Class"]) for k in risky)))
            return EXIT_USAGE
    o.say("Target  : " + _fmt_dev(dev))
    o.say("Instance: " + dev.instance_id)
    if hub:
        o.say("Hub     : %s  %s" % (hub["InstanceId"], hub.get("Name") or ""))
        o.say("Behind it: %d device(s), all of them will be disconnected for a moment: %s" % (
            len(kids), ", ".join(k["Name"] or k["InstanceId"] for k in kids) or "-"))
    for p in stuck:
        old_enough = int(p.get("Seconds", 0)) >= args.stuck_after
        o.say("pnputil %d has been working on this device for %d s: %s" % (
            int(p["Pid"]), int(p.get("Seconds", 0)), "stuck, it will be stopped" if old_enough
            else "younger than --stuck-after %d, left alone" % args.stuck_after))
    if not stuck:
        o.say("No pnputil command is working on this device.")
    cmds = ops.usb_reset_plan(dev, stuck, hub, args.stuck_after)
    o.data = dict(o.data or {}, stuck=stuck, hub=hub)
    o.say("Plan:")
    for c in cmds:
        o.say("  " + _q(c))
    gate = _gate(args, admin, o)
    if gate is not None:
        return gate
    o.begin(len(cmds) + 1)
    rest = []
    for c in cmds:
        if c[0] != "taskkill":
            rest.append(c)
            continue
        o.advance("stopping the stuck command")
        o.say("running: " + _q(c))
        res = run(c)
        if res.returncode != 0:      # il processo può essere finito da solo nel frattempo: non è un errore
            o.say("note: could not stop it (exit %d): %s" % (res.returncode, (res.stderr or res.stdout or "").strip()))
    code = _execute(rest, run, o, steps=True)
    if code != EXIT_OK:
        return code
    o.advance("waiting for the device to come back")
    tries, pause = RESET_WAIT
    for i in range(tries):
        if [d for d in list_devices(run) if d.instance_id.lower() == dev.instance_id.lower()]:
            break
        if i + 1 < tries:
            time.sleep(pause)
    else:
        o.fail("the device is not listed after the reset. Unplug it and plug it in again; if it does not come back, "
               "try another port or run 'fili diagnose'.")
        return EXIT_DRIVER
    return _post_check(dev, None, run, o)


def _cmd_extract(args, cfg, dev, o: Out) -> int:
    out_dir = args.out or cfg["driver"]["extract_dir"]
    if not out_dir:
        raise ValueError("--out DIR is required (or set extract_dir in fili.toml)")
    driver = args.driver or "winusb"
    wcid = cfg["driver"]["wcid"] if args.wcid is None else args.wcid
    path = extract.extract_package(dev, out_dir, driver, name=args.name, wcid=wcid)
    o.data = dict(o.data or {}, inf=path)
    o.say("Wrote UNSIGNED INF: " + path)
    o.say("Nothing was installed and no certificate was created: the system is unchanged.")
    return EXIT_OK


def _cmd_diagnose(args, dev, run, o: Out, setupapi_text: Optional[str]) -> int:
    since = diagnose.parse_since(args.since) if args.since else None
    text = setupapi_text
    note = None
    if text is None:
        path = args.setupapi or diagnose.SETUPAPI_LOG
        try:
            text = diagnose.read_setupapi(path)
        except OSError as e:
            note = "cannot read %s: %s" % (path, e)
    events = [] if args.no_events else diagnose.read_events(run, dev, since or diagnose.default_since(),
                                                            max(1, args.max_events))
    rep = diagnose.build_report(dev, text, events, since, args.last)
    o.data = rep
    o.say(_fmt_dev(dev))
    o.say("problem code : %d - %s" % (dev.problem_code, diagnose.describe_cm_code(dev.problem_code)))
    o.say("problem status: " + diagnose.describe_ntstatus(dev.problem_status))
    o.say("driver       : service '%s', package %s, version %s (%s), provider %s" % (
        dev.service or "-", dev.inf_path or "-", dev.driver_version or "-", dev.driver_date or "-", dev.provider or "-"))
    if note:
        o.say("setupapi.dev.log: " + note)
    for s in rep["setupapi_sections"]:
        o.say("\n--- setupapi.dev.log: %s (%s)" % (s["title"], s["start"] or "?"))
        for line in s["lines"][:60]:
            o.say("  " + line)
        if len(s["lines"]) > 60:
            o.say("  ... (%d more lines)" % (len(s["lines"]) - 60))
    if not rep["setupapi_sections"] and not note:
        o.say("setupapi.dev.log: no matching sections.")
    for ev in events:
        o.say("event %s %s id=%s %s: %s" % (ev.get("Time"), ev.get("Log"), ev.get("Id"), ev.get("Level"), ev.get("Message")))
    return EXIT_OK


def _cmd_cert(args, run, admin, o: Out) -> int:
    certs = ops.list_certs(run)
    if not args.thumbprint:
        o.data = [c.__dict__ for c in certs]
        if not certs:
            o.say("No libwdi self-signed certificates found.")
        for c in certs:
            o.say("%-16s %s  %s  (expires %s)" % (c.store, c.thumbprint, c.subject, c.not_after))
        return EXIT_OK
    cmds = ops.cert_removal_commands(certs, args.thumbprint)
    o.say("Plan:")
    for c in cmds:
        o.say("  " + c[-1])
    gate = _gate(args, admin, o)
    if gate is not None:
        return gate
    return _execute(cmds, run, o)
