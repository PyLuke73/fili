"""Elenco e selezione dei dispositivi/interfacce USB (sola lettura)."""

import json
import re
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional

INSTANCE_RE = re.compile(
    r"^USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})(?:&MI_([0-9A-F]{2}))?\\(.+)$",
    re.IGNORECASE,
)

HUB_SERVICES = {"usbhub", "usbhub3", "usbhub4"}
CM_PROB_NOT_INSTALLED = 28

LIST_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$keys = 'DEVPKEY_Device_ProblemStatus','DEVPKEY_Device_Service','DEVPKEY_Device_DriverInfPath',
        'DEVPKEY_Device_DriverVersion','DEVPKEY_Device_DriverDate','DEVPKEY_Device_DriverProvider'
$devs = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\*' })
# una sola interrogazione per tutte le proprietà: una per dispositivo costava ~1 s ciascuna (19 s contro 2 s)
$byId = @{}
if ($devs.Count) {
  foreach ($x in (Get-PnpDeviceProperty -InstanceId @($devs | ForEach-Object { $_.InstanceId }) -KeyName $keys)) {
    if (-not $byId.ContainsKey($x.InstanceId)) { $byId[$x.InstanceId] = @{} }
    $byId[$x.InstanceId][$x.KeyName] = $x.Data
  }
}
$rows = @($devs | ForEach-Object {
  $id = $_.InstanceId
  $p = $byId[$id]
  if (-not $p) {   # la richiesta cumulativa a volte salta un dispositivo: lo interroga da solo
    $p = @{}
    foreach ($x in (Get-PnpDeviceProperty -InstanceId $id -KeyName $keys)) { $p[$x.KeyName] = $x.Data }
  }
  $dd = $p['DEVPKEY_Device_DriverDate']
  [pscustomobject]@{
    InstanceId    = $id
    Class         = $_.Class
    Status        = [string]$_.Status
    FriendlyName  = $_.FriendlyName
    ProblemCode   = [int]$_.ConfigManagerErrorCode
    ProblemStatus = $p['DEVPKEY_Device_ProblemStatus']
    Service       = $p['DEVPKEY_Device_Service']
    InfPath       = $p['DEVPKEY_Device_DriverInfPath']
    DriverVersion = $p['DEVPKEY_Device_DriverVersion']
    DriverDate    = if ($dd) { ([datetime]$dd).ToString('yyyy-MM-dd') } else { '' }
    Provider      = $p['DEVPKEY_Device_DriverProvider']
  }
})
ConvertTo-Json -InputObject $rows -Compress
"""


class SelectionError(Exception):
    """La richiesta VID/PID/interfaccia non identifica esattamente un dispositivo."""


class NotFoundError(SelectionError):
    pass


class AmbiguousError(SelectionError):
    pass


@dataclass(frozen=True)
class UsbDevice:
    instance_id: str
    vid: int
    pid: int
    mi: Optional[int]
    serial: str
    cls: str
    status: str
    name: str
    service: str
    inf_path: str
    driver_version: str
    driver_date: str
    provider: str
    problem_code: int
    problem_status: Optional[int]

    @property
    def vidpid(self) -> str:
        return "%04X:%04X" % (self.vid, self.pid)

    @property
    def has_driver(self) -> bool:
        return bool(self.service) and self.problem_code != CM_PROB_NOT_INSTALLED

    @property
    def is_hub(self) -> bool:
        return self.service.lower() in HUB_SERVICES

    def to_dict(self) -> dict:
        d = asdict(self)
        d["vidpid"] = self.vidpid
        return d


def parse_hex_id(text: str, what: str = "ID") -> int:
    """Accetta '0483', '0x0483', '483'. Restituisce un int in 0..0xFFFF."""
    t = text.strip().lower()
    if t.startswith("0x"):
        t = t[2:]
    if not re.fullmatch(r"[0-9a-f]{1,4}", t):
        raise ValueError("invalid %s '%s': expected 1-4 hex digits (e.g. 1234)" % (what, text))
    return int(t, 16)


def _to_int(v) -> Optional[int]:
    try:
        return None if v in (None, "") else int(v)
    except (TypeError, ValueError):
        return None


def parse_device_list(json_text: str) -> List[UsbDevice]:
    """Interpreta il JSON prodotto da LIST_SCRIPT. Le voci senza VID/PID (root hub...) vengono saltate."""
    json_text = (json_text or "").strip()
    if not json_text:
        return []
    data = json.loads(json_text)
    if isinstance(data, dict):
        data = [data]
    devices = []
    for row in data or []:
        m = INSTANCE_RE.match(row.get("InstanceId") or "")
        if not m:
            continue
        devices.append(
            UsbDevice(
                instance_id=row["InstanceId"],
                vid=int(m.group(1), 16),
                pid=int(m.group(2), 16),
                mi=int(m.group(3), 16) if m.group(3) else None,
                serial=m.group(4),
                cls=row.get("Class") or "",
                status=row.get("Status") or "",
                name=row.get("FriendlyName") or "",
                service=row.get("Service") or "",
                inf_path=row.get("InfPath") or "",
                driver_version=row.get("DriverVersion") or "",
                driver_date=row.get("DriverDate") or "",
                provider=row.get("Provider") or "",
                problem_code=_to_int(row.get("ProblemCode")) or 0,
                problem_status=_to_int(row.get("ProblemStatus")),
            )
        )
    devices.sort(key=lambda d: (d.vid, d.pid, d.serial, -1 if d.mi is None else d.mi))
    return devices


def list_devices(run: Callable) -> List[UsbDevice]:
    """Sola lettura: chiede a PowerShell i dispositivi USB presenti."""
    res = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", LIST_SCRIPT])
    if res.returncode != 0:
        raise RuntimeError("device enumeration failed: %s" % (res.stderr or "").strip())
    return parse_device_list(res.stdout)


def filter_devices(devices: List[UsbDevice], only_no_driver: bool = False,
                   include_hubs: bool = False, include_parents: bool = True,
                   trim: bool = False) -> List[UsbDevice]:
    """Filtri dell'elenco, come in Zadig.

    only_no_driver  : tiene i dispositivi senza driver (la vista predefinita di Zadig)
    include_hubs    : tiene gli hub USB (Zadig: 'Ignore Hubs or Composite Parents' non selezionato)
    include_parents : tiene i genitori compositi (dispositivi che hanno anche figli MI_xx)
    """
    out = []
    for d in devices:
        if only_no_driver and d.has_driver:
            continue
        if not include_hubs and d.is_hub:
            continue
        if not include_parents and d.mi is None and any(
                c.mi is not None and (c.vid, c.pid) == (d.vid, d.pid) for c in devices):
            continue
        out.append(d)
    if trim:
        out = [_replace_name(d, " ".join(d.name.split())) for d in out]
    return out


def _replace_name(d: UsbDevice, name: str) -> UsbDevice:
    from dataclasses import replace
    return replace(d, name=name)


def select_target(devices: List[UsbDevice], vid: int, pid: int,
                  iface: Optional[int] = None, instance: Optional[str] = None) -> UsbDevice:
    """Restituisce esattamente un dispositivo/interfaccia oppure solleva NotFoundError / AmbiguousError."""
    if instance is not None:
        found = [d for d in devices if d.instance_id.lower() == instance.lower()]
        if len(found) != 1:
            raise NotFoundError("no present USB device with instance ID '%s'" % instance)
        d = found[0]
        if (d.vid, d.pid) != (vid, pid):
            raise NotFoundError("instance ID %s is %s, not %04X:%04X" % (d.instance_id, d.vidpid, vid, pid))
        return d

    matches = [d for d in devices if d.vid == vid and d.pid == pid]
    if not matches:
        raise NotFoundError("no present USB device %04X:%04X" % (vid, pid))
    children = [d for d in matches if d.mi is not None]

    if iface is not None:
        if not children:
            raise NotFoundError("device %04X:%04X has no per-interface entries (not composite): omit --iface" % (vid, pid))
        sel = [d for d in children if d.mi == iface]
        if not sel:
            avail = ", ".join(sorted("MI_%02X" % d.mi for d in children))
            raise NotFoundError("interface %d not found on %04X:%04X (available: %s)" % (iface, vid, pid, avail))
        if len(sel) > 1:
            raise AmbiguousError("several devices %04X:%04X are connected; use --instance to pick one" % (vid, pid))
        return sel[0]

    if children:
        avail = ", ".join(sorted("MI_%02X" % d.mi for d in children))
        raise AmbiguousError("device %04X:%04X is composite: choose an interface with --iface (available: %s)" % (vid, pid, avail))
    if len(matches) > 1:
        raise AmbiguousError("several devices %04X:%04X are connected; use --instance to pick one" % (vid, pid))
    return matches[0]
