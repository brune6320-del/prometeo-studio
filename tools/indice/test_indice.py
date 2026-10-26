"""Pruebas únicamente con imágenes y vectores sintéticos."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from buscar import cargar_indice, duplicados, grupos, parecidos
from exportar import exportar, origenes_indice, split_sha
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
            (recortes / "piezas.json").write_text(json.dumps({"piezas": [{
                "sha256_png": sha256_archivo(recortes / "pieza.png"),
                "sha256_imagen_origen": sha_pdf}]}))
            gustos = origen / "gustos.json"
            gustos.write_text(json.dumps({"referentes": {sha_pdf: 2}, "items": [
                {"ruta": "recortador/pieza.png", "voto": "♥"}]}))
            resumen = exportar(destino, base / "dataset")
            registros = []
            for nombre in ("train", "holdout"):
                registros.extend(json.loads(x) for x in
                                 (base / "dataset" / f"{nombre}.jsonl").read_text().splitlines())
            self.assertEqual({x["pagina"] for x in registros if x["tipo"] == "pagina_pdf"}, {1, 2})
            self.assertEqual(len({x["split"] for x in registros if x["tipo"] == "pagina_pdf"}), 1)
            self.assertEqual(resumen["raices_medios"]["recortador"], str(recortes))
            # Una raíz de recortes ya incluida no debe duplicarse.
            segundo = construir_indice(base, base / "otro-indice", CodificadorFalso(),
                                       recortes=recortes)
            self.assertEqual(sum(x["ruta"] == "piezas/pieza.png" for x in segundo["items"]), 1)

    def test_derivados_distintos_comparten_origen_y_rechaza_legacy(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporal:
            base = Path(temporal)
            sha = "a" * 64
            otros = [f"{i:064x}" for i in range(100)]
            hijos = [next(h for h in otros if split_sha(h, 20, "s") == t)
                     for t in ("train", "holdout")]
            items = [{"id": h, "ruta": f"{i}.png", "sha256_archivo": h,
                      "sha256_visual": h, "sha256_origen": sha, "tipo": tipo}
                     for i, (h, tipo) in enumerate(zip(hijos, ("pagina_pdf", "fotograma")))]
            items.append(dict(items[0], id="recorte", ruta="recorte.png", origen="recortador"))
            indice = {"raiz": str(base), "items": items}
            (base / "indice.json").write_text("{}")
            (base / "vectores.npz").write_bytes(b"test")
            with patch("exportar.cargar_indice", return_value=(None, indice)):
                exportar(base, base / "out", sal="s")
                filas = [json.loads(x) for x in (base / "out/sin_etiqueta.jsonl").read_text().splitlines()]
                self.assertEqual(len({x["split"] for x in filas}), 1)
                self.assertEqual({x["sha256_origen"] for x in filas}, {sha})
                h = base / "out/holdout.json"
                datos = json.loads(h.read_text()); datos["version"] = 1
                h.write_text(json.dumps(datos))
                with self.assertRaisesRegex(ValueError, "otra política"):
                    exportar(base, base / "out", sal="s")
            del items[-1]["sha256_origen"]
            items[-1]["sha256_archivo"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "sin procedencia"):
                origenes_indice(indice)

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

    def test_recall_rechaza_nulos_y_no_modifica_entradas(self):
        bases = np.eye(6, dtype=np.float32) * 3
        consultas = bases.copy() * 2
        copia = consultas.copy()
        evaluar(bases, consultas, list(range(6)), ["giro"] * 6)
        np.testing.assert_array_equal(consultas, copia)
        np.testing.assert_array_equal(bases, np.eye(6, dtype=np.float32) * 3)
        consultas[0] = 0
        with self.assertRaises(ValueError):
            evaluar(bases, consultas, list(range(6)), ["giro"] * 6)

    def test_integridad_vectores_y_casi_duplicados(self):
        cache = Path(__file__).parent / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporal:
            base = Path(temporal)
            origen = base / "medios"
            origen.mkdir()
            for nombre, color in (("a.png", (200, 20, 20)), ("b.png", (198, 20, 20)),
                                  ("c.png", (20, 20, 200))):
                Image.new("RGB", (32, 32), color).save(origen / nombre)
            destino = base / "indice"
            construir_indice(origen, destino, CodificadorFalso(), recortes=None)
            vectores, indice = cargar_indice(destino)
            pares = duplicados(vectores, indice)
            self.assertEqual(len(pares), 1)
            self.assertEqual(pares[0]["clase"], "casi_exacto")
            with np.load(destino / "vectores.npz", allow_pickle=False) as npz:
                contenido = {k: npz[k].copy() for k in npz.files}
            contenido["vectores"][0] = vectores[2]
            np.savez_compressed(destino / "vectores.npz", **contenido)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                cargar_indice(destino)
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
            # También se validan asignaciones de fuentes que ya no están en el índice.
            congelado_path = salida / "holdout.json"
            corrupto = json.loads(congelado_path.read_text())
            corrupto["asignaciones"]["0" * 64] = "alterado"
            congelado_path.write_text(json.dumps(corrupto))
            with self.assertRaises(ValueError):
                exportar(indice_dir, salida, gustos)

    def test_exportar_protege_gustos_y_funciona_sin_etiquetas(self):
        cache = Path(__file__).parent / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporal:
            base = Path(temporal)
            origen = base / "origen"
            origen.mkdir()
            Image.new("RGB", (24, 24), "red").save(origen / "a.png")
            indice_dir = base / "indice"
            construir_indice(origen, indice_dir, CodificadorFalso(), recortes=None)
            salida = base / "dataset"
            resumen = exportar(indice_dir, salida)
            self.assertEqual(resumen["totales"], {"train": 0, "holdout": 0, "sin_etiqueta": 1})
            # El nombre del archivo no autoriza a escribir sobre una entrada de gustos.
            gustos = salida / "train.jsonl"
            contenido = '{"items": [{"ruta": "a.png", "voto": "♥"}]}'
            gustos.write_text(contenido)
            with self.assertRaises(ValueError):
                exportar(indice_dir, salida, gustos)
            self.assertEqual(gustos.read_text(), contenido)


if __name__ == "__main__":
    unittest.main()
