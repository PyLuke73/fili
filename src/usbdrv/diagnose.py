"""Read-only diagnostics for a USB device whose driver misbehaves."""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from .devices import UsbDevice

SETUPAPI_LOG = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "INF", "setupapi.dev.log")

# Device Manager (ConfigManagerErrorCode) problem codes.
CM_CODES = {
    0: "OK: no problem reported",
    1: "NOT_CONFIGURED: the device is not configured correctly",
    3: "OUT_OF_MEMORY: the driver may be corrupted or the system is low on memory",
    10: "FAILED_START: the device cannot start (driver loaded but start failed)",
    12: "NORMAL_CONFLICT: not enough free resources",
    14: "NEED_RESTART: a restart is needed to work properly",
    18: "REINSTALL: reinstall the drivers for this device",
    19: "REGISTRY: Windows cannot start the device (registry configuration problem)",
    21: "WILL_BE_REMOVED: Windows is removing this device",
    22: "DISABLED: the device is disabled",
    24: "DEVICE_NOT_THERE: the device is missing, not working properly, or lacks all drivers",
    28: "FAILED_INSTALL: the drivers for this device are not installed",
    29: "HARDWARE_DISABLED: disabled because its firmware did not give it the required resources",
    31: "FAILED_ADD: the device is not working properly (Windows cannot load its driver)",
    32: "DISABLED_SERVICE: the driver service is disabled",
    33: "TRANSLATION_FAILED: cannot determine the resources the device needs",
    34: "NO_SOFTCONFIG: the device needs manually configured resources",
    35: "BIOS_TABLE: the firmware tables lack information for the device",
    36: "IRQ_TRANSLATION_FAILED: interrupt request translation failed",
    37: "FAILED_DRIVER_ENTRY: the driver returned a failure from DriverEntry",
    38: "DRIVER_FAILED_PRIOR_UNLOAD: a previous instance of the driver is still in memory",
    39: "DRIVER_FAILED_LOAD: the driver is corrupted or missing",
    40: "DRIVER_SERVICE_KEY_INVALID: the service registry key is missing or corrupted",
    41: "LEGACY_SERVICE_NO_DEVICES: the driver loaded but the hardware was not found",
    42: "DUPLICATE_DEVICE: a duplicate device is already running",
    43: "FAILED_POST_START: Windows stopped the device because it reported a problem (e.g. USB request failed)",
    44: "HALTED: an application or service shut the device down",
    45: "PHANTOM: the device is not connected",
    46: "SYSTEM_SHUTDOWN: not available, Windows is shutting down",
    47: "HELD_FOR_EJECT: prepared for safe removal",
    48: "DRIVER_BLOCKED: the driver was blocked from starting",
    49: "REGISTRY_TOO_LARGE: the system hive exceeds its size limit",
    50: "SETPROPERTIES_FAILED: cannot apply the device's properties",
    51: "WAITING_ON_DEPENDENCY: the device is waiting on another device to start",
    52: "UNSIGNED_DRIVER: Windows cannot verify the driver's digital signature",
    53: "USED_BY_DEBUGGER: reserved for use by a debugger",
    54: "DEVICE_RESET: the device failed and is being reset",
}

# A few common NTSTATUS values seen in DEVPKEY_Device_ProblemStatus.
NTSTATUS = {
    0xC0000001: "STATUS_UNSUCCESSFUL",
    0xC000000D: "STATUS_INVALID_PARAMETER",
    0xC0000022: "STATUS_ACCESS_DENIED",
    0xC0000034: "STATUS_OBJECT_NAME_NOT_FOUND",
    0xC000009A: "STATUS_INSUFFICIENT_RESOURCES",
    0xC00000E5: "STATUS_INTERNAL_ERROR",
    0xC0000185: "STATUS_IO_DEVICE_ERROR",
    0xC0000365: "STATUS_DEVICE_NOT_READY",
    0xC0000428: "STATUS_INVALID_IMAGE_HASH (signature problem)",
    0xC0000450: "STATUS_DRIVER_BLOCKED",
}

SECTION_START_RE = re.compile(r"^>>>\s+\[(?P<title>.*)\]\s*$")
SECTION_TIME_RE = re.compile(r"^>>>\s+Section start (?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")
SECTION_END_RE = re.compile(r"^<<<\s+Section end")


def default_since(now: Optional[datetime] = None) -> datetime:
    """Default window for event-log queries: the last 7 days."""
    return (now or datetime.now()) - timedelta(days=7)


def describe_cm_code(code: int) -> str:
    return CM_CODES.get(code, "code %d: not in the table (see Microsoft 'Device Manager error codes')" % code)


