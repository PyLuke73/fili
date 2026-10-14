"""usbdrv command line.

Exit codes
  0 ok            1 unexpected error      2 invalid arguments / refused by a safety rule
  3 not admin     4 device not found      5 ambiguous device (several / composite)
  6 driver error  7 cancelled (no --yes)
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
from typing import Callable, List, Optional

from . import __version__, diagnose, extract, licenses, ops
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
    with it is then trusted by this machine. Remove it later with 'usbdrv cert-remove'.
  * Needs Administrator rights. Use only on devices you own and understand.
  * Undo the driver change with 'usbdrv restore'."""


RESTORE_MAX_PASSES = 5

# libwdi returns WDI_ERROR_NEEDS_ADMIN (-15) when it cannot start its installer process. Besides a missing
# elevation this was seen once on a PC with a third-party antivirus, on the very first run of a freshly
# extracted installer; it did not happen again.
WDI_NEEDS_ADMIN = (-15, 0xFFFFFFF1)
# libwdi returns WDI_ERROR_EXISTS (-13) when Windows finds no driver to update for the device; with --wcid this
# is what happens on a device that does not advertise the WCID compatible ID.
WDI_EXISTS = (-13, 0xFFFFFFF3)

ADMIN_HELP = """Administrator rights are required. Open an elevated terminal and run the same command again:
  Start menu -> right-click 'Windows Terminal' or 'PowerShell' -> Run as administrator
  (or press Win+X and choose 'Terminal (Admin)')."""


def _oem_codec() -> str:
    """Code page used by console programs (pnputil, powershell) when their output is piped."""
    try:
        return "cp%d" % ctypes.windll.kernel32.GetOEMCP()
    except Exception:
        return "cp437"


def decode_output(data: bytes) -> str:
    """Decode the output of a child process: UTF-8 if it is valid, otherwise the OEM code page
    (pnputil prints localized text such as accented letters in cp850), never failing."""
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


def _default_run(cmd: List[str]):
    res = subprocess.run(cmd, capture_output=True)
    res.stdout = decode_output(res.stdout)
    res.stderr = decode_output(res.stderr)
    return res


def _safe_streams(*streams) -> None:
    """A redirected stdout/stderr can have a code page (cp1252, cp850...) that cannot encode every
    character in the messages we print (including text coming from Windows tools): replace, never crash."""
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
    """Collects human messages and structured data; prints either text or one JSON object."""

    def __init__(self, stream, err, json_mode: bool, silent: bool):
        self.stream, self.err, self.json_mode, self.silent = stream, err, json_mode, silent
        self.messages: List[str] = []
        self.data = None
        self.error: Optional[str] = None
        self.last_rc: Optional[int] = None

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
    p.add_argument("--config", default=S, help="path of usbdrv.toml")
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
  usbdrv list                                   show the USB devices and their drivers
  usbdrv status --vid 1234 --pid 5678           show the driver bound to a device
  usbdrv install --vid 1234 --pid 5678 --driver winusb --dry-run
                                                show what would be done, run nothing
  usbdrv install --vid 1234 --pid 5678 --driver winusb --yes
                                                replace the driver (Administrator)
  usbdrv diagnose --vid 1234 --pid 5678         why does the driver fail to start?

Run 'usbdrv <command> --help' for the options and examples of each command.
""",
    "list": """\
Examples:
  usbdrv list                          devices that are present now
  usbdrv list --only-no-driver         only devices that have no driver
  usbdrv list --hubs --parents         include hubs and composite parents
  usbdrv list --json                   machine-readable output
""",
    "status": """\
Examples:
  usbdrv status --vid 1234 --pid 5678
  usbdrv status --vid 1234 --pid 5678 --iface 1          one interface of a composite device
  usbdrv status --vid 1234 --pid 5678 --instance "USB\\VID_1234&PID_5678\\SERIAL1"
                                                         one of several identical devices
""",
    "install": """\
