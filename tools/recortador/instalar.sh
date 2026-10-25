#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p .tmp .cache weights
export TMPDIR="$PWD/.tmp" PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 SAM2_BUILD_CUDA=0
PYTHON="${PYTHON:-python3.11}"
"$PYTHON" -m venv .venv
nice -n 15 .venv/bin/python -m pip install 'setuptools>=64' wheel
# SAM importa torch al preparar sus metadatos: instalar primero las dependencias.
sed '/^SAM-2 @ /d' requirements.txt > .tmp/requirements-base.txt
nice -n 15 .venv/bin/python -m pip install -r .tmp/requirements-base.txt
nice -n 15 .venv/bin/python -m pip install --no-build-isolation -r requirements.txt
nice -n 15 .venv/bin/python -B descargar_pesos.py
