"""Fixtures propios; no abre PDFs de Bruno ni el examen sellado."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pymupdf as fitz
from PIL import Image
from comun import ROOT, familia_sha, guardar, lab, leer, ortografia, particion, sha256, validar_pagina
from nativo import extraer, comprobar_documento
from modelo import geometria, cargar_imagen
from generar_sintetico import renderizar
from medir import evaluar
from entrenar import entrenar
from preparar_examen import preparar

class ADNTest(unittest.TestCase):
    def test_nativo_caracter_fuente_y_pixeles(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); pdf=root/'propio.pdf'
            with fitz.open() as d:
                p=d.new_page(width=300,height=200)
                p.insert_text((25,40),'Hola mundo',fontname='helv',fontsize=14,color=(.2,.3,.4))
                p.insert_text((25,80),'Otra linea',fontname='hebo',fontsize=18)
                d.save(pdf)
            before=sha256(pdf)
            pages=extraer(pdf,root/'out',propio=True)
            self.assertEqual(sha256(pdf),before)
            self.assertEqual(''.join(c['c'] for c in pages[0]['spans'][0]['caracteres']),'Hola mundo')
            self.assertEqual(pages[0]['spans'][0]['tamano_pt'],14)
            self.assertEqual(pages[0]['spans'][1]['peso'],700)
            validar_pagina(leer(root/'out/pagina-0001/adn.json'))
            self.assertTrue(all(x['soportado'] for x in pages[0]['comparacion']['bloques']))
            self.assertLess(max(x['mae_pixel'] for x in pages[0]['comparacion']['bloques']),2.)
    def test_embebida_y_rotacion(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);pdf=root/'propio.pdf'
            with fitz.open() as d:
                p=d.new_page(width=200,height=200)
                p.insert_font(fontname='custom',fontfile=str(ROOT/'.cache/fuentes/lato/Lato-Regular.ttf'))
                p.insert_text((20,40),'Árbol',fontname='custom',fontsize=16)
                p.set_rotation(90);d.save(pdf)
            result=extraer(pdf,root/'out',propio=True)[0]
            self.assertTrue(any(f['sha256'] for f in result['fuentes']))
            self.assertEqual(result['spans'][0]['texto'],'Árbol')
            self.assertLess(result['comparacion']['bloques'][0]['mae_pixel'],2.)
    def test_rechaza_firmas_sellos_y_sin_declaracion(self):
        with fitz.open() as d:
            p=d.new_page()
            with self.assertRaises(ValueError): comprobar_documento(d,False)
            p.add_stamp_annot(fitz.Rect(10,10,100,50))
            with self.assertRaisesRegex(ValueError,'sellos'): comprobar_documento(d,True)
        with fitz.open() as d:
            p=d.new_page();w=fitz.Widget();w.field_name='Firma';w.field_type=fitz.PDF_WIDGET_TYPE_SIGNATURE;w.rect=fitz.Rect(10,10,100,50)
            p.add_widget(w)
            with self.assertRaisesRegex(ValueError,'firma'): comprobar_documento(d,True)
    def test_familia_normalizada_y_estilos_mismo_split(self):
        self.assertEqual(familia_sha('  LATO '),familia_sha('Lato'))
        lock=leer(ROOT/'fuentes.lock.json'); asignaciones={}
        for f in lock['fuentes']:
            asignaciones.setdefault(f['familia'],set()).add(particion(familia_sha(f['familia'])))
        self.assertTrue(all(len(v)==1 for v in asignaciones.values()))
        self.assertGreaterEqual(sum(v=={'holdout'} for v in asignaciones.values()),2)
    def test_sintetico_tamano_efectivo_y_semilla(self):
        f=ROOT/'.cache/fuentes/lato/Lato-Regular.ttf'
        a,size=renderizar(f,'a',14.2,[0,0,0],[255]*3,ruido=2,rng=np.random.default_rng(9))
        b,_=renderizar(f,'a',14.2,[0,0,0],[255]*3,ruido=2,rng=np.random.default_rng(9))
        self.assertEqual(a.tobytes(),b.tobytes());self.assertEqual(size,round(14.2*96/72)*72/96)
    def test_lab_y_ortografia_no_corrige(self):
        np.testing.assert_allclose(lab([255]*3),[100,0,0],atol=.02)
        text='árbol qzxqz';marks=ortografia(text)
        self.assertEqual(marks[0]['texto'],'qzxqz');self.assertEqual(text,'árbol qzxqz')
    def test_sha_de_imagen_y_holdout(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);Image.new('RGB',(64,64),'white').save(root/'a.png')
            row=dict(archivo='a.png',sha256='0'*64)
            with self.assertRaises(ValueError): cargar_imagen(root,row)
            guardar(root/'holdout.json',{'muestras':[]})
            with self.assertRaisesRegex(ValueError,'sellado'): evaluar(root,root/'out.json','0'*64)
    def test_rechaza_fuga_train_antes_de_gradientes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);row=dict(familia='Arvo',familia_sha256=familia_sha('Arvo'),split='train',dpi=96)
            guardar(root/'train.json',[row]);guardar(root/'manifest.json',{'train_sha256':sha256(root/'train.json')})
            with self.assertRaisesRegex(ValueError,'holdout'): entrenar(root,root/'out',epocas=1)
    def test_plan_rechaza_origen_en_ambos_splits_sin_abrir_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);guardar(root/'plan.json',{'documentos':[{'sha256':'a','split':'train'},{'sha256':'a','split':'holdout'}]})
            with self.assertRaisesRegex(ValueError,'repetido'):preparar(root/'plan.json',root/'out','holdout',True)
    def test_maestro_train_propio_sin_abrir_examen(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); pdf=root/'fixture.pdf'
            with fitz.open() as d:
                p=d.new_page(width=200,height=100)
                p.insert_font(fontname='lato',fontfile=str(ROOT/'.cache/fuentes/lato/Lato-Regular.ttf'))
                p.insert_text((20,40),'Hola',fontname='lato',fontsize=18)
                d.save(pdf)
            guardar(root/'plan.json',dict(documentos=[dict(archivo=str(pdf),sha256=sha256(pdf),split='train')],mapa_fuentes={'latoregular':'Lato'}))
            preparar(root/'plan.json',root/'train','train',True)
            rows=leer(root/'train/train.json')
            self.assertEqual(len(rows),4)
            self.assertTrue(all(r['tamano_pt']==18 and r['sha256_origen']==sha256(pdf) for r in rows))
            self.assertFalse((root/'train/holdout.json').exists())

    def test_pdf_mixto_enruta_y_preserva_pagina(self):
        from extraer import extraer as entrada_unificada
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);pdf=root/'mixto.pdf'
            with fitz.open() as d:
                p=d.new_page();p.insert_text((20,40),'Nativo')
                d.new_page();d.save(pdf)
            with self.assertRaisesRegex(ValueError,'galeria'):
                entrada_unificada(pdf,root/'out',propio=True)
            fake=dict(version='1.0.0',pagina=1,spans=[])
            with patch('extraer.inferir',return_value=fake) as ocr:
                pages=entrada_unificada(pdf,root/'out',propio=True,galeria=root)
            ocr.assert_called_once()
            self.assertEqual(pages[1]['pagina'],2)
            self.assertEqual(pages[1]['sha256_origen'],sha256(pdf))

    def test_evaluacion_rechaza_familia_vista(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            row=dict(familia='Arvo',familia_sha256=familia_sha('Arvo'))
            guardar(root/'holdout.json',dict(muestras=[row]))
            ck=dict(familias_train_sha256=[familia_sha('Arvo')],origenes_train=[])
            with patch('medir.Buscador',return_value=SimpleNamespace(checkpoint=ck)):
                with self.assertRaisesRegex(ValueError,'Fuga de familias'):
                    evaluar(root,root/'m.json',sha256(root/'holdout.json'))

    def test_cajas_vacias_y_lab_invalido(self):
        shape,alto,_=geometria(Image.new('RGB',(64,64),'white'))
        self.assertEqual(alto,0);self.assertEqual(shape.shape,(1024,))
        with self.assertRaises(ValueError):validar_pagina({'version':'99','pagina':1,'spans':[]})

if __name__=='__main__':unittest.main()
