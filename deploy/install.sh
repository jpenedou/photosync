#!/usr/bin/env bash
# install.sh - instala PhotoSync watcher como systemd --user service
# Uso:
#   bash deploy/install.sh [opciones] [SOURCE_DIR] [REPO_PARENT]
#   - Se puede ejecutar desde cualquier ruta
#   - SOURCE_DIR por defecto es el directorio del propio script (deploy/)
#   - REPO_PARENT por defecto es la raíz del repo (padre de deploy/)
set -euo pipefail

usage() {
  cat <<USAGE
Uso: $(basename "$0") [opciones] [SOURCE_DIR] [REPO_PARENT]
Opciones:
  --no-systemd         No recarga, habilita ni arranca la unidad systemd
  --force              Fuerza sobreescritura de ~/.config/photosync/photosync.env (hace backup)
  --non-interactive    Falla si faltan PHOTOSYNC_* requeridas en entorno, sin preguntar
  -h, --help           Muestra esta ayuda
USAGE
}

# Resolver rutas en base a la ubicación del script
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"

# Flags
NO_SYSTEMD=0
FORCE_OVERWRITE=0
NON_INTERACTIVE=0

# Parseo de opciones
ARGS=()
while [ $# -gt 0 ]; do
  case "${1:-}" in
    --no-systemd) NO_SYSTEMD=1; shift ;;
    --force|--overwrite|--force-overwrite) FORCE_OVERWRITE=1; shift ;;
    --non-interactive) NON_INTERACTIVE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "Opción desconocida: $1"; usage; exit 1 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
set -- "${ARGS[@]:-}"

# --- Parámetros y rutas (por defecto usan rutas del script) ---
SOURCE_DIR="${1:-$SCRIPT_DIR}"
REPO_PARENT="${2:-$REPO_ROOT}"

CURRENT_USER="$(id -un)"
HOME_DIR="${HOME:-/home/$CURRENT_USER}"

QUIET_SECONDS="${QUIET_SECONDS:-60}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-300}"
POLL_INTERVAL="${POLL_INTERVAL:-300}"
POLL_MTIME_DELTA="${POLL_MTIME_DELTA:-1.0}"

WATCHER_SRC="$SOURCE_DIR/photosync-watcher.py"
RUNNER_SRC="$SOURCE_DIR/photosync-run"

WATCHER_DST="$HOME_DIR/.local/bin/photosync-watcher.py"
RUNNER_DST="$HOME_DIR/.local/bin/photosync-run"

ENV_DIR="$HOME_DIR/.config/photosync"
ENV_FILE="$ENV_DIR/photosync.env"

SERVICE_DIR="$HOME_DIR/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/photosync-watcher.service"

LOCK_DIR="$HOME_DIR/.cache/photosync"
LOCK_PATH="$LOCK_DIR/.photosync.lock"

# --- Prechecks ---
echo "Install: usando SOURCE_DIR=$SOURCE_DIR"
echo "Install: usando REPO_PARENT=$REPO_PARENT"
command -v python3 >/dev/null 2>&1 || {
  echo "ERROR: python3 no encontrado"
  exit 1
}
command -v pip3 >/dev/null 2>&1 || {
  echo "ERROR: pip3 no encontrado"
  exit 1
}

missing=""
command -v exiftool >/dev/null 2>&1 || missing+=" exiftool"
command -v file >/dev/null 2>&1 || missing+=" file"
if [ -n "$missing" ]; then
  echo "AVISO: faltan utilidades del sistema:$missing (instálalas si aún no lo has hecho)."
fi

# Detectar directorio de exiftool para ampliar PATH en el unit
EXIFTOOL_BIN="$(command -v exiftool || true)"
EXIFTOOL_DIR=""
if [ -n "$EXIFTOOL_BIN" ]; then
  EXIFTOOL_DIR="$(dirname "$EXIFTOOL_BIN")"
fi

if [ ! -f "$WATCHER_SRC" ]; then
  echo "ERROR: watcher no encontrado en $WATCHER_SRC"
  exit 1
fi
if [ ! -f "$RUNNER_SRC" ]; then
  echo "ERROR: runner no encontrado en $RUNNER_SRC"
  exit 1
fi

# --- Crear dirs ---
mkdir -p "$(dirname "$WATCHER_DST")"
mkdir -p "$(dirname "$RUNNER_DST")"
mkdir -p "$ENV_DIR"
mkdir -p "$SERVICE_DIR"
mkdir -p "$LOCK_DIR"

# --- Instalar dependencia Python (watchdog) en user-space ---
echo "Instalando watchdog (user)..."
python3 -m pip install --user watchdog 2>/dev/null || {
  echo "AVISO: No se pudo instalar watchdog con pip (sistema PEP 668)."
  echo "Asegúrate de tenerlo instalado: sudo pacman -S python-watchdog"
}

# --- Copiar archivos (no incrustamos código aquí) ---
echo "Copiando watcher a $WATCHER_DST"
cp -f "$WATCHER_SRC" "$WATCHER_DST"
chmod +x "$WATCHER_DST"

echo "Copiando runner a $RUNNER_DST"
cp -f "$RUNNER_SRC" "$RUNNER_DST"
chmod +x "$RUNNER_DST"

# --- Solicitar/usar valores de configuración PhotoSync ---
# Permitir override por variables de entorno o usar prompts interactivos
echo ""
echo "=== Configuración de PhotoSync ==="

