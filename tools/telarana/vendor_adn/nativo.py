"""Camino A offline: RAWDICT por carácter y reconstrucción independiente."""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import numpy as np
import pymupdf as fitz
from .comun import VERSION, guardar, lab, ortografia, sha256, validar_pagina

BASE14 = {n.lower().replace('-', ''): n for n in ('Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique',
    'Helvetica-BoldOblique', 'Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic',
    'Courier', 'Courier-Bold', 'Courier-Oblique', 'Courier-BoldOblique', 'Symbol', 'ZapfDingbats')}

def nombre_limpio(n):
    return n.split('+', 1)[-1].replace(' ', '').replace('-', '').lower()

def comprobar_documento(doc, propio):
    if not propio:
        raise ValueError('Requiere declaración explícita de documento propio sin sellos de terceros')
    if doc.needs_pass:
        raise ValueError('PDF cifrado')
    if doc.get_sigflags() > 0:
        raise ValueError('No procesar PDF con campos de firma')
    for p in doc:
        if any(a.type[0] == fitz.PDF_ANNOT_STAMP for a in p.annots() or []):
            raise ValueError('No procesar PDF con sellos')
    # No puede detectar una firma/sello rasterizado: la declaración humana sigue siendo necesaria.

def fuentes_pagina(doc, page, salida):
    fuentes = []
    for xref, ext, tipo, base, recurso, *_ in page.get_fonts(full=True):
        item = dict(xref=xref, nombre=base, recurso=recurso, tipo=tipo, archivo=None, sha256=None)
        try:
            nombre, extension, _, datos = doc.extract_font(xref)
            if datos:
                destino = salida / 'fuentes' / f'{xref}.{extension}'
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(datos)
                item.update(archivo=str(destino.relative_to(salida)), sha256=sha256(destino))
        except (ValueError, RuntimeError) as e:
            item['advertencia'] = str(e)
        fuentes.append(item)
    return fuentes

def resolver_fuente(nombre, fuentes, salida):
    candidatos = [x for x in fuentes if nombre_limpio(x['nombre']) == nombre_limpio(nombre)]
    if len(candidatos) == 1 and candidatos[0]['archivo']:
        f = candidatos[0]
        return fitz.Font(fontfile=str(salida / f['archivo'])), f
    if any(x['archivo'] for x in candidatos):
        return None, None  # Nombres ambiguos: no sustituir silenciosamente una fuente incrustada.
    base = BASE14.get(nombre_limpio(nombre))
    if base:
        return fitz.Font(fontname=base), None
    return None, None

def extraer(entrada, salida, *, propio=False, comparar=True, dpi=144):
    entrada, salida = Path(entrada), Path(salida)
    if not 72 <= dpi <= 600:
        raise ValueError('DPI 72–600')
    with fitz.open(entrada) as doc:
        comprobar_documento(doc, propio)
        salida.mkdir(parents=True, exist_ok=False)
        resultados = []
        for numero, page in enumerate(doc, 1):
            if page.rotation:
                # RAWDICT y las coordenadas de inserción viven en página sin rotación.
                page.set_rotation(0)
            fuentes = fuentes_pagina(doc, page, salida)
            spans, bloques, advertencias = [], [], []
            raw = page.get_text('rawdict', flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)
            for bi, b in enumerate(raw['blocks']):
                if b['type'] != 0:
                    continue
                bloques.append({'id': bi, 'bbox': b['bbox']})
                lineas = b['lines']
                for li, linea in enumerate(lineas):
                    dx, dy = linea['dir']
                    for s in linea['spans']:
                        font, recurso = resolver_fuente(s['font'], fuentes, salida)
                        color = [(s['color'] >> k) & 255 for k in (16, 8, 0)]
                        chars = []
                        espacios = []
                        for ci, c in enumerate(s['chars']):
                            cc = dict(c)
                            cc.update(fuente=s['font'], tamano_pt=s['size'], flags=s['flags'],
                                      color_srgb=color, tinta_lab=lab(color))
                            chars.append(cc)
                            if font and ci + 1 < len(s['chars']):
                                siguiente = s['chars'][ci + 1]['origin']
                                avance = (siguiente[0]-c['origin'][0])*dx + (siguiente[1]-c['origin'][1])*dy
                                espacios.append(avance - font.text_length(c['c'], fontsize=s['size']))
                        interlinea = None
                        if li + 1 < len(lineas) and lineas[li + 1]['spans']:
                            sig = lineas[li + 1]['spans'][0]['origin']
                            interlinea = abs(-(sig[0]-s['origin'][0])*dy + (sig[1]-s['origin'][1])*dx)
                        texto = ''.join(c['c'] for c in chars)
                        span = dict(pagina=numero, bbox=s['bbox'], texto=texto, fuente=s['font'],
                            tamano_pt=s['size'], peso=700 if s['flags'] & 16 else 400,
                            inclinacion=math.degrees(math.atan2(dy, dx)),
                            cursiva=bool(s['flags'] & 2), tinta_lab=lab(color), color_srgb=color,
                            interletra=float(np.median(espacios)) if espacios else None,
                            interlinea=interlinea, linea_base={'origen': s['origin'], 'direccion': [dx, dy]},
                            origen='nativo', confianza=1.0, flags=s['flags'], caracteres=chars,
                            bloque=bi, linea=li, alfa=s.get('alpha', 255),
                            fuente_xref=recurso['xref'] if recurso else None,
                            ortografia=ortografia(texto), peso_metodo='flags: aproximación 400/700')
                        if font is None:
                            span['confianza'] = 0.8
                            advertencias.append(f'Fuente no reconstruible: {s["font"]}')
                        spans.append(span)
            pagina = dict(version=VERSION, pagina=numero, ancho_pt=page.rect.width,
                          alto_pt=page.rect.height, coordenadas='pt; página sin rotación; origen superior izquierdo',
                          sha256_origen=sha256(entrada), spans=spans, fuentes=fuentes,
                          advertencias=sorted(set(advertencias)))
            if comparar:
                pagina['comparacion'] = comparar_pagina(page, pagina, bloques, salida, dpi)
            validar_pagina(pagina)
            guardar(salida / f'pagina-{numero:04d}' / 'adn.json', pagina)
            resultados.append(pagina)
        guardar(salida / 'manifest.json', dict(version=VERSION, sha256_origen=sha256(entrada),
                paginas=len(resultados), archivos=[f'pagina-{i:04d}/adn.json' for i in range(1,len(resultados)+1)]))
        return resultados