def describe_ntstatus(value: Optional[int]) -> str:
    if value is None:
        return "-"
    v = value & 0xFFFFFFFF
    return "0x%08X %s" % (v, NTSTATUS.get(v, "(unknown NTSTATUS)"))


def parse_since(text: str, now: Optional[datetime] = None) -> datetime:
    """'2h', '3d', '30m', 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'."""
    now = now or datetime.now()
    t = text.strip()
    m = re.fullmatch(r"(\d+)([mhd])", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        unit_name = {"m": "minutes", "h": "hours", "d": "days"}[unit]
        return now - timedelta(**{unit_name: n})
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            pass
    raise ValueError("invalid --since '%s': use 30m, 2h, 7d, YYYY-MM-DD or 'YYYY-MM-DD HH:MM'" % text)


def split_sections(log_text: str) -> List[dict]:
    """Split setupapi.dev.log into sections: {title, start(datetime|None), lines}."""
    sections, cur = [], None
    for line in log_text.splitlines():
        m = SECTION_START_RE.match(line)
        if m:
            cur = {"title": m.group("title"), "start": None, "lines": [line]}
            sections.append(cur)
            continue
        if cur is None:
            continue
        cur["lines"].append(line)
        t = SECTION_TIME_RE.match(line)
        if t and cur["start"] is None:
            cur["start"] = datetime.strptime(t.group("ts"), "%Y/%m/%d %H:%M:%S")
        if SECTION_END_RE.match(line):
            cur = None
    return sections


def device_needles(dev: UsbDevice) -> List[str]:
    needles = ["VID_%04X&PID_%04X" % (dev.vid, dev.pid)]
    if dev.serial:
        needles.append(dev.serial)
    return [n.lower() for n in needles]


def relevant_sections(log_text: str, dev: UsbDevice, since: Optional[datetime] = None,
                      last: int = 5) -> List[dict]:
    """Last N sections of setupapi.dev.log that mention the device's VID/PID or instance."""
    needle_ids = device_needles(dev)
    vp = needle_ids[0]
    out = []
    for s in split_sections(log_text):
        blob = "\n".join(s["lines"]).lower()
        if vp not in blob and dev.instance_id.lower() not in blob:
            continue
        if since and s["start"] and s["start"] < since:
            continue
        out.append(s)
    return out[-last:]


def read_setupapi(path: str = SETUPAPI_LOG) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


EVENT_LOGS = ("Microsoft-Windows-Kernel-PnP/Configuration",
              "Microsoft-Windows-DriverFrameworks-UserMode/Operational")


def event_script(dev: UsbDevice, since: datetime, max_events: int = 20) -> str:
    return r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$start = [datetime]'%s'
$vp = 'VID_%04X&PID_%04X'
$rows = @(foreach ($log in %s) {
  Get-WinEvent -FilterHashtable @{ LogName = $log; StartTime = $start } -MaxEvents 2000 |
    Where-Object { $_.Message -match [regex]::Escape($vp) } | Select-Object -First %d |
    ForEach-Object { [pscustomobject]@{ Log = $log; Time = $_.TimeCreated.ToString('s'); Id = $_.Id; Level = $_.LevelDisplayName; Message = ($_.Message -replace '\s+', ' ').Substring(0, [Math]::Min(400, $_.Message.Length)) } }
})
ConvertTo-Json -InputObject $rows -Compress
""" % (since.strftime("%Y-%m-%dT%H:%M:%S"), dev.vid, dev.pid,
       ",".join("'%s'" % n for n in EVENT_LOGS), max_events)


def read_events(run: Callable, dev: UsbDevice, since: datetime, max_events: int = 20) -> List[dict]:
    """Best effort: some logs are disabled or need Administrator; returns [] in that case."""
    res = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", event_script(dev, since, max_events)])
    if res.returncode != 0 or not (res.stdout or "").strip():
        return []
    data = json.loads(res.stdout)
    return [data] if isinstance(data, dict) else data


def build_report(dev: UsbDevice, setupapi_text: Optional[str], events: List[dict],
                 since: Optional[datetime], last: int) -> dict:
    sections = relevant_sections(setupapi_text, dev, since, last) if setupapi_text else []
    return {
        "device": dev.to_dict(),
        "problem": {"code": dev.problem_code, "meaning": describe_cm_code(dev.problem_code),
                    "status": describe_ntstatus(dev.problem_status)},
        "driver": {"service": dev.service, "inf": dev.inf_path, "version": dev.driver_version,
                   "date": dev.driver_date, "provider": dev.provider},
        "setupapi_sections": [{"title": s["title"], "start": s["start"].isoformat() if s["start"] else None,
                               "lines": s["lines"]} for s in sections],
        "events": events,
    }
