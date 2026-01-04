from photosync import settings, main

if __name__ == "__main__":
    main.logger.info("Photosync iniciado")

    if not settings.SOURCE_PATHS:
        main.logger.warning("No hay rutas de origen definidas; init no ejecuta sincronización.")
        main.logger.info("Define PHOTOSYNC_SOURCE_PATHS en ~/.config/photosync/photosync.env o como variable de entorno.")
        exit(0)

    try:
        main.sync_times = main.load_sync_times()
    except Exception:
        # TODO: controla la excepción si hay algún error leyendo el archivo
        main.logger.error("No se ha encontrado el fichero de los tiempos de la última sincronización")
        # exit()

    for path in settings.SOURCE_PATHS:
        main.process_folder(path)

    main.logger.info("Photosync finalizado")
