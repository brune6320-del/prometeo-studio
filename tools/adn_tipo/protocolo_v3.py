"""Partición y parada v3; no abre imágenes, holdout ni examen."""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass

PRERREGISTRO_SHA = '13d904c646f392b4b219ca45faec14c0a8e7c9707d387301d225a9bc4f4e9daa'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def es_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def dividir(filas, dominio):
    if dominio not in ('sintetico', 'nativo_train'):
        raise ValueError('v3 requiere sintético o nativo_train')
    grupos = {}
    for i, row in enumerate(filas):
        if not es_sha(row.get('sha256')):
            raise ValueError('SHA de imagen inválido')
        if dominio == 'sintetico':
            if not es_sha(row.get('fuente_sha256')) or not row.get('texto'):
                raise ValueError('Sintético requiere fuente_sha256 y texto')
            key = json.dumps([row['fuente_sha256'], row['texto']], ensure_ascii=False, separators=(',', ':'))
        else:
            key = row.get('sha256_origen')
            if not es_sha(key):
                raise ValueError('Nativo requiere SHA de documento origen')
        grupos.setdefault(key, []).append(i)
    familias = {r['familia'] for r in filas}
    if not familias:
        raise ValueError('Train vacío')
    # Una identidad sintética no puede pertenecer a dos familias distintas.
    if dominio == 'sintetico' and any(len({filas[i]['familia'] for i in ids}) != 1 for ids in grupos.values()):
        raise ValueError('Grupo fuente/carácter con familias inconsistentes')
    validacion = set()
    for familia in sorted(familias) if dominio == 'sintetico' else [None]:
        keys = [k for k, ids in grupos.items()
                if familia is None or filas[ids[0]]['familia'] == familia]
        if len(keys) < 2:
            raise ValueError('Al menos dos grupos por familia / dos orígenes')
        keys.sort(key=lambda k: (hashlib.sha256(('adn-v3:2610:' + k).encode()).hexdigest(), k))
        for key in keys[:math.ceil(.2 * len(keys))]:
            validacion.update(grupos[key])
    train = sorted(set(range(len(filas))) - validacion)
    validacion = sorted(validacion)
    if any({filas[i]['familia'] for i in ids} != familias for ids in (train, validacion)):
        raise ValueError('Todas las familias deben estar en train y validación; no mover grupos')
    if {filas[i]['sha256'] for i in train} & {filas[i]['sha256'] for i in validacion}:
        raise ValueError('Imagen idéntica cruza train/validación')
    return dict(version=3, dominio=dominio, train=train, validacion=validacion,
                grupos={k: {'indices': ids, 'split': 'validacion' if ids[0] in validacion else 'train'}
                        for k, ids in sorted(grupos.items())})


@dataclass
class Parada:
    mejor: float = float('inf')
    epoca_mejor: int = 0
    sin_mejorar: int = 0
    paciencia: int = 25
    delta: float = 1e-4

    def observar(self, epoca, score):
        if not math.isfinite(score):
            raise ValueError('Score no finito: detener, no seleccionar')
        mejora = score < self.mejor - self.delta
        if mejora:
            self.mejor, self.epoca_mejor, self.sin_mejorar = score, epoca, 0
        else:
            self.sin_mejorar += 1
        return mejora, self.sin_mejorar >= self.paciencia
