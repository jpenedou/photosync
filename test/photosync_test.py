import os
import shutil
from pathlib import Path
import pytest
import subprocess
from unittest.mock import patch, Mock
from photosync import main, settings


# Función para copiar un archivo de un directorio fuente a un directorio de destino
def copiar_archivo(ruta_origen, ruta_destino, nombre_archivo):
    origen = os.path.join(ruta_origen, nombre_archivo)
    destino = os.path.join(ruta_destino, nombre_archivo)

    if os.path.exists(origen):
        shutil.copy(origen, destino)
        print(f"Archivo {nombre_archivo} copiado de {ruta_origen} a {ruta_destino}")
    else:
        raise FileNotFoundError(f"El archivo {nombre_archivo} no existe en {ruta_origen}")


# Extraer la fecha del nombre de archivo, formato esperado YYYYmmDD_HHMMSS
def extraer_fecha_desde_nombre(nombre_archivo):
    try:
        # Dividir el nombre del archivo por el guion bajo
        partes = nombre_archivo.split("_")

        # Asegurarse de que hay al menos dos partes (fecha y hora)
        if len(partes) < 2:
            raise ValueError("Formato de nombre de archivo inválido.")

        fecha = partes[0]  # YYYYMMDD
        # Separar la hora de la extensión
        hora_con_extension = partes[1]
        hora = hora_con_extension.split(".")[0]  # Obtener solo la parte de la hora sin extensión

        # Verificar que la fecha y la hora tienen la longitud correcta
        if len(fecha) != 8 or len(hora) != 6:
            raise ValueError("Formato de fecha y hora inválido.")

        # Formatear la fecha
        fecha_formateada = f"{fecha[:4]}-{fecha[4:6]}-{fecha[6:]} {hora[:2]}:{hora[2:4]}:{hora[4:]}"
        return fecha_formateada
    except (IndexError, ValueError) as e:
        # Lanzar excepción en caso de error
        raise ValueError("El nombre del archivo no tiene un formato válido.") from e


# Detectar el tipo de archivo usando la herramienta file
def detectar_tipo_archivo(archivo):
    resultado = subprocess.run(["file", "--mime-type", "-b", archivo], capture_output=True, text=True)
    tipo = resultado.stdout.strip()
    return tipo


# Fixture para preparar y limpiar el entorno de prueba
@pytest.fixture
def entorno_de_prueba():
    # Asegurar que main use 'exiftool' aunque no esté en PATH del entorno de test
    main.EXIFTOOL_PATH = "exiftool"

    settings.SOURCE_PATHS = os.path.abspath("./test/movil")
    settings.TARGET_PATH = os.path.abspath("./test/fotos")
    settings.TAGNAME_NOTFOUND_PATH = os.path.abspath("./test/fotos/no_date")
    # TODO: Este fichero no se crea durane la ejecución de los tests, no se llama a save_sync_times
    settings.LAST_SYNC_TIME_PATH = "./test/.photosync_last.json"
    media_path = os.path.abspath("./test/media")

    # Crear directorios
    Path(settings.SOURCE_PATHS).mkdir(parents=True, exist_ok=True)
    Path(settings.TARGET_PATH).mkdir(parents=True, exist_ok=True)
    Path(media_path).mkdir(parents=True, exist_ok=True)

    yield settings.SOURCE_PATHS, settings.TARGET_PATH, settings.TAGNAME_NOTFOUND_PATH, media_path

    # Limpiar directorios después de la prueba
    shutil.rmtree(settings.SOURCE_PATHS)
    if os.path.exists(settings.TARGET_PATH):
        shutil.rmtree(settings.TARGET_PATH)
    if os.path.exists(settings.TAGNAME_NOTFOUND_PATH):
        shutil.rmtree(settings.TAGNAME_NOTFOUND_PATH)


# Test parametrizado para imágenes y vídeos
@patch("subprocess.run")
@pytest.mark.parametrize(
    "nombre_archivo_original, nuevo_nombre_esperado",
    [
        ("IMG_20240901_102904.jpg", "20240901_102905.jpg"),
        ("IMG_5153.HEIC", "20240901_205832_5153.HEIC"),
        ("IMG_5154.MP4", "20240901_190032_5154.MP4"),
        ("IMG_5155.MOV", "20240901_190417_5155.MOV"),
        ("VID_20240903_161055.mp4", "20240903_151141.mp4"),
    ],
)
def test_copiar_archivo(mock_run, entorno_de_prueba, nombre_archivo_original, nuevo_nombre_esperado):
    base_path, target_path, links_path, media_path = entorno_de_prueba

    with open(os.path.join(media_path, nombre_archivo_original), "w") as f:
        pass

    def side_effect(*args, **kwargs):
        command = args[0]
        cmd = os.path.basename(command[0])
        if cmd == "file":
            if ".jpg" in command[-1] or ".HEIC" in command[-1]:
                return Mock(stdout="whatever: image/jpeg")
            elif ".MP4" in command[-1] or ".MOV" in command[-1] or ".mp4" in command[-1]:
                return Mock(stdout="whatever: video/mp4")
        elif cmd == "exiftool":
            fecha_str = extraer_fecha_desde_nombre(nuevo_nombre_esperado).replace("-", ":")
            if ".jpg" in command[-1] or ".HEIC" in command[-1]:
                return Mock(stdout=f"Date/Time Original: {fecha_str}")
            elif ".MP4" in command[-1] or ".MOV" in command[-1] or ".mp4" in command[-1]:
                return Mock(stdout=f"Track Create Date: {fecha_str}")
        return Mock(stdout="")

    mock_run.side_effect = side_effect

    copiar_archivo(media_path, base_path, nombre_archivo_original)

    main.process_files(base_path, target_path, links_path)

    fecha_desde_nombre = extraer_fecha_desde_nombre(nuevo_nombre_esperado)

    assert fecha_desde_nombre, f"No se ha podido obtener la fecha del archivo: {nuevo_nombre_esperado}"

    anio_mes = f"{fecha_desde_nombre[:4]}-{fecha_desde_nombre[5:7]}"
    ruta_esperada = os.path.join(target_path, fecha_desde_nombre[:4], anio_mes, nuevo_nombre_esperado)

    assert os.path.exists(ruta_esperada), f"El archivo no se copió a la ruta esperada: {ruta_esperada}"