Examples:
  usbdrv install --vid 1234 --pid 5678 --driver winusb --dry-run
      print the plan and the command, execute nothing (start here)
  usbdrv install --vid 1234 --pid 5678 --driver winusb --yes
      replace the driver (needs Administrator and --yes)
  usbdrv install --vid 1234 --pid 5678 --iface 1 --driver libusbk --yes
      replace the driver of interface 1 only
  usbdrv install --vid 1234 --pid 5678 --driver winusb --name "My device" --yes
      set the device name written in the INF
  usbdrv --log-file usbdrv.log -v install --vid 1234 --pid 5678 --driver winusb --yes
      keep a timestamped log of the run

The driver is signed with a self-signed certificate that is added to this PC's trusted
stores: see 'usbdrv cert-remove --help' to list and remove it.
""",
    "reinstall": """\
Examples:
  usbdrv reinstall --vid 1234 --pid 5678 --dry-run
  usbdrv reinstall --vid 1234 --pid 5678 --iface 1 --yes
""",
    "restore": """\
Examples:
  usbdrv restore --vid 1234 --pid 5678 --dry-run         show what would be removed
  usbdrv restore --vid 1234 --pid 5678 --yes             go back to the original driver
  usbdrv restore --vid 1234 --pid 5678 --iface 1 --yes   one interface only
""",
    "extract": """\
Examples:
  usbdrv extract --vid 1234 --pid 5678 --out pkg          write pkg\\usbdrv.inf (unsigned)
  usbdrv extract --vid 1234 --pid 5678 --iface 1 --out pkg
  usbdrv extract --vid 1234 --pid 5678 --wcid --out pkg   match the WCID compatible ID

Nothing is installed and no certificate is created: the INF is only for inspection.
""",
    "diagnose": """\
Examples:
  usbdrv diagnose                                    all devices that report a problem
  usbdrv diagnose --vid 1234 --pid 5678              one device
  usbdrv diagnose --vid 1234 --pid 5678 --since 2h   only events of the last 2 hours
  usbdrv diagnose --vid 1234 --pid 5678 --last 10 --no-events
  usbdrv --json diagnose --vid 1234 --pid 5678       machine-readable output
""",
    "cert-remove": """\
Examples:
  usbdrv cert-remove                                  list the certificates (changes nothing)
  usbdrv cert-remove --thumbprint <40 hex> --dry-run  show what would be removed
  usbdrv cert-remove --thumbprint <40 hex> --yes      remove it (Administrator)
""",
    "licenses": """\
Examples:
  usbdrv licenses                       components and licenses (changes nothing)
  usbdrv licenses --json                machine-readable output
""",
    "sample-config": """\
Examples:
  usbdrv sample-config > usbdrv.toml
  usbdrv --config usbdrv.toml list
