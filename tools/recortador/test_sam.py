"""Integración con SAM real y pesos locales: falla si faltan; nunca descarga."""
import base64
import json
import importlib.metadata
import math
import os
from pathlib import Path
import resource
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from recortador import ROOT, MODELO, MotorSAM, abrir_fuente, ejecutar, sha256
from sinteticos import forma, documento


class TestSAMReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / '.tmp').mkdir(exist_ok=True)
        cls.red = patch.object(socket.socket, 'connect', side_effect=AssertionError('La prueba no permite red'))
        cls.red.start()
        cls.addClassCleanup(cls.red.stop)
        cls.inicio = time.monotonic()
        cls.dispositivo = os.environ.get('RECORTADOR_DISPOSITIVO', 'cpu')
        cls.motor = MotorSAM(cls.dispositivo)
        cls.evidencia = []
        cls.hubo_fallos = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='test-sam-', dir=ROOT / '.tmp')
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def tearDown(self):
        resultado = self._outcome.result
        type(self).hubo_fallos |= bool(resultado.errors or resultado.failures)

    def comprobar_exportacion(self, resultado, salida, origen):
        self.assertEqual(resultado['fuente']['sha256_origen'], sha256(origen))
        board = json.loads((salida/'tablero.json').read_text())
        self.assertEqual(board['format'], 'prometeo-studio-board')
        cards = board['board']['cards']
        self.assertEqual(cards[0]['datos']['vista'], 'mesa')
        self.assertEqual(cards[0]['datos']['hijos'], [p['id'] for p in resultado['piezas']])
        for p, card in zip(resultado['piezas'], cards[1:]):
            with Image.open(salida/p['archivo']) as im:
                self.assertEqual(im.mode, 'RGBA')
                self.assertEqual(im.size, (p['caja'][2]-p['caja'][0], p['caja'][3]-p['caja'][1]))
                self.assertEqual(np.count_nonzero(np.array(im)[:,:,3]), p['area'])
                self.assertEqual(im.getbbox(), (0,0,im.width,im.height))
            self.assertEqual(sha256(salida/p['archivo']), p['sha256_png'])
            self.assertEqual(base64.b64decode(card['media']['dataUrl'].split(',')[1]), (salida/p['archivo']).read_bytes())
        self.assertEqual(json.loads((salida/'piezas.json').read_text()), resultado)

    def test_tres_imagenes_area_menos_cinco_por_ciento(self):
        for tipo in ('rectangulo', 'circulo', 'triangulo'):
            with self.subTest(tipo=tipo):
                path, verdad, prompts = forma(self.raiz, tipo)
                salida = self.raiz/('salida-'+tipo)
                r = ejecutar(path,salida,prompts=prompts,motor=self.motor,dispositivo=self.dispositivo)
                self.assertEqual(len(r['piezas']),1)
                p=r['piezas'][0]
                real=int(verdad.sum()); error=abs(p['area']-real)/real
                # IoU adicional: un área igual en una ubicación errónea tampoco pasa.
                pred=np.zeros_like(verdad)
                x0,y0,x1,y1=p['caja']
                with Image.open(salida/p['archivo']) as im:
                    pred[y0:y1,x0:x1]=np.array(im)[:,:,3]>0
                iou=float(np.count_nonzero(pred & verdad)/np.count_nonzero(pred | verdad))
                self.evidencia.append({'caso':tipo,'area_real':real,'area_exportada':p['area'],
                                      'error_relativo':error,'iou':iou,'puntuacion':p['puntuacion']})
                self.assertLessEqual(error,.05)
                self.assertGreaterEqual(iou,.95)
                self.comprobar_exportacion(r,salida,path)

    def test_pagina_documento_tres_bloques(self):
        path,prompts=documento(self.raiz)
        salida=self.raiz/'salida-doc'
        r=ejecutar(path,salida,prompts=prompts,ppp=150,motor=self.motor,dispositivo=self.dispositivo)
        self.assertEqual(len(r['piezas']),3)
        for p,solicitud in zip(r['piezas'],prompts['piezas']):
            caja=solicitud['caja']; scale=150/72
            real=(math.ceil(caja[2]*scale)-math.floor(caja[0]*scale))*(math.ceil(caja[3]*scale)-math.floor(caja[1]*scale))
            error=abs(p['area']-real)/real
            self.evidencia.append({'caso':'documento-'+p['nombre'],'area_real_bloque':real,
                                  'area_exportada':p['area'],'error_relativo':error,
                                  'politica':p['politica_alfa'],'puntuacion_sam':p['puntuacion']})
            self.assertLessEqual(error,.05)
            self.assertEqual(p['politica_alfa'],'bloque_caja_usuario')
            for original,exportada in zip(caja,p['caja_pagina']):
                self.assertLessEqual(abs(original-exportada),72/150+.000001)
        self.comprobar_exportacion(r,salida,path)

    def test_rejilla_real_propone_rectangulo(self):
        path,verdad,_=forma(self.raiz,'rectangulo')
        salida=self.raiz/'rejilla'
        r=ejecutar(path,salida,rejilla=4,motor=self.motor,dispositivo=self.dispositivo)
        self.assertGreaterEqual(len(r['piezas']),1)
        for pieza in r['piezas']:
            self.assertLessEqual(abs(pieza['area']-int(verdad.sum()))/int(verdad.sum()),.05)
        cercano=min(r['piezas'],key=lambda p:abs(p['area']-int(verdad.sum())))
        error=abs(cercano['area']-int(verdad.sum()))/int(verdad.sum())
        self.assertLessEqual(error,.05)
        self.evidencia.append({'caso':'rejilla-4x4','propuestas':len(r['piezas']),
                              'error_area_rectangulo':error})

    @classmethod
    def tearDownClass(cls):
        informe={'modelo':MODELO['modelo'],'pesos_sha256':MODELO['sha256'],
                 'pruebas_correctas':not cls.hubo_fallos,
                 'codigo_sam_commit':MODELO['codigo_commit'],
                 'versiones':{p:importlib.metadata.version(p) for p in ('torch','torchvision','numpy','Pillow','PyMuPDF')},
                 'dispositivo':cls.dispositivo,'red':'socket.connect bloqueado durante carga e inferencia',
                 'mps_fallback_cpu':cls.dispositivo == 'mps' and os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK') == '1',
                 'casos':cls.evidencia,'segundos':time.monotonic()-cls.inicio,
                 'pico_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 'nota_documento':'Área del bloque declarado; no certifica detección semántica SAM.'}
        (ROOT/f'evidencia-{cls.dispositivo}.json').write_text(json.dumps(informe,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    unittest.main(verbosity=2)
