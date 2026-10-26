"""Modelo OCR español fijado; local a .cache, nunca instala datos globales."""
import argparse
import ssl
from pathlib import Path
from urllib.request import urlopen
import certifi
from comun import ROOT, leer, sha256

def descargar(destino):
    destino=Path(destino);destino.mkdir(parents=True,exist_ok=True)
    lock=leer(ROOT/'ocr.lock.json')
    for nombre in ('spa.traineddata','LICENSE'):
        p=destino/nombre
        if not p.exists():
            with urlopen(lock[nombre]['url'],context=ssl.create_default_context(cafile=certifi.where()),timeout=60) as r:
                data=r.read()
            import hashlib
            if hashlib.sha256(data).hexdigest()!=lock[nombre]['sha256']:raise ValueError('OCR SHA inválido')
            p.write_bytes(data)
        if sha256(p)!=lock[nombre]['sha256']:raise ValueError('OCR alterado')
    return destino
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--salida',type=Path,default=ROOT/'.cache/ocr')
    print(descargar(p.parse_args().salida))
