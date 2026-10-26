"""Top-k por familias distintas, MAE en pt y ΔE2000; holdout por SHA obligatorio."""
from __future__ import annotations
import argparse
import time
from pathlib import Path
import numpy as np
from skimage.color import deltaE_ciede2000
from comun import familia_sha, guardar, leer, sha256
from modelo import cargar_imagen, cargar_pesos, geometria, prediccion_red

class Buscador:
    def __init__(self, dataset, pesos=None, device='cpu'):
        self.root=Path(dataset); self.device=device; self.net=None; self.checkpoint=None
        m=leer(self.root/'manifest.json')
        if sha256(self.root/'galeria.json')!=m['galeria_sha256']: raise ValueError('Galería alterada')
        self.galeria=leer(self.root/'galeria.json'); self.features=[]; self.alturas=[]
        if pesos: self.net,self.checkpoint=cargar_pesos(pesos,device)
        for r in self.galeria:
            im=cargar_imagen(self.root,r); shape,alto,_=geometria(im)
            self.features.append(prediccion_red(self.net,im,device)[0] if self.net else shape)
            self.alturas.append(alto)
        self.features=np.stack(self.features)
    def predecir(self,im,texto,dpi=96):
        ids=[i for i,r in enumerate(self.galeria) if r['texto']==texto]
        if not ids: return None
        shape,alto,tinta=geometria(im)
        if self.net: feature,size,tinta=prediccion_red(self.net,im,self.device)
        else: feature=shape
        dist=((self.features[ids]-feature)**2).mean(1)
        orden=[ids[i] for i in np.argsort(dist,kind='stable')]
        vecinos=[]
        for i in orden:
            if self.galeria[i]['familia'] not in vecinos: vecinos.append(self.galeria[i]['familia'])
        mejor=orden[0]; r=self.galeria[mejor]
        if not self.net: size=r['tamano_pt']*alto/max(1,self.alturas[mejor])*r['dpi']/dpi
        if self.net: size *= 96 / dpi
        # Margen de semejanza, NO probabilidad calibrada.
        vals=np.sort(dist); confianza=float(np.clip((vals[1]-vals[0])/(vals[1]+1e-8),0,1)) if len(vals)>1 else 0.
        return dict(fuentes=vecinos[:5],fuente=r['familia'],tamano_pt=float(size),tinta_lab=tinta,
                    peso=r['peso'],cursiva=r['cursiva'],confianza=confianza)

def evaluar(dataset, salida, esperado, pesos=None, galeria=None, device='cpu'):
    root=Path(dataset)
    if sha256(root/'holdout.json')!=esperado: raise ValueError('Holdout distinto del sellado')
    examen=leer(root/'holdout.json'); rows=examen['muestras']
    if not rows: raise ValueError('Holdout vacío')
    if any(r['familia_sha256'] != familia_sha(r['familia']) for r in rows): raise ValueError('Familia inconsistente')
    buscador=Buscador(galeria or root,pesos,device)
    ck=buscador.checkpoint
    if ck:
        if {r['familia_sha256'] for r in rows}&set(ck['familias_train_sha256']): raise ValueError('Fuga de familias')
        if {r.get('sha256_origen') for r in rows}&set(ck['origenes_train']): raise ValueError('Fuga de documentos')
        if examen.get('dominio','sintetico')=='sintetico' and esperado!=ck['holdout_sha256']:
            raise ValueError('Checkpoint entrenado para otro holdout')
    inicio=time.perf_counter(); ac1=[]; ac5=[]; tamanos=[]; colores=[]; omitidos=0
    for r in rows:
        pred=buscador.predecir(cargar_imagen(root,r),r['texto'],r['dpi'])
        ac1.append(bool(pred and pred['fuente']==r['familia']))
        ac5.append(bool(pred and r['familia'] in pred['fuentes']))
        if not pred: omitidos+=1; continue
        tamanos.append(abs(pred['tamano_pt']-r['tamano_pt']))
        colores.append(float(deltaE_ciede2000(np.asarray(r['tinta_lab']),np.asarray(pred['tinta_lab']))))
    def errores(xs):
        return dict(media=float(np.mean(xs)),mediana=float(np.median(xs)),p95=float(np.percentile(xs,95))) if xs else None
    informe=dict(version=1,metodo=ck['etapa'] if ck else 'vecino_pixeles',
        dominio=examen.get('dominio','sintetico'),n=len(rows),cobertura=(len(rows)-omitidos)/len(rows),
        familias_holdout=len({r['familia'] for r in rows}),candidatas=len({r['familia'] for r in buscador.galeria}),
        top1=float(np.mean(ac1)),top5=float(np.mean(ac5)),error_tamano_pt=errores(tamanos),deltaE2000=errores(colores),
        sha256_holdout=esperado,sha256_pesos=sha256(pesos) if pesos else None,
        sha256_galeria=sha256(buscador.root/'galeria.json'),segundos_inferencia=time.perf_counter()-inicio,
        dispositivo=device,coste_usd=None,ocr='carácter conocido para aislar tipografía; OCR no evaluado')
    if pesos:
        informe['entrenamiento']=leer(Path(pesos).parent/'entrenamiento.json')
    else: informe['entrenamiento']=dict(gpu=None,segundos=0,coste_usd=0)
    guardar(salida,informe); return informe

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path)
    p.add_argument('--salida',type=Path,required=True);p.add_argument('--holdout-sha256',required=True)
    p.add_argument('--pesos',type=Path);p.add_argument('--galeria',type=Path);p.add_argument('--dispositivo',default='cpu',choices=['cpu','cuda'])
    a=p.parse_args();print(evaluar(a.dataset,a.salida,a.holdout_sha256,a.pesos,a.galeria,a.dispositivo))
