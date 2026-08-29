"""
Preferenze persistenti per Grafite.

File JSON in ~/.config/grafite/preferenze.json (Linux)
o %APPDATA%\\Grafite\\preferenze.json (Windows).

L'assenza o la corruzione del file non impedisce mai l'avvio.
"""
import json
import logging
import os
import sys

_log = logging.getLogger("grafite.preferenze")


def _dir_preferenze():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "Grafite")
    return os.path.join(os.path.expanduser("~"), ".config", "grafite")


_FILE = os.path.join(_dir_preferenze(), "preferenze.json")


def carica():
    """Ritorna il dizionario delle preferenze, o {} se il file non esiste o è corrotto."""
    try:
        with open(_FILE, "r", encoding="utf-8") as f:
            dati = json.load(f)
        if isinstance(dati, dict):
            return dati
    except FileNotFoundError:
        pass
    except Exception:
        _log.warning("Preferenze corrotte o illeggibili, ignorate: %s", _FILE)
    return {}


def salva(dati):
    """Scrive il dizionario delle preferenze su disco."""
    try:
        cartella = os.path.dirname(_FILE)
        os.makedirs(cartella, exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(dati, f, indent=2, ensure_ascii=False)
    except Exception:
        _log.exception("Impossibile salvare le preferenze in %s", _FILE)
