"""Preparador de TRAIN nativo exclusivamente. Para examen: examen/preparar.py.
La generación persistente de holdout está deshabilitada por el protocolo v2.
"""
from __future__ import annotations
import argparse
import io
import tempfile
from pathlib import Path
import numpy as np
import pymupdf as fitz
from PIL import Image, ImageFilter
from comun import ROOT, SEED, familia_sha, guardar, leer, particion, sha256
from nativo import comprobar_documento, extraer, nombre_limpio
from generar_sintetico import GLIFOS

def preparar(plan_path,salida,modo,propio=False):
    if modo != 'train':
        raise ValueError('Holdout persistente deshabilitado: usar medir_examen.py en Colab')
    plan=leer(plan_path); salida=Path(salida)
    if not propio: raise ValueError('Claude debe verificar autoría y ausencia de firmas/sellos de terceros')
    docs=plan['documentos']
    if len({d['sha256'] for d in docs})!=len(docs): raise ValueError('Origen repetido en plan; riesgo de fuga')
    if any(d['split'] not in ('train','holdout') for d in docs): raise ValueError('Split de origen inválido')
    elegidos=[d for d in docs if d['split']==modo]
    if not elegidos: raise ValueError('Sin documentos del split solicitado')
    familias_catalogo={f['familia'] for f in leer(ROOT/'fuentes.lock.json')['fuentes']}
    if not set(plan['mapa_fuentes'].values())<=familias_catalogo: raise ValueError('Ampliar catálogo/prerregistro antes de sellar')
    salida.mkdir(parents=True,exist_ok=False)
    rng=np.random.default_rng(SEED); rows=[]; omitidos=0
    for di,d in enumerate(elegidos):
        path=Path(d['archivo']).expanduser()
        if sha256(path)!=d['sha256']: raise ValueError('Origen distinto del aprobado')
        with tempfile.TemporaryDirectory(dir=salida,prefix='.maestro-') as temp:
            paginas=extraer(path,Path(temp)/'a',propio=propio,comparar=False)
            with fitz.open(path) as pdf:
                comprobar_documento(pdf,propio)
                for page,adn in zip(pdf,paginas):
                    page.set_rotation(0);pix=page.get_pixmap(dpi=96,colorspace=fitz.csRGB,alpha=False)
                    im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                    im=im.filter(ImageFilter.GaussianBlur(.45))
                    arr=np.asarray(im,dtype=float)+rng.normal(0,2,(im.height,im.width,3))
                    im=Image.fromarray(np.clip(arr,0,255).astype('uint8'))
                    buf=io.BytesIO(); im.save(buf,format='JPEG',quality=80);buf.seek(0)
                    with Image.open(buf) as enc: im=enc.convert('RGB')
                    for s in adn['spans']:
                        fam=plan['mapa_fuentes'].get(nombre_limpio(s['fuente']))
                        if not fam or particion(familia_sha(fam))!=modo or s['inclinacion']!=0:
                            omitidos+=len(s['caracteres']);continue
                        for c in s['caracteres']:
                            if c['c'] not in GLIFOS: omitidos+=1;continue
                            x0,y0,x1,y1=np.asarray(c['bbox'])*96/72
                            box=(int(np.floor(x0)),int(np.floor(y0)),int(np.ceil(x1)),int(np.ceil(y1)))
                            crop=im.crop(box)
                            offy=round(48+(box[1]-c['origin'][1]*96/72))
                            if crop.width>60 or crop.height>60 or offy<0 or offy+crop.height>64:
                                omitidos+=1;continue
                            parche=Image.new('RGB',(64,64),'white');parche.paste(crop,(32-crop.width//2,offy))
                            name=f'imagenes/{len(rows):07d}.png'; target=salida/name;target.parent.mkdir(exist_ok=True);parche.save(target)
                            rows.append(dict(id=str(len(rows)),archivo=name,sha256=sha256(target),
                                sha256_origen=d['sha256'],pagina=adn['pagina'],bbox=c['bbox'],texto=c['c'],
                                familia=fam,familia_sha256=familia_sha(fam),split=modo,tamano_pt=s['tamano_pt'],
                                tinta_lab=s['tinta_lab'],dpi=96,peso=s['peso'],cursiva=s['cursiva']))
    if not rows: raise ValueError('No hay glifos elegibles: revisar familias, escala y partición')
    manifest=dict(version=1,dominio='nativo_train' if modo=='train' else 'real_rasterizado',
        sha256_plan=sha256(plan_path),origenes=[d['sha256'] for d in elegidos],n=len(rows),omitidos=omitidos,
        advertencia='Rasterización con ruido; NO es impresión/escáner físico. Examen de glifos con transcripción A conocida.')
    guardar(salida/'train.json',rows,exclusivo=True)
    manifest['train_sha256']=sha256(salida/'train.json')
    guardar(salida/'manifest.json',manifest,exclusivo=True)
    print(manifest)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('plan',type=Path)
    p.add_argument('--salida',type=Path,required=True);p.add_argument('--modo',choices=['train'],required=True)
    p.add_argument('--propios-bruno-sin-firmas-ni-sellos',action='store_true');a=p.parse_args()
    preparar(a.plan,a.salida,a.modo,a.propios_bruno_sin_firmas_ni_sellos)