if [ -z "${PHOTOSYNC_SOURCE_PATHS:-}" ]; then
  if [ "$NON_INTERACTIVE" -eq 1 ]; then
    echo "ERROR: PHOTOSYNC_SOURCE_PATHS no definido y modo --non-interactive activo"
    exit 1
  fi
  echo "Introduce las rutas de origen (separadas por ':'), por ejemplo: /mnt/a:/mnt/b"
  read -p "Rutas de origen: " PHOTOSYNC_SOURCE_PATHS
fi

if [ -z "${PHOTOSYNC_TARGET_PATH:-}" ]; then
  if [ "$NON_INTERACTIVE" -eq 1 ]; then
    echo "ERROR: PHOTOSYNC_TARGET_PATH no definido y modo --non-interactive activo"
    exit 1
  fi
  read -p "Ruta de destino para fotos organizadas: " PHOTOSYNC_TARGET_PATH
fi

if [ -z "${PHOTOSYNC_TAGNAME_NOTFOUND_PATH:-}" ]; then
  read -p "Ruta para archivos sin fecha [usar TARGET_PATH/NO_DATE]: " INPUT_NOTFOUND
  if [ -n "$INPUT_NOTFOUND" ]; then
    PHOTOSYNC_TAGNAME_NOTFOUND_PATH="$INPUT_NOTFOUND"
  elif [ -n "$PHOTOSYNC_TARGET_PATH" ]; then
    PHOTOSYNC_TAGNAME_NOTFOUND_PATH="$PHOTOSYNC_TARGET_PATH/NO_DATE"
  else
    PHOTOSYNC_TAGNAME_NOTFOUND_PATH=""
  fi
fi

PHOTOSYNC_LAST_SYNC_TIME_PATH="${PHOTOSYNC_LAST_SYNC_TIME_PATH:-~/.cache/photosync/.photosync_last.json}"
PHOTOSYNC_DRY_RUN="${PHOTOSYNC_DRY_RUN:-0}"

# --- Escribir env file (no sobrescribir por defecto) ---
if [ -f "$ENV_FILE" ] && [ "$FORCE_OVERWRITE" -ne 1 ]; then
  echo "Env ya existe en $ENV_FILE; no se sobrescribe (usa --force para sobreescribir)."
else
  if [ -f "$ENV_FILE" ] && [ "$FORCE_OVERWRITE" -eq 1 ]; then
    ts="$(date +%Y%m%d%H%M%S)"
    cp -f "$ENV_FILE" "$ENV_FILE.bak.$ts" || true
    echo "Backup creado: $ENV_FILE.bak.$ts"
  fi
  echo "Escribiendo env file en $ENV_FILE"
  cat >"$ENV_FILE" <<EOF
# PhotoSync user service env
PYTHONPATH=$REPO_PARENT

# Watcher configuration
QUIET_SECONDS=$QUIET_SECONDS
MAX_WAIT_SECONDS=$MAX_WAIT_SECONDS
RUNNER_PATH=$RUNNER_DST
LOCK_PATH=$LOCK_PATH

# Polling configuration
POLL_INTERVAL=$POLL_INTERVAL
POLL_MTIME_DELTA=$POLL_MTIME_DELTA

# PhotoSync paths configuration
PHOTOSYNC_SOURCE_PATHS=$PHOTOSYNC_SOURCE_PATHS
PHOTOSYNC_TARGET_PATH=$PHOTOSYNC_TARGET_PATH
PHOTOSYNC_TAGNAME_NOTFOUND_PATH=$PHOTOSYNC_TAGNAME_NOTFOUND_PATH
PHOTOSYNC_LAST_SYNC_TIME_PATH=$PHOTOSYNC_LAST_SYNC_TIME_PATH

# PhotoSync behavior
PHOTOSYNC_DRY_RUN=$PHOTOSYNC_DRY_RUN
EOF
fi

# --- Escribir systemd user unit ---
echo "Escribiendo unit user en $SERVICE_FILE"
# Construir PATH extendido incluyendo directorios estándar y el de exiftool si se detectó
EXT_PATH="/usr/local/bin:/usr/bin:/bin"
if [ -n "$EXIFTOOL_DIR" ]; then
  case ":$EXT_PATH:" in
    *":$EXIFTOOL_DIR:"*) : ;; # ya está incluido
    *) EXT_PATH="$EXT_PATH:$EXIFTOOL_DIR" ;;
  esac
fi
cat >"$SERVICE_FILE" <<EOF
[Unit]
Description=PhotoSync Watcher (user)
After=network.target

[Service]
Type=simple
EnvironmentFile=%h/.config/photosync/photosync.env
Environment=PATH=$EXT_PATH
ExecStart=/usr/bin/python3 %h/.local/bin/photosync-watcher.py
SyslogIdentifier=photosync
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# --- Habilitar & arrancar la unidad user (opcional) ---
if [ "$NO_SYSTEMD" -eq 1 ]; then
  echo "Saltando pasos systemd (--no-systemd)"
else
  echo "Recargando systemd user..."
  systemctl --user daemon-reload
  echo "Habilitando y arrancando photosync-watcher.service (user)..."
  systemctl --user enable --now photosync-watcher.service
fi

echo "Instalación completada."
echo "Comprueba logs con: journalctl --user -u photosync-watcher.service -f"
