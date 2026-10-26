"""OCR local + catálogo tipográfico; produce ADN por carácter, sin corregir texto."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
from comun import ROOT, VERSION, guardar, ortografia, sha256, validar_pagina
from medir import Buscador

def inferir(entrada,salida,galeria,pesos=None,dpi=None,propio=False,tessdata=None):
    if not propio: raise ValueError('Solo imágenes propias sin firmas/sellos de terceros')
    if dpi is None or not 50 <= dpi <= 1200: raise ValueError('DPI físico conocido requerido (50–1200)')
    # OCR es opcional para el camino A nativo; solo importarlo al usar B.
    # Si falta en B, fallar explícitamente: nunca simular una transcripción.
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError('Camino B requiere pytesseract y Tesseract español; OCR no ejecutado') from exc
    entrada,salida=Path(entrada),Path(salida)
    if salida.exists(): raise ValueError('Salida existente')
    with Image.open(entrada) as img: im=ImageOps.exif_transpose(img).convert('RGB')
    factor=72/dpi; escala=96/dpi
    tessdata = Path(tessdata) if tessdata else ROOT/'.cache/ocr'
    config = f'--tessdata-dir "{tessdata}"' if tessdata.is_dir() else ''
    if 'spa' not in pytesseract.get_languages(config=config): raise RuntimeError('Instalar datos Tesseract spa para OCR español')
    palabras=pytesseract.image_to_data(im,lang='spa',config=config,output_type=pytesseract.Output.DICT)
    cajas=pytesseract.image_to_boxes(im,lang='spa',config=config).splitlines()
    buscador=Buscador(galeria,pesos); spans=[]
    texto=pytesseract.image_to_string(im,lang='spa',config=config)
    for caja in cajas:
        c,x0,y0,x1,y1,_=caja.split(); x0,y0,x1,y1=map(int,(x0,y0,x1,y1))
        y0,y1=im.height-y1,im.height-y0
        crop=im.crop((x0,y0,x1,y1)); w=max(1,round(crop.width*escala));h=max(1,round(crop.height*escala))
        pred=None
        if w<=60 and h<=44:
            # Conserva escala física; fondo/posición normalizados a la plantilla sintética.
            papel=tuple(np.percentile(np.asarray(im.crop((max(0,x0-3),max(0,y0-3),min(im.width,x1+3),min(im.height,y1+3)))).reshape(-1,3),90,axis=0).astype('uint8'))
            parche=Image.new('RGB',(64,64),papel)
            parche.paste(crop.resize((w,h),Image.Resampling.LANCZOS),(32-w//2,48-h))
            pred=buscador.predecir(parche,c)
        word=None; grupo=None
        for i,t in enumerate(palabras['text']):
            if not t.strip(): continue
            px,py,pw,ph=(palabras[k][i] for k in ('left','top','width','height'))
            if px<=x0+(x1-x0)/2<=px+pw and py<=y0+(y1-y0)/2<=py+ph:
                word=t; grupo=[palabras[k][i] for k in ('block_num','par_num','line_num')]; break
        s=dict(pagina=1,bbox=[v*factor for v in (x0,y0,x1,y1)],texto=c,
            fuente=pred['fuente'] if pred else None,tamano_pt=pred['tamano_pt'] if pred and pred['tamano_pt']>0 else None,
            peso=pred['peso'] if pred else None,cursiva=pred['cursiva'] if pred else None,
            inclinacion=None,tinta_lab=pred['tinta_lab'] if pred else None,interletra=None,interlinea=None,
            linea_base={'origen':[x0*factor,y1*factor],'direccion':[1.,0.],'metodo':'borde inferior OCR; aproximado'},
            origen='inferido',metodo='vecino' if pesos is None else 'cnn',
            confianza=min(.8,pred['confianza']) if pred else 0.,
            alternativas=pred['fuentes'] if pred else [],linea=grupo,
            palabra_ocr=word,ortografia=ortografia(word or c),
            advertencias=['Escala/posición normalizadas; línea base e interletra son aproximaciones geométricas.'])
        spans.append(s)
    grupos={tuple(s['linea']) for s in spans if s['linea']}
    lineas=[]
    for g in sorted(grupos):
        ss=sorted([s for s in spans if tuple(s['linea'] or [])==g],key=lambda s:s['bbox'][0])
        centers=np.asarray([[(s['bbox'][0]+s['bbox'][2])/2,s['bbox'][3]] for s in ss])
        slope=float(np.polyfit(centers[:,0],centers[:,1],1)[0]) if len(ss)>1 and np.ptp(centers[:,0])>0 else 0.
        angle=float(np.degrees(np.arctan(slope)))
        for i,s in enumerate(ss):
            s['inclinacion']=angle
            s['linea_base']['direccion']=[float(np.cos(np.arctan(slope))),float(np.sin(np.arctan(slope)))]
            if i+1<len(ss): s['interletra']=ss[i+1]['bbox'][0]-s['bbox'][2]
        lineas.append((g,float(np.median(centers[:,1])),ss))
    for i,(g,y,ss) in enumerate(lineas[:-1]):
        if lineas[i+1][0][:2]==g[:2]:
            for s in ss: s['interlinea']=lineas[i+1][1]-y
    page=dict(version=VERSION,pagina=1,ancho_pt=im.width*factor,alto_pt=im.height*factor,
        dpi=dpi,sha256_origen=sha256(entrada),spans=spans,texto_ocr=texto,ortografia=ortografia(texto),
        origen='inferido',metodo='vecino' if pesos is None else 'cnn',
        advertencias=['Confianza es margen de similitud, no probabilidad calibrada.',
        'OCR, fuentes fuera de catálogo y glifos >44 px de alto requieren revisión.'])
    validar_pagina(page);guardar(salida/'pagina-0001/adn.json',page)
    guardar(salida/'manifest.json',dict(version=VERSION,paginas=1,sha256_origen=sha256(entrada)))
    return page

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('imagen',type=Path)
    p.add_argument('--salida',type=Path,required=True);p.add_argument('--galeria',type=Path,required=True)
    p.add_argument('--pesos',type=Path);p.add_argument('--dpi',type=float,required=True)
    p.add_argument('--tessdata',type=Path);p.add_argument('--propio-sin-firmas-ni-sellos',action='store_true');a=p.parse_args()
    inferir(a.imagen,a.salida,a.galeria,a.pesos,a.dpi,a.propio_sin_firmas_ni_sellos,a.tessdata)
