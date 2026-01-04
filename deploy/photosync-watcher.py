#!/usr/bin/env python3
# photosync-watcher.py - Watcher con watchdog, debounce QUIET_SECONDS y MAX_WAIT_SECONDS
import os
import sys
import time
import threading
import subprocess
import logging
import fcntl
import signal
from datetime import datetime
from pathlib import Path
import json

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except Exception:
    print("Error: watchdog no está instalado. Instala con: pip install --user watchdog", file=sys.stderr)
    raise

# Config (puede override por env o EnvironmentFile en systemd)
QUIET_SECONDS = int(os.environ.get("QUIET_SECONDS", "60"))  # 60s
MAX_WAIT_SECONDS = int(os.environ.get("MAX_WAIT_SECONDS", "300"))  # 300s (5 min)
LOCK_PATH = os.environ.get("LOCK_PATH", os.path.expanduser("~/.cache/photosync/.photosync.lock"))
RUNNER_PATH = os.environ.get("RUNNER_PATH", os.path.expanduser("~/.local/bin/photosync-run"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("photosync-watcher")
logger.debug("Startup: environ PYTHONPATH=%r", os.environ.get("PYTHONPATH"))

# State
first_event_time = None
last_event_time = None
debounce_timer = None
state_lock = threading.Lock()
# Cuando se ejecuta el runner, suprimir eventos generados por él
suppress_events = False

# Ensure lock dir exists
Path(LOCK_PATH).parent.mkdir(parents=True, exist_ok=True)


def read_watch_paths():
    # Import settings to use SOURCE_PATHS
    from photosync import settings

    sp = getattr(settings, "SOURCE_PATHS", ())
    if isinstance(sp, str):
        return [sp]
    return list(sp)


# WATCH_PATHS will be loaded at runtime inside main() with retries if necessary


ALLOWED_EVENT_TYPES = {"modified", "created", "moved", "deleted"}  # events that should schedule sync

# Polling / fallback configuration
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "300"))  # seconds (default 5 minutes)
LAST_SYNC_FILE = os.environ.get("LAST_SYNC_FILE", os.path.expanduser("~/.cache/photosync/.photosync_last.json"))
POLL_PATH = os.environ.get("POLL_PATH", "<poll>")
POLL_MTIME_DELTA = float(os.environ.get("POLL_MTIME_DELTA", "1.0"))  # seconds tolerance for mtime comparison


class EventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        # Ignorar directorios; solo archivos
        if event.is_directory:
            return
        # Si estamos suprimiendo eventos (runner en curso), ignorar
        if suppress_events:
            logger.debug("(evt) suppressed %s path=%s", getattr(event, "event_type", "unknown"), event.src_path)
            return
        # Only process relevant event types (ignore read-only events like opened / closed_no_write)
        ev_type = getattr(event, "event_type", None)
        if ev_type not in ALLOWED_EVENT_TYPES:
            logger.debug("(evt) ignored event_type=%s path=%s", ev_type, event.src_path)
            return
        try:
            logger.info("(evt) %s path=%s", ev_type, event.src_path)
        except Exception:
            logger.debug("Failed to log event", exc_info=True)
        schedule_on_event(event.src_path)


def schedule_on_event(path):
    global first_event_time, last_event_time, debounce_timer
    now = time.time()
    with state_lock:
        if first_event_time is None:
            first_event_time = now
            logger.info(f"Primer evento detectado: {path}; iniciando ventana de espera.")
            # Instrumentation: log the window duration values for clarity
            try:
                logger.info("(runner schedule) QUIET_SECONDS=%ds MAX_WAIT_SECONDS=%ds", QUIET_SECONDS, MAX_WAIT_SECONDS)
            except Exception:
                pass
        last_event_time = now
        # Instrumentation: compute scheduled fire time and log window info
        try:
            scheduled_fire_at = last_event_time + QUIET_SECONDS
            ft = datetime.fromtimestamp(first_event_time).isoformat() if first_event_time else None
            lt = datetime.fromtimestamp(last_event_time).isoformat()
            sfa = datetime.fromtimestamp(scheduled_fire_at).isoformat()
            total_since_first = scheduled_fire_at - first_event_time if first_event_time else 0
            logger.info(
                "(runner schedule) path=%s first=%s last=%s fire_at=%s total_since_first=%.1fs",
                path,
                ft,
                lt,
                sfa,
                total_since_first,
            )
        except Exception:
            logger.debug("Instrumentation failed to format timestamps", exc_info=True)
        # cancelar timer previo
        if debounce_timer and debounce_timer.is_alive():
            debounce_timer.cancel()
        # Si excedimos MAX_WAIT desde el primer evento, disparar ya
        if (first_event_time is not None) and (now - first_event_time >= MAX_WAIT_SECONDS):
            logger.info("MAX_WAIT_SECONDS alcanzado; disparando sincronización inmediata.")
            threading.Thread(target=trigger_sync, args=("max_wait",), daemon=True).start()
            return
        # programar maybe_fire tras QUIET_SECONDS
        debounce_timer = threading.Timer(QUIET_SECONDS, maybe_fire)
        debounce_timer.daemon = True
        debounce_timer.start()


