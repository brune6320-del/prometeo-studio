"""Fuente sin plantilla: medoid por carácter y contornos con huecos. No usa Potrace."""
from pathlib import Path
import math
import shutil
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, TTLibError
from .comun import abrir_adn, guardar, sha256, validar_documento


def medoid(samples):
    # Tamaño normalizado solo para selección; el contorno conserva escala original.
    small=np.stack([cv2.resize(s['mask'],(32,32),interpolation=cv2.INTER_AREA).ravel()/255 for s in samples])
    # Distancias por bloques para no construir N×N×1024.
    distances=np.maximum(0,(small*small).sum(1)[:,None]+(small*small).sum(1)[None,:]-2*small@small.T)
    return int(np.argmin(distances.sum(1)))


def contorno(mask, em_px, baseline, left=0.):
    if em_px<=0 or not np.isfinite(em_px):raise ValueError('Escala de glifo inválida')
    contours,hierarchy=cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    pen=TTGlyphPen(None)
    if hierarchy is None:return pen.glyph()
    for i,contour in enumerate(contours):
        points=contour[:,0,:].astype(float)
        if len(points)<3 or abs(cv2.contourArea(contour))<1:continue
        # RETR_TREE conserva niveles: contorno exterior y agujeros en sentidos opuestos.
        depth=0;parent=hierarchy[0][i][3]
        while parent>=0:depth+=1;parent=hierarchy[0][parent][3]
        xy=np.column_stack(((points[:,0]+left)*1000/em_px,(baseline-points[:,1])*1000/em_px))
        signed=float(np.sum(xy[:,0]*np.roll(xy[:,1],-1)-np.roll(xy[:,0],-1)*xy[:,1]))
        if (depth%2==0 and signed>0) or (depth%2==1 and signed<0):xy=xy[::-1]
        pen.moveTo(tuple(xy[0]))
        for point in xy[1:]:pen.lineTo(tuple(point))
        pen.closePath()
    return pen.glyph()


def construir(pdf, adn, salida, *, pagina=1, excluir_spans=(), dpi=300, propio=False,
              fuente_xref=None):
    salida=Path(salida)
    if salida.exists():raise ValueError('No sobrescribir fuente')
    data,pages=abrir_adn(pdf,adn);page_data=pages[pagina-1]
    cv2.setNumThreads(1)
    with fitz.open(pdf) as doc:
        validar_documento(doc,propio)
        page=doc[pagina-1]
        if page.rotation:raise ValueError('Normalizar coordenadas de página rotada antes de extraer')
        pix=page.get_pixmap(dpi=dpi,alpha=False);raster=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3)
        source_fonts=[s.get('fuente_xref') for i,s in enumerate(page_data['spans']) if i not in excluir_spans]
        xrefs=set(source_fonts)
        if fuente_xref is None:
            if len(xrefs)!=1:raise ValueError('Varios estilos/fuentes: elegir fuente_xref, no mezclarlos')
            fuente_xref=next(iter(xrefs))
        samples={};excluded=0
        for si,span in enumerate(page_data['spans']):
            if si in excluir_spans or span.get('fuente_xref')!=fuente_xref:continue
            if abs(span.get('inclinacion') or 0)>0.01:excluded+=1;continue
            chars=span.get('caracteres')
            if not chars:
                if len(span['texto'])!=1:excluded+=1;continue
                chars=[dict(c=span['texto'],bbox=span['bbox'],origin=span['linea_base']['origen'])]
            for ci,char in enumerate(chars):
                c=char['c']
                if len(c)!=1 or c.isspace():continue
                box=np.array(char['bbox'])*dpi/72
                x0,y0=np.floor(box[:2]).astype(int);x1,y1=np.ceil(box[2:]).astype(int)
                if x0<0 or y0<0 or x1>pix.width or y1>pix.height or x1<=x0 or y1<=y0:excluded+=1;continue
                crop=raster[y0:y1,x0:x1];paper=np.percentile(crop.reshape(-1,3),90,axis=0)
                dist=np.linalg.norm(crop.astype(float)-paper,axis=2)
                mask=(dist>max(30.,float(dist.max())*.35)).astype(np.uint8)*255
                if np.count_nonzero(mask)<3:excluded+=1;continue
                em=span['tamano_pt']*dpi/72
                baseline=char['origin'][1]*dpi/72-y0
                left=x0-char['origin'][0]*dpi/72
                advance=(chars[ci+1]['origin'][0]-char['origin'][0])*1000/span['tamano_pt'] if ci+1<len(chars) else (char['bbox'][2]-char['origin'][0])*1000/span['tamano_pt']
                samples.setdefault(c,[]).append(dict(mask=mask,em_px=em,baseline=baseline,left=left,
                    advance=max(100,advance),span=si,caracter=ci,bbox=char['bbox']))
        if not samples:raise ValueError('No hay muestras utilizables')
        salida.mkdir(parents=True,exist_ok=False)
        embedded=None;embedding_reason=None
        if fuente_xref:
            _,ext,_,blob=doc.extract_font(fuente_xref)
            if blob:
                native=salida/f'incrustada.{ext}';native.write_bytes(blob)
                try:
                    tt=TTFont(native);cmap=tt.getBestCmap() or {}
                    fs=tt['OS/2'].fsType if 'OS/2' in tt else 0
                    if fs & (2|256|512):embedding_reason='Restricción de embedding/edición: revisar licencia original'
                    elif all(ord(c) in cmap for c in samples):embedded=native.name
                    else:embedding_reason='Subconjunto incrustado sin cobertura Unicode suficiente'
                    tt.close()
                except TTLibError:embedding_reason='Fuente CID/CFF sin contenedor sfnt/cmap Unicode reutilizable por este módulo'
        selected={c:values[medoid(values)] for c,values in sorted(samples.items())}
        glyphs={'.notdef':TTGlyphPen(None).glyph(),'space':TTGlyphPen(None).glyph()}
        metrics={'.notdef':(500,0),'space':(300,0)};cmap={32:'space'};records=[]
        for c,s in selected.items():
            name=f'uni{ord(c):04X}';glyphs[name]=contorno(s['mask'],s['em_px'],s['baseline'],s['left'])
            metrics[name]=(int(round(s['advance'])),int(round(s['left']*1000/s['em_px'])))
            cmap[ord(c)]=name
            target=salida/f'U{ord(c):04X}.png';Image.fromarray(s['mask']).save(target)
            records.append(dict(caracter=c,n=len(samples[c]),span=s['span'],indice=s['caracter'],
                bbox=s['bbox'],mask=target.name,mask_sha256=sha256(target),avance=metrics[name][0]))
        fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(list(glyphs));fb.setupCharacterMap(cmap)
        fb.setupGlyf(glyphs);fb.setupHorizontalMetrics(metrics);fb.setupHorizontalHeader(ascent=1200,descent=-400)
        fb.setupNameTable(dict(familyName='Prometeo Documento',styleName='Regular',
            uniqueFontIdentifier='Prometeo-'+data['sha256_origen'][:16],fullName='Prometeo Documento Regular',psName='PrometeoDocumento-Regular'))
        fb.setupOS2(sTypoAscender=1200,sTypoDescender=-400,usWinAscent=1400,usWinDescent=500)
        fb.setupPost();fb.setupMaxp();fb.save(salida/'observada.ttf')
        report=dict(version=1,sha256_origen=data['sha256_origen'],pagina=pagina,dpi=dpi,
            fuente_xref=fuente_xref,excluir_spans=list(excluir_spans),muestras=sum(map(len,samples.values())),
            glifos_observados=len(selected),omitidos=excluded,glifos=records,
            fuente=embedded or 'observada.ttf',sha256_fuente=sha256(salida/(embedded or 'observada.ttf')),
            incrustada_reutilizable=embedded,incrustada_limitacion=embedding_reason,
            metodo='contornos raster observados; medoid; sin plantilla; no entrenamiento',
            licencia_fuente='Solo experimento local sobre documento autorizado; no acredita licencia para distribuir fuente derivada')
        guardar(salida/'fuente.json',report)
        return report


