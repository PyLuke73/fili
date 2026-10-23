Subject: Free code signing for an open source project: fili (USB driver replacement tool for Windows)

Hello,

I would like to apply for free code signing through the SignPath Foundation for an open source project.

Project: fili
Repository: https://github.com/PyLuke73/fili
Release: https://github.com/PyLuke73/fili/releases/tag/v0.1.0 (pre-release)
License: GPL-3.0-or-later (OSI approved), full text in LICENSE
Maintainer: PyLuke73 (sole maintainer)

What it does
fili replaces the driver of a USB device or interface on Windows (WinUSB, libusbK, libusb-win32, usbser), like Zadig but scriptable, from the command line (fili.exe) or a small window (fili-gui.exe). The driver is installed by libwdi's wdi-simple.exe, which fili runs as a separate program. The project is written in Python and packaged with PyInstaller; the installer is built with Inno Setup.

Why signing matters here
The tool changes drivers on the user's PC, so users have good reason to be careful about what they run. Today the executables are unsigned: SmartScreen shows "unknown publisher" and some antivirus products flag PyInstaller executables. A signature would let users check who published the files.

What I would sign
fili.exe, fili-gui.exe, wdi-simple.exe (built from libwdi, source and licence in THIRD_PARTY) and the installer fili-setup-<version>.exe.

Project status
- Public repository, single author history, tests in tests/ (about 170, none touch the system).
- Not malware, no telemetry, no network access at runtime.
- The installer only copies files; it changes no driver and adds no certificate. Licences and corresponding sources of the bundled third-party components are in the LICENSES and THIRD_PARTY folders.
- Released as a pre-release 0.1.0; I intend to keep maintaining it.

Build process
I understand that SignPath needs a verifiable build. I will move the build to GitHub Actions (windows runner) so that the artifacts are produced from the public repository and submitted to SignPath from the workflow. I will also add a code signing policy and a privacy statement to the README, as required.

Contact: via GitHub (https://github.com/PyLuke73)

Thank you,
PyLuke73
