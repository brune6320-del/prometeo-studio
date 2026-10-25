"""Fixtures dibujados; no incluye ni descarga imágenes de terceros."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw


def forma(carpeta, tipo):
    carpeta = Path(carpeta)
    mask = Image.new('L', (512, 512), 0)
    draw = ImageDraw.Draw(mask)
    if tipo == 'rectangulo':
        draw.rectangle((100, 120, 299, 319), fill=255)
        prompt = {'caja': [90, 110, 310, 330]}
    elif tipo == 'circulo':
        draw.ellipse((128, 128, 383, 383), fill=255)
        prompt = {'puntos': [[256, 256], [30, 30]], 'etiquetas': [1, 0]}
    elif tipo == 'triangulo':
        draw.polygon([(256, 85), (90, 390), (420, 390)], fill=255)
        prompt = {'caja': [80, 75, 430, 400]}
    else:
        raise ValueError(tipo)
    rgb = Image.new('RGB', mask.size, '#f6f5ee')
    rgb.paste(Image.new('RGB', mask.size, '#3564b7'), mask=mask)
    path = carpeta / (tipo + '.png')
    rgb.save(path)
    return path, np.array(mask) > 0, {'coordenadas': 'imagen_px', 'piezas': [{'nombre': tipo, **prompt}]}


def documento(carpeta):
    import pymupdf
    path = Path(carpeta) / 'documento-sintetico.pdf'
    cajas = [[30, 40, 180, 100], [30, 120, 180, 180], [210, 40, 370, 220]]
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.insert_text((30, 25), 'DOCUMENTO SINTETICO - D-1', fontsize=11)
        for caja in cajas[:2]:
            page.draw_rect(pymupdf.Rect(caja), color=(.7,.7,.7), fill=(.94,.94,.94), width=.5)
            for y in range(caja[1]+10, caja[3]-4, 10):
                page.draw_rect(pymupdf.Rect(caja[0]+8,y,caja[2]-12,y+3),color=None,fill=(.12,.12,.12))
        x0,y0,x1,y1=cajas[2]
        page.draw_rect(pymupdf.Rect(cajas[2]),color=(0,0,0),width=1)
        for y in range(y0+30,y1,30):
            page.draw_line((x0,y),(x1,y),color=(0,0,0),width=.7)
        for x in range(x0+40,x1,40):
            page.draw_line((x,y0),(x,y1),color=(0,0,0),width=.7)
        page.insert_text((30,260),'Dos bloques de texto dibujado y una tabla.',fontsize=10)
        doc.save(path)
    return path, {'coordenadas':'pagina_pt','piezas':[
        {'caja':caja,'tipo':'tabla' if i==2 else 'texto','nombre':f'bloque-{i+1}'}
        for i,caja in enumerate(cajas)]}
