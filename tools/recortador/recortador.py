"""SAM 2.1 Small local: una imagen/tesela cada vez, sin descargas en inferencia."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
MODELO = json.loads((ROOT / 'modelo.json').read_text(encoding='utf-8'))
MAX_PX = 2048
TIPOS = {'objeto', 'bloque', 'texto', 'tabla', 'cota', 'simbolo', 'leyenda', 'cajetin'}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def guardar_json(path, datos):
    Path(path).write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


@contextmanager
def exclusivo():
    """Evita dos inferencias concurrentes, también entre CLI y servidor."""
    if hasattr(os, 'getpriority'):
        actual = os.getpriority(os.PRIO_PROCESS, 0)
        if actual < 15:
            os.nice(15 - actual)
    with (ROOT / '.inferencia.lock').open('a') as archivo:
        try:
            fcntl.flock(archivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Ya hay una inferencia activa; espera a que termine.') from exc
        try:
            yield
        finally:
            fcntl.flock(archivo, fcntl.LOCK_UN)


@dataclass
class Fuente:
    imagen: Image.Image
    procedencia: dict

    def caja_pagina(self, caja):
        p = self.procedencia
        if p['tipo'] != 'pdf':
            return list(caja)
        ox, oy = p['origen_raster_px']
        escala = p['ppp'] / 72
        return [(caja[0] + ox) / escala, (caja[1] + oy) / escala,
                (caja[2] + ox) / escala, (caja[3] + oy) / escala]


def abrir_fuente(path, *, pagina=1, ppp=150, tesela=1, region=None):
    path = Path(path)
    procedencia = {'archivo': path.name, 'sha256_origen': sha256(path)}
    if path.suffix.lower() != '.pdf':
        with Image.open(path) as original:
            # Comprobar antes de decodificar para no cargar fotos enormes accidentalmente.
            if max(original.size) > MAX_PX:
                raise ValueError('La imagen supera 2048 px; reduce una copia antes de cargarla.')
            imagen = ImageOps.exif_transpose(original).convert('RGBA')
        procedencia.update(tipo='imagen', ancho=imagen.width, alto=imagen.height,
                           coordenadas='px de la imagen orientada por EXIF', tesela=1, total_teselas=1)
    else:
        import pymupdf
        if not 150 <= ppp <= 300:
            raise ValueError('PDF: ppp debe estar entre 150 y 300.')
        with pymupdf.open(path) as doc:
            if not 1 <= pagina <= len(doc):
                raise ValueError('Página fuera del documento (numeración desde 1).')
            page = doc[pagina - 1]
            escala = ppp / 72
            w, h = math.ceil(page.rect.width * escala), math.ceil(page.rect.height * escala)
            columnas, filas = math.ceil(w / MAX_PX), math.ceil(h / MAX_PX)
            if region is None:
                if not 1 <= tesela <= columnas * filas:
                    raise ValueError('Tesela fuera de la página (numeración desde 1).')
                col, fila = (tesela - 1) % columnas, (tesela - 1) // columnas
                # Límites enteros en píxeles; se evita redondear hacia 2049 en get_pixmap.
                clip = pymupdf.Rect(col * MAX_PX / escala, fila * MAX_PX / escala,
                                    min((col + 1) * MAX_PX, w) / escala,
                                    min((fila + 1) * MAX_PX, h) / escala) & page.rect
            else:
                clip = pymupdf.Rect(region)
                if clip.is_empty or not page.rect.contains(clip):
                    raise ValueError('La región debe estar dentro de la página visible.')
            if max(math.ceil(clip.x1 * escala) - math.floor(clip.x0 * escala),
                   math.ceil(clip.y1 * escala) - math.floor(clip.y0 * escala)) > MAX_PX:
                raise ValueError('La región supera 2048 px; usa una tesela o una región menor.')
            pix = page.get_pixmap(matrix=pymupdf.Matrix(escala, escala), clip=clip,
                                  colorspace=pymupdf.csRGB, alpha=False)
            if max(pix.width, pix.height) > MAX_PX:
                raise ValueError('La región supera 2048 px a los ppp elegidos; selecciona una región menor.')
            imagen = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).convert('RGBA')
            procedencia.update(tipo='pdf', pagina=pagina, ppp=ppp, tesela=tesela,
                               total_teselas=columnas * filas if region is None else 1,
                               region_pagina_pt=list(clip), pagina_tamano_pt=list(page.rect)[2:],
                               origen_raster_px=[pix.x, pix.y], ancho=pix.width, alto=pix.height,
                               rotacion=page.rotation, matriz_desrotacion=list(page.derotation_matrix),
                               coordenadas='pt (1/72 pulgada), origen superior izquierdo de página visible rotada')
    # Hash del raster RGB efectivo, además del fichero original (PDF o foto).
    fondo = Image.new('RGBA', imagen.size, 'white')
    rgb = Image.alpha_composite(fondo, imagen).convert('RGB')
    procedencia['sha256_raster_rgb'] = hashlib.sha256(rgb.tobytes()).hexdigest()
    return Fuente(imagen, procedencia)


def validar_prompts(datos, fuente):
    if not isinstance(datos, dict) or not isinstance(datos.get('piezas'), list):
        raise ValueError('JSON: se requiere un objeto con lista piezas.')
    if not 1 <= len(datos['piezas']) <= 128:
        raise ValueError('Se requieren entre 1 y 128 piezas por imagen.')
    coordenadas = datos.get('coordenadas', 'imagen_px')
    if coordenadas not in ('imagen_px', 'pagina_pt'):
        raise ValueError('coordenadas debe ser imagen_px o pagina_pt.')
    if coordenadas == 'pagina_pt' and fuente.procedencia['tipo'] != 'pdf':
        raise ValueError('pagina_pt solo es válido para PDF.')
    w, h = fuente.imagen.size

    def punto(v):
        if not isinstance(v, list) or len(v) != 2 or any(type(n) not in (int, float) or not math.isfinite(n) for n in v):
            raise ValueError('Cada punto debe ser [x,y] finito.')
        if coordenadas == 'pagina_pt':
            ox, oy = fuente.procedencia['origen_raster_px']
            escala = fuente.procedencia['ppp'] / 72
            return [v[0] * escala - ox, v[1] * escala - oy]
        return list(v)

    salida = []
    for p in datos['piezas']:
        if not isinstance(p, dict):
            raise ValueError('Cada pieza debe ser un objeto.')
        tipo = p.get('tipo', 'bloque' if fuente.procedencia['tipo'] == 'pdf' else 'objeto')
        if not isinstance(tipo, str) or tipo not in TIPOS:
            raise ValueError('Tipo de pieza desconocido.')
        raw_puntos = p.get('puntos', [])
        if not isinstance(raw_puntos, list) or len(raw_puntos) > 256:
            raise ValueError('puntos debe ser una lista de hasta 256 coordenadas.')
        puntos = [punto(v) for v in raw_puntos]
        labels = p.get('etiquetas', [1] * len(puntos))
        if not isinstance(labels, list) or len(labels) != len(puntos) or any(type(v) is not int or v not in (0, 1) for v in labels):
            raise ValueError('etiquetas debe contener 0/1 y corresponder a los puntos.')
        if any(not (0 <= x < w and 0 <= y < h) for x, y in puntos):
            raise ValueError('Punto fuera de la imagen/tesela seleccionada.')
        caja = p.get('caja')
        if caja is not None:
            if not isinstance(caja, list) or len(caja) != 4:
                raise ValueError('caja debe ser [x0,y0,x1,y1], con extremo final exclusivo.')
            caja = punto(caja[:2]) + punto(caja[2:])
            if not (0 <= caja[0] < caja[2] <= w and 0 <= caja[1] < caja[3] <= h):
                raise ValueError('Caja fuera de la tesela o vacía; usa --region-pagina si cruza una unión.')
        if caja is None and (not puntos or 1 not in labels):
            raise ValueError('Cada pieza necesita una caja o al menos un punto positivo.')
        salida.append({'tipo': tipo, 'nombre': str(p.get('nombre', tipo))[:120],
                       'puntos': puntos, 'etiquetas': labels, 'caja': caja})
    return salida


class MotorSAM:
    def __init__(self, dispositivo='cpu', pesos=None):
        # Torch 2.5.1 necesita CPU para interpolación bicúbica en MPS.
        # Debe establecerse antes de importar torch en este proceso.
        if dispositivo == 'mps':
            os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        if dispositivo not in ('cpu', 'mps'):
            raise ValueError('Dispositivo permitido: cpu o mps.')
        if dispositivo == 'mps' and not torch.backends.mps.is_available():
            raise ValueError('MPS no está disponible; usa --dispositivo cpu.')
        pesos = Path(pesos or ROOT / 'weights' / MODELO['archivo'])
        if sha256(pesos) != MODELO['sha256']:
            raise ValueError('SHA256 de pesos incorrecto; no se carga el checkpoint.')
        torch.set_num_threads(2)
        self.torch, self.dispositivo = torch, dispositivo
        self.predictor = SAM2ImagePredictor(build_sam2(
            MODELO['config'], str(pesos), device=dispositivo, apply_postprocessing=False))

    def preparar(self, fuente):
        if max(fuente.imagen.size) > MAX_PX:
            raise ValueError('La imagen supera 2048 px.')
        fondo = Image.new('RGBA', fuente.imagen.size, 'white')
        rgb = np.array(Image.alpha_composite(fondo, fuente.imagen).convert('RGB'), copy=True)
        with self.torch.inference_mode():
            self.predictor.set_image(rgb)

    def predecir(self, prompt):
        puntos = np.asarray(prompt['puntos'], dtype=np.float32) if prompt['puntos'] else None
        labels = np.asarray(prompt['etiquetas'], dtype=np.int32) if puntos is not None else None
        caja = np.asarray(prompt['caja'], dtype=np.float32) if prompt['caja'] else None
        with self.torch.inference_mode():
            masks, scores, _ = self.predictor.predict(point_coords=puntos, point_labels=labels,
                                                     box=caja, multimask_output=caja is None)
        indice = int(np.argmax(scores))
        score = float(scores[indice])
        if not math.isfinite(score):
            raise ValueError('SAM ha devuelto una puntuación no finita.')
        return np.asarray(masks[indice], dtype=bool), score

    def liberar_imagen(self):
        self.predictor.reset_predictor()
        if self.dispositivo == 'mps':
            self.torch.mps.empty_cache()


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def propuestas(motor, fuente, prompts=None, rejilla=0, min_score=0.8, min_area=64):
    w, h = fuente.imagen.size
    if rejilla:
        if not 2 <= rejilla <= 16:
            raise ValueError('Rejilla: entre 2 y 16 puntos por lado.')
        prompts = [{'nombre': 'propuesta', 'tipo': 'bloque' if fuente.procedencia['tipo'] == 'pdf' else 'objeto',
                    'puntos': [[(x + .5) * w / rejilla, (y + .5) * h / rejilla]],
                    'etiquetas': [1], 'caja': None}
                   for y in range(rejilla) for x in range(rejilla)]
    aceptadas = []  # máscaras empaquetadas: evita guardar N matrices de 2048² booleanos.
    for prompt in prompts or []:
        mask, score = motor.predecir(prompt)
        area = int(mask.sum())
        if rejilla:
            if score < min_score or area < min_area or area > w * h * .9:
                continue
            # El fondo puede dejar unos píxeles vacíos en las esquinas. Medir una
            # franja, no solo cuatro píxeles; las selecciones explícitas no se filtran.
            franja = max(1, round(min(w, h) * .02))
            borde = (np.count_nonzero(mask[:franja]) + np.count_nonzero(mask[-franja:])
                     + np.count_nonzero(mask[franja:-franja, :franja])
                     + np.count_nonzero(mask[franja:-franja, -franja:]))
            area_borde = w * h - max(0, w - 2*franja) * max(0, h - 2*franja)
            if borde / area_borde > .5:
                continue
            duplicado = False
            for anterior in aceptadas:
                previo = np.unpackbits(anterior, count=w * h).reshape(h, w).astype(bool)
                inter = np.count_nonzero(previo & mask)
                union = np.count_nonzero(previo | mask)
                if union and inter / union > .85:
                    duplicado = True
                    break
            if duplicado:
                continue
            aceptadas.append(np.packbits(mask))
        if bbox(mask) is not None:
            yield prompt, mask, score


def exportar_pieza(fuente, prompt, mask, score, carpeta, indice, documento=False):
    """Foto: silueta SAM. Documento: bloque rectangular, sin perforar letras/tablas."""
    caja_sam = bbox(mask)
    area_sam = int(mask.sum())
    if caja_sam is None:
        return None
    politica = 'silueta_sam'
    if documento:
        if prompt['caja'] is not None:
            x0, y0, x1, y1 = prompt['caja']
            caja = [math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)]
            politica = 'bloque_caja_usuario'
        else:
            caja = caja_sam
            politica = 'bloque_envolvente_sam'
        mask = np.zeros_like(mask)
        mask[caja[1]:caja[3], caja[0]:caja[2]] = True
    original = np.asarray(fuente.imagen)
    alpha = np.where(mask, original[:, :, 3], 0).astype(np.uint8)
    caja = bbox(alpha > 0)
    if caja is None:
        return None
    x0, y0, x1, y1 = caja
    recorte = original[y0:y1, x0:x1].copy()
    recorte[:, :, 3] = alpha[y0:y1, x0:x1]
    nombre = f'pieza-{indice:03d}.png'
    Image.fromarray(recorte).save(carpeta / nombre)
    return {'id': f'pieza-{indice:03d}', 'archivo': nombre, 'nombre': prompt['nombre'], 'tipo': prompt['tipo'],
            'caja': caja, 'caja_formato': 'xyxy; extremo final exclusivo; px de tesela/imagen',
            'caja_pagina': fuente.caja_pagina(caja), 'caja_sam': caja_sam,
            'area': int(np.count_nonzero(alpha)), 'area_unidad': 'px con alfa > 0',
            'area_sam': area_sam,
            'puntuacion': score, 'puntuacion_tipo': 'IoU predicha por SAM; no probabilidad ni calidad semántica del bloque',
            'politica_alfa': politica, 'sha256_png': sha256(carpeta / nombre),
            'sha256_imagen_origen': fuente.procedencia['sha256_origen'],
            'procedencia': fuente.procedencia, 'prompt': prompt,
            'toca_borde_tesela': x0 == 0 or y0 == 0 or x1 == fuente.imagen.width or y1 == fuente.imagen.height}


def ejecutar(entrada, salida, *, prompts=None, rejilla=0, dispositivo='cpu', pagina=1,
             ppp=150, tesela=1, region=None, documento=False, motor=None):
    if (prompts is not None) == bool(rejilla):
        raise ValueError('Elige JSON de indicaciones o rejilla, exclusivamente.')
    salida = Path(salida).resolve()
    if salida.exists():
        raise ValueError('La carpeta de salida ya existe; elige una nueva para no mezclar piezas.')
    fuente = abrir_fuente(entrada, pagina=pagina, ppp=ppp, tesela=tesela, region=region)
    instrucciones = validar_prompts(prompts, fuente) if prompts is not None else None
    if rejilla and not 2 <= rejilla <= 16:
        raise ValueError('Rejilla: entre 2 y 16 puntos por lado.')
    salida.parent.mkdir(parents=True, exist_ok=True)
    temporal = Path(tempfile.mkdtemp(prefix='.recortador-', dir=salida.parent))
    try:
        with exclusivo():
            motor = motor or MotorSAM(dispositivo)
            piezas = []
            try:
                motor.preparar(fuente)
                for prompt, mask, score in propuestas(motor, fuente, instrucciones, rejilla):
                    pieza = exportar_pieza(fuente, prompt, mask, score, temporal, len(piezas) + 1,
                                           documento=documento or fuente.procedencia['tipo'] == 'pdf')
                    if pieza:
                        piezas.append(pieza)
            finally:
                motor.liberar_imagen()
        resultado = {'version': 1, 'modelo': MODELO, 'dispositivo': dispositivo,
                     'mps_fallback_cpu': dispositivo == 'mps' and os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK') == '1',
                     'fuente': fuente.procedencia, 'modo': 'rejilla' if rejilla else 'indicaciones',
                     'rejilla': rejilla or None, 'piezas': piezas,
                     'nota': 'Tipos declarados por el usuario; SAM no clasifica texto, tablas o símbolos.'}
        guardar_json(temporal / 'piezas.json', resultado)
        from tablero import exportar_tablero
        exportar_tablero(resultado, temporal)
        temporal.rename(salida)
        return resultado
    except BaseException:
        shutil.rmtree(temporal)
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('imagen', type=Path)
    ap.add_argument('--salida', type=Path, required=True)
    opcion = ap.add_mutually_exclusive_group(required=True)
    opcion.add_argument('--prompts', type=Path)
    opcion.add_argument('--rejilla', type=int, metavar='N')
    ap.add_argument('--documento', action='store_true', help='bloques rectangulares para una página rasterizada')
    ap.add_argument('--dispositivo', choices=['cpu', 'mps'], default='cpu')
    ap.add_argument('--pagina', type=int, default=1)
    ap.add_argument('--ppp', type=int, default=150)
    ap.add_argument('--tesela', type=int, default=1, help='tesela PDF de hasta 2048 px; desde 1, por filas')
    ap.add_argument('--region-pagina', type=float, nargs=4, metavar=('X0','Y0','X1','Y1'))
    a = ap.parse_args()
    try:
        prompts = json.loads(a.prompts.read_text()) if a.prompts else None
        r = ejecutar(a.imagen, a.salida, prompts=prompts, rejilla=a.rejilla or 0,
                     documento=a.documento, dispositivo=a.dispositivo, pagina=a.pagina,
                     ppp=a.ppp, tesela=a.tesela, region=a.region_pagina)
        print(json.dumps({'piezas': len(r['piezas']), 'salida': str(a.salida),
                          'tesela': r['fuente']['tesela'], 'total_teselas': r['fuente']['total_teselas']}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