def componer_faltante(mask_a, mask_b, regla):
    """Baseline de combinación explícita, sin atribuir identidad al contorno."""
    if regla not in ('union','interseccion'):raise ValueError('Regla no soportada')
    if mask_a.shape!=mask_b.shape:raise ValueError('Alinear glifos antes de combinar')
    return np.maximum(mask_a,mask_b) if regla=='union' else np.minimum(mask_a,mask_b)


def completar_mayuscula(fuente, salida, *, destino, modelo_minuscula, referencia_altura):
    """Baseline explícita: reescala los trazos de un glifo similar observado.

    No aprende, no garantiza identidad y no rellena caracteres silenciosamente.
    """
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.transformPen import TransformPen
    salida=Path(salida)
    if salida.exists():raise ValueError('No sobrescribir fuente completada')
    font=TTFont(fuente);cmap=font.getBestCmap();glyphset=font.getGlyphSet()
    if len(destino)!=1 or ord(destino) in cmap:raise ValueError('Destino debe ser un carácter faltante')
    if any(ord(c) not in cmap for c in (modelo_minuscula,referencia_altura)):raise ValueError('Faltan glifos de referencia')
    bounds=[]
    for c in (modelo_minuscula,referencia_altura):
        pen=BoundsPen(glyphset);glyphset[cmap[ord(c)]].draw(pen)
        if pen.bounds is None:raise ValueError('Glifo vacío')
        bounds.append(pen.bounds)
    a,b=bounds;sy=(b[3]-b[1])/(a[3]-a[1]);sx=(b[2]-b[0])/(a[2]-a[0])
    pen=TTGlyphPen(glyphset);glyphset[cmap[ord(modelo_minuscula)]].draw(TransformPen(pen,(sx,0,0,sy,b[0]-a[0]*sx,b[1]-a[1]*sy)))
    name=f'uni{ord(destino):04X}';order=list(font.getGlyphOrder())
    font['glyf'][name]=pen.glyph()
    font.setGlyphOrder(order+[name]);font['hmtx'].metrics[name]=font['hmtx'].metrics[cmap[ord(referencia_altura)]]
    for table in font['cmap'].tables:
        if table.isUnicode():table.cmap[ord(destino)]=name
    font.save(salida);font.close()
    record=dict(metodo='baseline reescala trazos de glifo similar observado',destino=destino,
        origen=modelo_minuscula,referencia_altura=referencia_altura,escala=[sx,sy],
        sha256_padre=sha256(fuente),sha256_salida=sha256(salida),aprendido=False,
        advertencia='Glifo aproximado, no muestra observada ni resultado de modelo')
    guardar(salida.with_suffix('.json'),record)
    return record
