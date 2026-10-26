"""Examen único en Colab: tres métodos en una pasada, solo agregados a disco."""
from __future__ import annotations
import argparse
from collections import Counter
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageFilter
import pymupdf as fitz
from skimage.color import deltaE_ciede2000

from comun import ROOT, SEED, familia_sha, guardar, lab, leer, particion, sha256
from examen.preparar import ErrorExamen, digest_bytes, exigir_sha, preparar
from generar_sintetico import GLIFOS
from medir import Buscador
from nativo import comprobar_documento, nombre_limpio


class Silencio:
    def write(self, value):
        return len(value)
    def flush(self):
        pass


@contextlib.contextmanager
def sin_contenido_en_logs():
    errors=fitz.TOOLS.mupdf_display_errors()
    warnings=fitz.TOOLS.mupdf_display_warnings()
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
    try:
        with contextlib.redirect_stdout(Silencio()), contextlib.redirect_stderr(Silencio()):
            yield
    finally:
        fitz.TOOLS.mupdf_warnings(reset=True)
        fitz.TOOLS.mupdf_display_errors(errors)
        fitz.TOOLS.mupdf_display_warnings(warnings)


def verificar_protocolo(esperado):
    exigir_sha(esperado)
    protocolo=leer(ROOT/'examen/protocolo.json')
    if esperado!=protocolo['prerregistro_sha256'] or sha256(ROOT/'PRERREGISTRO.md')!=esperado:
        raise ErrorExamen('PRERREGISTRO_SHA_NO_COINCIDE')
    if sha256(ROOT/'examen/catalogo_preexamen.json')!=protocolo['catalogo_preexamen_sha256']:
        raise ErrorExamen('CATALOGO_PREEXAMEN_ALTERADO')
    if sha256(ROOT/'fuentes.lock.json')!=protocolo['fuentes_lock_sha256']:
        raise ErrorExamen('FUENTES_LOCK_ALTERADO')
    return leer(ROOT/'examen/catalogo_preexamen.json')['alias']


def verificar_galeria(root, esperado):
    root=Path(root);exigir_sha(esperado)
    if sha256(root/'galeria.json')!=esperado:
        raise ErrorExamen('GALERIA_SHA_NO_COINCIDE')
    m=leer(root/'manifest.json')
    if m['galeria_sha256']!=esperado or m['fuentes_lock_sha256']!=sha256(ROOT/'fuentes.lock.json'):
        raise ErrorExamen('GALERIA_DE_OTRO_PROTOCOLO')
    fuentes={f['sha256']:f['familia'] for f in leer(ROOT/'fuentes.lock.json')['fuentes']}
    rows=leer(root/'galeria.json');pairs=set()
    for r in rows:
        if fuentes.get(r['fuente_sha256'])!=r['familia'] or familia_sha(r['familia'])!=r['familia_sha256']:
            raise ErrorExamen('GALERIA_FAMILIA_INVALIDA')
        if r['texto'] not in GLIFOS or r['dpi']!=96 or r['tamano_pt']!=24:
            raise ErrorExamen('GALERIA_NO_ES_PLANTILLA_PRERREGISTRADA')
        key=(r['fuente_sha256'],r['texto'])
        if key in pairs:
            raise ErrorExamen('GALERIA_DUPLICADA')
        pairs.add(key)
    if pairs!={(h,c) for h in fuentes for c in GLIFOS}:
        raise ErrorExamen('GALERIA_INCOMPLETA')


