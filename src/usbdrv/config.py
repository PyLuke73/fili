"""Optional configuration file (usbdrv.toml), the counterpart of Zadig's zadig.ini.

Search order: --config PATH, ./usbdrv.toml, <APPDATA>/usbdrv/usbdrv.toml.
Command-line options always win over the file. The file can never carry a
confirmation: --yes must be given on the command line.
"""

import os
from typing import Optional

try:  # Python 3.11+
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

DEFAULTS = {
    "general": {"log_level": "INFO", "log_file": None, "log_format": "text", "silent": False},
    "device": {"only_no_driver": False, "include_hubs": False, "include_parents": True, "trim_whitespaces": False},
    "driver": {"default_driver": "winusb", "extract_dir": None, "timeout_ms": None, "wcid": False},
    "tool": {"wdi_path": None},
}

SAMPLE = """\
# usbdrv.toml - defaults for usbdrv. Command-line options override these.
[general]
log_level  = "INFO"      # DEBUG | INFO | WARN | ERROR
# log_file = "usbdrv.log"
log_format = "text"      # text | json
silent     = false       # reduce console output

[device]
only_no_driver   = false # list only devices without driver (Zadig default view)
include_hubs     = false
include_parents  = true  # composite parents
trim_whitespaces = false

[driver]
default_driver = "winusb"   # winusb | libusbk | libusb-win32 | usbser
# extract_dir  = "usb_driver"
# timeout_ms   = 60000
wcid = false

[tool]
# wdi_path = "C:\\tools\\wdi-simple.exe"
"""


class ConfigError(Exception):
    pass


def candidate_paths(explicit: Optional[str], env: dict, cwd: str):
    if explicit:
        yield explicit
        return
    yield os.path.join(cwd, "usbdrv.toml")
    appdata = env.get("APPDATA")
    if appdata:
        yield os.path.join(appdata, "usbdrv", "usbdrv.toml")


def load_config(explicit: Optional[str] = None, env: Optional[dict] = None, cwd: Optional[str] = None) -> dict:
    """Return DEFAULTS merged with the first config file found. Unknown keys are rejected."""
    cfg = {k: dict(v) for k, v in DEFAULTS.items()}
    env = os.environ if env is None else env
    for path in candidate_paths(explicit, env, cwd or os.getcwd()):
        if not os.path.isfile(path):
            if explicit:
                raise ConfigError("config file not found: %s" % path)
            continue
        if tomllib is None:
            raise ConfigError("reading usbdrv.toml needs Python 3.11+")
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, ValueError) as e:
            raise ConfigError("cannot read %s: %s" % (path, e))
        for section, values in data.items():
            if section not in cfg or not isinstance(values, dict):
                raise ConfigError("%s: unknown section [%s]" % (path, section))
            for key, val in values.items():
                if key not in cfg[section]:
                    raise ConfigError("%s: unknown key '%s' in [%s]" % (path, key, section))
                cfg[section][key] = val
        cfg["_path"] = path
        break
    return cfg
