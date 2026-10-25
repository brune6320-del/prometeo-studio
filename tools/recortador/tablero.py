"""Adaptador al BoardExport v1 de studio/frontend/src/board/model.ts (d6d3558)."""
import base64
from datetime import datetime, timezone
import json


def exportar_tablero(resultado, carpeta):
    ahora = datetime.now(timezone.utc).isoformat()
    cards = []
    for i, p in enumerate(resultado['piezas']):
        contenido = (carpeta / p['archivo']).read_bytes()
        if len(contenido) > 12 * 1024 * 1024:
            raise ValueError('Una pieza excede los 12 MiB aceptados por Prometeo.')
        x0, y0, x1, y1 = p['caja']
        ancho = min(400, max(120, x1-x0))
        alto = min(2400, max(60, ancho * (y1-y0) / (x1-x0)))
        cards.append({'id': p['id'], 'type': 'media', 'title': p['nombre'],
                      'body': json.dumps({'origen': p['procedencia'], 'caja_pagina': p['caja_pagina'],
                                          'politica_alfa': p['politica_alfa']}, ensure_ascii=False),
                      'x': 140 + (i % 4) * 440, 'y': 140 + (i // 4) * 440,
                      'width': ancho, 'height': alto, 'color': 'paper',
                      'media': {'name': p['archivo'], 'mimeType': 'image/png', 'kind': 'image',
                                'dataUrl': 'data:image/png;base64,' + base64.b64encode(contenido).decode()}})
    marco = {'id': 'marco-recortes', 'type': 'marco', 'title': 'Recortes · Mesa de luz',
             'body': '', 'x': 60, 'y': 60, 'width': 1900, 'color': 'paper',
             'datos': {'alto': max(520, 180 + ((len(cards)+3)//4) * 440),
                       'hijos': [c['id'] for c in cards], 'vista': 'mesa'}}
    board = {'schemaVersion': 1, 'id': 'recortes-' + resultado['fuente']['sha256_origen'][:16],
             'title': 'Recortes de ' + resultado['fuente']['archivo'],
             'createdAt': ahora, 'updatedAt': ahora, 'cards': [marco] + cards, 'relations': []}
    export = {'format': 'prometeo-studio-board', 'schemaVersion': 1, 'exportedAt': ahora, 'board': board}
    (carpeta / 'tablero.json').write_text(json.dumps(export, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
