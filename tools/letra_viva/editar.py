"""Edición raster autorizada, inpainting y escritura con historial reversible."""
from pathlib import Path
import json
import math
import time
import cv2
import numpy as np
import pymupdf as fitz
from PIL import Image
from fontTools.ttLib import TTFont
from skimage.color import lab2rgb, rgb2lab
from skimage.metrics import structural_similarity
from .comun import abrir_adn,guardar,sha256,validar_documento


def caja_px(box,dpi,width,height):
    if len(box)!=4 or not np.isfinite(box).all():raise ValueError('Caja inválida')
    x0,y0=map(math.floor,np.asarray(box[:2])*dpi/72)
    x1,y1=map(math.ceil,np.asarray(box[2:])*dpi/72)
    if not 0<=x0<x1<=width or not 0<=y0<y1<=height:raise ValueError('Caja fuera de página')
    return x0,y0,x1,y1


def dentro(outer,inner):return outer[0]<=inner[0] and outer[1]<=inner[1] and inner[2]<=outer[2] and inner[3]<=outer[3]
def intersecta(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]


def reponer_region(original, editada, box):
    out=original.copy();x0,y0,x1,y1=box
    out[y0:y1,x0:x1]=editada[y0:y1,x0:x1]
    return out


def editar(pdf, adn, fuente, salida, *, pagina=1, span_id=18, texto=None,
           autorizado=None, excluidas=(), propio=False, dpi=144, metodo='estilo'):
    started=time.perf_counter();salida=Path(salida)
    if salida.exists():raise ValueError('Salida existente')
    if metodo not in ('simple','estilo'):raise ValueError('Método desconocido')
    if not 72<=dpi<=300:raise ValueError('DPI fuera del rango de laboratorio')
    data,pages=abrir_adn(pdf,adn);span=pages[pagina-1]['spans'][span_id]
    if 'educational' in span['texto'].casefold():raise ValueError('Marca educativa excluida de edición')
    if abs(span.get('inclinacion') or 0)>.01:raise ValueError('Aún no admite texto inclinado; no fingir soporte')
    original_text=span['texto'];texto=original_text if texto is None else texto
    if not isinstance(texto,str) or not texto:raise ValueError('Texto vacío')
    font=fitz.Font(fontfile=str(fuente))
    if any(c!=' ' and not font.has_glyph(ord(c)) for c in texto):raise ValueError('Glifo faltante: construir baseline explícita o abstenerse')
    if autorizado is None or not dentro(autorizado,span['bbox']):raise ValueError('Falta región autorizada que contenga el texto')
    if any(intersecta(autorizado,r) for r in excluidas):raise ValueError('Región intersecta firma/sello/zona excluida')
    with fitz.open(pdf) as doc:
        validar_documento(doc,propio);page=doc[pagina-1]
        if page.rotation:raise ValueError('Página rotada aún no soportada')
        pix=page.get_pixmap(dpi=dpi,alpha=False)
        original=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()
        box=caja_px(autorizado,dpi,pix.width,pix.height);x0,y0,x1,y1=box
        crop=original[y0:y1,x0:x1];paper=np.percentile(crop.reshape(-1,3),90,axis=0)
        mask=np.zeros(original.shape[:2],np.uint8)
        chars=span.get('caracteres') or [dict(c=original_text,bbox=span['bbox'],origin=span['linea_base']['origen'])]
        for char in chars:
            cb=caja_px(char['bbox'],dpi,pix.width,pix.height);a,b,c,d=cb
            local=original[b:d,a:c].astype(float)
            # Máscara de tinta dentro de cajas aprobadas; dilatar antialiasing sin salir de región.
            foreground=(np.linalg.norm(local-paper,axis=2)>30).astype(np.uint8)*255
            mask[b:d,a:c]=np.maximum(mask[b:d,a:c],foreground)
        mask=cv2.dilate(mask,np.ones((3,3),np.uint8))
        authorized_mask=np.zeros_like(mask);authorized_mask[y0:y1,x0:x1]=255;mask &= authorized_mask
        if metodo=='simple':
            canvas=original.copy();canvas[y0:y1,x0:x1]=np.round(paper).astype(np.uint8)
        else:
            cv2.setNumThreads(1)
            # Procesar un margen local; no inpaint sobre toda la lámina.
            margin=8;a=max(0,x0-margin);b=max(0,y0-margin);c=min(pix.width,x1+margin);d=min(pix.height,y1+margin)
            canvas=original.copy();canvas[b:d,a:c]=cv2.inpaint(original[b:d,a:c],mask[b:d,a:c],3,cv2.INPAINT_TELEA)
        origins=np.asarray([c['origin'] for c in chars],float)
        residuals=origins[:,1]-np.median(origins[:,1])
        measured_lab=np.array(span['tinta_lab'],float)
        rgb=np.clip(lab2rgb(measured_lab.reshape(1,1,3))[0,0]*255,0,255)
        original_ink=original[mask>0]
        ink_noise=float(np.std(original_ink.mean(1))) if len(original_ink) else 0.
        with fitz.open() as overlay:
            target=overlay.new_page(width=page.rect.width,height=page.rect.height)
            writer=fitz.TextWriter(target.rect);size=span['tamano_pt']
            if texto==original_text and metodo=='estilo':
                for c in chars:writer.append(c['origin'],c['c'],font=font,fontsize=size)
            else:
                writer.append(span['linea_base']['origen'],texto,font=font,fontsize=size)
            if not fitz.Rect(autorizado).contains(writer.text_rect):
                # Writer rect may include ascender allowance: check actual alpha below.
                pass
            writer.write_text(target,color=(0,0,0))
            rendered=target.get_pixmap(dpi=dpi,alpha=True)
            rgba=np.frombuffer(rendered.samples,np.uint8).reshape(rendered.height,rendered.width,4)
            alpha=rgba[:,:,3].astype(float)/255
        # Clipping silent prohibited: reject if new ink would leave authorization.
        if np.any((alpha>0)&(authorized_mask==0)):raise ValueError('Texto nuevo excede región autorizada')
        # Residual de tinta solo en caso estilo; amplitud conservadora medida del núcleo.
        noise=np.zeros((y1-y0,x1-x0,1))
        if metodo=='estilo' and len(original_ink):
            core=original_ink[np.linalg.norm(original_ink.astype(float)-paper,axis=1)>np.percentile(np.linalg.norm(original_ink.astype(float)-paper,axis=1),70)]
            sigma=float(core.std(axis=0).mean()) if len(core)>1 else 0.
            noise=np.random.default_rng(2610).normal(0,min(sigma,3.),noise.shape)
        local_alpha=alpha[y0:y1,x0:x1,None]
        composed=canvas.copy();composed[y0:y1,x0:x1]=np.clip(np.rint(canvas[y0:y1,x0:x1]*(1-local_alpha)+(rgb+noise)*local_alpha),0,255).astype(np.uint8)
        result=reponer_region(original,composed,box)
        diff=np.any(result!=original,axis=2);outside=diff&(authorized_mask==0)
        if np.any(outside):raise AssertionError('Modificación fuera de región autorizada')
        salida.mkdir(parents=True,exist_ok=False)
        Image.fromarray(original).save(salida/'pagina-antes.png');Image.fromarray(result).save(salida/'pagina-despues.png')
        Image.fromarray(crop).save(salida/'parche-antes.png');Image.fromarray(result[y0:y1,x0:x1]).save(salida/'parche-despues.png')
        target=result[y0:y1,x0:x1]
        metrics=dict(ssim=float(structural_similarity(crop,target,channel_axis=2,data_range=255)),
            mae_rgb=float(np.abs(crop.astype(float)-target).mean()),lpips=None,
            lpips_estado='NO VERIFICADO: pesos no autorizados ni descargados',
            pixeles_fuera_modificados=int(outside.sum()),pixeles_modificados=int(diff.sum()),
            segundos=time.perf_counter()-started,gpu_unidades=0,coste_usd=None)
        report=dict(version=1,sha256_origen=data['sha256_origen'],sha256_adn=sha256(adn),
            sha256_fuente=sha256(fuente),pagina=pagina,span=span_id,region_pt=autorizado,region_px=list(box),
            dpi=dpi,metodo=metodo,antes=original_text,despues=texto,tamano_pt=size,tinta_lab=measured_lab.tolist(),
            inclinacion=span.get('inclinacion'),residual_linea_base_pt=residuals.tolist(),
            textura_tinta_std_observada=ink_noise,region_excluidas=list(excluidas),
            sha256_antes=sha256(salida/'pagina-antes.png'),sha256_despues=sha256(salida/'pagina-despues.png'),
            sha256_parche_antes=sha256(salida/'parche-antes.png'),sha256_parche_despues=sha256(salida/'parche-despues.png'),
            metricas=metrics,dominio='DESARROLLO_MISMO_ORIGEN',aprendizaje_pesos=False,
            limite='Inpainting local puede degradar líneas/grano dentro de la región; revisar visualmente')
        guardar(salida/'edicion.json',report);return report
