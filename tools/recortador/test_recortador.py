"""Pruebas de contrato, recursos, PDF y HTTP; no descargan ni simulan precisión SAM."""
import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import numpy as np
from PIL import Image
import pymupdf

from recortador import (ROOT, Fuente, MotorSAM, abrir_fuente, bbox, ejecutar, exclusivo,
                         exportar_pieza, propuestas, validar_prompts)
from servidor import Servidor
from sinteticos import documento, forma


class TestContrato(unittest.TestCase):
    def setUp(self):
        (ROOT/'.tmp').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='contrato-',dir=ROOT/'.tmp')
        self.addCleanup(self.tmp.cleanup)
        self.raiz=Path(self.tmp.name)
        self.path,self.mask,self.prompts=forma(self.raiz,'rectangulo')
        self.fuente=abrir_fuente(self.path)

    def test_imagen_grande_se_rechaza(self):
        path=self.raiz/'grande.png'
        Image.new('RGB',(2049,3)).save(path)
        with self.assertRaisesRegex(ValueError,'2048'):
            abrir_fuente(path)

    def test_coordenadas_y_etiquetas_invalidas(self):
        for pieza in ({'caja':[10,10,5,20]}, {'caja':[0,0,513,512]},
                      {'puntos':[[512,0]]}, {'puntos':[[10,10]],'etiquetas':[2]},
                      {'puntos':[[10,10]],'etiquetas':[0]}, {'caja':[0,0,float('nan'),20]},
                      {'puntos':None}, {'tipo':[]}, {'puntos':[[1,1]],'etiquetas':None}, {}):
            with self.subTest(pieza=pieza),self.assertRaises(ValueError):
                validar_prompts({'piezas':[pieza]},self.fuente)
        with self.assertRaisesRegex(ValueError,'solo es válido'):
            validar_prompts({**self.prompts,'coordenadas':'pagina_pt'},self.fuente)

    def test_peso_incorrecto_no_se_carga(self):
        path=self.raiz/'falso.pt';path.write_bytes(b'NO SON PESOS')
        with self.assertRaisesRegex(ValueError,'SHA256'):
            MotorSAM(pesos=path)

    def test_bloqueo_doble_inferencia(self):
        with exclusivo():
            with self.assertRaisesRegex(ValueError,'inferencia activa'):
                with exclusivo():
                    self.fail('Entró una segunda inferencia')

    def test_alfa_original_y_area_sam_distintas(self):
        rgba=np.zeros((6,8,4),dtype=np.uint8);rgba[:,:,:3]=100;rgba[1:5,2:7,3]=120
        fuente=Fuente(Image.fromarray(rgba),{'tipo':'imagen','sha256_origen':'sintetico'})
        mask=np.ones((6,8),dtype=bool)
        p=exportar_pieza(fuente,{'caja':None,'nombre':'prueba','tipo':'objeto'},mask,.8,self.raiz,1)
        self.assertEqual(p['caja'],[2,1,7,5]);self.assertEqual(p['area'],20);self.assertEqual(p['area_sam'],48)
        with Image.open(self.raiz/p['archivo']) as im:
            self.assertTrue(np.all(np.array(im)[:,:,3]==120))

    def test_mascara_vacia_no_inventa_pieza(self):
        self.assertIsNone(bbox(np.zeros((3,3),dtype=bool)))
        self.assertIsNone(exportar_pieza(self.fuente,{},np.zeros((512,512),dtype=bool),.1,self.raiz,1))

    def test_documento_conserva_bloque_y_area_sam_real(self):
        mask=np.zeros((512,512),dtype=bool);mask[20:25,30:35]=True
        p=exportar_pieza(self.fuente,{'caja':[10,10,100,100],'nombre':'bloque','tipo':'texto'},
                         mask,.9,self.raiz,1,documento=True)
        self.assertEqual(p['area'],8100);self.assertEqual(p['area_sam'],25)
        self.assertEqual(p['caja_sam'],[30,20,35,25])

    def test_rejilla_filtra_repeticiones_y_baja_puntuacion(self):
        class Motor:
            def predecir(_self,p):
                return self.mask.copy(),.9
        propuestas_lista=list(propuestas(Motor(),self.fuente,rejilla=4))
        self.assertEqual(len(propuestas_lista),1)
        class Bajo:
            def predecir(_self,p):
                return self.mask.copy(),.2
        self.assertEqual(list(propuestas(Bajo(),self.fuente,rejilla=2)),[])

    def test_fallo_no_publica_salida_parcial(self):
        class Motor:
            def preparar(_self,f):
                raise RuntimeError('fallo de prueba')
            def liberar_imagen(_self):
                pass
        salida=self.raiz/'error'
        with self.assertRaisesRegex(RuntimeError,'fallo de prueba'):
            ejecutar(self.path,salida,prompts=self.prompts,motor=Motor())
        self.assertFalse(salida.exists())
        self.assertEqual(list(self.raiz.glob('.recortador-*')),[])

    def test_salida_existente_no_se_modifica(self):
        salida=self.raiz/'existente';salida.mkdir();(salida/'conservar.txt').write_text('original')
        with self.assertRaisesRegex(ValueError,'ya existe'):
            ejecutar(self.path,salida,prompts=self.prompts)
        self.assertEqual((salida/'conservar.txt').read_text(),'original')

    def test_pdf_ppp_teselas_rotacion_y_coordenadas(self):
        for rotacion in (0,90):
            path=self.raiz/f'pagina-{rotacion}.pdf'
            with pymupdf.open() as doc:
                page=doc.new_page(width=595,height=842);page.set_rotation(rotacion);doc.save(path)
            for ppp in (150,300):
                primera=abrir_fuente(path,ppp=ppp)
                for t in range(1,primera.procedencia['total_teselas']+1):
                    f=abrir_fuente(path,ppp=ppp,tesela=t)
                    self.assertLessEqual(max(f.imagen.size),2048)
                    self.assertEqual(f.procedencia['ppp'],ppp)
                    caja=f.caja_pagina([0,0,f.imagen.width,f.imagen.height])
                    self.assertAlmostEqual(caja[0],f.procedencia['origen_raster_px'][0]*72/ppp)
                    self.assertAlmostEqual(caja[1],f.procedencia['origen_raster_px'][1]*72/ppp)
            with self.assertRaises(ValueError):abrir_fuente(path,ppp=149)
            with self.assertRaises(ValueError):abrir_fuente(path,tesela=999)
            with self.assertRaises(ValueError):abrir_fuente(path,pagina=0)
            with self.assertRaises(ValueError):abrir_fuente(path,ppp=300,region=[0,0,590,590])

    def test_region_pdf_y_prompt_pagina(self):
        path,prompts=documento(self.raiz)
        f=abrir_fuente(path,ppp=300,region=[200,30,380,230])
        normalizado=validar_prompts({'coordenadas':'pagina_pt','piezas':[prompts['piezas'][2]]},f)[0]
        for real,esperado in zip(f.caja_pagina(normalizado['caja']),prompts['piezas'][2]['caja']):
            self.assertAlmostEqual(real,esperado)


class TestHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=Servidor(('127.0.0.1',0))
        cls.hilo=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.hilo.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.hilo.join();cls.server.server_close()

    def post(self,ruta,datos,token=True,origin=None):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Recortador-Token']=self.server.token
        if origin:headers['Origin']=origin
        req=Request(self.base+ruta,data=json.dumps(datos).encode(),headers=headers)
        return urlopen(req,timeout=10)

    def test_interfaz_y_carga_local(self):
        with urlopen(self.base) as r:
            html=r.read().decode()
            self.assertIn('Recortador de referentes',html)
            self.assertNotIn('__TOKEN__',html)
        im=Image.new('RGB',(64,64),'white');buf=io.BytesIO();im.save(buf,format='PNG')
        with self.post('/api/preparar',{'nombre':'sintetica.png','contenido':base64.b64encode(buf.getvalue()).decode()}) as r:
            datos=json.load(r)
        self.assertEqual(datos['fuente']['ancho'],64)
        self.assertTrue(datos['imagen'].startswith('data:image/png;base64,'))
        with self.post('/api/preparar',{'ppp':150}) as r:
            self.assertEqual(json.load(r)['fuente']['ancho'],64)

    def test_token_origen_y_rutas(self):
        for token,origin in ((False,None),(True,'https://otro.example')):
            with self.assertRaises(HTTPError) as err:
                self.post('/api/preparar',{},token,origin)
            self.assertEqual(err.exception.code,403)
        with self.assertRaises(HTTPError) as err:
            urlopen(self.base+'/salidas/../../modelo.json')
        self.assertEqual(err.exception.code,404)
        with self.assertRaises(HTTPError) as err:
            self.post('/api/preparar',{'nombre':'x.png','contenido':'%%%INVALIDO%%%'})
        self.assertEqual(err.exception.code,400)


if __name__=='__main__':
    unittest.main(verbosity=2)
