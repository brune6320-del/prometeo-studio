"""Verificación integral opcional: SigLIP real, únicamente medios sintéticos."""
from __future__ import annotations

import io
import json
import os
import platform
import resource
import tempfile
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import cv2
import numpy as np
import pymupdf

from buscar import cargar_indice, duplicados, grupos, parecidos
from exportar import exportar, split_sha
from indexar import construir_indice
from medir import crear_pares_sinteticos, evaluar
from modelo import MODEL_ID, ModeloVisual, sha256_archivo


def verificar():
    inicio = time.monotonic()
    cache = Path(__file__).resolve().parent / ".cache"
    cache.mkdir(exist_ok=True)
    modelo = ModeloVisual("cpu")
    bases, consultas = crear_pares_sinteticos(n=6)
    with tempfile.TemporaryDirectory(dir=cache) as temporal:
        carpeta = Path(temporal)
        medios, piezas = carpeta / "medios", carpeta / "piezas"
        medios.mkdir()
        piezas.mkdir()
        for i, imagen in enumerate(bases):
            imagen.save(medios / f"ref-{i:02}.png")
        (medios / "copia.png").write_bytes((medios / "ref-00.png").read_bytes())
        consultas[0][0].save(piezas / "recorte.png")
        with pymupdf.open() as pdf:
            for imagen in bases[2:4]:
                pagina = pdf.new_page(width=224, height=224)
                datos = io.BytesIO()
                imagen.save(datos, format="PNG")
                pagina.insert_image(pagina.rect, stream=datos.getvalue())
            pdf.save(medios / "paginas.pdf")
        video = cv2.VideoWriter(str(medios / "muestra.mp4"),
                                cv2.VideoWriter_fourcc(*"mp4v"), 2.0, (224, 224))
        assert video.isOpened(), "No se pudo crear video sintético"
        try:
            for imagen in bases[:4]:
                video.write(cv2.cvtColor(np.asarray(imagen), cv2.COLOR_RGB2BGR))
        finally:
            video.release()
        (piezas / "piezas.json").write_text(json.dumps({"piezas": [{
            "sha256_png": sha256_archivo(piezas / "recorte.png"),
            "sha256_imagen_origen": sha256_archivo(medios / "ref-00.png")}]}))
        originales = {p: sha256_archivo(p) for p in [*medios.iterdir(), *piezas.iterdir()]}
        construir_indice(medios, carpeta / "indice", modelo, lote=1,
                         cada_segundos=1, max_fotogramas=2, recortes=piezas)
        vectores, indice = cargar_indice(carpeta / "indice")
        assert len(vectores) == 12
        consulta = modelo.codificar([consultas[3][0]], lote=1)[0]
        vecinos = parecidos(vectores, indice, consulta)
        assert len(vecinos) == 12
        posicion_positivo = next(i + 1 for i, x in enumerate(vecinos) if x["ruta"] == "ref-01.png")
        pares = duplicados(vectores, indice)
        assert any(x["clase"] == "mismo_archivo" for x in pares)
        agrupacion = grupos(vectores, indice, k=3)
        assert sum(len(x["elementos"]) for x in agrupacion) == 12
        gustos = medios / "gustos.json"
        gustos.write_text(json.dumps({"referentes": {
            sha256_archivo(medios / "ref-00.png"): 2,
            sha256_archivo(medios / "paginas.pdf"): 0.5,
            sha256_archivo(medios / "muestra.mp4"): 2}, "items": [
                {"ruta": "recortador/recorte.png", "voto": "♥"}]}))
        originales[gustos] = sha256_archivo(gustos)
        resumen = exportar(carpeta / "indice", carpeta / "dataset")
        holdout = (carpeta / "dataset" / "holdout.json").read_bytes()
        exportar(carpeta / "indice", carpeta / "dataset")
        assert holdout == (carpeta / "dataset" / "holdout.json").read_bytes()
        assert all(sha256_archivo(p) == sha for p, sha in originales.items())
        vb = modelo.codificar(bases, lote=1)
        vc = modelo.codificar([x[0] for x in consultas], lote=1)
        recall = evaluar(vb, vc, [x[1] for x in consultas], [x[2] for x in consultas])
        holdout_ids = [i for i in range(len(bases)) if split_sha(
            sha256_archivo(medios / f"ref-{i:02}.png"), 20, "prometeo-indice-v1") == "holdout"]
        seleccion = [i for i, x in enumerate(consultas) if x[1] in holdout_ids]
        assert seleccion, "El fixture debe tener orígenes holdout"
        recall_holdout = evaluar(vb, vc[seleccion], [consultas[i][1] for i in seleccion],
                                 [consultas[i][2] for i in seleccion])
        return {
            "solo_datos_sinteticos": True, "dispositivo": "cpu", "lote": 1,
            "nice": os.getpriority(os.PRIO_PROCESS, 0),
            "modelo": MODEL_ID, "sha256_pesos_recalculado": modelo.pesos_sha256,
            "tipos": dict(Counter(x["tipo"] for x in indice["items"])),
            "consulta_recorte_top1": vecinos[0]["ruta"], "coseno": vecinos[0]["similitud"],
            "consulta_recorte_positivo": "ref-01.png", "posicion_positivo": posicion_positivo,
            "duplicados_exactos_detectados": True, "grupos": len(agrupacion),
            "export_totales": resumen["totales"], "gustos_solo_lectura": True,
            "holdout_repetido_identico": True, "recall": recall,
            "recall_holdout_por_origen": recall_holdout, "origenes_holdout": holdout_ids,
            "nota_recall": "Galería de referencia fija; solo consultas de orígenes holdout. SigLIP no se entrena.",
            "segundos": round(time.monotonic() - inicio, 2),
            "rss_pico_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2, 2),
            "plataforma": platform.platform(), "python": platform.python_version(),
            "paquetes": {x: version(x) for x in ("numpy", "Pillow", "torch", "transformers",
                                                   "PyMuPDF", "opencv-python-headless")},
        }


if __name__ == "__main__":
    print(json.dumps(verificar(), ensure_ascii=False, indent=2))
