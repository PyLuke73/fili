"""Logic behind the GUI, with no tkinter: it only drives the CLI.

Every action goes through cli.main(--json), so the GUI has exactly the same safety rules as the command line
(protected classes, --yes, administrator check, post-install check). Nothing here runs a system command itself.
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
    """Run one CLI command in-process and return its JSON result."""
    out, err = io.StringIO(), io.StringIO()
    code = main(["--json"] + list(argv), out=out, err=err, **kw)
    try:
        doc = json.loads(out.getvalue())
    except ValueError:
        return Result(code or cli.EXIT_ERROR, False, (err.getvalue() or out.getvalue()).strip() or "no output",
                      None, [])
    return Result(code, bool(doc.get("ok")), doc.get("error"), doc.get("data"), doc.get("messages") or [])


def target_args(dev: dict) -> List[str]:
    """Select exactly this device/interface (the instance ID is unique)."""
    return ["--vid", "%04X" % dev["vid"], "--pid", "%04X" % dev["pid"], "--instance", dev["instance_id"]]


def install_args(action: str, dev: dict, driver: str = "winusb", *, force: bool = False, name: str = "",
                 wcid: bool = False, filter_driver: bool = False) -> List[str]:
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
    if force:
        argv.append("--force")
    return argv


def list_devices(main: Callable = cli.main, hubs: bool = False, **kw) -> Result:
    return call(["list"] + (["--hubs"] if hubs else []), main, **kw)


def preview(argv: List[str], main: Callable = cli.main, **kw) -> Result:
    """Dry run: shows the plan, changes nothing."""
    return call(argv + ["--dry-run"], main, **kw)


def apply(argv: List[str], main: Callable = cli.main, **kw) -> Result:
    """The real run. The caller must have shown the preview and obtained the user's confirmation."""
    return call(argv + ["--yes"], main, **kw)


def is_admin() -> bool:
    return cli._default_is_admin()


def relaunch_elevated(argv: Optional[List[str]] = None) -> bool:
    """Ask Windows (UAC) to start this program again as Administrator. True if the request was accepted."""
    rest = list(argv if argv is not None else sys.argv[1:])
    if not getattr(sys, "frozen", False):
        rest = ["-m", "usbdrv.gui"] + rest
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, subprocess.list2cmdline(rest),
                                               None, 1) > 32
