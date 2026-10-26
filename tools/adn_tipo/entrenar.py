"""Entrena exclusivamente train; nunca usa métricas holdout para elegir pesos."""
from __future__ import annotations
import argparse
import os
import platform
import random
import time
from pathlib import Path
import numpy as np
import torch
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
from comun import ROOT, SEED, familia_sha, guardar, leer, particion, sha256
from modelo import TipoNet, cargar_imagen, cargar_pesos, tensor

def entrenar(dataset, salida, epocas=20, device='cpu', inicial=None, coste_hora=None, batch=64):
    if epocas < 1 or batch < 1: raise ValueError('Épocas y batch positivos')
    dataset,salida=Path(dataset),Path(salida)
    if salida.exists(): raise ValueError('No sobrescribir entrenamiento')
    manifest=leer(dataset/'manifest.json')
    if sha256(dataset/'train.json')!=manifest['train_sha256']: raise ValueError('train alterado')
    filas=leer(dataset/'train.json')
    if not filas: raise ValueError('train vacío')
    if any(r['familia_sha256'] != familia_sha(r['familia']) for r in filas): raise ValueError('Identidad de familia inválida')
    if any(r.get('dpi') != 96 for r in filas): raise ValueError('Entrenamiento requiere normalización a 96 DPI')
    if any(particion(r['familia_sha256'])!='train' for r in filas): raise ValueError('Familia holdout en train')
    if any(r.get('split')!='train' for r in filas): raise ValueError('Split incorrecto')
    familias=sorted({r['familia'] for r in filas})
    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    if device=='cuda' and not torch.cuda.is_available(): raise ValueError('CUDA no disponible')
    previo=None
    if inicial:
        net,previo=cargar_pesos(inicial,device)
        if manifest.get('dominio')!='nativo_train': raise ValueError('Afinado exige etiquetas A de train')
        if not set(familias)<=set(previo['familias']): raise ValueError('Familia nativa fuera del vocabulario train')
        familias=previo['familias']
    else:
        if manifest.get('dominio')!='sintetico': raise ValueError('Primera etapa requiere sintético')
        net=TipoNet(len(familias)).to(device)
    x=torch.stack([tensor(cargar_imagen(dataset,r)) for r in filas])
    y=torch.tensor([familias.index(r['familia']) for r in filas])
    reg=torch.tensor([[r['tamano_pt']/24,* (np.asarray(r['tinta_lab'])/[100,128,128])] for r in filas],dtype=torch.float32)
    loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(x,y,reg),batch_size=batch,shuffle=True,num_workers=0,
        generator=torch.Generator().manual_seed(SEED))
    net.train(); optimizer=torch.optim.Adam(net.parameters(),lr=1e-4 if inicial else 1e-3)
    inicio=time.perf_counter(); historial=[]
    for epoch in range(epocas):
        total=0.
        for xx,yy,rr in loader:
            xx,yy,rr=xx.to(device),yy.to(device),rr.to(device)
            emb,clase,pred=net(xx)
            loss=torch.nn.functional.cross_entropy(clase,yy)+torch.nn.functional.mse_loss(pred,rr)
            # Pares positivos de la misma familia y negativos con margen.
            sim=emb@emb.T
            same=yy[:,None]==yy[None,:]; diag=torch.eye(len(yy),dtype=torch.bool,device=device)
            pos=same & ~diag; neg=~same
            contrast=0*sim.sum()
            if pos.any(): contrast=contrast+(1-sim[pos]).mean()
            if neg.any(): contrast=contrast+torch.relu(sim[neg]-.3).mean()
            loss=loss+.2*contrast
            optimizer.zero_grad(); loss.backward(); optimizer.step(); total+=float(loss.detach())*len(xx)
        historial.append(total/len(filas)); print(f'epoca {epoch+1}: loss={historial[-1]:.5f}',flush=True)
    if device=='cuda': torch.cuda.synchronize()
    segundos=time.perf_counter()-inicio
    salida.mkdir(parents=True,exist_ok=False)
    fuentes=sorted({r.get('sha256_origen') for r in filas if r.get('sha256_origen')} | set(previo['origenes_train'] if previo else []))
    ck=dict(state=net.cpu().state_dict(),familias=familias,
        familias_train_sha256=sorted({r['familia_sha256'] for r in filas} | set(previo['familias_train_sha256'] if previo else [])),origenes_train=fuentes,
        holdout_sha256=previo['holdout_sha256'] if previo else manifest['holdout_sha256'],
        train_sha256=manifest['train_sha256'],etapa='afinado_A' if inicial else 'solo_sintetico',
        pesos_iniciales_sha256=sha256(inicial) if inicial else None)
    torch.save(ck,salida/'pesos.pt')
    resultado=dict(version=1,etapa=ck['etapa'],epocas=epocas,n=len(filas),seed=SEED,
        dispositivo=device,gpu=torch.cuda.get_device_name(0) if device=='cuda' else None,
        segundos=segundos,coste_usd=segundos/3600*coste_hora if coste_hora is not None else None,
        tarifa_usd_h=coste_hora,plataforma=platform.platform(),nice=os.getpriority(os.PRIO_PROCESS,0),
        parametros=sum(p.numel() for p in net.parameters()),loss=historial,
        sha256_pesos=sha256(salida/'pesos.pt'),sha256_holdout=ck['holdout_sha256'],
        sha256_train=manifest['train_sha256'],sha256_prerregistro=sha256(ROOT/'PRERREGISTRO.md'))
    guardar(salida/'entrenamiento.json',resultado); return resultado

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dataset',type=Path); ap.add_argument('--salida',type=Path,required=True)
    ap.add_argument('--epocas',type=int,default=20); ap.add_argument('--dispositivo',choices=['cpu','cuda'],default='cpu')
    ap.add_argument('--inicial',type=Path); ap.add_argument('--coste-hora-usd',type=float); ap.add_argument('--batch',type=int,default=64)
    a=ap.parse_args(); print(entrenar(a.dataset,a.salida,a.epocas,a.dispositivo,a.inicial,a.coste_hora_usd,a.batch))
