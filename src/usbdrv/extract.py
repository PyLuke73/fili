"""Side-effect-free driver package extraction (INF only, no catalog, no certificate).

Stock wdi-simple cannot do this safely: its extract mode still creates a self-signed
certificate and adds it to the machine's trusted stores. This module writes an UNSIGNED
INF itself, only into a directory chosen by the user, and never touches the system.

Supported: WinUSB (the INF uses the in-box winusb.inf, no binaries are needed).
libusbK / libusb-win32 / CDC need driver binaries, so they are refused here.
"""

import os
import uuid
from typing import Optional

from .devices import UsbDevice
from .ops import clean_name

# Provenance: written from the structure documented by Microsoft in "WinUSB (Winusb.sys)
# Installation" (Windows Driver docs, sample INF that binds a device to the in-box WinUSB
# driver through Include/Needs = winusb.inf). The section names and directives are the
# documented ones, so they are dictated by the INF format; the text, the comments and the
# values are ours. Targets Windows 10/11 (the USBDevice class and winusb.inf are in-box, so
# no ClassInstall32 section and no co-installers). The file libwdi/winusb.inf.in was NOT
# consulted for this template.
INF_TEMPLATE = """\
; usbdrv: UNSIGNED driver package for inspection only.
; It has no catalog file, so 64-bit Windows will not install it as is.
; Generated for: {hwid}

[Version]
Signature = "$Windows NT$"
Class     = USBDevice
ClassGuid = {{88BAE032-5A81-49f0-BC3D-A4FF138216D6}}
Provider  = %ProviderName%
DriverVer = {date}, 1.0.0.0

[Manufacturer]
%ProviderName% = Models, NTx86, NTamd64, NTarm64

[Models.NTx86]
%DeviceDesc% = Install, USB\\{hwid}

[Models.NTamd64]
%DeviceDesc% = Install, USB\\{hwid}

[Models.NTarm64]
%DeviceDesc% = Install, USB\\{hwid}

; --- Install: use the WinUSB driver that ships with Windows ---------------------------
[Install]
Include = winusb.inf
Needs   = WINUSB.NT

[Install.Services]
Include    = winusb.inf
AddService = WinUSB, 0x00000002, WinUSB_Service

[WinUSB_Service]
DisplayName   = "WinUSB"
ServiceType   = 1
StartType     = 3
ErrorControl  = 1
ServiceBinary = %12%\\winusb.sys

[Install.Wdf]
KmdfService = WINUSB, WinUSB_Wdf

[WinUSB_Wdf]
KmdfLibraryVersion = 1.9

[Install.HW]
AddReg = {guid_section}

[AddInterfaceGuid]
HKR,, DeviceInterfaceGUIDs, 0x10000, "{guid}"

[NoInterfaceGuid]
; WCID device: the interface GUID comes from the device's own descriptors.

[Strings]
ProviderName = "usbdrv"
DeviceDesc   = "{name}"
"""


def hardware_id(dev: UsbDevice, wcid: bool) -> str:
    if wcid:
        return "MS_COMP_WINUSB"
    if dev.mi is not None:
        return "VID_%04X&PID_%04X&MI_%02X" % (dev.vid, dev.pid, dev.mi)
    return "VID_%04X&PID_%04X" % (dev.vid, dev.pid)


def render_inf(dev: UsbDevice, *, name: Optional[str] = None, wcid: bool = False,
               date: str = "01/01/2024", guid: Optional[str] = None) -> str:
    guid = guid or "{%s}" % str(uuid.uuid4())
    return INF_TEMPLATE.format(
        hwid=hardware_id(dev, wcid), name=clean_name(name or dev.name),
        guid=guid, date=date,
        guid_section="NoInterfaceGuid" if wcid else "AddInterfaceGuid")


def extract_package(dev: UsbDevice, out_dir: str, driver: str, *, name: Optional[str] = None,
                    wcid: bool = False) -> str:
    """Write <out_dir>/usbdrv.inf and return its path. Creates nothing else."""
    if driver != "winusb":
        raise ValueError("extract supports only the winusb driver (others need driver binaries "
                         "and are produced by libwdi at install time)")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "usbdrv.inf")
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(render_inf(dev, name=name, wcid=wcid))
    return path
