# PhotoSync

## Descripción

PhotoSync es una herramienta de sincronización de fotos y videos diseñada para organizar automáticamente tus archivos multimedia. Procesa imágenes y videos, los renombra basándose en sus metadatos EXIF (fecha de captura/creación) y los organiza en una estructura de directorios basada en el año y el mes. Los archivos que no contienen metadatos de fecha son movidos a un directorio específico para su revisión manual.

## Características

-   **Organización Automática**: Renombra y organiza fotos y videos en directorios `YYYY/YYYY-MM` basados en la fecha de sus metadatos EXIF.
-   **Manejo de Archivos sin Fecha**: Crea enlaces duros para archivos que no tienen metadatos de fecha, facilitando su identificación y procesamiento manual.
-   **Detección de Duplicados**: Evita la copia de archivos duplicados mediante la verificación de hashes SHA256.
-   **Registro Detallado**: Genera logs para un seguimiento completo de las operaciones realizadas.
-   **Sincronización Incremental**: Solo procesa archivos nuevos o modificados desde la última sincronización.

## Instalación

1.  **Clonar el repositorio**:
    ```bash
    git clone https://github.com/yourusername/photosync.git
    cd photosync
    ```

2.  **Crear un entorno virtual (recomendado)**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # En Windows: `venv\Scripts\activate`
    ```

3.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```
    
    O en sistemas con gestión de paquetes del sistema (Arch Linux):
    ```bash
    sudo pacman -S python-pytest python-ruff python-dotenv
    ```

