#!/usr/bin/env bash
# uninstall.sh - desinstala PhotoSync watcher user service
set -euo pipefail

CURRENT_USER="$(id -un)"
HOME_DIR="${HOME:-/home/$CURRENT_USER}"

WATCHER_DST="$HOME_DIR/.local/bin/photosync-watcher.py"
RUNNER_DST="$HOME_DIR/.local/bin/photosync-run"
ENV_FILE="$HOME_DIR/.config/photosync/photosync.env"
SERVICE_FILE="$HOME_DIR/.config/systemd/user/photosync-watcher.service"
LOCK_DIR="$HOME_DIR/.cache/photosync"

echo "Deteniendo servicio user (si existe)..."
systemctl --user stop photosync-watcher.service 2>/dev/null || true
systemctl --user disable photosync-watcher.service 2>/dev/null || true
systemctl --user daemon-reload

echo "Eliminando archivos..."
rm -f "$WATCHER_DST" || true
rm -f "$RUNNER_DST" || true
rm -f "$ENV_FILE" || true
rm -f "$SERVICE_FILE" || true

echo "Nota: el directorio de lock/cache ($LOCK_DIR) no se elimina automáticamente."
echo "Para eliminarlo manualmente: rm -rf \"$LOCK_DIR\""

echo "Desinstalación completada."
