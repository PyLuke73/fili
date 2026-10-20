"""File di configurazione facoltativo (fili.toml), l'equivalente dello zadig.ini di Zadig.

Ordine di ricerca: --config PATH, ./fili.toml, <APPDATA>/fili/fili.toml.
Le opzioni da riga di comando prevalgono sempre sul file. Il file non può mai contenere
una conferma: --yes va indicato sulla riga di comando.
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
# fili.toml - defaults for fili. Command-line options override these.
[general]
log_level  = "INFO"      # DEBUG | INFO | WARN | ERROR
# log_file = "fili.log"
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
    yield os.path.join(cwd, "fili.toml")
    appdata = env.get("APPDATA")
    if appdata:
        yield os.path.join(appdata, "fili", "fili.toml")


def load_config(explicit: Optional[str] = None, env: Optional[dict] = None, cwd: Optional[str] = None) -> dict:
    """Restituisce DEFAULTS unito al primo file di configurazione trovato. Le chiavi sconosciute vengono rifiutate."""
    cfg = {k: dict(v) for k, v in DEFAULTS.items()}
    env = os.environ if env is None else env
    for path in candidate_paths(explicit, env, cwd or os.getcwd()):
        if not os.path.isfile(path):
            if explicit:
                raise ConfigError("config file not found: %s" % path)
            continue
        if tomllib is None:
            raise ConfigError("reading fili.toml needs Python 3.11+")
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
