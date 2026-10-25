"""Pruebas únicamente con imágenes y vectores sintéticos."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from buscar import cargar_indice, duplicados, grupos, parecidos
from exportar import exportar
from indexar import construir_indice
from medir import crear_pares_sinteticos, evaluar
from modelo import sha256_archivo


class CodificadorFalso:
    pesos_sha256 = "sintetico"

    def codificar(self, imagenes, lote=2):
        vectores = []
        for imagen in imagenes:
            rgb = np.asarray(imagen, dtype=np.float32)
            vectores.append(np.r_[rgb.mean(axis=(0, 1)), rgb.std(axis=(0, 1))])
        return np.asarray(vectores, dtype=np.float32)


class IndiceSinteticoTest(unittest.TestCase):
    def test_pdf_y_recortador_sinteticos(self):
        import pymupdf
        from unittest.mock import patch
        cache = Path(__file__).parent / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporal:
            base = Path(temporal)
            origen, recortes = base / "medios", base / "piezas"
            origen.mkdir()
            recortes.mkdir()
            pdf = origen / "referentes.pdf"
            with pymupdf.open() as documento:
                for color in ((1, 0, 0), (0, 0, 1)):
                    pagina = documento.new_page(width=8000, height=4000)
                    pagina.draw_rect(pagina.rect, fill=color)
                documento.save(pdf)
            sha_pdf = sha256_archivo(pdf)
            Image.new("RGB", (32, 32), "green").save(recortes / "pieza.png")
            destino = origen / "indice"
            destino.mkdir()
            Image.new("RGB", (32, 32), "yellow").save(destino / "no-indexar.png")
            from indexar import _paginas_pdf
            with patch("indexar._paginas_pdf", wraps=_paginas_pdf) as render:
                indice = construir_indice(origen, destino, CodificadorFalso(),
                                          pdf_lado_max=512, recortes=recortes, lote=1)
                render.assert_called_once_with(pdf, 512)
            self.assertEqual(len(indice["items"]), 3)
            self.assertEqual([x["pagina"] for x in indice["items"][:2]], [1, 2])
            self.assertEqual({x["sha256_archivo"] for x in indice["items"][:2]}, {sha_pdf})
            self.assertEqual(indice["items"][2]["ruta"], "recortador/pieza.png")
            self.assertEqual(indice["items"][2]["ruta_fuente"], "pieza.png")
            self.assertEqual(sha256_archivo(pdf), sha_pdf)
            self.assertEqual(cargar_indice(destino)[0].shape[0], 3)
            paginas = list(_paginas_pdf(pdf, 512))
            self.assertTrue(all(max(im.size) <= 513 for im, _ in paginas))
            for imagen, _ in paginas:
                imagen.close()
            # Una raíz de recortes ya incluida no debe duplicarse.
            segundo = construir_indice(base, base / "otro-indice", CodificadorFalso(),
                                       recortes=recortes)
            self.assertEqual(sum(x["ruta"] == "piezas/pieza.png" for x in segundo["items"]), 1)

    def test_fotogramas_video_sintetico(self):
        try:
            import cv2
        except ImportError:
            self.skipTest("opencv-python-headless opcional no instalado")
        cache = Path(__file__).parent / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporal:
            base = Path(temporal)
            video = base / "muestra.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 2.0, (32, 32))
            self.assertTrue(writer.isOpened())
            try:
                for color in ((0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0)):
                    writer.write(np.full((32, 32, 3), color, dtype=np.uint8))
            finally:
                writer.release()
            indice = construir_indice(base, base / "indice", CodificadorFalso(),
                                     cada_segundos=1, max_fotogramas=2)
            self.assertEqual(len(indice["items"]), 2)
            self.assertTrue(all(x["tipo"] == "fotograma" and x["ruta"] == "muestra.mp4"
                                for x in indice["items"]))
            self.assertEqual({x["fotograma"] for x in indice["items"]}, {0, 2})
            self.assertEqual(len({x["sha256_archivo"] for x in indice["items"]}), 1)

    def test_indexar_buscar_y_duplicados(self):
        cache = Path(__file__).parent / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporal:
            raiz = Path(temporal) / "imagenes"
            raiz.mkdir()
            Image.new("RGB", (24, 24), (220, 20, 20)).save(raiz / "roja.png")
            (raiz / "copia.png").write_bytes((raiz / "roja.png").read_bytes())
            Image.new("RGB", (24, 24), (20, 20, 220)).save(raiz / "azul.png")
            destino = Path(temporal) / "salida"
            documento = construir_indice(raiz, destino, CodificadorFalso())
            matriz, indice = cargar_indice(destino)
            self.assertEqual(matriz.shape[0], 3)
            self.assertEqual([x["fila"] for x in documento["items"]], [0, 1, 2])
            with np.load(destino / "vectores.npz", allow_pickle=False) as datos:
                self.assertEqual(datos["sha256_archivos"].tolist(),
                                 [x["sha256_archivo"] for x in indice["items"]])
            vecinos = parecidos(matriz, indice, matriz[0], n=12, excluir_fila=0)
            self.assertEqual(len(vecinos), 2)
            self.assertTrue(any(x["ruta"] == "roja.png" for x in vecinos))
            self.assertEqual(duplicados(matriz, indice)[0]["clase"], "mismo_archivo")
            self.assertEqual(sum(len(x["elementos"]) for x in grupos(matriz, indice, k=2)), 3)
            with (destino / "indice.json").open(encoding="utf-8") as handle:
                dañado = json.load(handle)
            dañado["items"][0]["sha256_archivo"] = "0" * 64
            (destino / "indice.json").write_text(json.dumps(dañado), encoding="utf-8")
            with self.assertRaises(ValueError):
                cargar_indice(destino)

    def test_recortes_giros_color_y_recall(self):
        bases, consultas = crear_pares_sinteticos(n=6, lado=128)
        self.assertEqual(len(bases), 6)
        self.assertEqual(len(consultas), 18)
        self.assertEqual({x[2] for x in consultas}, {"recorte", "giro", "color"})
        self.assertTrue(all(x[0].tobytes() != bases[x[1]].tobytes() for x in consultas))
        base = np.eye(6, dtype=np.float32)
        consulta = np.repeat(base, 3, axis=0)
        tipos = [x[2] for x in consultas]
        positivos = [x[1] for x in consultas]
        resultado = evaluar(base, consulta, positivos, tipos)
        self.assertEqual(resultado["global"]["recall@1"], 1.0)
        self.assertEqual(resultado["global"]["recall@5"], 1.0)
        consulta[0] = base[1]
        resultado = evaluar(base, consulta, positivos, tipos)
        self.assertLess(resultado["global"]["recall@1"], 1.0)
        self.assertEqual(resultado["global"]["recall@5"], 1.0)

    def test_exportar_gustos_solo_lectura_y_holdout_congelado(self):
        cache = Path(__file__).parent / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporal:
            base = Path(temporal)
            origen = base / "origen"
            origen.mkdir()
            Image.new("RGB", (24, 24), (200, 20, 20)).save(origen / "a.png")
            (origen / "a-copia.png").write_bytes((origen / "a.png").read_bytes())
            Image.new("RGB", (24, 24), (20, 20, 200)).save(origen / "b.png")
            indice_dir = base / "indice"
            indice = construir_indice(origen, indice_dir, CodificadorFalso())
            sha_a = next(x["sha256_archivo"] for x in indice["items"] if x["ruta"] == "a.png")
            gustos = base / "gustos.json"
            contenido = json.dumps({"version": 1, "referentes": {sha_a: 2, "sin-vinculo": 0.2},
                                   "items": [{"ruta": "b.png", "voto": "✕"}]})
            gustos.write_text(contenido, encoding="utf-8")
            salida = base / "dataset"
            primero = exportar(indice_dir, salida, gustos, porcentaje=20)
            congelado = (salida / "holdout.json").read_bytes()
            segundo = exportar(indice_dir, salida, gustos, porcentaje=20)
            self.assertEqual(congelado, (salida / "holdout.json").read_bytes())
            self.assertEqual(gustos.read_text(encoding="utf-8"), contenido)
            self.assertEqual(primero["totales"], segundo["totales"])
            self.assertEqual(primero["gustos_sin_vincular"], ["sin-vinculo"])
            registros = []
            for nombre in ("train", "holdout"):
                registros.extend(json.loads(line) for line in (salida / f"{nombre}.jsonl").read_text().splitlines())
            self.assertEqual(len(registros), 3)
            self.assertEqual({x["etiqueta"] for x in registros}, {"♥", "✕"})
            self.assertEqual(len({x["split"] for x in registros if x["sha256_archivo"] == sha_a}), 1)
            with self.assertRaises(ValueError):
                exportar(indice_dir, salida, gustos, porcentaje=25)


if __name__ == "__main__":
    unittest.main()
