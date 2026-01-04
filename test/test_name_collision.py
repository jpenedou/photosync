import os
import shutil
from pathlib import Path
from unittest.mock import patch, Mock
from photosync import main, settings


def _prep_env(tmp_root):
    base = os.path.join(tmp_root, "movil")
    target = os.path.join(tmp_root, "fotos")
    links = os.path.join(target, "no_date")
    Path(base).mkdir(parents=True, exist_ok=True)
    Path(target).mkdir(parents=True, exist_ok=True)
    settings.SOURCE_PATHS = base
    settings.TARGET_PATH = target
    settings.TAGNAME_NOTFOUND_PATH = links
    settings.LAST_SYNC_TIME_PATH = os.path.join(tmp_root, ".photosync_last.json")
    # Forzar exiftool lógico en tests
    main.EXIFTOOL_PATH = "exiftool"
    return base, target, links


def _touch(path, content):
    with open(path, "wb") as f:
        f.write(content)


@patch("subprocess.run")
def test_collision_creates_suffix(mock_run, tmp_path):
    base, target, links = _prep_env(str(tmp_path))
    # Crear dos archivos distintos
    f1 = os.path.join(base, "A.jpg")
    f2 = os.path.join(base, "B.jpg")
    _touch(f1, b"one")
    _touch(f2, b"two")

    # Mock file/exiftool
    def side_effect(*args, **kwargs):
        cmd = os.path.basename(args[0][0])
        if cmd == "file":
            return Mock(stdout="whatever: image/jpeg")
        elif cmd == "exiftool":
            # misma fecha para ambos
            return Mock(stdout="Date/Time Original: 2026:01:03 19:36:38")
        return Mock(stdout="")

    mock_run.side_effect = side_effect

    main.process_files(base, target, links)

    dest_dir = os.path.join(target, "2026", "2026-01")
    assert os.path.isdir(dest_dir)
    files = sorted(os.listdir(dest_dir))
    assert files[0].startswith("20260103_193638")
    assert files[1].startswith("20260103_193638_")


@patch("subprocess.run")
def test_idempotent_no_extra_suffix(mock_run, tmp_path):
    base, target, links = _prep_env(str(tmp_path))
    f1 = os.path.join(base, "A.jpg")
    f2 = os.path.join(base, "B.jpg")
    _touch(f1, b"one")
    _touch(f2, b"two")

    def side_effect(*args, **kwargs):
        cmd = os.path.basename(args[0][0])
        if cmd == "file":
            return Mock(stdout="whatever: image/jpeg")
        elif cmd == "exiftool":
            return Mock(stdout="Date/Time Original: 2026:01:03 19:36:38")
        return Mock(stdout="")

    mock_run.side_effect = side_effect

    # Primera pasada
    main.process_files(base, target, links)
    dest_dir = os.path.join(target, "2026", "2026-01")
    files_first = sorted(os.listdir(dest_dir))
    assert len(files_first) == 2

    # Segunda pasada (sin cambios)
    main.process_files(base, target, links)
    files_second = sorted(os.listdir(dest_dir))
    assert files_second == files_first
