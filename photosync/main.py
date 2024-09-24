import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from typing import Dict
from logging.handlers import TimedRotatingFileHandler
from photosync import settings

# TODO: mover a settings.py
logpath = "~/.cache/photosync/logs"
logfilename = "photosync.log"

logpath = os.path.expanduser(logpath)

if not os.path.exists(logpath):
    os.makedirs(logpath)

if not os.path.exists(settings.TAGNAME_NOTFOUND_PATH):
    os.makedirs(settings.TAGNAME_NOTFOUND_PATH)

# format the log entries
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

handler = TimedRotatingFileHandler(logpath + "/" + logfilename, when="midnight", backupCount=30)
handler.setFormatter(formatter)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.addHandler(consoleHandler)
logger.setLevel(logging.DEBUG)

# TODO: revisar si la fecha es UTC para las dos tags
time_format = "%Y-%m-%d %H:%M:%S"
images_tagname = "datetimeoriginal"
videos_tagname = "trackcreatedate"

sync_times: Dict[str, str] = {}


# Función para detectar el tipo de archivo con el comando file
def detectar_tipo_archivo(archivo):
    resultado = subprocess.run(["file", "--mime-type", archivo], stdout=subprocess.PIPE, text=True)
    mime_type = resultado.stdout.strip().split(": ")[1]
    return mime_type


# Función para obtener la fecha de captura o creación con exiftool
def obtener_fecha_exif(archivo):
    resultado = subprocess.run(
        ["exiftool", "-DateTimeOriginal", "-TrackCreateDate", archivo],
        stdout=subprocess.PIPE,
        text=True,
    )
    salida = resultado.stdout.strip()

    fecha_str = None
    fecha = None

    # Buscar si hay una fecha para DateTimeOriginal
    for linea in salida.splitlines():
        if "Date/Time Original" in linea:
            fecha_str = linea.split(": ", 1)[1]
            break
        elif "Track Create Date" in linea:
            fecha_str = linea.split(": ", 1)[1]
            break

    # Si se encontró una fecha, parsearla
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, "%Y:%m:%d %H:%M:%S")
            return fecha.strftime("%Y%m%d_%H%M%S"), fecha
        except ValueError:
            return None, None

    return None, None


# Función para construir la nueva ruta basada en la fecha
def construir_nueva_ruta(base_path, fecha):
    year = fecha.strftime("%Y")
    year_month = fecha.strftime("%Y-%m")

    nueva_ruta = os.path.join(base_path, year, year_month)

    # Crear directorios si no existen
    os.makedirs(nueva_ruta, exist_ok=True)

    return nueva_ruta


# Función para renombrar el archivo basado en el formato IMG_XXXX.EEE
def renombrar_archivo(archivo, fecha_formateada):
    nombre_archivo, extension = os.path.splitext(os.path.basename(archivo))

    # Detectar si el archivo tiene el formato IMG_XXXX.EEE
    match = re.match(r"IMG_(\d+)(\..+)", nombre_archivo + extension)

    if match:
        numero = match.group(1)  # Extraer XXXX
        nueva_extension = match.group(2)  # Extraer EEE (con punto incluido)
        nuevo_nombre = f"{fecha_formateada}_{numero}{nueva_extension}"
    else:
        nuevo_nombre = f"{fecha_formateada}{extension}"

    return nuevo_nombre


# Función para calcular el hash SHA256 de un archivo
def calcular_hash_archivo(archivo):
    hash_sha256 = hashlib.sha256()
    with open(archivo, "rb") as f:
        while chunk := f.read(8192):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


