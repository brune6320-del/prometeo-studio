"""SUPER-4 · I7: una página se desarma en piezas sin ejecutar su JavaScript."""
from __future__ import annotations

import importlib
import unittest
from unittest import mock

backend_app = importlib.import_module("studio.backend.app")


HTML = """
<!doctype html><html><head>
<title>Taller de papel</title>
<meta property="og:title" content="Taller de papel">
<meta property="og:description" content="Un cuaderno de pruebas">
<link rel="stylesheet" href="https://fonts.example/display.css">
<style>
  body { font-family: Georgia, serif; color: #112233; background: #faf7f2; }
  h1 { font-family: 'Helvetica Neue', sans-serif; color: #c0392b; }
</style>
</head><body>
<h1>El pliegue como medida</h1>
<h2>Notas de taller</h2>
<p>Una hoja doblada cambia la escala de lo que contiene.</p>
<img src="/media/pliegue.png" alt="Una hoja doblada">
<img src="https://cdn.example/otra.jpg" alt="Otra imagen">
</body></html>
"""


class DesarmarParserTests(unittest.TestCase):
    def test_extrae_titulares_textos_colores_y_fuentes(self):
        parser = backend_app._DesarmarParser()
        parser.feed(HTML)
        self.assertEqual(parser.title, "Taller de papel")
        self.assertEqual(parser.headings[0]["text"], "El pliegue como medida")
        self.assertIn("Una hoja doblada", parser.paragraphs[0])
        self.assertEqual(len(parser.images), 2)
        self.assertIn("#112233", backend_app._colores_de_estilos(parser.styles))
        self.assertIn("#faf7f2", backend_app._colores_de_estilos(parser.styles))
        fuentes = backend_app._fuentes_de_estilos(parser.styles)
        self.assertTrue(any("Georgia" in fuente for fuente in fuentes), fuentes)

    def test_la_captura_minima_no_inventa_una_foto(self):
        captura = backend_app._captura_svg("Taller de papel", "example.com")
        self.assertTrue(captura.startswith("data:image/svg+xml;base64,"))

    def test_el_endpoint_devuelve_piezas_con_su_fuente(self):
        with mock.patch.object(backend_app, "_robots_permite", return_value=True), \
             mock.patch.object(backend_app, "_descargar_html", return_value={"url": "https://example.com/diseno", "html": HTML}), \
             mock.patch.object(backend_app, "_descargar_imagen_pagina", return_value={"url": "https://example.com/media/pliegue.png", "mime": "image/png", "bytes": b"png"}):
            respuesta = backend_app.desarmar_referente(backend_app.DesarmarRequest(url="https://example.com/diseno"))
        self.assertTrue(respuesta["ok"], respuesta)
        self.assertEqual(respuesta["titulo"], "Taller de papel")
        self.assertTrue(respuesta["captura"].startswith("data:"))
        clases = {pieza["kind"] for pieza in respuesta["piezas"]}
        self.assertTrue({"image", "text", "color", "font"}.issubset(clases), clases)
        for pieza in respuesta["piezas"]:
            self.assertEqual(pieza["fuente"], "https://example.com/diseno")


if __name__ == "__main__":
    unittest.main()
