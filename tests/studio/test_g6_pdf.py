"""G6 · reintentos y explicación de la verificación con los ejemplos del repo.

Se ejecuta con el Python empaquetado (trae PyMuPDF, FastAPI y Tesseract):
  PYTHONPATH="$PWD:$PWD/fase0" studio-desktop/resources/runtime/bin/python3 \
    -m unittest tests.studio.test_g6_pdf -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest

from studio.backend.session import StudioSessionManager


class G6PdfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="prometeo_g6_")
        self.manager = StudioSessionManager(workspace_root=self.root, instance_id="g6-tests")

    def tearDown(self) -> None:
        try:
            self.manager.shutdown()
        finally:
            shutil.rmtree(self.root, ignore_errors=True)

    def _text_node(self, session, needle: str = "Contratado"):
        result = session.query_nodes(page=0, node_type="TEXT", with_meta=True)
        nodes = result["nodes"]
        node = next((item for item in nodes if needle.lower() in (item.get("text") or "").lower()), None)
        self.assertIsNotNone(node, f"No se encontró un nodo de texto con «{needle}»")
        return node

    def _eligible_observation(self, session):
        ocr = session.get_ocr_layer(0)
        self.assertTrue(ocr.get("ok"), ocr.get("error"))
        for observation in ocr.get("observations", []):
            safety = session.get_raster_safety(0, observation["id"])
            if safety.get("ok") and safety.get("edit_eligible"):
                return observation
        self.skipTest("La muestra escaneada no tiene observaciones elegibles para parche")

    def test_vector_retry_reuses_the_prepared_change(self):
        session = self.manager.create_session_from_sample("case_a")
        node = self._text_node(session)

        first = session.stage_edit("Contratado: Ana Ruiz", node_id=node["id"])
        self.assertTrue(first.get("ok"), first.get("error"))
        second = session.stage_edit("Contratado: Ana Ruiz (v2)", node_id=node["id"])

        self.assertTrue(second.get("ok"), second.get("error"))
        self.assertTrue(second.get("reused"))
        self.assertEqual(len(session.staged_operations_public()), 1)
        self.assertEqual(session.staged_operations_public()[0]["new_text"], "Contratado: Ana Ruiz (v2)")
        self.assertEqual(second["operation"]["op_id"], first["operation"]["op_id"])

    def test_raster_retry_reuses_the_prepared_patch(self):
        session = self.manager.create_session_from_sample("case_b_scan")
        observation = self._eligible_observation(session)

        first = session.stage_raster_edit(0, observation["id"], "CONTRATO2")
        self.assertTrue(first.get("ok"), first.get("error"))
        second = session.stage_raster_edit(0, observation["id"], "CONTRATO3")

        self.assertTrue(second.get("ok"), second.get("error"))
        self.assertTrue(second.get("reused"))
        self.assertEqual(len(session.staged_operations_public()), 1)
        staged = session.staged_operations_public()[0]
        self.assertEqual(staged["new_text"], "CONTRATO3")
        self.assertEqual(second["operation"]["op_id"], first["operation"]["op_id"])

    def test_raster_failure_explains_check_expected_and_actual(self):
        session = self.manager.create_session_from_sample("case_b_scan")
        observation = self._eligible_observation(session)
        staged = session.stage_raster_edit(0, observation["id"], "ZZZZZZZZ")
        self.assertTrue(staged.get("ok"), staged.get("error"))

        result = session.verify_and_export("g6-failure.pdf")
        verifier = result["verifier_result"]
        self.assertFalse(result["ok"])
        self.assertEqual(verifier["verdict"], "FAILED")
        self.assertTrue(verifier["verifier_executed"])

        details = verifier["details"]
        self.assertTrue(details)
        checks = details[0]["checks"]
        text_check = next(check for check in checks if check["id"] == "text_new")
        self.assertFalse(text_check["pass"])
        self.assertEqual(text_check["expected"], "ZZZZZZZZ")
        self.assertIsInstance(text_check["actual"], str)
        self.assertTrue(text_check["actual"])
        self.assertEqual(details[0]["old_text"], observation["text"])
        self.assertTrue(details[0]["observed_text"])


if __name__ == "__main__":
    unittest.main()
