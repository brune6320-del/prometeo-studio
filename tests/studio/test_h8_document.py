"""H8 · contrato de documento: tipografía verificada, capa de anotación y páginas.

Se ejecuta con el Python empaquetado:
  PYTHONPATH="$PWD:$PWD/fase0" studio-desktop/resources/runtime/bin/python3 \
    -m unittest tests.studio.test_h8_document -v
"""
from __future__ import annotations

import base64
import hashlib
import os
import shutil
import tempfile
import unittest

import pymupdf

from studio.backend.session import StudioSessionManager


def sha(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class H8DocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="prometeo_h8_")
        self.manager = StudioSessionManager(workspace_root=self.root, instance_id="h8-tests")

    def tearDown(self) -> None:
        try:
            self.manager.shutdown()
        finally:
            shutil.rmtree(self.root, ignore_errors=True)

    def _session(self):
        return self.manager.create_session_from_sample("case_a")

    def _node(self, session, needle: str = "Contratado"):
        result = session.query_nodes(page=0, node_type="TEXT", with_meta=True)
        node = next((item for item in result["nodes"] if needle.lower() in (item.get("text") or "").lower()), None)
        self.assertIsNotNone(node, f"No hay texto con «{needle}»")
        return node

    def test_typography_changes_one_span_and_leaves_the_others_identical(self):
        session = self._session()
        node = self._node(session)
        original_sha = sha(session.source_path)
        before = [session._span_signature(span) for span in session._spans(pymupdf.open(session.working_copy_path)[0])]

        result = session.typography_edit(node_id=node["id"], new_text="Contratado: Ana", font_size_pt=node.get("font_size") or 11)
        self.assertTrue(result.get("ok"), result)
        self.assertTrue(result.get("others_unchanged"))
        self.assertTrue(os.path.isfile(os.path.join(session.session_dir, "advanced", result["token"])))
        self.assertEqual(sha(session.source_path), original_sha, "El original cambió")

        with pymupdf.open(os.path.join(session.session_dir, "advanced", result["token"])) as salida:
            after = [session._span_signature(span) for span in session._spans(salida[0])]
        bbox = result["target_span"]["bbox"]
        rect = pymupdf.Rect(bbox[0] - 3, bbox[1] - 3, bbox[2] + 3, bbox[3] + 3)
        def fuera_del_objetivo(span):
            if span[1].strip() == result["target_span"]["new_text"] and rect.contains(pymupdf.Rect(span[0])):
                return False
            return True
        antes_otros = [span for span in before if span[1].strip() != node["text"]]
        despues_otros = [span for span in after if fuera_del_objetivo(span)]
        self.assertEqual(sorted(antes_otros), sorted(despues_otros), "Otros spans de texto cambiaron")

    def test_typography_refuses_when_it_does_not_fit(self):
        session = self._session()
        node = self._node(session)
        result = session.typography_edit(node_id=node["id"], new_text="Contratado: Ana Ruiz de la Vega y Asociados S. L.", font_size_pt=20)
        self.assertFalse(result.get("ok"))
        self.assertIn(result.get("code"), {"TYPOGRAPHY_DOES_NOT_FIT", "TYPOGRAPHY_TOO_TALL"})
        self.assertIn("reason", result)
        self.assertFalse(any(name.startswith("tipografia_") for name in session.advanced_outputs))

    def test_annotation_layer_and_organize_pages_make_new_files(self):
        session = self._session()
        original_sha = sha(session.source_path)
        text = session.annotate_document(page_number=1, kind="text", text="Nota de Prometeo", x=72, y=72, width=200, height=40)
        self.assertTrue(text.get("ok"), text)
        self.assertEqual(text.get("layer"), "Prometeo · anotaciones")
        image = session.annotate_document(
            page_number=1,
            kind="image",
            image_data_url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
            x=300,
            y=80,
            width=80,
            height=80,
        )
        self.assertTrue(image.get("ok"), image)
        with pymupdf.open(os.path.join(session.session_dir, "advanced", image["token"])) as doc:
            self.assertGreaterEqual(doc.page_count, 1)
            self.assertIn("Prometeo", doc.get_ocgs().__str__())
            pages = doc.page_count

        organizado = session.organize_pages(order=list(range(pages, 0, -1)), rotate=[{"page": 1, "degrees": 90}])
        self.assertTrue(organizado.get("ok"), organizado)
        self.assertTrue(organizado.get("sha256"))
        self.assertEqual(sha(session.source_path), original_sha, "El original cambió")

        with open(session.source_path, "rb") as handle:
            data_url = "data:application/pdf;base64," + base64.b64encode(handle.read()).decode("ascii")
        unido = session.organize_pages(merge=[data_url], order=None)
        self.assertTrue(unido.get("ok"), unido)
        with pymupdf.open(os.path.join(session.session_dir, "advanced", unido["token"])) as doc:
            self.assertEqual(doc.page_count, pages * 2)


if __name__ == "__main__":
    unittest.main()
