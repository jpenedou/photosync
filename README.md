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

4.  **Instalar ExifTool**:
    PhotoSync depende de `ExifTool` para extraer metadatos. Asegúrate de tenerlo instalado en tu sistema.
    -   **Linux (Debian/Ubuntu)**: `sudo apt-get install libimage-exiftool-perl`
    -   **macOS**: `brew install exiftool`
    -   **Windows**: Descarga el ejecutable desde la [página oficial de ExifTool](https://exiftool.org/install.html) y añádelo a tu PATH.

## Configuración

La configuración de las rutas de origen, destino y para archivos sin fecha se realiza en el archivo `photosync/settings.py`.

-   `SOURCE_PATHS`: Una tupla de rutas a los directorios de origen que contienen las fotos y videos a sincronizar.
-   `TARGET_PATH`: La ruta al directorio donde se organizarán las fotos y videos con metadatos de fecha.
-   `TAGNAME_NOTFOUND_PATH`: La ruta al directorio donde se crearán enlaces duros para los archivos sin metadatos de fecha.

Ejemplo de `photosync/settings.py`:
```python
SOURCE_PATHS = "/ruta/a/tus/fotos/movil1", "/ruta/a/tus/fotos/movil2"
TARGET_PATH = "/ruta/a/tu/biblioteca/fotos"
TAGNAME_NOTFOUND_PATH = "/ruta/a/tu/biblioteca/fotos/sin_fecha"
LAST_SYNC_TIME_PATH = "~/.cache/photosync/.photosync_last.json"
```

## Uso

Para ejecutar PhotoSync, navega al directorio raíz del proyecto y ejecuta el script `main.py`.

```bash
python photosync/main.py
```

**Nota**: Este script no acepta argumentos de línea de comandos. Toda la configuración de rutas se realiza a través del archivo `photosync/settings.py`. El script procesará los directorios definidos en `SOURCE_PATHS` de forma recursiva.

## Pruebas

Para ejecutar las pruebas del proyecto, asegúrate de tener `pytest` instalado (`pip install pytest`) y luego ejecuta:

```bash
pytest
```
