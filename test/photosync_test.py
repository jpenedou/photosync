import os
import shutil
from pathlib import Path
import pytest
import subprocess
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
    settings.SOURCE_PATHS = os.path.abspath("./test/movil")
    settings.TARGET_PATH = os.path.abspath("./test/fotos")
    settings.TAGNAME_NOTFOUND_PATH = os.path.abspath("./test/fotos/sin_fecha")
    media_path = os.path.abspath("./test/media")

    # Crear directorios
    Path(settings.SOURCE_PATHS).mkdir(parents=True, exist_ok=True)
    Path(settings.TARGET_PATH).mkdir(parents=True, exist_ok=True)
    Path(media_path).mkdir(parents=True, exist_ok=True)

    yield settings.SOURCE_PATHS, settings.TARGET_PATH, settings.TAGNAME_NOTFOUND_PATH, media_path

    # Limpiar directorios después de la prueba
    shutil.rmtree(settings.SOURCE_PATHS)
    shutil.rmtree(settings.TAGNAME_NOTFOUND_PATH)
    shutil.rmtree(settings.TARGET_PATH)


# Test parametrizado para imágenes y vídeos
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
def test_copiar_archivo(entorno_de_prueba, nombre_archivo_original, nuevo_nombre_esperado):
    base_path, target_path, _, media_path = entorno_de_prueba

    # Copiar archivo del media_path al base_path
    copiar_archivo(media_path, base_path, nombre_archivo_original)

    main.process_files(base_path, target_path)

    fecha_desde_nombre = extraer_fecha_desde_nombre(nuevo_nombre_esperado)

    assert fecha_desde_nombre, f"No se ha podido obtener la fecha del archivo: {nuevo_nombre_esperado}"

    anio_mes = f"{fecha_desde_nombre[:4]}-{fecha_desde_nombre[5:7]}"
    ruta_esperada = os.path.join(target_path, fecha_desde_nombre[:4], anio_mes, nuevo_nombre_esperado)

    assert os.path.exists(ruta_esperada), f"El archivo no se copió a la ruta esperada: {ruta_esperada}"


# Test para verificar la eliminación de archivo existente
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
def test_eliminar_archivo_existente(entorno_de_prueba, nombre_archivo_original, nuevo_nombre_esperado):
    base_path, target_path, _, media_path = entorno_de_prueba

    # Copiar archivo del media_path al base_path
    copiar_archivo(media_path, base_path, nombre_archivo_original)

    fecha_desde_nombre = extraer_fecha_desde_nombre(nuevo_nombre_esperado)

    assert fecha_desde_nombre, f"No se ha podido obtener la fecha del archivo: {nuevo_nombre_esperado}"

    anio_mes = f"{fecha_desde_nombre[:4]}-{fecha_desde_nombre[5:7]}"
    ruta_esperada = os.path.join(target_path, fecha_desde_nombre[:4], anio_mes)

    # Crear el directorio si no existe
    Path(ruta_esperada).mkdir(parents=True, exist_ok=True)

    # Copiar el archivo original a la ruta esperada
    copiar_archivo(media_path, ruta_esperada, nombre_archivo_original)

    path_archivo_existente = os.path.join(ruta_esperada, nombre_archivo_original)
    # Verificar que el archivo existe antes de ejecutar el proceso
    assert os.path.exists(path_archivo_existente), f"El archivo esperado no se encontró: {path_archivo_existente}"

    # Ejecutar el procesamiento
    main.process_files(base_path, target_path)

    # Verificar que el archivo original haya sido eliminado
    assert not os.path.exists(path_archivo_existente), f"El archivo no fue eliminado de la ruta esperada: {path_archivo_existente}"


# Test para verificar la creación de los hardlinks
@pytest.mark.parametrize(
    "nombre_archivo_original",
    [
        ("Screenshot(0).jpg"),
        ("VID-20230702-WA0019.mp4"),
    ],
)
def test_create_hardlinks(entorno_de_prueba, nombre_archivo_original):
    base_path, target_path, links_path, media_path = entorno_de_prueba

    # Verificar que el archivo no contiene los tags DateTimeOriginal ni TrackCreateDate
    archivo_en_media_path = os.path.join(media_path, nombre_archivo_original)

    # Usar exiftool para extraer los metadatos
    output = subprocess.run(["exiftool", archivo_en_media_path], capture_output=True, text=True)
    assert "DateTimeOriginal" not in output.stdout, f"El archivo {nombre_archivo_original} contiene el tag DateTimeOriginal."
    assert "TrackCreateDate" not in output.stdout, f"El archivo {nombre_archivo_original} contiene el tag TrackCreateDate."

    # Copiar archivo del media_path al base_path
    copiar_archivo(media_path, base_path, nombre_archivo_original)

    # Ejecutar el procesamiento
    main.process_files(base_path, target_path, links_path)

    # Verificar que el hardlink se ha creado en links_path
    hardlink_file = os.path.join(links_path, nombre_archivo_original)
    original_file = os.path.join(base_path, nombre_archivo_original)

    assert os.path.exists(hardlink_file), f"El hardlink no se creó en la ruta: {hardlink_file}"
    assert os.path.samefile(original_file, hardlink_file), "El archivo no es un hardlink al original."
