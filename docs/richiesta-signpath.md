# Richiesta di firma gratuita a SignPath Foundation

Da compilare su https://signpath.org/apply (il modulo si vede solo nel browser: i campi qui sotto sono le risposte pronte,
da adattare alle domande). Le condizioni del programma sono su https://signpath.org/terms.

## Risposte pronte (in inglese, per il modulo)

**Project name:** fili

**Repository / home page:** https://github.com/PyLuke73/fili

**Download page:** https://github.com/PyLuke73/fili/releases (pre-release 0.1.0, already released in the form to be signed)

**License:** GPL-3.0-or-later (OSI approved, no commercial dual licensing, no proprietary components)

**Description:** fili replaces the driver of a USB device or interface on Windows (WinUSB, libusbK, libusb-win32, usbser),
like Zadig but scriptable, from the command line (fili.exe) or a small window (fili-gui.exe). The driver itself is installed by
libwdi's wdi-simple.exe, run as a separate program. Python, packaged with PyInstaller; installer built with Inno Setup.

**What would be signed:** fili.exe, fili-gui.exe and the installer fili-setup-<version>.exe, all built from the repository by the
GitHub Actions workflow .github/workflows/release.yml. wdi-simple.exe (built from libwdi, third-party code) is not signed by this project.

**Why signing matters:** the tool changes drivers on the user's PC, so users must be able to see who published the files. Unsigned,
SmartScreen shows "unknown publisher" and some antivirus products flag PyInstaller executables.

**Code signing policy page:** README section "Code signing policy" (with the SignPath.io and SignPath Foundation attribution, roles and privacy statement).

**Team:** one person, PyLuke73 (https://github.com/PyLuke73): author, reviewer and approver. Multi-factor authentication on GitHub and SignPath.

**Privacy / system changes:** no telemetry and no network access at runtime. The installer only copies files and has an uninstaller.
fili changes the driver of a device the user selects and, through libwdi, adds a self-signed certificate to the PC's trusted
stores: this is stated at the top of the README, in the installer's first page and before every change (dry-run first, explicit
confirmation, protected device classes refused without --force), and `fili cert-remove` removes the certificates.

**Maintenance:** actively developed; about 170 automated tests (none touch the system); real-hardware test reports in docs/.

## Punti che il revisore potrebbe sollevare

* *"Bypass security measures" / "change system configuration":* fili installa driver e un certificato autofirmato (come Zadig, che libwdi usa). È
  dichiarato ovunque e richiede conferma; conviene dirlo noi per primi nel modulo, come sopra.
* *"Own binaries only":* per questo `wdi-simple.exe` non si firma.
* *Reputazione:* il progetto è nuovo (0.1.0): può servire tempo o qualche segnale (stelle, uso, post).
