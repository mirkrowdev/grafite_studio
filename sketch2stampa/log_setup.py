"""
Configurazione del logging per Grafite.

Il log viene scritto in ~/.config/grafite/grafite.log con rotazione automatica
(max 1 MB, 2 file di backup). L'assenza della directory o errori di scrittura
non devono mai bloccare l'avvio — in quel caso si usa solo il logger su stderr.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.join(os.path.expanduser("~"), ".config", "grafite")
_LOG_FILE = os.path.join(_LOG_DIR, "grafite.log")
_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def percorso_log() -> str:
    return _LOG_FILE


def configura() -> None:
    """Chiama questa funzione una sola volta all'avvio dell'app."""
    root = logging.getLogger()
    if root.handlers:
        return  # già configurato

    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # Handler su file rotante
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        fh = RotatingFileHandler(
            _LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except Exception as exc:
        # Non blocca l'avvio: si scrive solo su stderr
        print(f"[grafite] impossibile aprire il file di log: {exc}", file=sys.stderr)

    # Handler su stderr per gli errori critici durante lo sviluppo
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(formatter)
    root.addHandler(sh)

    logging.getLogger("grafite").info("Grafite avviato. Log: %s", _LOG_FILE)
