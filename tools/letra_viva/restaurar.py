"""Restauración comprobada del raster, sin alterar el PDF original."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .comun import sha256


def restaurar(edicion, salida):
    edicion, salida = Path(edicion), Path(salida)
    if salida.exists():
        raise ValueError('No sobrescribir restauración')
    r = json.loads((edicion/'edicion.json').read_text())
    for name, key in [('pagina-despues.png', 'sha256_despues'),
                      ('parche-antes.png', 'sha256_parche_antes'),
                      ('pagina-antes.png', 'sha256_antes')]:
        if sha256(edicion/name) != r[key]:
            raise ValueError('Historial o imagen alterados: '+name)
    current = np.array(Image.open(edicion/'pagina-despues.png').convert('RGB'))
    before = np.array(Image.open(edicion/'pagina-antes.png').convert('RGB'))
    patch = np.array(Image.open(edicion/'parche-antes.png').convert('RGB'))
    x0,y0,x1,y1 = r['region_px']
    if patch.shape != (y1-y0,x1-x0,3):
        raise ValueError('Dimensiones del parche incorrectas')
    current[y0:y1,x0:x1] = patch
    if not np.array_equal(current,before):
        raise ValueError('Restauración no coincide píxel a píxel con original')
    salida.parent.mkdir(parents=True,exist_ok=True)
    Image.fromarray(current).save(salida)
    return dict(pixel_identico=True,sha256_restaurada=sha256(salida),
                sha256_original_raster=r['sha256_antes'])