def maybe_fire():
    global first_event_time, last_event_time, debounce_timer
    with state_lock:
        if last_event_time is None:
            return
        now = time.time()
        if now - last_event_time >= QUIET_SECONDS:
            logger.info("Quiet period completado; disparando sincronización.")
            threading.Thread(target=trigger_sync, args=("quiet",), daemon=True).start()
        else:
            remaining = QUIET_SECONDS - (now - last_event_time)
            # Instrumentation: log why we re-scheduled the timer
            try:
                ft = datetime.fromtimestamp(first_event_time).isoformat() if first_event_time else None
                lt = datetime.fromtimestamp(last_event_time).isoformat()
                logger.info("(runner schedule) reprogramando maybe_fire; remaining=%.1fs first=%s last=%s", remaining, ft, lt)
            except Exception:
                logger.debug("Instrumentation maybe_fire failed", exc_info=True)
            debounce_timer = threading.Timer(remaining, maybe_fire)
            debounce_timer.daemon = True
            debounce_timer.start()


def trigger_sync(reason="manual"):
    """
    Intenta adquirir lock no bloqueante y ejecutar el runner.
    Mantiene el lock hasta que el runner termine.
    Durante la ejecución del runner se suprimen eventos generados por el propio runner.
    """
    global first_event_time, last_event_time, suppress_events
    # Instrumentation: include timestamps when attempting acquisition
    try:
        ft = datetime.fromtimestamp(first_event_time).isoformat() if first_event_time else None
        lt = datetime.fromtimestamp(last_event_time).isoformat() if last_event_time else None
        logger.info("Trigger sincronización (reason=%s) intentando adquirir lock %s (first=%s last=%s)", reason, LOCK_PATH, ft, lt)
    except Exception:
        logger.info(f"Trigger sincronización (reason={reason}) intentando adquirir lock {LOCK_PATH}")
    try:
        lock_fd = open(LOCK_PATH, "w")
    except Exception as e:
        logger.error(f"No se pudo abrir el fichero de lock: {e}")
        return
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.info("Otra sincronización está en curso; saltando trigger.")
        lock_fd.close()
        return
    except Exception as e:
        logger.error(f"Error al adquirir lock: {e}")
        lock_fd.close()
        return

    # Run runner while holding the lock. Suppress events generated by the runner.
    try:
        # Mark suppression so on_any_event ignores runner-generated events
        try:
            with state_lock:
                suppress_events = True
        except Exception:
            # Fallback: set without lock if something goes wrong
            suppress_events = True

        if not os.path.exists(RUNNER_PATH) or not os.access(RUNNER_PATH, os.X_OK):
            logger.error(f"Runner no encontrado o no ejecutable: {RUNNER_PATH}")
        else:
            logger.info(f"Lanzando runner: {RUNNER_PATH}")
            proc = subprocess.run([sys.executable, RUNNER_PATH])
            logger.info(f"Runner finalizado con código {proc.returncode}")
    except Exception as e:
        logger.exception(f"Error ejecutando el runner: {e}")
    finally:
        # Ensure we always clear suppression and release the lock
        try:
            lock_fd.close()  # libera el lock
            logger.info("Lock liberado.")
        except Exception:
            pass
        try:
            with state_lock:
                suppress_events = False
                first_event_time = None
                last_event_time = None
        except Exception:
            # Best effort cleanup
            suppress_events = False
            first_event_time = None
            last_event_time = None


def handle_exit(signum, frame):
    logger.info(f"Signal {signum} recibido, cerrando watcher.")
    try:
        if debounce_timer and debounce_timer.is_alive():
            debounce_timer.cancel()
    except Exception:
        pass
    sys.exit(0)


