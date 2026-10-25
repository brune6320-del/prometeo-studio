#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p .tmp .cache weights
export TMPDIR="$PWD/.tmp" PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 SAM2_BUILD_CUDA=0
PYTHON="${PYTHON:-python3.11}"
"$PYTHON" -m venv .venv
nice -n 15 .venv/bin/python -m pip install 'setuptools>=64' wheel
nice -n 15 .venv/bin/python -m pip install --no-build-isolation -r requirements.txt
nice -n 15 .venv/bin/python -B descargar_pesos.py
