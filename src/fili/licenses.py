"""Componenti di terze parti e relative licenze, per 'fili licenses'. Sola lettura: stampa dati, non tocca nulla."""

COMPONENTS = [
    {"name": "fili", "license": "GPL-3.0-or-later", "role": "this program", "redistributed": True},
    {"name": "libwdi / wdi-simple.exe", "license": "LGPL-3.0-or-later",
     "role": "builds, signs and installs the driver package (run as a separate program)", "redistributed": False},
    {"name": "WinUSB (winusb.sys)", "license": "part of Windows",
     "role": "WinUSB driver; the Microsoft WDK co-installers are not embedded (only needed before Windows 10)",
     "redistributed": False},
    {"name": "libusb-win32 1.4.0.0", "license": "GPL (driver libusb0.sys), LGPL (library, installer)",
     "role": "libusb-win32 driver", "redistributed": False},
    {"name": "libusbK 3.1.0.0", "license": "New BSD or GPL (dual)", "role": "libusbK driver", "redistributed": False},
    {"name": "usbser", "license": "part of Windows", "role": "CDC driver", "redistributed": False},
]

NOTE = ("The installer ships wdi-simple.exe (libwdi) with the drivers it embeds; their licence texts and corresponding "
        "sources are in the LICENSES and THIRD_PARTY folders next to the program. If you redistribute that binary, its "
        "obligations apply to you: see docs/licenza.md, docs/embedded-drivers.txt and NOTICE. Not legal advice.")
