"""Controllo degli aggiornamenti: legge dalle Release di GitHub qual e' l'ultima versione pubblicata.

Non scarica e non installa nulla. Parte solo se l'utente lo chiede ('fili update', la voce di menu della finestra) o se ha
attivato la casella 'Check at startup' (spenta di default; al massimo un controllo al giorno). La richiesta e' una GET
anonima all'API pubblica di GitHub: non porta con se' nessun dato dell'utente, dei dispositivi o del PC.
"""

import json
import os
import re
import time
import urllib.request
from typing import Callable, List, Optional, Tuple

from . import __version__

REPO = "PyLuke73/fili"
API_URL = "https://api.github.com/repos/%s/releases?per_page=20" % REPO
RELEASES_URL = "https://github.com/%s/releases" % REPO
TIMEOUT_S = 10
CHECK_EVERY_S = 24 * 3600


class UpdateError(Exception):
    pass


def version_key(text: str) -> Optional[Tuple]:
    """'v0.2.0' -> ((0, 2, 0), 1, ''); 'v0.2.0-rc1' viene prima di 'v0.2.0'. None se non assomiglia a una versione."""
    m = re.match(r"^v?(\d+(?:\.\d+)*)(.*)$", (text or "").strip())
    if not m:
        return None
    nums = [int(n) for n in m.group(1).split(".")]
    while len(nums) > 1 and nums[-1] == 0:      # 1.0 == 1.0.0
        nums.pop()
    suffix = m.group(2).strip("-.+ ").lower()
    return (tuple(nums), 0 if suffix else 1, suffix)


def fetch_releases(timeout: int = TIMEOUT_S) -> List[dict]:
    """Le Release pubbliche del progetto (le bozze non compaiono senza autenticazione). Solleva UpdateError se la rete non risponde."""
    req = urllib.request.Request(API_URL, headers={"User-Agent": "fili/" + __version__,
                                                   "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            doc = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError) as e:
        raise UpdateError("cannot reach GitHub: %s" % e)
    if not isinstance(doc, list):
        raise UpdateError("unexpected answer from GitHub")
    return doc


def check(current: str = __version__, fetch: Optional[Callable[[], List[dict]]] = None) -> dict:
    """Confronta la versione installata con la piu' recente pubblicata. Non ha effetti collaterali."""
    releases = (fetch or fetch_releases)()
    best, best_key = None, None
    for rel in releases:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        key = version_key(str(rel.get("tag_name") or ""))
        if key and (best_key is None or key > best_key):
            best, best_key = rel, key
    cur_key = version_key(current)
    data = {"current": current, "latest": None, "url": RELEASES_URL, "prerelease": False, "published": None,
            "update_available": False}
    if best is None:
        return data
    url = str(best.get("html_url") or "")
    data.update(latest=str(best["tag_name"]).lstrip("v"), prerelease=bool(best.get("prerelease")),
                published=best.get("published_at"),
                url=url if url.startswith(RELEASES_URL + "/") else RELEASES_URL,    # solo pagine di questo progetto
                update_available=bool(cur_key and best_key > cur_key))
    return data


def describe(data: dict) -> List[str]:
    """Le righe da mostrare all'utente (CLI e finestra)."""
    lines = ["Installed version: %s" % data["current"]]
    if data["latest"] is None:
        return lines + ["No release is published yet.", "Releases: " + data["url"]]
    lines.append("Latest published: %s%s" % (data["latest"], " (pre-release)" if data["prerelease"] else ""))
    if data["update_available"]:
        lines += ["A newer version is available: " + data["url"],
                  "Download the installer from that page and check it against SHA256SUMS. fili does not download or install anything by itself."]
    else:
        lines.append("You have the latest version.")
    return lines


# -- impostazioni della finestra (facoltative; mai lette dalla riga di comando) -----------------------------------

def settings_path(env: dict) -> Optional[str]:
    appdata = env.get("APPDATA")
    return os.path.join(appdata, "fili", "settings.json") if appdata else None


def load_settings(env: dict) -> dict:
    path = settings_path(env)
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        return doc if isinstance(doc, dict) else {}
    except (TypeError, OSError, ValueError):
        return {}


def save_settings(env: dict, **changes) -> bool:
    """Aggiorna il file delle impostazioni; False se non si riesce a scrivere (non e' mai un errore fatale)."""
    path = settings_path(env)
    if not path:
        return False
    doc = load_settings(env)
    doc.update(changes)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        return True
    except OSError:
        return False


def auto_check_due(settings: dict, now: Optional[float] = None) -> bool:
    """True solo se l'utente ha attivato il controllo all'avvio e l'ultimo e' di oltre 24 ore fa."""
    if settings.get("check_updates") is not True:
        return False
    last = settings.get("last_check")
    now = time.time() if now is None else now
    return not isinstance(last, (int, float)) or now - last >= CHECK_EVERY_S or last > now