def validar_modelos(buscadores, archivos, hashes, origenes):
    train={};seen=set();anterior=None
    for metodo in ('solo_sintetico','afinado_A'):
        ck=buscadores[metodo].checkpoint
        if set(ck['familias_train_sha256'])!={familia_sha(n) for n in ck['familias']}:
            raise ErrorExamen('PESOS_FAMILIAS_INCONSISTENTES')
        if ck['etapa']!=metodo:
            raise ErrorExamen('ETAPA_PESOS_INVALIDA')
        if not set(ck['familias_train_sha256']) or any(particion(h)!='train' for h in ck['familias_train_sha256']):
            raise ErrorExamen('PESOS_ENTRENARON_FAMILIA_HOLDOUT')
        if set(ck['origenes_train']) & origenes:
            raise ErrorExamen('PESOS_ENTRENARON_ORIGEN_EXAMEN')
        if metodo=='afinado_A':
            if ck['pesos_iniciales_sha256']!=hashes['solo_sintetico']:
                raise ErrorExamen('AFINADO_NO_PARTE_DE_MISMA_CNN')
            if (ck['holdout_sha256']!=anterior['holdout_sha256'] or ck['familias']!=anterior['familias'] or
                    not set(anterior['familias_train_sha256'])<=set(ck['familias_train_sha256']) or
                    not set(anterior['origenes_train'])<=set(ck['origenes_train'])):
                raise ErrorExamen('AFINADO_PERDIO_PROCEDENCIA')
        anterior=ck;seen.update(ck['familias_train_sha256'])
        meta=leer(Path(archivos[metodo]).parent/'entrenamiento.json')
        if meta['sha256_pesos']!=hashes[metodo] or meta['etapa']!=metodo or meta['sha256_train']!=ck['train_sha256']:
            raise ErrorExamen('METADATA_PESOS_INCONSISTENTE')
        if meta['epocas'] != (20 if metodo=='solo_sintetico' else 5):
            raise ErrorExamen('EPOCAS_NO_COINCIDEN_CON_PRERREGISTRO')
        numeric={k:meta.get(k) for k in ('segundos','coste_usd')}
        for v in numeric.values():
            if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0):
                raise ErrorExamen('COSTE_O_TIEMPO_INVALIDO')
        train[metodo]={**numeric,'gpu':meta.get('gpu'),'epocas':meta['epocas']}
    train['vecino_pixeles']=dict(segundos=0.,coste_usd=0.,gpu=None,epocas=0)
    return seen,train


class Agregados:
    def __init__(self):
        self.n=0;self.ac1=0;self.ac5=0;self.validas=0
        self.tamanos=[];self.colores=[];self.segundos=0.
    def agregar(self,pred,familia,size,color):
        self.n+=1
        if pred is None:
            return
        ps=pred.get('tamano_pt');pc=np.asarray(pred.get('tinta_lab'),dtype=float)
        if ps is None or not np.isfinite(ps) or ps<=0 or pc.shape!=(3,) or not np.isfinite(pc).all():
            return
        self.validas+=1
        self.ac1+=int(pred['fuente']==familia)
        self.ac5+=int(familia in pred['fuentes'])
        self.tamanos.append(abs(ps-size))
        self.colores.append(float(deltaE_ciede2000(np.asarray(color),pc)))
    def resumen(self):
        def stats(v):
            return dict(n=len(v),media=float(np.mean(v)),mediana=float(np.median(v)),p95=float(np.percentile(v,95))) if v else None
        return dict(n=self.n,n_predicciones_validas=self.validas,
            top1=self.ac1/self.n if self.n else None,top5=self.ac5/self.n if self.n else None,
            cobertura_prediccion=self.validas/self.n if self.n else None,
            error_tamano_pt=stats(self.tamanos),deltaE2000=stats(self.colores),segundos_inferencia=self.segundos)


def raster_ruidoso(page,origen,numero):
    # Solo RAM: BytesIO no crea temporales. Semilla estable ante orden de archivos.
    pix=page.get_pixmap(dpi=96,colorspace=fitz.csRGB,alpha=False)
    im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
    im=im.filter(ImageFilter.GaussianBlur(.45))
    seed=int(hashlib.sha256(f'{SEED}:{origen}:{numero}'.encode()).hexdigest()[:16],16)
    rng=np.random.default_rng(seed)
    arr=np.asarray(im,dtype=float)+rng.normal(0,2,(im.height,im.width,3))
    im=Image.fromarray(np.clip(arr,0,255).astype('uint8'))
    with io.BytesIO() as b:
        im.save(b,format='JPEG',quality=80);b.seek(0)
        with Image.open(b) as enc:
            return enc.convert('RGB')


