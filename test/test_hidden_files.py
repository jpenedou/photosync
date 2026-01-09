import os
from pathlib import Path
from unittest.mock import patch, Mock
from photosync import main, settings


def _prep_env(tmp_path, sync_hidden=False):
    base = os.path.join(tmp_path, "movil")
    target = os.path.join(tmp_path, "fotos")
    links = os.path.join(target, "no_date")
    Path(base).mkdir(parents=True, exist_ok=True)
    Path(target).mkdir(parents=True, exist_ok=True)
    settings.SOURCE_PATHS = base
    settings.TARGET_PATH = target
    settings.TAGNAME_NOTFOUND_PATH = links
    settings.LAST_SYNC_TIME_PATH = os.path.join(tmp_path, ".photosync_last.json")
    settings.PHOTOSYNC_SYNC_HIDDEN = sync_hidden
    main.EXIFTOOL_PATH = "exiftool"
    return base, target, links


@patch("subprocess.run")
def test_hidden_file_ignored_by_default(mock_run, tmp_path):
    base, target, links = _prep_env(str(tmp_path), sync_hidden=False)
    hidden = os.path.join(base, ".hidden.jpg")
    with open(hidden, "wb") as f:
        f.write(b"data")

    def side_effect(*args, **kwargs):
        cmd = os.path.basename(args[0][0])
        if cmd == "file":
            return Mock(stdout="whatever: image/jpeg")
        elif cmd == "exiftool":
            return Mock(stdout="Date/Time Original: 2026:01:03 19:36:38")
        return Mock(stdout="")

    mock_run.side_effect = side_effect

    main.process_files(base, target, links)

    year_dir = os.path.join(target, "2026")
    assert not os.path.exists(year_dir), "No debería crear destino para ocultos por defecto"


@patch("subprocess.run")
def test_hidden_file_processed_when_enabled(mock_run, tmp_path):
    base, target, links = _prep_env(str(tmp_path), sync_hidden=True)
    hidden = os.path.join(base, ".hidden.jpg")
    with open(hidden, "wb") as f:
        f.write(b"data")

    def side_effect(*args, **kwargs):
        cmd = os.path.basename(args[0][0])
        if cmd == "file":
            return Mock(stdout="whatever: image/jpeg")
        elif cmd == "exiftool":
            return Mock(stdout="Date/Time Original: 2026:01:03 19:36:38")
        return Mock(stdout="")

    mock_run.side_effect = side_effect

    main.process_files(base, target, links)

    dest_dir = os.path.join(target, "2026", "2026-01")
    assert os.path.isdir(dest_dir), "Debe procesar ocultos cuando está habilitado"
