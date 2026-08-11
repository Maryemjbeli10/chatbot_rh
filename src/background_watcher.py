"""
Surveillance automatique des documents en arrière-plan.
"""

import threading
import time

from .ingest import build_index, index_is_stale

CHECK_INTERVAL_SECONDS = 15

_watcher_lock = threading.Lock()
_watcher_started = False


def _watch_loop():
    while True:
        try:
            if index_is_stale():
                print("[watcher] Changement détecté dans data/documents/ -> ré-indexation...")
                build_index(verbose=True)
        except Exception as e:
            print(f"[watcher] Erreur pendant la vérification : {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_watcher():
    global _watcher_started
    with _watcher_lock:
        if _watcher_started:
            return
        thread = threading.Thread(target=_watch_loop, daemon=True)
        thread.start()
        _watcher_started = True
        print(f"[watcher] Surveillance des documents démarrée (vérification toutes les {CHECK_INTERVAL_SECONDS}s).")