# Test para verificar la eliminación de archivo existente
@patch("subprocess.run")
@pytest.mark.parametrize(
    "nombre_archivo_original, nuevo_nombre_esperado",
    [
        ("IMG_20240901_102904.jpg", "20240901_102905.jpg"),
        ("IMG_5153.HEIC", "20240901_205832_5153.HEIC"),
        ("IMG_5154.MP4", "20240901_190032_5154.MP4"),
        ("IMG_5155.MOV", "20240901_190417_5155.MOV"),
        ("VID_20240903_161055.mp4", "20240903_151141.mp4"),
    ],
)
def test_eliminar_archivo_existente(mock_run, entorno_de_prueba, nombre_archivo_original, nuevo_nombre_esperado):
    base_path, target_path, links_path, media_path = entorno_de_prueba

    with open(os.path.join(media_path, nombre_archivo_original), "w") as f:
        pass

    def side_effect(*args, **kwargs):
        command = args[0]
        cmd = os.path.basename(command[0])
        if cmd == "file":
            if ".jpg" in command[-1] or ".HEIC" in command[-1]:
                return Mock(stdout="whatever: image/jpeg")
            elif ".MP4" in command[-1] or ".MOV" in command[-1] or ".mp4" in command[-1]:
                return Mock(stdout="whatever: video/mp4")
        elif cmd == "exiftool":
            fecha_str = extraer_fecha_desde_nombre(nuevo_nombre_esperado).replace("-", ":")
            if ".jpg" in command[-1] or ".HEIC" in command[-1]:
                return Mock(stdout=f"Date/Time Original: {fecha_str}")
            elif ".MP4" in command[-1] or ".MOV" in command[-1] or ".mp4" in command[-1]:
                return Mock(stdout=f"Track Create Date: {fecha_str}")
        return Mock(stdout="")

    mock_run.side_effect = side_effect

    copiar_archivo(media_path, base_path, nombre_archivo_original)

    fecha_desde_nombre = extraer_fecha_desde_nombre(nuevo_nombre_esperado)

    assert fecha_desde_nombre, f"No se ha podido obtener la fecha del archivo: {nuevo_nombre_esperado}"

    anio_mes = f"{fecha_desde_nombre[:4]}-{fecha_desde_nombre[5:7]}"
    ruta_esperada = os.path.join(target_path, fecha_desde_nombre[:4], anio_mes)

    Path(ruta_esperada).mkdir(parents=True, exist_ok=True)

    copiar_archivo(media_path, ruta_esperada, nombre_archivo_original)

    path_archivo_existente = os.path.join(ruta_esperada, nombre_archivo_original)

    assert os.path.exists(path_archivo_existente), f"El archivo esperado no se encontró: {path_archivo_existente}"

    main.process_files(base_path, target_path, links_path)

    assert not os.path.exists(path_archivo_existente), f"El archivo no fue eliminado de la ruta esperada: {path_archivo_existente}"


# Test para verificar la creación de los hardlinks
@patch("subprocess.run")
@pytest.mark.parametrize(
    "nombre_archivo_original",
    [
        ("Screenshot(0).jpg"),
        ("VID-20230702-WA0019.mp4"),
    ],
)
def test_create_hardlinks(mock_run, entorno_de_prueba, nombre_archivo_original):
    base_path, target_path, links_path, media_path = entorno_de_prueba

    with open(os.path.join(media_path, nombre_archivo_original), "w") as f:
        pass

    def side_effect(*args, **kwargs):
        command = args[0]
        cmd = os.path.basename(command[0])
        if cmd == "file":
            if ".jpg" in command[-1] or ".HEIC" in command[-1]:
                return Mock(stdout="whatever: image/jpeg")
            elif ".MP4" in command[-1] or ".MOV" in command[-1] or ".mp4" in command[-1]:
                return Mock(stdout="whatever: video/mp4")
        elif cmd == "exiftool":
            # Sin fecha para forzar ruta de hardlink
            return Mock(stdout="")
        return Mock(stdout="")

    mock_run.side_effect = side_effect

    copiar_archivo(media_path, base_path, nombre_archivo_original)

    main.process_files(base_path, target_path, links_path)

    hardlink_file = os.path.join(links_path, nombre_archivo_original)
    original_file = os.path.join(base_path, nombre_archivo_original)

    assert os.path.exists(hardlink_file), f"El hardlink no se creó en la ruta: {hardlink_file}"
    assert os.path.samefile(original_file, hardlink_file), "El archivo no es un hardlink al original."
