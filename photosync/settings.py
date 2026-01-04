import os
from pathlib import Path

# Configuration loaded from environment variables.
# Settings auto-loads ~/.config/photosync/photosync.env if present using python-dotenv.
# Environment variables take precedence over file values.
#
# Expected variables:
#   PHOTOSYNC_SOURCE_PATHS       - colon-separated source directories (e.g. /mnt/a:/mnt/b)
#   PHOTOSYNC_TARGET_PATH        - target directory for organized photos
#   PHOTOSYNC_TAGNAME_NOTFOUND_PATH - directory for files without date metadata
#   PHOTOSYNC_LAST_SYNC_TIME_PATH   - path to last sync timestamp file
#   PHOTOSYNC_DRY_RUN            - set to "1", "true", "yes", or "on" to enable dry-run mode

try:
    from dotenv import load_dotenv

    # Auto-load user env file at import time (override=False preserves existing env vars)
    user_env_file = Path.home() / ".config" / "photosync" / "photosync.env"
    load_dotenv(dotenv_path=user_env_file, override=False)
except ImportError:
    # python-dotenv not installed; skip auto-load (env vars can still be set externally)
    pass


def _expand_path(p):
    """Expand ~ in path and return absolute path."""
    if not p:
        return p
    return os.path.abspath(os.path.expanduser(p))


# Read SOURCE_PATHS from environment (colon-separated, expand ~)
SOURCE_PATHS_ENV = os.environ.get("PHOTOSYNC_SOURCE_PATHS", "")
if SOURCE_PATHS_ENV:
    SOURCE_PATHS = tuple(_expand_path(p.strip()) for p in SOURCE_PATHS_ENV.split(":") if p.strip())
else:
    SOURCE_PATHS = tuple()

# Read other configuration from environment (expand ~ for paths)
TARGET_PATH = _expand_path(os.environ.get("PHOTOSYNC_TARGET_PATH", ""))
TAGNAME_NOTFOUND_PATH = _expand_path(os.environ.get("PHOTOSYNC_TAGNAME_NOTFOUND_PATH", ""))
LAST_SYNC_TIME_PATH = _expand_path(os.environ.get("PHOTOSYNC_LAST_SYNC_TIME_PATH", "~/.cache/photosync/.photosync_last.json"))
DRY_RUN = os.environ.get("PHOTOSYNC_DRY_RUN", "").lower() in ("1", "true", "yes", "on")
