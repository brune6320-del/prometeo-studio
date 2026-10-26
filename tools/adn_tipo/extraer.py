"""Entrada unificada PDF/imagen. A offline; páginas sin texto pasan a OCR B."""
from __future__ import annotations
import argparse
import tempfile
from pathlib import Path
import pymupdf as fitz
from comun import VERSION, guardar, sha256, validar_pagina
from nativo import extraer as nativo, comprobar_documento
from inferir import inferir

def extraer(entrada,salida,*,propio=False,dpi=None,galeria=None,pesos=None,tessdata=None):
    entrada,salida=Path(entrada),Path(salida)
    if entrada.suffix.lower()!='.pdf':
        if not galeria: raise ValueError('Imagen requiere --galeria')
        return [inferir(entrada,salida,galeria,pesos,dpi,propio,tessdata)]
    # Detectar requisitos ANTES de crear salida para permitir reintento seguro.
    with fitz.open(entrada) as doc:
        comprobar_documento(doc,propio)
        escaneadas=[i for i,p in enumerate(doc) if not p.get_text().strip()]
    if escaneadas and not galeria: raise ValueError('PDF con páginas sin texto: proporcionar --galeria para OCR')
    paginas=nativo(entrada,salida,propio=propio)
    if escaneadas:
        with fitz.open(entrada) as doc, tempfile.TemporaryDirectory(dir=salida,prefix='.ocr-') as tmp:
            for i in escaneadas:
                page=doc[i];page.set_rotation(0)
                render=Path(tmp)/f'{i}.png';page.get_pixmap(dpi=144).save(render)
                p=inferir(render,Path(tmp)/f'ocr-{i}',galeria,pesos,144,propio,tessdata)
                p.update(pagina=i+1,sha256_origen=sha256(entrada))
                for s in p['spans']:s['pagina']=i+1
                validar_pagina(p);guardar(salida/f'pagina-{i+1:04d}'/'adn.json',p);paginas[i]=p
    guardar(salida/'manifest.json',dict(version=VERSION,sha256_origen=sha256(entrada),paginas=len(paginas),
        archivos=[f'pagina-{i+1:04d}/adn.json' for i in range(len(paginas))]))
    return paginas

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('entrada',type=Path);p.add_argument('--salida',type=Path,required=True)
    p.add_argument('--galeria',type=Path);p.add_argument('--pesos',type=Path);p.add_argument('--dpi',type=float)
    p.add_argument('--tessdata',type=Path);p.add_argument('--propio-sin-firmas-ni-sellos',action='store_true');a=p.parse_args()
    extraer(a.entrada,a.salida,propio=a.propio_sin_firmas_ni_sellos,dpi=a.dpi,galeria=a.galeria,pesos=a.pesos,tessdata=a.tessdata)
