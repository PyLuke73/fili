"""Il testo di 'fili --skill': una guida completa per un'AI (un agente) che deve usare fili al posto di una persona.

Il testo è scritto in inglese perché è destinato a un modello. I codici di uscita e la versione vengono dal programma;
l'elenco dei comandi è qui sotto e un test controlla che coincida con quelli del parser, così non resta indietro.
"""

from typing import Dict, List

# (comando, effetto sul sistema, quando usarlo)
COMMANDS = [
    ("list", "read-only", "Show the USB devices and interfaces present now (VID:PID, interface, class, driver, status). Start here."),
    ("status", "read-only", "Driver package, version, date, provider and problem code of ONE device/interface."),
    ("diagnose", "read-only", "Explain why a device fails: Device Manager code, NTSTATUS, setupapi.dev.log excerpts, events. "
                        "Without a target it lists every device that reports a problem."),
    ("extract", "read-only", "Write an UNSIGNED INF for inspection into --out DIR. Creates no certificate."),
    ("install", "CHANGES the system, needs --yes + Administrator", "Replace the driver of ONE device/interface (winusb, libusbk, libusb-win32, usbser)."),
    ("reinstall", "CHANGES the system, needs --yes + Administrator", "Install again the same kind of driver the device already uses; for a manufacturer's or Windows' driver, remove the device and let Windows detect it again (no certificate)."),
    ("restore", "CHANGES the system, needs --yes + Administrator", "Undo install: remove the OEM package fili created (and the libusb0 filter) so Windows binds the original driver."),
    ("uninstall", "CHANGES the system, needs --yes + Administrator", "Same as restore."),
    ("restart", "CHANGES the system, needs --yes + Administrator", "Enable a device that Windows shows as disabled (problem 22), or restart it. Changes no driver."),
    ("usb-reset", "CHANGES the system, needs --yes + Administrator", "Recover a device (or its external hub) that does not respond: stop stuck pnputil commands, "
                        "disable and enable it. Never touches the USB controller or the root hub."),
    ("cert-remove", "read-only without --thumbprint; with it CHANGES the system, needs --yes + Administrator", "Without --thumbprint: list the self-signed libwdi certificates (read-only). With --thumbprint and --yes: remove one."),
    ("licenses", "read-only", "Third-party components and licenses."),
    ("sample-config", "read-only", "Print a sample fili.toml."),
]

