import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from .grafo import Proyecto, ficha, sha
from .relacionar import relacionar


class TelaranaTest(unittest.TestCase):
    def proyecto(self, root):
        p=Proyecto(root/'proyecto.json')
        for ident in ('a','b','c'):
            p.crear(ficha(ident,'region',{'etiqueta':ident},origenes=['a'*64]))
        p.crear(ficha('ab','conclusion',{'misma':True},depende_de=[dict(id='a',revision=1),dict(id='b',revision=1)]))
        p.crear(ficha('hija','conclusion',{'reusar':True},depende_de=[dict(id='ab',revision=1)]))
        p.crear(ficha('independiente','conclusion',{'texto':'en pie'},depende_de=[dict(id='c',revision=1)]))
        return p

    def test_corregir_invalida_solo_descendientes_y_replay_exacto(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.proyecto(Path(td));before=p.estado()
            after=p.corregir('a',1,{'etiqueta':'revisada'},'Bruno corrige')
            self.assertEqual({k for k,n in after['fichas'].items() if n['estado']=='invalidada'},{'ab','hija'})
            for key in ('b','c','independiente'):
                self.assertEqual(before['fichas'][key],after['fichas'][key])
            reopened=Proyecto(p.path).estado()
            self.assertEqual(after,reopened);self.assertEqual(sha(after),sha(reopened))

    def test_revision_obsoleta_no_escribe(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.proyecto(Path(td));p.corregir('a',1,{},'motivo');before=p.path.read_bytes()
            with self.assertRaises(ValueError):p.corregir('a',1,{},'motivo')
            self.assertEqual(before,p.path.read_bytes())

    def test_dependencia_obsoleta_y_ciclo_no_entran(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.proyecto(Path(td));p.corregir('a',1,{},'motivo')
            for deps in ([dict(id='a',revision=1)],[dict(id='ab',revision=1)],[dict(id='nuevo',revision=1)]):
                with self.assertRaises(ValueError):p.crear(ficha('nuevo','conclusion',{},depende_de=deps))

    def test_log_manipulado_rechazado(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.proyecto(Path(td));doc=json.loads(p.path.read_text())
            doc['eventos'][0]['datos']['contenido']['etiqueta']='alterada'
            p.path.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'alterada'):p.estado()

    def test_copias_un_solo_origen(self):
        f=ficha('a','region',{},origenes=['a'*64,'a'*64])
        self.assertEqual(len(f['origenes']),1)

    def test_rotacion_con_geometria_y_textura(self):
        rng=np.random.default_rng(2610)
        im=Image.fromarray(rng.integers(0,256,(320,400,3),dtype=np.uint8))
        result=relacionar(im,im.transpose(Image.Transpose.ROTATE_90))
        self.assertTrue(result['misma_figura_propuesta'])
        self.assertGreater(result['inliers'],8)
        self.assertGreater(result['textura_correlacion'],.7)

    def test_papel_blanco_no_es_evidencia(self):
        im=Image.new('RGB',(300,300),'white')
        self.assertFalse(relacionar(im,im)['misma_figura_propuesta'])


if __name__=='__main__':unittest.main()
