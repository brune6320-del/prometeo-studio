"""Validación de implementación v3; fixtures artificiales, nunca examen."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from comun import guardar, familia_sha, sha256
from protocolo_v3 import Parada, dividir
from entrenar_v3 import entrenar
from modelo import cargar_pesos


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def filas():
    return [dict(familia='Lato', familia_sha256=familia_sha('Lato'), fuente_sha256=sha('font'),
                 sha256=sha(str(i)), texto=chr(65+i//2), split='train', dpi=96,
                 tinta_lab=[30., -10., 20.], tamano_pt=18.) for i in range(10)]


class V3Test(unittest.TestCase):
    def test_grupo_fuente_caracter_y_orden_independiente(self):
        rows = filas(); split = dividir(rows, 'sintetico')
        a = {rows[i]['texto'] for i in split['train']}
        b = {rows[i]['texto'] for i in split['validacion']}
        self.assertFalse(a & b)
        rev = list(reversed(rows)); rs = dividir(rev, 'sintetico')
        self.assertEqual(b, {rev[i]['texto'] for i in rs['validacion']})

    def test_documento_completo_no_cruza_particion(self):
        rows = filas()
        for i, r in enumerate(rows): r['sha256_origen'] = sha('doc'+str(i//2))
        s = dividir(rows, 'nativo_train')
        self.assertFalse({rows[i]['sha256_origen'] for i in s['train']} &
                         {rows[i]['sha256_origen'] for i in s['validacion']})

    def test_no_reubica_grupos_si_falta_clase(self):
        rows = filas()
        for i, r in enumerate(rows):
            r['sha256_origen'] = sha(str(i//2)); r['familia'] = str(i//2)
        with self.assertRaisesRegex(ValueError, 'Todas las familias'):
            dividir(rows, 'nativo_train')

    def test_no_acepta_copia_cruzada(self):
        rows = filas(); s = dividir(rows, 'sintetico')
        rows[s['train'][0]]['sha256'] = rows[s['validacion'][0]]['sha256']
        with self.assertRaisesRegex(ValueError, 'Imagen idéntica'):
            dividir(rows, 'sintetico')

    def test_parada_empate_y_no_finito(self):
        p = Parada()
        self.assertEqual(p.observar(1, 1.), (True, False))
        for i in range(2, 26): self.assertEqual(p.observar(i, 1.), (False, False))
        self.assertEqual(p.observar(26, 1.), (False, True))
        self.assertEqual(p.epoca_mejor, 1)
        with self.assertRaises(ValueError): p.observar(27, float('nan'))

    def test_cpu_no_admite_entrenamiento_completo(self):
        with self.assertRaisesRegex(ValueError, 'CPU solo'):
            entrenar('no-leer', 'no-crear')

    def test_humo_guarda_generacion_y_no_abre_holdout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); rows = filas()
            for i, r in enumerate(rows):
                a = np.full((64,64,3), 255, np.uint8)
                a[15:45, 15:25+i] = [20+i, 40, 30]
                path = root/f'{i}.png'; Image.fromarray(a).save(path)
                r.update(archivo=path.name, sha256=sha256(path))
            guardar(root/'train.json', rows)
            guardar(root/'manifest.json', dict(dominio='sintetico', train_sha256=sha256(root/'train.json'),
                holdout_sha256='a'*64))
            # Deliberadamente no existe holdout.json ni catálogo/examen.
            result = entrenar(root, root/'humo', humo=True)
            self.assertEqual(result['estado'], 'HUMO_NO_EVIDENCIA')
            self.assertFalse(result['promocion'])
            self.assertEqual(result['epocas'], 1)
            self.assertEqual(result['sha256_pesos'], sha256(root/'humo/epoca-0001/pesos.pt'))
            self.assertTrue((root/'humo/epoca-0001/predicciones.json').exists())
            net, ck = cargar_pesos(root/'humo/pesos.pt')
            self.assertEqual(ck['protocolo'], 'v3')
            with self.assertRaisesRegex(ValueError, 'sobrescribir'):
                entrenar(root, root/'humo', humo=True)


if __name__ == '__main__':
    unittest.main()