# Función para copiar y renombrar el archivo
def copiar_y_renombrar_archivo(archivo, nueva_ruta, nuevo_nombre):
    archivo_nuevo = os.path.join(nueva_ruta, nuevo_nombre)

    # Obtener el nombre del archivo original
    nombre_original = os.path.basename(archivo)

    # Verificar si existe un archivo con el mismo nombre en la nueva ruta
    archivo_existente = os.path.join(nueva_ruta, nombre_original)

    hash_archivo = calcular_hash_archivo(archivo)

    def comprobar_si_sincronizado(hash_archivo, archivo_nuevo):
        if os.path.exists(archivo_nuevo):
            return hash_archivo == calcular_hash_archivo(archivo_nuevo)

    if os.path.exists(archivo_existente):
        # Comparar contenido de los archivos
        if hash_archivo == calcular_hash_archivo(archivo_existente):
            if comprobar_si_sincronizado(hash_archivo, archivo_nuevo):
                logger.info(f"{nombre_original} se omite, ya sincronizado en: {archivo_nuevo}")
            else:
                # Copiar el archivo
                shutil.copy2(archivo, archivo_nuevo)  # shutil.copy2 mantiene los metadatos

            # Verificar si la copia fue exitosa
            if os.path.exists(archivo_nuevo):
                # Eliminar el archivo existente después de una copia exitosa
                os.remove(archivo_existente)
                logger.info(f"{nombre_original} copiado a: {archivo_nuevo} y eliminado el archivo existente: {archivo_existente}")
            else:
                logger.error(f"{nombre_original} no se pudo copiar a: {archivo_nuevo}")
        else:
            logger.warning(f"{nombre_original} ya existe con diferente contenido en: {archivo_existente}")
    else:
        if comprobar_si_sincronizado(hash_archivo, archivo_nuevo):
            logger.info(f"{nombre_original} se omite, ya sincronizado en: {archivo_nuevo}")
            return

        # Copiar el archivo si no existe en la nueva ruta
        shutil.copy2(archivo, archivo_nuevo)  # shutil.copy2 mantiene los metadatos

        logger.info(f"{nombre_original} copiado a: {archivo_nuevo}")


# Función para crear un enlace duro
def crear_enlace_duro(archivo, links_path):
    """
    Crea un enlace duro al archivo especificado en el directorio links_path.

    :param archivo: Ruta del archivo original.
    :param links_path: Ruta del directorio donde se creará el enlace duro.
    """
    if not os.path.isfile(archivo):
        logger.error(f"El archivo original no existe: {archivo}")
        return

    enlace_nuevo = os.path.join(links_path, os.path.basename(archivo))

    os.makedirs(links_path, exist_ok=True)  # Crear directorios si no existen

    if os.path.exists(enlace_nuevo):
        logger.warning(f"{os.path.basename(archivo)} ya tiene un enlace duro en: {enlace_nuevo}")
        return

    try:
        os.link(archivo, enlace_nuevo)
        logger.info(f"{os.path.basename(archivo)} enlace duro creado en: {enlace_nuevo}")
    except Exception as e:
        logger.error(f"{os.path.basename(archivo)} no se pudo crear el enlace duro: {e}")


# Función para obtener el tiempo de modificación de un archivo
def obtener_changed_time(archivo):
    # TODO: revisar getmtime
    return datetime.fromtimestamp(os.path.getctime(archivo))


# Función principal que integra los procesos
def process_files(base_path, target_path="./", links_path="./links"):
    # Obtener el tiempo de modificación de base_path
    base_path_changed_time = obtener_changed_time(base_path)
    base_path_sync_time = None

    if base_path in sync_times:
        base_path_sync_time = datetime.strptime(sync_times[base_path], time_format)

    # Iterar sobre todos los archivos en base_path
    for raiz, _, archivos in os.walk(base_path):
        for archivo in archivos:
            archivo_path = os.path.join(raiz, archivo)
            # Verificar el tiempo de modificación del archivo
            archivo_changed_time = obtener_changed_time(archivo_path)

            if base_path_sync_time is None or archivo_changed_time >= base_path_sync_time:
                mime_type = detectar_tipo_archivo(archivo_path)

                if "image" in mime_type or "video" in mime_type:
                    fecha_formateada, fecha = obtener_fecha_exif(archivo_path)

                    if fecha:
                        nueva_ruta = construir_nueva_ruta(target_path, fecha)
                        nuevo_nombre = renombrar_archivo(archivo_path, fecha_formateada)
                        copiar_y_renombrar_archivo(archivo_path, nueva_ruta, nuevo_nombre)
                    else:
                        # Crear enlace duro si la fecha no existe
                        crear_enlace_duro(archivo_path, links_path)
                else:
                    logger.warning(f"{archivo} no es una imagen ni un video.")
            else:
                logger.info(f"{archivo} se omite, no se ha modificado (ctime: {archivo_changed_time})")

    sync_times[base_path] = base_path_changed_time.strftime(time_format)


