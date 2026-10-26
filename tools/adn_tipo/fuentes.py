"""Descarga OFL fijada por revisión y doble SHA (fuente/licencia); nunca a Git."""
from pathlib import Path
import ssl
import certifi
from urllib.request import urlopen
from comun import ROOT, guardar, leer, sha256

def descargar(destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    lock = leer(ROOT / 'fuentes.lock.json')
    for f in lock['fuentes']:
        for campo, hashcampo in [('archivo', 'sha256'), ('licencia', 'licencia_sha256')]:
            path = destino / f[campo]
            if path.exists():
                if sha256(path) != f[hashcampo]:
                    raise ValueError(f'Archivo alterado: {path}')
                continue
            url = f"https://raw.githubusercontent.com/google/fonts/{lock['revision']}/ofl/{f['directorio']}/{Path(f[campo]).name}"
            path.parent.mkdir(parents=True, exist_ok=True)
            temporal = path.with_suffix(path.suffix + '.tmp')
            try:
                with urlopen(url, timeout=60, context=ssl.create_default_context(cafile=certifi.where())) as r:
                    temporal.write_bytes(r.read())
                if sha256(temporal) != f[hashcampo]:
                    raise ValueError('SHA incorrecto: ' + url)
                temporal.rename(path)
            finally:
                temporal.unlink(missing_ok=True)
    guardar(destino / 'manifest.json', lock)
    return lock

if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--salida',type=Path,default=ROOT/'.cache/fuentes')
    descargar(p.parse_args().salida)
