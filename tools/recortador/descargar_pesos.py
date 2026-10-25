"""Única operación del recortador que descarga pesos; la inferencia es local."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent


def descargar():
    modelo = json.loads((ROOT / 'modelo.json').read_text())
    destino = ROOT / 'weights' / modelo['archivo']
    destino.parent.mkdir(exist_ok=True)
    if destino.exists() and hashlib.sha256(destino.read_bytes()).hexdigest() == modelo['sha256']:
        print(modelo['sha256'], destino)
        return
    temporal = destino.with_suffix('.part')
    try:
        digest = hashlib.sha256()
        with urllib.request.urlopen(modelo['url'], timeout=60) as entrada, temporal.open('wb') as salida:
            while bloque := entrada.read(1024 * 1024):
                digest.update(bloque)
                salida.write(bloque)
        if digest.hexdigest() != modelo['sha256']:
            raise ValueError('SHA256 de pesos distinto del registrado: no se instalarán')
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)
    print(modelo['sha256'], destino)


if __name__ == '__main__':
    descargar()
