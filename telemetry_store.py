
# telemetry_store.py
import collections
import threading
import os
import time
import json
import logging
from logging.handlers import RotatingFileHandler

# --- Configuration ---
VAL = os.getenv("TELEMETRY_MAXLEN", "0")  # "0" => illimité
try:
    N = int(VAL)
    MAXLEN = N if N > 0 else None
except ValueError:
    MAXLEN = None

# "DEBUG" pour plus verbeux
LOG_LEVEL = os.getenv("DEBUG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, "app_debug.log")

# --- Préparer logger global ---
os.makedirs(LOG_DIR, exist_ok=True)
_logger = logging.getLogger("telemetry")
if not _logger.handlers:
    _logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    _logger.addHandler(handler)
    _logger.propagate = False

# --- Buffer + Lock + Statistiques ---
telemetry_buf = collections.deque(maxlen=MAXLEN)
telemetry_lock = threading.RLock()
telemetry_stat = {
    "seq": 0,                  # compteur de points ajoutés
    "last_append_ts": 0.0,     # horodatage 't' du dernier point (horloge jeu)
    "last_append_wall": 0.0,   # time.time() du dernier append (horloge mur)
    "maxlen": MAXLEN,
}


def get_logger():
    """Retourne le logger partagé."""
    return _logger


def append_point(p: dict):
    """
    Append thread-safe + mise à jour des stats + log léger (rate-limit).
    Exige au minimum 't' (time.time), 't_game_ms', 'lap'.
    """
    now = time.time()
    if "t" not in p:
        p["t"] = now
    with telemetry_lock:
        telemetry_buf.append(p)
        telemetry_stat["seq"] += 1
        telemetry_stat["last_append_ts"] = float(p.get("t", now))
        telemetry_stat["last_append_wall"] = now

        # Log DEBUG rate-limit (toutes ~1000 inserts)
        if telemetry_stat["seq"] % 1000 == 0:
            _logger.debug(
                "append_point: seq=%d len=%d last_wall=%.3f lap=%s t_ms=%.1f",
                telemetry_stat["seq"], len(telemetry_buf),
                telemetry_stat["last_append_wall"], p.get(
                    "lap"), p.get("t_game_ms", 0.0)
            )


def snapshot():
    """
    Snapshot atomique du buffer + stat (copie).
    """
    with telemetry_lock:
        buf_copy = list(telemetry_buf)
        stat_copy = dict(telemetry_stat)
        return buf_copy, stat_copy


def dump_snapshot(max_points: int = 20000, filename_prefix: str = "snapshot"):
    """
    Écrit un snapshot JSON du buffer (limité à max_points) dans LOG_DIR.
    Retourne le chemin du fichier écrit.
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"{filename_prefix}_{ts}.json")
    with telemetry_lock:
        data = list(telemetry_buf)[-max_points:]
    try:
        with open(path, "w", encoding="utf-8") as fp:
            json.dump({"points": data, "meta": telemetry_stat},
                      fp, ensure_ascii=False, indent=2)
        _logger.info("dump_snapshot: %s (points=%d)", path, len(data))
        return path
    except Exception as e:
        _logger.error("dump_snapshot ERROR: %s", e)
        return ""