GUIDE = """\
# fili - guide for an AI agent (version {version})

fili replaces the driver of a USB device or interface on Windows (a scriptable, Zadig-like tool). You are expected to
drive it on behalf of a person. It can make a keyboard, mouse, disk or Bluetooth adapter stop working, and it adds a
self-signed certificate to the machine's trusted stores. Read the rules before running anything.

## Rules you must follow

1. **Look before you touch.** `list`, `status`, `diagnose`, `extract`, `licenses`, `sample-config` and every command
   with `--dry-run` change nothing. Use them first.
2. **Never add `--yes` or `--force` on your own.** Run the command with `--dry-run`, show the person the plan (it is in
   the output), say what will change and what could go wrong, and run it with `--yes` only after the person has clearly
   approved that exact command. Approval for one device or one command does not carry over to another.
3. **`--force` only if the person asks for it by name.** Without it fili refuses protected classes (HID, keyboard,
   mouse, Bluetooth, disks, WPD): replacing their driver can disable the input devices the person is using.
4. **Administrator.** Commands that change the system need an elevated terminal (exit code 3 otherwise). Tell the
   person to open "Terminal (Admin)" and rerun; do not try to elevate yourself.
5. **Certificates.** `install`, and `reinstall` of a driver fili installed, add a self-signed certificate to the Root and TrustedPublisher stores of
   this PC. Tell the person, and at the end offer `fili cert-remove` (list) and `cert-remove --thumbprint <40 hex> --yes`.
6. **Only devices the person owns**, preferably a sacrificial one. Never experiment on the boot disk, keyboard or mouse.
7. **Do not restart the USB controller or work around fili's refusals.** A refusal (exit code 2) is a safety rule: report
   it to the person instead of trying other flags.

## Workflow for a change

1. `fili --json list` and find the device (VID:PID, class, driver). Add `--hubs` or `--parents` only if you need them.
2. `fili --json status --vid V --pid P [--iface N] [--instance ID]` to confirm it is the right one.
3. Preview: the same command plus `--dry-run`. Read the plan and the warning.
4. Ask the person. Wait for a clear yes.
5. Run it with `--yes` (in an elevated terminal). Progress goes to stderr as `[2/4] step`; use `--json` or `--silent` to keep stdout clean.
6. Check the exit code and the `after` data (driver, status, problem code). Exit 0 means the device is in the expected state.
7. Say how to undo it (`fili restore ...`) and mention the certificate.

## Selecting a device

- `--vid` and `--pid` are hex (`0483`, `374B`). They are required for the commands that act on a device.
- **Composite devices** (several `MI_xx` interfaces): add `--iface N`. Without it fili stops with exit code 5.
- **Identical devices** (same VID:PID): add `--instance "<instance id>"` (take it from `list --json`, field `instance_id`).
  Without it fili stops with exit code 5. With `--instance`, `install` changes only that instance.
  `install --all-matching` changes all identical devices at once; undo it with `restore --instance ID --all-matching`.
  Without `--all-matching`, `restore` refuses a package that identical devices share.

## Commands

{commands}

Useful flags: `--driver winusb|libusbk|libusb-win32|usbser`, `--name`, `--wcid` (only for devices that advertise
WCID, otherwise exit 6 with "Resource already exists"), `--filter` (libusb-win32 filter on top of the current driver;
needs `--all-matching` when identical devices exist), `--timeout MS`, `--wdi PATH`, `--dry-run`, `--yes`, `--force`.
Global flags (before or after the command): `--json`, `--silent`, `--log-file FILE`, `--log-level`, `--log-format
text|json`, `-v`, `--config FILE`.

## Machine-readable output

With `--json` stdout is exactly one JSON document:
`{{"command": str, "ok": bool, "exit_code": int, "exit_meaning": str, "error": str|null, "data": ..., "messages": [str]}}`.
`list` puts the device list in `data` (fields include `vid`, `pid`, `mi`, `cls`, `service`, `status`, `name`,
`instance_id`). Commands that change the system add `after` (the device re-read) to `data`; with `--dry-run`
`data.dry_run` is true. Read `error` for the reason when `ok` is false.

## Exit codes

{exit_codes}

## What to do when something goes wrong

- **5 (ambiguous)**: add `--iface` or `--instance` as above. Do not guess: ask the person which device.
- **6 (driver error)**: run `fili diagnose --vid V --pid P` and report the problem code and the log lines. The change may
  be half done; offer `fili restore`.
- **The device disappears after `restore`/`install`** (typical of firmware bootloaders): ask the person to unplug and
  replug it. fili prints this hint.
- **A command timed out** (message "timed out after N s", exit 6): Windows' USB stack or the device is stuck. Run
  `fili usb-reset ... --dry-run`, show the plan, and with approval `--yes`. Add `--hub` to restart the external hub the
  device sits behind (everything behind that hub disconnects for a moment; fili refuses if a keyboard, mouse or disk is
  behind it unless `--force`). `usb-reset` cannot unstick a driver that is hung inside the kernel: if `pnputil
  /disable-device` itself times out, stop and ask the person to unplug and replug the device (or reboot). Do not loop.
- **A device is shown as disabled** (problem 22) or does not work after a plug event: `fili restart ... --dry-run`, show the
  plan, and with approval `--yes`: it enables a disabled device, otherwise restarts it. It changes no driver.
- **`wdi-simple.exe` not found**: `install` needs it (`--wdi PATH`, `$FILI_WDI`, `PATH`, or next to `fili.exe`). The
  read-only commands and every `--dry-run` work without it.
- **`--filter` on network adapters is not supported**: the device restart hangs. Use it on devices without a vendor
  network driver (for example a USB flash drive).
- **Antivirus or exit -15** from libwdi: fili retries once. If it persists, the person must allow the temporary installer.

## Limits

fili does not sign drivers with a real certificate, does not support Windows older than 10 (unless built with the
Microsoft co-installers), and has not been verified on ARM64 or 32-bit Windows. It does not report a percentage
while installing: the first step (installing the package) can take up to a minute.
"""


def build(version: str, exit_codes: Dict[int, str]) -> str:
    """Il testo completo, con la versione, l'elenco dei comandi e i codici di uscita del programma in esecuzione."""
    cmds: List[str] = []
    for name, effect, text in COMMANDS:
        cmds.append("- `%s` (%s): %s" % (name, effect, text))
    codes = "\n".join("- %d: %s" % (code, meaning) for code, meaning in sorted(exit_codes.items()))
    return GUIDE.format(version=version, commands="\n".join(cmds), exit_codes=codes)
