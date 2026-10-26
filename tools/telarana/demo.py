"""Demo sobre documento autorizado; recorte D-1 por caja, sin SAM ni GPU."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pymupdf as fitz
from PIL import Image
from .grafo import Proyecto, ficha, sha
from .relacionar import relacionar
from .vendor_adn.nativo import extraer
from .vendor_d1.recortador import abrir_fuente, exportar_pieza


def preparar(pdf, salida, caja, pagina=1, propio=False):
    pdf, salida = Path(pdf), Path(salida)
    if not propio: raise ValueError('Requiere documento propio autorizado')
    if salida.exists(): raise ValueError('No sobrescribir proyecto')
    origen = hashlib.sha256(pdf.read_bytes()).hexdigest()
    # A valida campos de firma y sellos; declaración humana cubre los rasterizados.
    adn = extraer(pdf, salida/'adn', propio=True, comparar=False)
    if not 1 <= pagina <= len(adn): raise ValueError('Página fuera del documento')
    source = abrir_fuente(pdf, pagina=pagina, ppp=150, region=caja)
    if source.procedencia['rotacion'] != 0:
        raise ValueError('Demo v0 requiere página sin rotación; no mezclar coordenadas')
    pieces = salida/'piezas'; pieces.mkdir()
    w,h = source.imagen.size
    prompt = dict(nombre='Figura seleccionada', tipo='bloque', caja=[0,0,w,h], puntos=[], etiquetas=[])
    item = exportar_pieza(source, prompt, np.ones((h,w), bool), 1., pieces, 1, documento=True)
    # La puntuación SAM no aplica: aquí la caja es explícita, no una predicción.
    item.update(puntuacion=None, puntuacion_tipo='aún no aplica: selección por caja, SAM no ejecutado')
    (pieces/'piezas.json').write_text(json.dumps(dict(version=1, fuente=source.procedencia, piezas=[item]), indent=2))
    with Image.open(pieces/item['archivo']) as im: first = im.convert('RGB')
    second = first.transpose(Image.Transpose.ROTATE_90)
    second.save(pieces/'transformada.png')
    with fitz.open(pdf) as doc:
        doc[pagina-1].get_pixmap(dpi=72, alpha=False).save(salida/'pagina.png')
    result = relacionar(first, second)
    project = Proyecto(salida/'proyecto.json')
    for i, span in enumerate(adn[pagina-1]['spans']):
        project.crear(ficha(f'texto-{i:03d}', 'region', dict(pagina=pagina,bbox=span['bbox'],
            coordenadas='pt sin rotación', texto=span['texto'], origen='nativo', metodo='A'), origenes=[origen]))
    project.crear(ficha('figura-original','region', dict(pagina=pagina,bbox=item['caja_pagina'],
        coordenadas='pt sin rotación', imagen='piezas/'+item['archivo'], etiqueta='Figura original',
        sha256_imagen=item['sha256_png'],
        extraccion='D-1 exportar_pieza; caja explícita; sin SAM'), origenes=[origen]))
    project.crear(ficha('figura-transformada','region', dict(imagen='piezas/transformada.png',
        etiqueta='Copia de demostración girada 90°', transformacion_controlada=True,
        sha256_imagen=hashlib.sha256((pieces/'transformada.png').read_bytes()).hexdigest()), origenes=[origen]))
    result.update(relaciones=dict(origen_compartido=True, apoyos_independientes=1,
        nota='La copia girada es una transformación controlada del mismo recorte; no otra evidencia real.'))
    project.crear(ficha('misma-figura','conclusion', result, origenes=[origen],
        depende_de=[dict(id='figura-original',revision=1), dict(id='figura-transformada',revision=1)]))
    project.crear(ficha('decision-reutilizacion','conclusion', dict(texto='Revisar propuesta de reutilización'),
        depende_de=[dict(id='misma-figura',revision=1)],origenes=[origen]))
    if adn[pagina-1]['spans']:
        project.crear(ficha('lectura-texto','conclusion', dict(texto='Texto nativo disponible para revisión'),
            depende_de=[dict(id='texto-000',revision=1)],origenes=[origen]))
    before = project.estado()
    (salida/'antes.json').write_text(json.dumps(before, ensure_ascii=False, indent=2))
    metrics = dict(sha256_origen=origen, regiones_texto=len(adn[pagina-1]['spans']),
        relacion=result, estado_antes_sha256=sha(before), aprendizaje=False, gpu_unidades=0,
        propio_declarado=True, documento_en_git=False, demo_transformacion_controlada=True)
    (salida/'metricas.json').write_text(json.dumps(metrics, ensure_ascii=False,indent=2))
    return metrics


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('pdf')
    ap.add_argument('--salida',required=True);ap.add_argument('--caja',type=float,nargs=4,required=True)
    ap.add_argument('--pagina',type=int,default=1);ap.add_argument('--propio',action='store_true')
    a=ap.parse_args();print(preparar(a.pdf,a.salida,a.caja,a.pagina,a.propio))