def _load_last_sync():
    try:
        with open(LAST_SYNC_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_dir_mtime(path):
    try:
        # Use modification time of the directory inode
        return os.path.getmtime(path)
    except Exception:
        return 0


def polling_thread(watch_paths):
    """Thread que compara tiempos en LAST_SYNC_FILE y programa una sincronización si detecta cambios.

    Itera las entradas de LAST_SYNC_FILE (path -> last_record) y compara la mtime
    del filesystem con el timestamp guardado. No filtra por `watch_paths`.
    """
    while True:
        logger.info("(polling) iteration start; LAST_SYNC_FILE=%s POLL_INTERVAL=%ds POLL_MTIME_DELTA=%.1f", LAST_SYNC_FILE, POLL_INTERVAL, POLL_MTIME_DELTA)
        try:
            last_sync = _load_last_sync()
            # last_sync is expected to be a dict mapping paths -> timestamp strings/numbers
            found_change = False
            for p, last_record in last_sync.items():
                try:
                    p_abs = os.path.abspath(os.path.realpath(p))
                    # Ignore the LAST_SYNC_FILE itself if present as a key
                    if p_abs == os.path.abspath(os.path.realpath(LAST_SYNC_FILE)):
                        continue
                    if not os.path.exists(p_abs):
                        continue

                    # Parse stored timestamp in a tolerant way
                    prev_ts = 0.0
                    if isinstance(last_record, str):
                        # Try ISO format first
                        try:
                            prev_dt = datetime.fromisoformat(last_record)
                            prev_ts = time.mktime(prev_dt.timetuple())
                        except Exception:
                            # Try common 'YYYY-MM-DD HH:MM:SS' format
                            try:
                                prev_dt = datetime.strptime(last_record, "%Y-%m-%d %H:%M:%S")
                                prev_ts = time.mktime(prev_dt.timetuple())
                            except Exception:
                                try:
                                    prev_ts = float(last_record)
                                except Exception:
                                    prev_ts = 0.0
                    elif isinstance(last_record, (int, float)):
                        prev_ts = float(last_record)
                    else:
                        prev_ts = 0.0

                    mtime = _get_dir_mtime(p_abs)
                    # Apply a small tolerance to avoid spurious detections due to clock/precision differences
                    if mtime > (prev_ts + POLL_MTIME_DELTA):
                        logger.info("(runner schedule) polling detected newer mtime for %s (mtime=%.0f prev=%.0f delta=%.1f)", p_abs, mtime, prev_ts, POLL_MTIME_DELTA)
                        schedule_on_event(POLL_PATH)
                        found_change = True
                        break  # programamos solo una vez por ciclo
                except Exception:
                    logger.debug("polling: error comprobando %s", p, exc_info=True)
            if not found_change:
                logger.info("(polling) no changes detected this iteration")
        except Exception:
            logger.debug("polling: error general", exc_info=True)
        time.sleep(POLL_INTERVAL)


def main():
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    # Try to read watch paths with retries (allows mounts and environment to become available)
    retries = int(os.environ.get("WATCHER_READ_RETRIES", "12"))
    retry_sleep = int(os.environ.get("WATCHER_READ_RETRY_SLEEP", "5"))
    watch_paths = []
    for attempt in range(1, retries + 1):
        watch_paths = read_watch_paths()
        if watch_paths:
            break
        logger.warning("Attempt %d/%d: No watch paths found yet; retrying in %ds", attempt, retries, retry_sleep)
        time.sleep(retry_sleep)

    if not watch_paths:
        logger.warning("No hay rutas para observar; arrancando en modo polling (sin inotify).")
        logger.info("Define PHOTOSYNC_SOURCE_PATHS en ~/.config/photosync/photosync.env para habilitar observación de cambios.")

    logger.info("Iniciando PhotoSync watcher en rutas: %s", watch_paths)
    observer = Observer()
    handler = EventHandler()

    # Only schedule observers if we have paths to watch
    if watch_paths:
        for p in watch_paths:
            if not os.path.exists(p):
                logger.warning(f"Ruta no existe (se ignorará): {p}")
                continue
            observer.schedule(handler, path=p, recursive=True)
        observer.start()
    else:
        logger.info("No se inicia observer (sin rutas); solo modo polling activo.")

    # Lanzamos el thread de polling (daemon)
    try:
        t = threading.Thread(target=polling_thread, args=(watch_paths,), daemon=True)
        t.start()
    except Exception:
        logger.debug("No se pudo iniciar polling thread", exc_info=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if watch_paths:
            observer.stop()

    if watch_paths:
        observer.join()


if __name__ == "__main__":
    main()
