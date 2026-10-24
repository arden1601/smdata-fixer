#!/usr/bin/env bash
# Build dist/SMDATA-Fixer.exe (Windows, single file) from Linux using a
# Wine + Windows-Python + PyInstaller Docker image.
set -euo pipefail

cd "$(dirname "$0")"
IMAGE="${IMAGE:-batonogov/pyinstaller-windows:latest}"

rm -rf build dist SMDATA-Fixer.spec
docker run --rm -v "$PWD:/src" --entrypoint /bin/bash "$IMAGE" -c '
  set -e
  cd /src
  pyinstaller --clean --noconfirm --onefile --windowed \
    --name SMDATA-Fixer smdata_fixer_gui.py
  chown -R '"$(id -u):$(id -g)"' build dist SMDATA-Fixer.spec
'
ls -lh dist/SMDATA-Fixer.exe