# # Ejemplo de uso
# base_path = "./origen"  # Ruta base para buscar archivos
# target_path = "./destino"  # Ruta base para copiar los archivos
# links_path = "./links"  # Ruta base para crear enlaces duros
# procesar_archivos(base_path, target_path, links_path)


# Procesa un directorio recursivamente
def process_folder(path):
    # TODO: revisar st_mtime, utilizar la funcion obtener_changed_time
    path_ctime = obtener_changed_time(path).replace(microsecond=0)
    path_ctime_str = datetime.strftime(path_ctime, time_format)

    if path not in sync_times or datetime.strptime(sync_times[path], time_format) < path_ctime:
        logger.info("Sincronizando " + path)
        # sync_times[path] = path_mtime_str
        # run_sync_tool(path, images_tagname, settings.TARGET_PATH)
        # run_sync_tool(path, videos_tagname, settings.TARGET_PATH)
        # create_hardlink_when_tagname_notfound(path, settings.TAGNAME_NOTFOUND_PATH)
        process_files(path, settings.TARGET_PATH, settings.TAGNAME_NOTFOUND_PATH)
        save_sync_times()
        logger.info("Sincronizado " + path + " con fecha de modificación: " + path_ctime_str)
    else:
        if path in sync_times:
            logger.info(f"{path} se omite, ya ha sido sincronizado")

    with os.scandir(path) as files:
        subdirectories = [file.path for file in files if file.is_dir() and not file.name.startswith(".")]

    for subdirectory in subdirectories:
        process_folder(subdirectory)


# Carga las fechas de la última sincronización
def load_sync_times():
    with open(os.path.expanduser(settings.LAST_SYNC_TIME_PATH), "r") as f:
        return json.load(f)


# Guarda las fechas de la última sincronización
def save_sync_times():
    with open(os.path.expanduser(settings.LAST_SYNC_TIME_PATH), "w") as f:
        return json.dump(sync_times, f)


# # Ejecuta la herramienta en el directorio path
# def run_sync_tool(path, tagname, targetpath):
#     command = 'cd {current_path}; exiftool -if \'${tag_name} and not (${tag_name} eq "0000:00:00 00:00:00")\' -o ./%d "-filename<{tag_name}" -d {target_path}/%Y/%Y-%m/%%f.%%e  -progress .'.format(
#         target_path=targetpath, current_path=path, tag_name=tagname
#     )
#     logger.info(command)
#     process = subprocess.Popen([command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
#
#     while True:
#         if process.stdout:
#             output = process.stdout.readline()
#
#             if not output:
#                 break
#
#             if output:
#                 logger.info(output.decode(encoding="cp850").strip())
#
#     process.communicate()
#
#
# def create_hardlink_when_tagname_notfound(path, targetpath):
#     command = "cd {current_path}; exiftool -if '(not $datetimeoriginal or ($datetimeoriginal eq \"0000:00:00 00:00:00\")) and (not $trackcreatedate or ($trackcreatedate eq \"0000:00:00 00:00:00\"))' -p '$filename' -q -q .".format(current_path=path)
#     logger.info(command)
#     process = subprocess.Popen([command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
#
#     while True:
#         if process.stdout:
#             output = process.stdout.readline()
#
#             if not output:
#                 break
#
#             create_hardlink(path, output.decode(encoding="cp850").strip(), targetpath)
#
#     process.communicate()
#
#
# def create_hardlink(sourcepath, filename, targetpath):
#     # TODO: añadir comillas para ficheros con ()
#     command = f"ln -t {targetpath} {sourcepath}/{filename}"
#     logger.info(command)
#     process = subprocess.run([command], capture_output=True, shell=True)
#     if process.stdout != b"":
#         output = process.stdout.decode(encoding="cp850").strip()
#         logger.info(output)
#     if process.stderr != b"":
#         output = process.stderr.decode(encoding="cp850").strip()
#         logger.error(output)
