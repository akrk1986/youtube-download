#!/bin/sh
# qBittorrent "Run external program on torrent completion" wrapper (Gmail).
#
# Wire qBittorrent's completion command to this single stable path:
#   /path/to/youtube-download/Utils/qb-hook-gmail.sh --name "%N" --path "%F"
#
# It resolves the shared venv and the post-download driver relative to its own
# location, so no interpreter path or project path is hardcoded in qBittorrent.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
# Shared per-OS venv lives in the parent of the project dir (see project README).
VENV_PY="$PROJECT_ROOT/../.venv-av-linux/bin/python"
DRIVER="$SCRIPT_DIR/main-qb-postdownload-gmail.py"

if [ ! -x "$VENV_PY" ]; then
    echo "qb-hook-gmail: venv python not found at $VENV_PY" >&2
    exit 1
fi

exec "$VENV_PY" "$DRIVER" "$@"