4.  **Instalar ExifTool**:
    PhotoSync depende de `ExifTool` para extraer metadatos. Asegúrate de tenerlo instalado en tu sistema.
    -   **Linux (Debian/Ubuntu)**: `sudo apt-get install libimage-exiftool-perl`
    -   **macOS**: `brew install exiftool`
    -   **Windows**: Descarga el ejecutable desde la [página oficial de ExifTool](https://exiftool.org/install.html) y añádelo a tu PATH.

## Configuración

PhotoSync utiliza variables de entorno para su configuración. Las rutas específicas del usuario deben definirse en `~/.config/photosync/photosync.env` después de ejecutar el script de instalación.

**Comportamiento de auto-carga**: El módulo `photosync.settings` utiliza `python-dotenv` para cargar automáticamente `~/.config/photosync/photosync.env` si existe. Las variables de entorno ya definidas tienen precedencia sobre los valores del archivo.

### Variables de configuración requeridas:

-   `PHOTOSYNC_SOURCE_PATHS`: Rutas de origen separadas por `:` (ej. `/mnt/a:/mnt/b`)
-   `PHOTOSYNC_TARGET_PATH`: Directorio donde se organizarán las fotos con metadatos de fecha
-   `PHOTOSYNC_TAGNAME_NOTFOUND_PATH`: Directorio para archivos sin metadatos de fecha

### Variables opcionales:

-   `PHOTOSYNC_LAST_SYNC_TIME_PATH`: Archivo para guardar marcas de tiempo (default: `~/.cache/photosync/.photosync_last.json`)
-   `PHOTOSYNC_DRY_RUN`: Activar modo dry-run (valores: `1`, `true`, `yes`, `on`)
-   `QUIET_SECONDS`: Segundos de silencio antes de disparar sincronización (default: `60`)
-   `MAX_WAIT_SECONDS`: Máximo tiempo de espera acumulando cambios (default: `300`)
-   `POLL_INTERVAL`: Intervalo de polling en segundos (default: `300`)
-   `POLL_MTIME_DELTA`: Tolerancia en segundos para comparación de mtime (default: `1.0`)

### Instalación como servicio systemd

Para instalar PhotoSync como servicio de usuario systemd con watcher automático:

```bash
bash deploy/install.sh
```

El instalador se puede ejecutar desde cualquier ubicación sin necesidad de parámetros. Detecta automáticamente las rutas del repositorio y crea:
- `~/.config/photosync/photosync.env` con tu configuración
- `~/.local/bin/photosync-run` y `~/.local/bin/photosync-watcher.py`
- Servicio systemd en `~/.config/systemd/user/photosync-watcher.service`

**Opciones del instalador**:
- `--no-systemd`: Instala archivos pero no activa el servicio systemd (útil para pruebas)
- `--force`: Sobrescribe `photosync.env` existente (crea backup automático)
- `--non-interactive`: Falla si faltan variables de entorno requeridas (no pregunta)
- `-h, --help`: Muestra ayuda de uso

**Comportamiento de protección**: Por defecto, el instalador NO sobrescribe `~/.config/photosync/photosync.env` si ya existe. Usa `--force` para actualizar la configuración (se creará un backup con timestamp).

**Ejemplos de uso**:

```bash
# Instalación normal (pregunta rutas si no están en entorno)
bash deploy/install.sh

# Instalación no interactiva con variables predefinidas
PHOTOSYNC_SOURCE_PATHS="/mnt/a:/mnt/b" \
PHOTOSYNC_TARGET_PATH="/mnt/photos" \
PHOTOSYNC_TAGNAME_NOTFOUND_PATH="/mnt/photos/NO_DATE" \
bash deploy/install.sh

# Solo instalar archivos sin activar systemd (para pruebas)
bash deploy/install.sh --no-systemd

# Forzar actualización de configuración (crea backup)
bash deploy/install.sh --force
```

Para desinstalar:

```bash
bash deploy/uninstall.sh
```

### Ejemplo de `~/.config/photosync/photosync.env`:

```bash
# PhotoSync user service env
PYTHONPATH=~/code/python/photosync

# Watcher configuration
QUIET_SECONDS=60
MAX_WAIT_SECONDS=300
RUNNER_PATH=~/.local/bin/photosync-run
LOCK_PATH=~/.cache/photosync/.photosync.lock

# Polling configuration
POLL_INTERVAL=300
POLL_MTIME_DELTA=1.0

# PhotoSync paths configuration (user-specific, set during install.sh)
PHOTOSYNC_SOURCE_PATHS=/mnt/disk1/photos:/mnt/disk2/photos
PHOTOSYNC_TARGET_PATH=/mnt/organized/photos
PHOTOSYNC_TAGNAME_NOTFOUND_PATH=/mnt/organized/photos/NO_DATE
PHOTOSYNC_LAST_SYNC_TIME_PATH=~/.cache/photosync/.photosync_last.json

# PhotoSync behavior
PHOTOSYNC_DRY_RUN=0
```

## Uso

### Ejecución manual (desarrollo)

Para ejecutar PhotoSync manualmente, el archivo `~/.config/photosync/photosync.env` se carga automáticamente si existe. También puedes definir o sobrescribir variables específicas exportándolas antes de la ejecución:

```bash
# Opción 1: Ejecución directa (auto-carga desde ~/.config/photosync/photosync.env)
python3 init.py

# Opción 2: Cargar explícitamente desde el archivo env (opcional)
set -a && source ~/.config/photosync/photosync.env && set +a && python3 init.py

# Opción 3: Sobrescribir variables específicas (tienen precedencia sobre el archivo)
export PHOTOSYNC_SOURCE_PATHS="/mnt/a:/mnt/b"
export PHOTOSYNC_TARGET_PATH="/mnt/fotos"
python3 init.py

# Opción 4: Dry-run (solo mostrar lo que se haría)
export PHOTOSYNC_DRY_RUN=1
python3 init.py
```

### Uso como servicio

Una vez instalado, el servicio se ejecuta automáticamente:

```bash
# Ver estado
systemctl --user status photosync-watcher.service

# Ver logs en tiempo real
journalctl --user -u photosync-watcher.service -f

# Detener/iniciar manualmente
systemctl --user stop photosync-watcher.service
systemctl --user start photosync-watcher.service
```

**Nota**: Si no se definen rutas de origen (`PHOTOSYNC_SOURCE_PATHS`), el watcher se ejecutará en "modo polling" (sin observar cambios con inotify) y el runner/init terminarán sin procesar nada, mostrando un mensaje informativo.

## Pruebas

Para ejecutar las pruebas del proyecto, asegúrate de tener `pytest` instalado (`pip install pytest`) y luego ejecuta:

```bash
pytest
```
