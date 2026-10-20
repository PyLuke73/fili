"""Componenti di terze parti e relative licenze, per 'fili licenses'. Sola lettura: stampa dati, non tocca nulla."""

COMPONENTS = [
    {"name": "fili", "license": "MIT", "role": "this program", "redistributed": True},
    {"name": "libwdi / wdi-simple.exe", "license": "LGPL-3.0-or-later",
     "role": "builds, signs and installs the driver package (run as a separate program)", "redistributed": False},
    {"name": "WinUSB co-installers (Microsoft WDK 8.0)", "license": "Microsoft Windows Driver Frameworks 1.11 terms",
     "role": "WinUSB (only needed on old Windows)", "redistributed": False},
    {"name": "libusb-win32 1.4.0.0", "license": "GPL (driver libusb0.sys), LGPL (library, installer)",
     "role": "libusb-win32 driver", "redistributed": False},
    {"name": "libusbK 3.1.0.0", "license": "New BSD or GPL (dual)", "role": "libusbK driver", "redistributed": False},
    {"name": "usbser", "license": "part of Windows", "role": "CDC driver", "redistributed": False},
]

NOTE = ("fili ships none of the third-party components: you fetch and build wdi-simple.exe yourself "
        "(docs/building-wdi-simple.md). If you redistribute a wdi-simple.exe binary, its obligations apply to you: "
        "see docs/licenza.md, docs/embedded-drivers.txt and NOTICE. Full license texts: LICENSES/. Not legal advice.")
