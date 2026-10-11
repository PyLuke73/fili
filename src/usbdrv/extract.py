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

INF_TEMPLATE = """\
; usbdrv - UNSIGNED package for inspection. Not installable on 64-bit Windows as is
; (no catalog file). Generated for: {hwid}
[Strings]
DeviceName = "{name}"
VendorName = "usbdrv"
SourceName = "{name} Install Disk"
DeviceID   = "{hwid}"
DeviceGUID = "{guid}"

[Version]
Signature   = "$Windows NT$"
Class       = "USBDevice"
ClassGuid   = {{88bae032-5a81-49f0-bc3d-a4ff138216d6}}
Provider    = "usbdrv"
DriverVer   = {date}, 1.0.0.0

[ClassInstall32]
Addreg = WinUSBDeviceClassReg

[WinUSBDeviceClassReg]
HKR,,,0,"Universal Serial Bus devices"
HKR,,Icon,,-20

[Manufacturer]
%VendorName% = Device_WinUSB,NTx86,NTamd64,NTarm64

[Device_WinUSB.NTx86]
%DeviceName% = USB_Install, USB\\%DeviceID%

[Device_WinUSB.NTamd64]
%DeviceName% = USB_Install, USB\\%DeviceID%

[Device_WinUSB.NTarm64]
%DeviceName% = USB_Install, USB\\%DeviceID%

[USB_Install]
Include = winusb.inf
Needs   = WINUSB.NT

[USB_Install.Services]
Include    = winusb.inf
AddService = WinUSB,0x00000002,WinUSB_ServiceInstall

[WinUSB_ServiceInstall]
DisplayName   = "WinUSB - Kernel Driver"
ServiceType   = 1
StartType     = 3
ErrorControl  = 1
ServiceBinary = %12%\\WinUSB.sys

[USB_Install.Wdf]
KmdfService = WINUSB, WinUsb_Install

[WinUsb_Install]
KmdfLibraryVersion = 1.11

[USB_Install.HW]
AddReg = {guid_section}

[NoDeviceInterfaceGUID]
; WCID: the interface GUID comes from the device's own descriptors

[AddDeviceInterfaceGUID]
HKR,,DeviceInterfaceGUIDs,0x10000,%DeviceGUID%
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
        guid_section="NoDeviceInterfaceGUID" if wcid else "AddDeviceInterfaceGUID")


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
