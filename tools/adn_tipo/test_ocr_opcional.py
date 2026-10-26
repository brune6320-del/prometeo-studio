"""El camino A no depende del motor OCR; B falla explícitamente si falta."""
import unittest
from unittest.mock import patch


class OCROpcionalTest(unittest.TestCase):
    def test_falta_motor_no_se_presenta_como_resultado(self):
        from inferir import inferir
        with patch.dict('sys.modules', {'pytesseract': None}):
            with self.assertRaisesRegex(RuntimeError, 'OCR no ejecutado'):
                inferir('no-abrir.png', 'no-crear', 'catalogo', dpi=144, propio=True)


if __name__ == '__main__':
    unittest.main()
