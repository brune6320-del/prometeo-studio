"""Verifica carpeta ↔ sello exclusivamente por bytes; no abre ni renderiza PDFs."""
from __future__ import annotations
import argparse
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re

class ErrorExamen(Exception):
    """Solo códigos constantes: nunca incluir una ruta, nombre o contenido privado."""


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest_archivo(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def exigir_sha(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
        raise ErrorExamen('SHA_INVALIDO')
    return value


def sin_claves_repetidas(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ErrorExamen('SELLO_INVALIDO')
        result[key]=value
    return result


def leer_sello(path, esperado):
    exigir_sha(esperado)
    try:
        data=Path(path).read_bytes()
        if digest_bytes(data)!=esperado:
            raise ErrorExamen('SELLO_SHA_NO_COINCIDE')
        raw=json.loads(data,object_pairs_hook=sin_claves_repetidas)
    except (OSError,ValueError,TypeError):
        raise ErrorExamen('SELLO_INVALIDO') from None
    if isinstance(raw,dict):
        if set(raw)-{'version','documentos'} or raw.get('version',1)!=1 or isinstance(raw.get('version'),bool):
            raise ErrorExamen('SELLO_INVALIDO')
        docs=raw.get('documentos')
    else:
        docs=raw
    if not isinstance(docs,list) or not 10<=len(docs)<=20:
        raise ErrorExamen('SELLO_REQUIERE_10_A_20_PDFS')
    seen=set()
    for d in docs:
        if not isinstance(d,dict) or set(d)!={'sha256','n_paginas','tipo'}:
            raise ErrorExamen('SELLO_SOLO_SHA_PAGINAS_TIPO')
        h=exigir_sha(d['sha256'])
        if h in seen:
            raise ErrorExamen('SELLO_HASH_DUPLICADO')
        seen.add(h)
        if type(d['n_paginas']) is not int or d['n_paginas']<1 or d['tipo'] not in ('nativo','escaneado'):
            raise ErrorExamen('SELLO_METADATA_INVALIDA')
    return sorted(docs,key=lambda d:d['sha256'])


@dataclass(repr=False)
class Inventario:
    documentos: list = field(repr=False)
    rutas: dict = field(repr=False)
    sello_sha256: str
    cohorte_sha256: str


def preparar(carpeta,sello,esperado):
    """Hash-only. Retorna rutas privadas en memoria; nunca las imprime o persiste."""
    docs=leer_sello(sello,esperado)
    root=Path(carpeta)
    if root.is_symlink() or not root.is_dir() or Path(sello).is_symlink():
        raise ErrorExamen('CARPETA_INVALIDA')
    root=root.resolve(); seal=Path(sello).resolve(); rutas={}
    try:
        for folder,dirs,files in os.walk(root,followlinks=False,onerror=lambda e:(_ for _ in ()).throw(e)):
            if any((Path(folder)/d).is_symlink() for d in dirs):
                raise ErrorExamen('ENLACES_NO_PERMITIDOS')
            for name in files:
                p=Path(folder)/name
                if p.is_symlink():
                    raise ErrorExamen('ENLACES_NO_PERMITIDOS')
                if p.resolve()==seal:
                    continue
                if not p.is_file() or p.suffix.lower()!='.pdf':
                    raise ErrorExamen('ARCHIVO_SOBRANTE_NO_PDF')
                h=digest_archivo(p)
                if h in rutas:
                    raise ErrorExamen('PDF_DUPLICADO_POR_BYTES')
                rutas[h]=p
    except OSError:
        raise ErrorExamen('LECTURA_CARPETA_FALLIDA') from None
    if set(rutas)!={d['sha256'] for d in docs}:
        raise ErrorExamen('FALTAN_O_SOBRAN_PDFS')
    cohorte=digest_bytes(('\n'.join(sorted(rutas))+'\n').encode())
    return Inventario(docs,rutas,esperado,cohorte)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('carpeta',type=Path);p.add_argument('sello',type=Path)
    p.add_argument('--sello-sha256',required=True)
    a=p.parse_args()
    try:
        i=preparar(a.carpeta,a.sello,a.sello_sha256)
        print(json.dumps({'estado':'HASHES_VERIFICADOS','n_pdfs':len(i.documentos),
            'sha256_sello':i.sello_sha256,'sha256_cohorte':i.cohorte_sha256}))
        return 0
    except ErrorExamen as e:
        print(json.dumps({'estado':'RECHAZADO','codigo':str(e)}));return 2
    except Exception:
        print('{"estado":"RECHAZADO","codigo":"ENTRADA_INVALIDA"}');return 2

if __name__=='__main__':
    raise SystemExit(main())