""",
}


def _build_parser() -> argparse.ArgumentParser:
    raw = argparse.RawDescriptionHelpFormatter
    p = argparse.ArgumentParser(
        prog="usbdrv", formatter_class=raw,
        epilog=_EXAMPLES["main"] + "\n" + textwrap.fill(
            "Exit codes: " + "; ".join("%d %s" % kv for kv in EXIT_CODES.items()), width=78),
        description="Replace the driver of a USB device/interface from the command line (Windows).\n"
                    "Read-only commands: list, status, diagnose, extract, sample-config and --dry-run.")
    p.add_argument("--version", action="version", version="usbdrv " + __version__)
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
                      ("reinstall", "reinstall the driver currently bound (needs --yes and Administrator)")):
        s = add(name, help=hlp)
        _target(s)
        if name == "install":
            s.add_argument("--driver", choices=sorted(ops.DRIVERS), help="driver to install (default from config)")
        s.add_argument("--name", help="device name to put in the INF (Zadig 'Edit')")
        s.add_argument("--wcid", action="store_true", default=None, help="WCID driver (match the compatible ID)")
        s.add_argument("--filter", dest="filter_driver", action="store_true", help="libusb-win32 filter driver")
        s.add_argument("--timeout", type=int, dest="timeout_ms", help="ms to wait for pending installations")
        s.add_argument("--wdi", help="path to wdi-simple.exe (default: config, $USBDRV_WDI, PATH, build/)")
        s.add_argument("--yes", action="store_true", help="confirm; without it nothing is executed")
        s.add_argument("--dry-run", action="store_true", help="print the plan and the command, execute nothing")
        s.add_argument("--force", action="store_true", help="allow protected classes (HID, storage, Bluetooth)")

    for name in ("restore", "uninstall"):
        s = add(name, help="remove the OEM driver package of a device and re-detect it"
                           + (" (same as restore)" if name == "uninstall" else ""))
        _target(s)
        s.add_argument("--yes", action="store_true")
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--force", action="store_true", help="remove even if the service is not WinUSB/libusbK/libusb0")

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

    add("licenses", help="list third-party components and their licenses (read-only)")
    add("sample-config", help="print a sample usbdrv.toml")
    return p


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
            log_fields(logger, logging.DEBUG, "stdout: " + clip(res.stdout), stream="stdout")
        if res.stderr:
            log_fields(logger, logging.DEBUG if ok else logging.ERROR, "stderr: " + clip(res.stderr), stream="stderr")
        return res
    return wrapped


def main(argv: Optional[List[str]] = None, *, run: Optional[Callable] = None,
         is_admin: Optional[Callable[[], bool]] = None, env: Optional[dict] = None,
         out=None, err=None, setupapi_text: Optional[str] = None) -> int:
    stream = out or sys.stdout
    errs = err or sys.stderr
    _safe_streams(stream, errs)
    env = os.environ if env is None else env
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code else EXIT_OK

    o = Out(stream, errs, args.json, False)
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
        if sys.platform != "win32" and args.cmd not in ("sample-config", "licenses"):
            o.fail("usbdrv works on Windows only.")
            return o.finish(args.cmd, EXIT_ERROR)
        run = _default_run
    run = _logged_run(run, logger)
    admin = is_admin or _default_is_admin
    log_fields(logger, logging.INFO, "usbdrv %s: %s" % (__version__, args.cmd), command=args.cmd)

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
        return _cmd_install(args, cfg, dev, run, admin, env, o)
    return _cmd_restore(args, dev, devs, run, admin, o)


def _gate(args, admin, o: Out) -> Optional[int]:
    """Common checks before executing anything that changes the system. None = go ahead."""
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


def _execute(cmds: List[List[str]], run, o: Out) -> int:
    for c in cmds:
        o.say("running: " + _q(c))
        res = run(c)
        o.last_rc = res.returncode
        if res.stdout:
            o.say(res.stdout.rstrip())
        if res.returncode != 0:
            o.fail("command failed (exit %d): %s %s" % (res.returncode, _q(c), (res.stderr or "").strip()))
            return EXIT_DRIVER
    return EXIT_OK


def _post_check(dev: UsbDevice, expected_service: Optional[str], run, o: Out) -> int:
    """Re-read the device after a change and report its driver state; explain failures."""
    now = [d for d in list_devices(run) if d.instance_id.lower() == dev.instance_id.lower()]
    if not now:
        o.say("note: the device is no longer listed (it may be re-enumerating).")
        return EXIT_OK
    d = now[0]
    o.say("after: driver '%s', status %s, problem %d (%s)" % (
        d.service or "-", d.status or "-", d.problem_code, diagnose.describe_cm_code(d.problem_code)))
    o.data = dict(o.data or {}, after=d.to_dict())
    if d.problem_code:
        o.fail("the device reports a driver problem after the change: %d %s. Run 'usbdrv diagnose'."
               % (d.problem_code, diagnose.describe_cm_code(d.problem_code)))
        return EXIT_DRIVER
    if expected_service and d.service.lower() != expected_service:
        o.fail("the device uses '%s', expected '%s'. Run 'usbdrv diagnose'." % (d.service or "-", expected_service))
        return EXIT_DRIVER
    return EXIT_OK


def _cmd_install(args, cfg, dev, run, admin, env, o: Out) -> int:
    dcfg = cfg["driver"]
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

    def build(dest):
        return ops.install_command(wdi or "wdi-simple.exe", dev, driver, dest, name=args.name, wcid=wcid,
                                   silent=silent, timeout_ms=timeout, filter_driver=args.filter_driver)

    o.say("\nCommand: " + _q(build("<temp dir>")))
    gate = _gate(args, admin, o)
    if gate is not None:
        return gate
    if not wdi:
        o.fail("wdi-simple.exe not found: build it (docs/building-wdi-simple.md) or pass --wdi.")
        return EXIT_ERROR
    code = _execute([build(tempfile.mkdtemp(prefix="usbdrv_"))], run, o)
    if code != EXIT_OK and o.last_rc in WDI_NEEDS_ADMIN:
        o.error = None
        o.say("note: libwdi could not start its installer (exit -15). Retrying once; if the terminal is elevated, "
              "an antivirus scanning the new file is the likely cause.")
        code = _execute([build(tempfile.mkdtemp(prefix="usbdrv_"))], run, o)
        if code != EXIT_OK and o.last_rc in WDI_NEEDS_ADMIN:
            o.fail("libwdi reports it cannot run its installer with administrative privileges. Check that "
                   "the terminal is elevated, then retry; if it still fails, allow the temporary installer in "
                   "your antivirus.")
    if code != EXIT_OK and o.last_rc in WDI_EXISTS:
        o.fail("libwdi found no driver to install for this device (WDI_ERROR_EXISTS)."
               + (" --wcid only works on devices that advertise the WCID compatible ID: try without it." if wcid else ""))
    if code != EXIT_OK:
        return code
    return _post_check(dev, EXPECTED_SERVICE[driver], run, o)


def _cmd_restore(args, dev, devs, run, admin, o: Out) -> int:
    # 'install --filter' leaves libusb0 as an upper filter on the ORIGINAL driver: no OEM package to remove
    filt = [f for f in ops.upper_filters(run, dev) if f.lower() == ops.FILTER_SERVICE]
    try:
        cmds = ops.restore_plan(dev, devs, args.force)
    except ValueError:
        if not filt:
            raise
        cmds = []
    if filt:
        o.say("note: the libusb-win32 filter driver (libusb0) is attached to this device: it will be removed.")
        cmds = ops.filter_removal_commands(dev, ops.upper_filters(run, dev)) + cmds
    o.say("Target : " + _fmt_dev(dev))
    o.say("Package: " + dev.inf_path)
    o.say("Plan:")
    for c in cmds:
        o.say("  " + _q(c))
    gate = _gate(args, admin, o)
    if gate is not None:
        return gate
    code = _execute(cmds, run, o)
    if code != EXIT_OK:
        return code
    # After a 'reinstall' (or a repeated install) the driver store can hold SEVERAL libwdi packages for the
    # same device. Removing the bound one makes Windows bind the next one, so the device would still not be
    # back on its original driver: remove the leftovers too, a few passes at most.
    for _ in range(RESTORE_MAX_PASSES):
        now = [d for d in list_devices(run) if d.instance_id.lower() == dev.instance_id.lower()]
        if not now or not ops.is_libwdi_package(now[0]):
            break
        left = now[0]
        o.say("note: the device is now bound to another libwdi package (%s): removing it too." % left.inf_path)
        try:
            more = ops.restore_plan(left, list_devices(run), args.force)
        except ValueError as e:
            o.fail(str(e))
            return EXIT_DRIVER
        for c in more:
            o.say("  " + _q(c))
        code = _execute(more, run, o)
        if code != EXIT_OK:
            return code
    else:
        o.fail("the device is still bound to a libwdi package after %d passes. Run 'usbdrv diagnose'."
               % RESTORE_MAX_PASSES)
        return EXIT_DRIVER
    return _post_check(dev, None, run, o)


def _cmd_extract(args, cfg, dev, o: Out) -> int:
    out_dir = args.out or cfg["driver"]["extract_dir"]
    if not out_dir:
        raise ValueError("--out DIR is required (or set extract_dir in usbdrv.toml)")
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