def consultar_pagina(page,raw,origen,numero,alias,seen,buscadores,agregados,contadores,familias):
    im=None
    for block in raw['blocks']:
        if block['type']!=0:
            continue
        for line in block['lines']:
            for span in line['spans']:
                fam=alias.get(nombre_limpio(span['font']))
                for c in span['chars']:
                    if not c['c'].strip():
                        continue
                    contadores['caracteres_nativos_no_blancos']+=1
                    if not fam:
                        contadores['fuente_fuera_catalogo']+=1;continue
                    h=familia_sha(fam)
                    if particion(h)!='holdout' or h in seen:
                        contadores['familia_train_excluida']+=1;continue
                    if c['c'] not in GLIFOS:
                        contadores['glifo_fuera_catalogo']+=1;continue
                    if tuple(line['dir'])!=(1.,0.):
                        contadores['texto_no_horizontal']+=1;continue
                    box=tuple(int(f(v*96/72)) for v,f in zip(c['bbox'],(np.floor,np.floor,np.ceil,np.ceil)))
                    x0,y0,x1,y1=box
                    offy=round(48+y0-c['origin'][1]*96/72)
                    if (not 0<x1-x0<=60 or not 0<y1-y0<=60 or offy<0 or offy+y1-y0>64 or
                            x0<0 or y0<0 or x1>math.ceil(page.rect.width*96/72) or y1>math.ceil(page.rect.height*96/72)):
                        contadores['caja_no_evaluable']+=1;continue
                    if im is None:
                        im=raster_ruidoso(page,origen,numero)
                    crop=im.crop(box)
                    patch=Image.new('RGB',(64,64),'white')
                    patch.paste(crop,(32-crop.width//2,offy))
                    rgb=[(span['color']>>k)&255 for k in (16,8,0)]
                    color=lab(rgb)
                    for metodo,buscador in buscadores.items():
                        start=time.perf_counter()
                        pred=buscador.predecir(patch,c['c'],96)
                        agregados[metodo].segundos+=time.perf_counter()-start
                        agregados[metodo].agregar(pred,fam,span['size'],color)
                    contadores['caracteres_evaluados']+=1;familias.add(h)
                    patch.close();crop.close()
    if im is not None:
        im.close()


def evaluar(carpeta,sello,*,sello_sha,prerregistro_sha,galeria,galeria_sha,
            sintetico,sintetico_sha,afinado,afinado_sha,control,salida,propio=False,
            device='cpu',coste_hora=None):
    """Solo llamar desde el Colab de Bruno; fixtures sintéticos en tests locales."""
    marca=None
    with sin_contenido_en_logs():
        try:
            if not propio:
                raise ErrorExamen('REQUIERE_PDFS_PROPIOS_SIN_FIRMAS_NI_SELLOS')
            if device not in ('cpu','cuda'):
                raise ErrorExamen('DISPOSITIVO_INVALIDO')
            if coste_hora is not None and (not math.isfinite(coste_hora) or coste_hora<0):
                raise ErrorExamen('TARIFA_INVALIDA')
            alias=verificar_protocolo(prerregistro_sha)
            # Validaciones de artefactos antes de leer bytes privados.
            verificar_galeria(galeria,galeria_sha)
            archivos={'solo_sintetico':Path(sintetico),'afinado_A':Path(afinado)}
            hashes={'solo_sintetico':exigir_sha(sintetico_sha),'afinado_A':exigir_sha(afinado_sha)}
            for k,p in archivos.items():
                if sha256(p)!=hashes[k]:
                    raise ErrorExamen('PESOS_SHA_NO_COINCIDE')
            buscadores={'vecino_pixeles':Buscador(galeria),
                        **{k:Buscador(galeria,p,device) for k,p in archivos.items()}}
            inv=preparar(carpeta,sello,sello_sha)
            seen,train=validar_modelos(buscadores,archivos,hashes,set(inv.rutas))
            control=Path(control).resolve();salida=Path(salida).resolve();root=Path(carpeta).resolve()
            if salida.exists() or control==root or root in control.parents or salida==root or root in salida.parents:
                raise ErrorExamen('SALIDA_O_CONTROL_INVALIDO')
            control.mkdir(parents=True,exist_ok=True)
            marca=control/f'{inv.cohorte_sha256}.json'
            inicio=time.perf_counter()
            try:
                guardar(marca,dict(estado='INICIADO',sha256_cohorte=inv.cohorte_sha256,
                    sha256_sello=sello_sha,sha256_prerregistro=prerregistro_sha),exclusivo=True)
            except FileExistsError:
                marca=None
                raise ErrorExamen('EXAMEN_YA_INICIADO_NO_REPETIR') from None
            agregados={k:Agregados() for k in buscadores};familias=set()
            contadores=Counter({k:0 for k in ('paginas_total','paginas_sin_referencia_A','paginas_con_referencia_A',
                'caracteres_nativos_no_blancos','fuente_fuera_catalogo','familia_train_excluida','glifo_fuera_catalogo',
                'texto_no_horizontal','caja_no_evaluable','caracteres_evaluados','pdfs_nativo','pdfs_escaneado')})
            for entry in inv.documentos:
                # Segunda comprobación de bytes cierra cambios entre inventario y apertura.
                data=inv.rutas[entry['sha256']].read_bytes()
                if digest_bytes(data)!=entry['sha256']:
                    raise ErrorExamen('PDF_CAMBIO_DESPUES_DE_VERIFICAR')
                with fitz.open(stream=data,filetype='pdf') as doc:
                    try:
                        comprobar_documento(doc,True)
                    except ValueError:
                        raise ErrorExamen('PDF_FIRMADO_SELLADO_O_CIFRADO') from None
                    if len(doc)!=entry['n_paginas']:
                        raise ErrorExamen('PAGINAS_NO_COINCIDEN_CON_SELLO')
                    texto_en_documento=False
                    for numero,page in enumerate(doc):
                        page.set_rotation(0)
                        raw=page.get_text('rawdict',flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)
                        hay_texto=any(c['c'].strip() for b in raw['blocks'] if b['type']==0
                            for l in b['lines'] for s in l['spans'] for c in s['chars'])
                        contadores['paginas_total']+=1
                        if not hay_texto:
                            contadores['paginas_sin_referencia_A']+=1;continue
                        texto_en_documento=True;contadores['paginas_con_referencia_A']+=1
                        consultar_pagina(page,raw,entry['sha256'],numero,alias,seen,
                            buscadores,agregados,contadores,familias)
                    tipo='nativo' if texto_en_documento else 'escaneado'
                    if tipo!=entry['tipo']:
                        raise ErrorExamen('TIPO_NO_COINCIDE_CON_SELLO')
                    contadores['pdfs_'+tipo]+=1
                del data
            filas=[];n=contadores['caracteres_evaluados'];total=contadores['caracteres_nativos_no_blancos']
            gpu=None
            if device=='cuda':
                import torch
                gpu=torch.cuda.get_device_name(0)
            for k,a in agregados.items():
                row=dict(metodo=k,dominio='real_nativo_rasterizado',estado='EVALUADO' if n else 'NO_EVALUABLE',
                    **a.resumen(),entrenamiento=train[k],gpu_inferencia=gpu if k!='vecino_pixeles' else None,
                    coste_inferencia_usd=a.segundos/3600*coste_hora if coste_hora is not None and k!='vecino_pixeles' else None,
                    sha256_pesos=hashes.get(k))
                if k!='vecino_pixeles':
                    base=agregados['vecino_pixeles'].resumen()
                    delta=row['top1']-base['top1'] if n else None
                    row['mejora_top1_vs_vecino']=delta
                    row['supera_umbrales_prerregistrados']=(n>0 and len(familias)>=2 and row['cobertura_prediccion']==1 and
                        row['top1']>=.8 and delta>=.05 and row['top5']>=.95 and
                        row['error_tamano_pt']['media']<=1 and row['deltaE2000']['media']<=3)
                filas.append(row)
            informe=dict(version=2,estado='EVALUADO' if n else 'NO_EVALUABLE',
                sha256_sello=sello_sha,sha256_prerregistro=prerregistro_sha,sha256_galeria=galeria_sha,
                sha256_codigo_evaluador=sha256(Path(__file__)),
                sha256_cohorte=inv.cohorte_sha256,n_pdfs=len(inv.documentos),contadores=dict(contadores),
                familias_holdout_evaluadas=len(familias),candidatas=len({r['familia'] for r in buscadores['vecino_pixeles'].galeria}),
                cobertura_caracteres_nativos=n/total if total else None,
                escaneados=dict(estado='NO_EVALUABLE_SIN_NATIVO_EMPAREJADO',
                    paginas=contadores['paginas_sin_referencia_A'],top1=None,top5=None,error_tamano_pt=None,deltaE2000=None),
                filas=filas,segundos_evaluacion_total=time.perf_counter()-inicio,
                nota='Tipografía condicionada a glifos/transcripción A; solo agregado del subconjunto elegible. No es OCR ni escáner físico.')
            guardar(salida,informe,exclusivo=True)
            guardar(marca,dict(estado='COMPLETADO',sha256_cohorte=inv.cohorte_sha256,
                sha256_sello=sello_sha,sha256_prerregistro=prerregistro_sha,sha256_metricas=sha256(salida)))
            return informe
        except Exception as e:
            codigo=str(e) if isinstance(e,ErrorExamen) else 'EVALUACION_FALLIDA'
            if marca is not None:
                try:
                    guardar(marca,dict(estado='FALLIDO_NO_REPETIR',codigo=codigo,sha256_prerregistro=prerregistro_sha))
                except Exception:
                    pass  # El marcador INICIADO también bloquea el reintento.
            raise ErrorExamen(codigo) from None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('carpeta',type=Path);p.add_argument('sello',type=Path)
    p.add_argument('--sello-sha256',required=True);p.add_argument('--prerregistro-sha256',required=True)
    p.add_argument('--galeria',type=Path,required=True);p.add_argument('--galeria-sha256',required=True)
    p.add_argument('--sintetico',type=Path,required=True);p.add_argument('--sintetico-sha256',required=True)
    p.add_argument('--afinado',type=Path,required=True);p.add_argument('--afinado-sha256',required=True)
    p.add_argument('--control',type=Path,required=True);p.add_argument('--salida',type=Path,required=True)
    p.add_argument('--propios-bruno-sin-firmas-ni-sellos',action='store_true')
    p.add_argument('--dispositivo',choices=['cpu','cuda'],default='cpu');p.add_argument('--coste-hora-usd',type=float)
    a=p.parse_args()
    try:
        result=evaluar(a.carpeta,a.sello,sello_sha=a.sello_sha256,prerregistro_sha=a.prerregistro_sha256,
            galeria=a.galeria,galeria_sha=a.galeria_sha256,sintetico=a.sintetico,sintetico_sha=a.sintetico_sha256,
            afinado=a.afinado,afinado_sha=a.afinado_sha256,control=a.control,salida=a.salida,
            propio=a.propios_bruno_sin_firmas_ni_sellos,device=a.dispositivo,coste_hora=a.coste_hora_usd)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except ErrorExamen as e:
        print(json.dumps({'estado':'RECHAZADO','codigo':str(e)}));return 2
    except Exception:
        print('{"estado":"RECHAZADO","codigo":"ENTRADA_INVALIDA"}');return 2

if __name__=='__main__':
    raise SystemExit(main())
