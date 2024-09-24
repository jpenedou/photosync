from photosync import settings, main

if __name__ == "__main__":
    try:
        main.sync_times = main.load_sync_times()
    except Exception:
        # TODO: controla la excepción si hay algún error leyendo el archivo
        main.logger.error("No se ha encontrado el fichero de los tiempos de la última sincronización")
        # exit()

    for path in settings.SOURCE_PATHS:
        main.process_folder(path)
