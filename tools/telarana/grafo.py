"""Log encadenado, revisiones explícitas e invalidación transitiva selectiva."""
from __future__ import annotations
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(canon(value).encode()).hexdigest()


def reconstruir(events):
    nodes = {}; previous = '0'*64
    for index, event in enumerate(events):
        body = {k:v for k,v in event.items() if k != 'sha256'}
        if (body.get('secuencia') != index or body.get('anterior') != previous
                or event.get('sha256') != sha(body)):
            raise ValueError('Cadena de eventos alterada')
        payload = copy.deepcopy(event['datos']); action = event['accion']
        if action == 'crear':
            ident = payload['id']
            if not isinstance(ident, str) or not ident or ident in nodes:
                raise ValueError('Identidad de ficha repetida o inválida')
            deps = payload.get('depende_de', [])
            if len({d['id'] for d in deps}) != len(deps):
                raise ValueError('Dependencia duplicada')
            for d in deps:
                parent = nodes.get(d['id'])
                if not parent or parent['revision'] != d['revision'] or parent['estado'] != 'vigente':
                    raise ValueError('Dependencia inexistente, obsoleta o inválida')
            if payload.get('tipo') not in ('region', 'conclusion'):
                raise ValueError('Tipo de ficha desconocido')
            if payload['tipo'] == 'conclusion' and not deps:
                raise ValueError('Conclusión requiere dependencias explícitas')
            payload.update(revision=1, estado='vigente', invalidada_por=None)
            nodes[ident] = payload
        elif action == 'corregir':
            ident = payload['id']; node = nodes.get(ident)
            if (not node or node['tipo'] != 'region' or node['estado'] != 'vigente'
                    or node['revision'] != payload['revision_esperada']):
                raise ValueError('Corrección obsoleta o región inválida')
            if not isinstance(payload.get('contenido'), dict) or not payload.get('motivo'):
                raise ValueError('Corrección requiere contenido y motivo')
            node['contenido'] = payload['contenido']; node['revision'] += 1
            affected = {ident}
            # Las dependencias solo pueden apuntar a fichas anteriores: DAG sin ciclos.
            for key, candidate in nodes.items():
                if key != ident and any(d['id'] in affected for d in candidate.get('depende_de', [])):
                    affected.add(key)
                    if candidate['estado'] == 'vigente':
                        candidate.update(estado='invalidada', invalidada_por=ident)
        else:
            raise ValueError('Acción desconocida')
        previous = event['sha256']
    return dict(version='telarana-v0', fichas=nodes, eventos=len(events), ultimo_evento=previous)


def ficha(ident, tipo, contenido, *, depende_de=(), origenes=(), productor='Codex C3', experiencia='D14', fecha='2026-10-26'):
    return dict(id=ident, tipo=tipo, contenido=contenido, depende_de=list(depende_de),
        origenes=sorted(set(origenes)), productor=productor, experiencia=experiencia,
        maestro='extractor nativo A / recortador D-1 / corrección humana',
        fecha=fecha, evaluador=None, evaluado_en=None, caduca='al cambiar cualquier dependencia',
        nivel_evidencia='TESTED_NO_VERIFIED', esquema='local-v0; SC-41 no integrado')


class Proyecto:
    def __init__(self, path):
        self.path = Path(path)

    def eventos(self):
        if not self.path.exists(): return []
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('version') != 'telarana-v0': raise ValueError('Versión de proyecto desconocida')
        reconstruir(data['eventos'])
        return data['eventos']

    def estado(self):
        return reconstruir(self.eventos())

    def aplicar(self, accion, datos):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            events = self.eventos()
            event = dict(secuencia=len(events), anterior=events[-1]['sha256'] if events else '0'*64,
                         accion=accion, datos=copy.deepcopy(datos))
            event['sha256'] = sha(event)
            events.append(event)
            state = reconstruir(events)  # Validar antes de escribir.
            fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.telarana-', suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    stream.write(canon(dict(version='telarana-v0', eventos=events))+'\n')
                    stream.flush(); os.fsync(stream.fileno())
                os.replace(name, self.path)
            finally:
                Path(name).unlink(missing_ok=True)
            return state

    def crear(self, data): return self.aplicar('crear', data)

    def corregir(self, ident, revision, contenido, motivo):
        return self.aplicar('corregir', dict(id=ident, revision_esperada=revision,
                                           contenido=contenido, motivo=motivo))
