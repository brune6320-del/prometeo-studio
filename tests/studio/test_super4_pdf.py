"""SUPER-4 · I1: editar en memoria no crea archivos; solo exportar crea una copia.

Se ejecuta con el Python empaquetado:
  PYTHONPATH="$PWD:$PWD/fase0" studio-desktop/resources/runtime/bin/python3 \
    -m unittest tests.studio.test_super4_pdf -v
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest

from studio.backend.session import StudioSessionManager


def _archivos(root: str) -> set[str]:
    encontrados: set[str] = set()
    for base, _dirs, files in os.walk(root):
        for nombre in files:
            encontrados.add(os.path.relpath(os.path.join(base, nombre), root))
    return encontrados


class Super4PdfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="prometeo_super4_")
        self.manager = StudioSessionManager(workspace_root=self.root, instance_id="super4-tests")
        self.session = self.manager.create_session_from_sample("case_a")
        self.sha_original = self.session.source_sha256

    def tearDown(self) -> None:
        try:
            self.manager.shutdown()
        finally:
            shutil.rmtree(self.root, ignore_errors=True)

    def _sha_original(self) -> str:
        with open(self.session.source_path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def _text_nodes(self) -> list[dict]:
        return [node for node in self.session.query_nodes(page=0) if node.get("type") == "TEXT"]

    def test_editar_diez_veces_no_crea_archivos_y_exportar_crea_uno(self):
        nodos = self._text_nodes()
        self.assertGreaterEqual(len(nodos), 5, "case_a debe tener textos para la prueba")
        antes = _archivos(self.session.session_dir)

        # Diez ediciones seguidas: cinco nodos, cada uno actualizado dos veces.
        for vuelta in range(2):
            for indice, nodo in enumerate(nodos[:5]):
                resultado = self.session.stage_edit(f"v{vuelta + 1}", node_id=nodo["id"])
                self.assertTrue(resultado.get("ok"), resultado.get("error"))
                if indice == 0:
                    previa = self.session.preflight()
                    self.assertTrue(previa.get("preflight"), previa)

        despues = _archivos(self.session.session_dir)
        self.assertEqual(antes, despues, f"editar no debe crear archivos: {despues - antes}")
        self.assertFalse(any("/staging/" in ruta for ruta in despues), "la comprobación previa debe borrar su temporal")
        self.assertEqual(
            self._sha_original(),
            self.sha_original,
        )

        self.assertEqual(len(self.session.staged_operations_public()), 5)

        exportado = self.session.verify_and_export()
        self.assertTrue(exportado.get("ok"), exportado)
        self.assertTrue(exportado.get("published"))
        self.assertEqual(len(exportado.get("output_sha256", "")), 64)

        finales = _archivos(self.session.session_dir)
        nuevas = finales - antes
        self.assertEqual(len([ruta for ruta in nuevas if ruta.endswith(".pdf")]), 1, nuevas)
        self.assertTrue(any(ruta.startswith("verified/") for ruta in nuevas), nuevas)
        self.assertEqual(
            self._sha_original(),
            self.sha_original,
            "el original conserva su SHA-256",
        )

    def test_preflight_rechaza_sin_operaciones(self):
        resultado = self.session.preflight()
        self.assertFalse(resultado.get("ok"))
        self.assertEqual(resultado.get("error_code"), "NO_STAGED_OPERATIONS")


if __name__ == "__main__":
    unittest.main()
