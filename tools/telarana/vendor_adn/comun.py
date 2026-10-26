"""Identidad, color y contrato compartidos. Sin red."""
from __future__ import annotations
import hashlib
import json
import re
import unicodedata
from pathlib import Path
import numpy as np
from skimage.color import rgb2lab

VERSION = '1.0.0'
SEED = 2610
ROOT = Path(__file__).resolve().parent

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def guardar(path, datos, exclusivo=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusivo else 'w', encoding='utf8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def leer(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def familia_sha(nombre):
    nombre = ' '.join(unicodedata.normalize('NFKC', nombre).casefold().split())
    return hashlib.sha256(nombre.encode()).hexdigest()

def particion(sha):
    return 'holdout' if int(hashlib.sha256(('adn-v1:' + sha).encode()).hexdigest()[:16], 16) % 100 < 25 else 'train'

def lab(rgb):
    return rgb2lab(np.asarray(rgb, dtype=float).reshape(1, 1, 3) / 255)[0, 0].tolist()

def ortografia(texto):
    from spellchecker import SpellChecker
    if not hasattr(ortografia, 'diccionario'):
        ortografia.diccionario = SpellChecker(language='es')
    palabras = list(re.finditer(r"[^\W\d_]+(?:['’][^\W\d_]+)?", texto, re.UNICODE))
    desconocidas = ortografia.diccionario.unknown([m.group().lower() for m in palabras])
    return [{'texto': m.group(), 'inicio': m.start(), 'fin': m.end(), 'marca': 'revisar'}
            for m in palabras if m.group().lower() in desconocidas]

def validar_pagina(p):
    if p.get('version') != VERSION or p['pagina'] < 1:
        raise ValueError('Versión o página inválida')
    for s in p['spans']:
        for k in ('pagina', 'bbox', 'texto', 'fuente', 'tamano_pt', 'peso', 'inclinacion',
                  'tinta_lab', 'interletra', 'linea_base', 'origen', 'confianza'):
            if k not in s:
                raise ValueError(f'Falta {k}')
        b = s['bbox']
        if len(b) != 4 or not np.isfinite(b).all() or b[2] < b[0] or b[3] < b[1]:
            raise ValueError('bbox inválido')
        if s['pagina'] != p['pagina'] or s['origen'] not in ('nativo', 'inferido') or not 0 <= s['confianza'] <= 1:
            raise ValueError('Span inválido')
        for k in ('tamano_pt', 'peso', 'inclinacion', 'interletra', 'interlinea'):
            if s.get(k) is not None and not np.isfinite(s[k]):
                raise ValueError(f'{k} no finito')
        if s['tamano_pt'] is not None and s['tamano_pt'] <= 0:
            raise ValueError('Tamaño no positivo')
        if s['linea_base'] is not None:
            for k in ('origen', 'direccion'):
                if len(s['linea_base'][k]) != 2 or not np.isfinite(s['linea_base'][k]).all():
                    raise ValueError('Línea base inválida')
        if s['tinta_lab'] is not None and (len(s['tinta_lab']) != 3 or not np.isfinite(s['tinta_lab']).all()):
            raise ValueError('Lab inválido')
    return p
