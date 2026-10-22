# fili icons

Three complete sets of the same 18 interface icons plus an application icon. Pick one set and use only that one.
Each folder has `preview.png` (the sheet, at 44 px with a 16 px copy in the corner) and `app-icon.svg` (512 px).

| set | style | application icon |
|---|---|---|
| `set-1-filo` | thin outline (1.6 px), navy `#1B2A41` with one teal "thread" stroke `#0E9AA7` per icon | the USB symbol, its stem drawn as a thread |
| `set-2-duotone` | bolder outline (1.9 px) with a light teal fill on closed shapes | a USB-C port above two swap arrows (driver replaced) |
| `set-3-badge` | white glyph on a colour tile by category: teal = action, blue = information, grey = neutral, amber = needs care | a chip with a swap symbol |

Sets 1 and 2 use a 24 px grid; set 3 is a 32 px tile with the 24 px glyph inside. Dark backgrounds: outline `#E8EEF5`, thread `#4FD1DC`.

| icon | used for |
|---|---|
| `usb-device.svg` | Device list |
| `install.svg` | Install |
| `reinstall.svg` | Reinstall |
| `restore.svg` | Restore |
| `diagnose.svg` | Diagnose |
| `certificates.svg` | Certificates |
| `licenses.svg` | Licenses |
| `save.svg` | Save output |
| `refresh.svg` | Refresh |
| `help.svg` | Help |
| `about.svg` | About |
| `support.svg` | Ko-fi |
| `usb-reset.svg` | usb-reset (restart a stuck device or hub) |
| `hubs.svg` | Show hubs |
| `admin.svg` | Administrator |
| `force.svg` | Force (protected class) |
| `twins.svg` | All matching |
| `filter.svg` | Filter driver |

The SVGs are generated: edit `build_icons.py` and run `python assets/icons/build_icons.py` (one geometry, three styles).
They are not used by the program yet: the executables and the installer need an `.ico` and the window needs PNGs.
