"""Estrazione del pacchetto driver senza effetti collaterali (solo INF, niente catalogo, niente certificato).

Il wdi-simple originale non può farlo in sicurezza: anche in modalità di estrazione crea un
certificato autofirmato e lo aggiunge agli archivi attendibili del computer. Questo modulo scrive
da solo un INF NON FIRMATO, soltanto in una cartella scelta dall'utente, e non tocca mai il sistema.

Supportato: WinUSB (l'INF usa il winusb.inf incluso in Windows, non servono binari).
libusbK / libusb-win32 / CDC richiedono binari del driver, quindi qui vengono rifiutati.
"""

import os
import uuid
from typing import Optional

from .devices import UsbDevice
from .ops import clean_name

# Provenienza: scritto a partire dalla struttura documentata da Microsoft in "WinUSB (Winusb.sys)
# Installation" (documentazione Windows Driver, INF di esempio che associa un dispositivo al WinUSB incluso in
# Windows tramite Include/Needs = winusb.inf). I nomi delle sezioni e le direttive sono quelli
# documentati, quindi sono imposti dal formato INF; il testo, i commenti e i
# valori sono nostri. Per Windows 10/11 (la classe USBDevice e winusb.inf sono incluse in Windows, quindi
# niente sezione ClassInstall32 e niente co-installer; il servizio e la sezione KMDF arrivano da
# winusb.inf tramite Needs = WINUSB.NT e WINUSB.NT.Services, nello stesso modo in cui gli INF
# di Windows per i dispositivi WinUSB li usano, quindi qui non si ripetono sezioni AddService/Wdf). Il file libwdi/winusb.inf.in NON e'
# stato consultato per questo modello.
INF_TEMPLATE = """\
; fili: UNSIGNED driver package for inspection only.
; It has no catalog file, so 64-bit Windows will not install it as is.
; Generated for: {hwid}

[Version]
Signature = "$Windows NT$"
Class     = USBDevice
ClassGuid = {{88BAE032-5A81-49f0-BC3D-A4FF138216D6}}
Provider  = %ProviderName%
DriverVer = {date}, 1.0.0.0
PnpLockdown = 1

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
Include = winusb.inf
Needs   = WINUSB.NT.Services

{hw_block}
[Strings]
ProviderName = "fili"
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
    # Nel file entra solo la sezione usata (infverif segnala le sezioni non referenziate).
    if wcid:
        hw_block = ""            # Dispositivo WCID: il GUID dell'interfaccia viene dai descrittori del dispositivo stesso
    else:
        hw_block = ("[Install.HW]\n"
                    "AddReg = AddInterfaceGuid\n"
                    "\n"
                    "[AddInterfaceGuid]\n"
                    "HKR,, DeviceInterfaceGUIDs, 0x10000, \"%s\"\n" % guid)
    return INF_TEMPLATE.format(
        hwid=hardware_id(dev, wcid), name=clean_name(name or dev.name),
        date=date, hw_block=hw_block)


def extract_package(dev: UsbDevice, out_dir: str, driver: str, *, name: Optional[str] = None,
                    wcid: bool = False) -> str:
    """Scrive <out_dir>/fili.inf e ne restituisce il percorso. Non crea nient'altro."""
    if driver != "winusb":
        raise ValueError("extract supports only the winusb driver (others need driver binaries "
                         "and are produced by libwdi at install time)")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "fili.inf")
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(render_inf(dev, name=name, wcid=wcid))
    return path
