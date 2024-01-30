import settings
import os
import json
import subprocess
from datetime import datetime

import logging
from logging.handlers import TimedRotatingFileHandler

logpath = '~/.cache/photosync/logs'
logfilename = 'photosync.log'

logpath = os.path.expanduser(logpath)

if not os.path.exists(logpath):
    os.makedirs(logpath)

if not os.path.exists(settings.TAGNAME_NOTFOUND_PATH):
    os.makedirs(settings.TAGNAME_NOTFOUND_PATH)

# format the log entries
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

handler = TimedRotatingFileHandler(logpath+'/'+logfilename, when='midnight', backupCount=30)
handler.setFormatter(formatter)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.addHandler(consoleHandler)
logger.setLevel(logging.DEBUG)

time_format = '%Y-%m-%d %H:%M:%S'
images_tagname = 'datetimeoriginal'
videos_tagname = 'trackcreatedate'
sync_times = {}


# Procesa un directorio recursivamente
def process_folder(path):
    path_info = os.stat(path)
    path_mtime_str = datetime.fromtimestamp(path_info.st_mtime).strftime(time_format)

    if sync_times is None:
        return

    if path not in sync_times or datetime.strptime(sync_times[path], time_format) < datetime.strptime(path_mtime_str, time_format):
        logger.info('Sincronizando ' + path)
        sync_times[path] = path_mtime_str
        run_sync_tool(path, images_tagname, settings.TARGET_PATH)
        run_sync_tool(path, videos_tagname, settings.TARGET_PATH)
        create_hardlink_when_tagname_notfound(path, settings.TAGNAME_NOTFOUND_PATH)
        save_sync_times()
        logger.info('Sincronizado ' + path + ' con fecha de modificación: ' + path_mtime_str)

    with os.scandir(path) as files:
        subdirectories = [file.path for file in files if file.is_dir() and not file.name.startswith('.')]

    for subdirectory in subdirectories:
        process_folder(subdirectory)


# Carga las fechas de la última sincronización
def load_sync_times():
    try:
        with open(os.path.expanduser(settings.LAST_SYNC_TIME_PATH), "r") as f:
            return json.load(f)
    except Exception:
        return None


# Guarda las fechas de la última sincronización
def save_sync_times():
    with open(os.path.expanduser(settings.LAST_SYNC_TIME_PATH), "w") as f:
        return json.dump(sync_times, f)


# Ejecuta la herramienta en el directorio path
def run_sync_tool(path, tagname, targetpath):
    command = 'cd {current_path}; exiftool -if \'${tag_name} and not (${tag_name} eq "0000:00:00 00:00:00")\' -o ./%d \"-filename<{tag_name}\" -d {target_path}/%Y/%Y-%m/%%f.%%e  -progress .'.format(target_path=targetpath, current_path=path, tag_name=tagname)
    logger.info(command)
    process = subprocess.Popen([command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    while True:
        if process.stdout:
            output = process.stdout.readline()

            if not output:
                break

            if output:
                logger.info(output.decode(encoding='cp850').strip())

    process.communicate()


def create_hardlink_when_tagname_notfound(path, targetpath):
    command = 'cd {current_path}; exiftool -if \'(not $datetimeoriginal or ($datetimeoriginal eq "0000:00:00 00:00:00")) and (not $trackcreatedate or ($trackcreatedate eq "0000:00:00 00:00:00"))\' -p \'$filename\' -q -q .'.format(current_path=path)
    logger.info(command)
    process = subprocess.Popen([command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    while True:
        if process.stdout:
            output = process.stdout.readline()

            if not output:
                break

            create_hardlink(path, output.decode(encoding='cp850').strip(), targetpath)

    process.communicate()


def create_hardlink(sourcepath, filename, targetpath):
    # TODO: añadir comillas para ficheros con ()
    command = f'ln -t {targetpath} {sourcepath}/{filename}'
    logger.info(command)
    process = subprocess.run([command], capture_output=True, shell=True)
    if process.stdout != b'':
        output = process.stdout.decode(encoding='cp850').strip()
        logger.info(output)
    if process.stderr != b'':
        output = process.stderr.decode(encoding='cp850').strip()
        logger.error(output)


# ---------------------------------------------INICIO-----------------------------------------------------------
sync_times = load_sync_times()

if sync_times is None:
    print('No se ha encontrado el fichero de los tiempos de la última sincronización')
    sync_times = {}

for path in settings.SOURCE_PATHS:
    process_folder(path)

# # Formatear propiedades de tiempo
# tiempo_acceso = datetime.fromtimestamp(info_directorio.st_atime).strftime('%Y-%m-%d %H:%M:%S')
# tiempo_modificacion = datetime.fromtimestamp(info_directorio.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
# tiempo_cambio = datetime.fromtimestamp(info_directorio.st_ctime).strftime('%Y-%m-%d %H:%M:%S')

# # Imprimir todas las propiedades del directorio
# print("Número de nodo de dispositivo:", info_directorio.st_dev)
# print("Número de nodo i:", info_directorio.st_ino)
# print("Modo:", info_directorio.st_mode)
# print("Número de enlaces rígidos:", info_directorio.st_nlink)
# print("ID de usuario del propietario:", info_directorio.st_uid)
# print("ID de grupo del propietario:", info_directorio.st_gid)
# print("Tamaño en bytes:", info_directorio.st_size)
# print("Tiempo de acceso:", tiempo_acceso)
# print("Tiempo de modificación:", tiempo_modificacion)
# print("Tiempo de cambio:", tiempo_cambio)
