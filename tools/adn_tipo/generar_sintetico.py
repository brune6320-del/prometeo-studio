"""Glifos con etiquetas exactas, catálogo compartido y holdout congelado por familia."""
from __future__ import annotations
import argparse
import io
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from comun import ROOT, SEED, familia_sha, guardar, lab, leer, particion, sha256
from fuentes import descargar

GLIFOS = 'abcdefghijklmnñopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZáéíóúüÁÉÍÓÚÜ0123456789.,;:!?¿¡()-'
DPI = 96

def renderizar(path, texto, tamano_pt, tinta, papel, angulo=0., blur=0., ruido=0., jpeg=100, rng=None):
    rng = rng if rng is not None else np.random.default_rng(SEED)
    # Pillow usa px enteros: la etiqueta en pt refleja el tamaño EFECTIVO renderizado.
    px = round(tamano_pt * DPI / 72)
    font = ImageFont.truetype(str(path), px)
    im = Image.new('RGB', (64,64), tuple(papel))
    d = ImageDraw.Draw(im)
    d.text((32,48),texto,font=font,anchor='ms',fill=tuple(tinta))
    im = im.rotate(angulo,resample=Image.Resampling.BICUBIC,fillcolor=tuple(papel))
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur))
    if ruido:
        arr=np.asarray(im,dtype=float)+rng.normal(0,ruido,(64,64,3))
        im=Image.fromarray(np.clip(arr,0,255).astype('uint8'))
    if jpeg < 100:
        buf=io.BytesIO(); im.save(buf,format='JPEG',quality=jpeg); buf.seek(0)
        with Image.open(buf) as j: im=j.convert('RGB')
    return im, px * 72 / DPI

def generar(salida, fuentes_dir, n=500, seed=SEED):
    salida, fuentes_dir = Path(salida), Path(fuentes_dir)
    if n < 1: raise ValueError('n debe ser positivo')
    lock=descargar(fuentes_dir)
    familias = {f['familia']: familia_sha(f['familia']) for f in lock['fuentes']}
    if len(familias)<6 or sum(particion(h)=='holdout' for h in familias.values())<2:
        raise ValueError('Se requieren >=6 familias y >=2 holdout; ampliar catálogo sin cambiar sal')
    salida.mkdir(parents=True,exist_ok=False)
    rng=np.random.default_rng(seed)
    registros=[]; galeria=[]
    for fi,f in enumerate(lock['fuentes']):
        famsha=familias[f['familia']]
        for i in range(n):
            c=GLIFOS[i%len(GLIFOS)]
            tinta=rng.integers(0,130,3).tolist(); papel=rng.integers(225,256,3).tolist()
            angle=float(rng.uniform(-7,7)); blur=float(rng.uniform(0,.7)); ruido=float(rng.uniform(0,4))
            jpeg=int(rng.integers(55,101)); size=float(rng.uniform(12,30))
            im,size=renderizar(fuentes_dir/f['archivo'],c,size,tinta,papel,angle,blur,ruido,jpeg,rng)
            nombre=f'imagenes/{fi:02d}-{i:05d}.png'; p=salida/nombre; p.parent.mkdir(exist_ok=True)
            im.save(p)
            registros.append(dict(id=f'{fi}-{i}', archivo=nombre, sha256=sha256(p),
                familia=f['familia'], familia_sha256=famsha, fuente_sha256=f['sha256'],
                split=particion(famsha), texto=c,tamano_pt=size,tinta_lab=lab(tinta),
                peso=f['peso'],cursiva=f['cursiva'],inclinacion=angle,dpi=DPI,
                parametros=dict(tinta=tinta,papel=papel,blur=blur,ruido=ruido,jpeg=jpeg)))
        for ci,c in enumerate(GLIFOS):
            im,size=renderizar(fuentes_dir/f['archivo'],c,24,[20,20,20],[255]*3)
            nombre=f'galeria/{fi:02d}-{ci}.png'; p=salida/nombre; p.parent.mkdir(exist_ok=True); im.save(p)
            galeria.append(dict(id=f'g{fi}-{ci}',archivo=nombre,sha256=sha256(p),familia=f['familia'],
                familia_sha256=famsha,fuente_sha256=f['sha256'],texto=c,tamano_pt=size,
                peso=f['peso'],cursiva=f['cursiva'],dpi=DPI))
    holdout=dict(version=1,semilla=seed,politica='adn-v1 familia normalizada sha256 25%',
        familias={n:{'sha256':h,'split':particion(h),'archivos':sorted(f['sha256'] for f in lock['fuentes'] if f['familia']==n)} for n,h in familias.items()},
        muestras=[r for r in registros if r['split']=='holdout'])
    guardar(salida/'holdout.json',holdout,exclusivo=True)
    guardar(salida/'train.json',[r for r in registros if r['split']=='train'],exclusivo=True)
    guardar(salida/'galeria.json',galeria,exclusivo=True)
    manifest=dict(version=1,dominio='sintetico',seed=seed,n_por_fuente=n,
        holdout_sha256=sha256(salida/'holdout.json'),train_sha256=sha256(salida/'train.json'),
        galeria_sha256=sha256(salida/'galeria.json'),fuentes_lock_sha256=sha256(ROOT/'fuentes.lock.json'))
    guardar(salida/'manifest.json',manifest,exclusivo=True)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--salida',type=Path,required=True)
    p.add_argument('--fuentes',type=Path,default=ROOT/'.cache/fuentes'); p.add_argument('--n',type=int,default=500)
    a=p.parse_args(); print(generar(a.salida,a.fuentes,a.n))