def comparar_pagina(original, datos, bloques, salida, dpi):
    informe = []
    with fitz.open() as reconstruido:
        p = reconstruido.new_page(width=original.rect.width, height=original.rect.height)
        no_soportados = set()
        for s in datos['spans']:
            font, _ = resolver_fuente(s['fuente'], datos['fuentes'], salida)
            if font is None or s['linea_base']['direccion'] != [1.0, 0.0]:
                no_soportados.add(s['bloque']); continue
            try:
                # Unicode por carácter con la misma fuente, tamaño y posición. No copia streams.
                for c in s['caracteres']:
                    w = fitz.TextWriter(p.rect)
                    w.append(c['origin'], c['c'], font=font, fontsize=s['tamano_pt'])
                    w.write_text(p, color=tuple(v/255 for v in s['color_srgb']), opacity=s['alfa']/255)
            except (ValueError, RuntimeError):
                no_soportados.add(s['bloque'])
        for b in bloques:
            clip = fitz.Rect(b['bbox']) & original.rect
            if clip.is_empty:
                continue
            a = original.get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csRGB, alpha=False)
            r = p.get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csRGB, alpha=False)
            aa = np.frombuffer(a.samples, np.uint8).reshape(a.height, a.width, 3)
            rr = np.frombuffer(r.samples, np.uint8).reshape(r.height, r.width, 3)
            diff = np.abs(aa.astype(float)-rr.astype(float))
            foreground = (aa.min(2) < 245) | (rr.min(2) < 245)
            informe.append(dict(bloque=b['id'], bbox=b['bbox'], dpi=dpi,
                soportado=b['id'] not in no_soportados, mae_pixel=float(diff.mean()),
                fraccion_pixeles_distintos=float((diff.max(2)>0).mean()),
                mae_tinta=float(diff[foreground].mean()) if foreground.any() else 0.0))
        carpeta = salida / f'pagina-{datos["pagina"]:04d}'
        carpeta.mkdir(exist_ok=True)
        original.get_pixmap(dpi=dpi).save(carpeta / 'original.png')
        p.get_pixmap(dpi=dpi).save(carpeta / 'reconstruido.png')
        reconstruido.save(carpeta / 'reconstruido.pdf')
    return {'bloques': informe, 'nota': 'Compara bloque completo: fondos, gráficos, clipping y modos de texto no reconstruidos afectan la diferencia.'}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pdf', type=Path); ap.add_argument('--salida', type=Path, required=True)
    ap.add_argument('--propio-sin-firmas-ni-sellos', action='store_true')
    ap.add_argument('--sin-comparar', action='store_true'); ap.add_argument('--dpi', type=int, default=144)
    a=ap.parse_args()
    extraer(a.pdf,a.salida,propio=a.propio_sin_firmas_ni_sellos,comparar=not a.sin_comparar,dpi=a.dpi)
if __name__ == '__main__': main()
