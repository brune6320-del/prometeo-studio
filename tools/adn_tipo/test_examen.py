"""Solo PDFs artificiales en temporales. Nunca accede a Drive/d10-examen."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pymupdf as fitz
from comun import ROOT, familia_sha, guardar, leer, sha256
from examen.preparar import ErrorExamen, leer_sello, preparar
from medir_examen import Agregados, evaluar, verificar_galeria

PRIVADO='NOMBRE_Y_CONTENIDO_PRIVADO_NO_DEBE_SALIR'

class BuscadorFalso:
    def __init__(self,root,pesos=None,device='cpu'):
        self.galeria=[dict(familia='Arvo'),dict(familia='Fjalla One')]
        self.checkpoint=leer(pesos) if pesos else None
    def predecir(self,im,texto,dpi):
        return dict(fuente='Arvo',fuentes=['Arvo','Fjalla One'],tamano_pt=18.,tinta_lab=[0.,0.,0.])


class ExamenTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.cache')
        self.root=Path(self.temp.name);self.pdfs=self.root/'pdfs';self.pdfs.mkdir()
        self.sello=self.root/'examen-sellado.json'
        self.sint=self.root/'solo/pesos.pt';self.fino=self.root/'afinado/pesos.pt'
        self._pesos()
    def tearDown(self):
        self.temp.cleanup()
    def _pesos(self,origenes=()):
        ck=dict(familias=['Lato'],familias_train_sha256=[familia_sha('Lato')],origenes_train=list(origenes),
                etapa='solo_sintetico',holdout_sha256='e'*64,train_sha256='f'*64,pesos_iniciales_sha256=None)
        guardar(self.sint,ck)
        guardar(self.sint.parent/'entrenamiento.json',dict(sha256_pesos=sha256(self.sint),
            etapa='solo_sintetico',sha256_train='f'*64,segundos=1.,coste_usd=None,gpu=None,epocas=20))
        guardar(self.fino,{**ck,'etapa':'afinado_A','pesos_iniciales_sha256':sha256(self.sint)})
        guardar(self.fino.parent/'entrenamiento.json',dict(sha256_pesos=sha256(self.fino),
            etapa='afinado_A',sha256_train='f'*64,segundos=1.,coste_usd=None,gpu=None,epocas=5))
    def corpus(self,scan=False):
        records=[]
        for i in range(10):
            path=self.pdfs/f'{PRIVADO}-{i}.pdf'
            with fitz.open() as d:
                p=d.new_page(width=250+i,height=100)
                if not scan:
                    file='arvo/Arvo-Regular.ttf' if i%2==0 else 'fjallaone/FjallaOne-Regular.ttf'
                    p.insert_font(fontname='fixture',fontfile=str(ROOT/'.cache/fuentes'/file))
                    p.insert_text((10,40),'Ab'+str(i),fontname='fixture',fontsize=18)
                d.set_metadata({'title':PRIVADO})
                d.save(path)
            records.append(dict(sha256=sha256(path),n_paginas=1,tipo='escaneado' if scan else 'nativo'))
        guardar(self.sello,dict(version=1,documentos=records))
        return records
    def args(self):
        return dict(sello_sha=sha256(self.sello),prerregistro_sha=sha256(ROOT/'PRERREGISTRO.md'),
            galeria=self.root/'catalogo',galeria_sha='b'*64,sintetico=self.sint,sintetico_sha=sha256(self.sint),
            afinado=self.fino,afinado_sha=sha256(self.fino),control=self.root/'control',salida=self.root/'metricas.json',propio=True)
    def medir(self,**overrides):
        args=self.args();args.update(overrides)
        with patch('medir_examen.verificar_galeria'),patch('medir_examen.Buscador',BuscadorFalso):
            return evaluar(self.pdfs,self.sello,**args)
    def test_sello_solo_metadatos_y_carpeta_exacta(self):
        self.corpus();inv=preparar(self.pdfs,self.sello,sha256(self.sello))
        self.assertEqual(len(inv.documentos),10)
        self.assertNotIn(PRIVADO,repr(inv))
        data=leer(self.sello);data['documentos'][0]['archivo']='privado.pdf';guardar(self.sello,data)
        with self.assertRaisesRegex(ErrorExamen,'SOLO_SHA'):preparar(self.pdfs,self.sello,sha256(self.sello))
    def test_rechaza_faltante_sobrante_duplicado_y_archivo_no_pdf(self):
        self.corpus();first=next(self.pdfs.iterdir());data=first.read_bytes()
        first.unlink()
        with self.assertRaisesRegex(ErrorExamen,'FALTAN'):preparar(self.pdfs,self.sello,sha256(self.sello))
        first.write_bytes(data);extra=self.pdfs/'sobrante.pdf';extra.write_bytes(b'otro')
        with self.assertRaisesRegex(ErrorExamen,'SOBRAN'):preparar(self.pdfs,self.sello,sha256(self.sello))
        extra.write_bytes(data)
        with self.assertRaisesRegex(ErrorExamen,'DUPLICADO'):preparar(self.pdfs,self.sello,sha256(self.sello))
        extra.unlink();(self.pdfs/'nota.txt').write_text(PRIVADO)
        with self.assertRaisesRegex(ErrorExamen,'NO_PDF'):preparar(self.pdfs,self.sello,sha256(self.sello))
    def test_rechaza_hash_sello_alterado_y_enlaces(self):
        self.corpus()
        with self.assertRaisesRegex(ErrorExamen,'SHA_NO_COINCIDE'):preparar(self.pdfs,self.sello,'0'*64)
        (self.pdfs/'enlace.pdf').symlink_to(next(self.pdfs.iterdir()))
        with self.assertRaisesRegex(ErrorExamen,'ENLACES'):preparar(self.pdfs,self.sello,sha256(self.sello))
    def test_rechaza_sello_duplicado_paginas_boolean_y_cantidad(self):
        records=self.corpus();records[0]['n_paginas']=True;guardar(self.sello,records)
        with self.assertRaisesRegex(ErrorExamen,'METADATA'):leer_sello(self.sello,sha256(self.sello))
        records[0]['n_paginas']=1;records[1]=records[0];guardar(self.sello,records)
        with self.assertRaisesRegex(ErrorExamen,'DUPLICADO'):leer_sello(self.sello,sha256(self.sello))
        guardar(self.sello,records[:2])
        with self.assertRaisesRegex(ErrorExamen,'10_A_20'):leer_sello(self.sello,sha256(self.sello))
    def test_una_apertura_por_pdf_solo_agregados_sin_temporales(self):
        self.corpus();before={p.relative_to(self.root) for p in self.root.rglob('*')}
        original_open=fitz.open;stdout=io.StringIO();stderr=io.StringIO()
        with patch('medir_examen.fitz.open',wraps=original_open) as abrir,patch('medir_examen.Image.Image.save',autospec=True,wraps=None) as save:
            # JPEG real en BytesIO; prohibir cualquier destino de archivo para imágenes.
            original_save=ImageSave
            def in_memory(img,dest,*a,**kw):
                self.assertIsInstance(dest,io.BytesIO)
                return original_save(img,dest,*a,**kw)
            save.side_effect=in_memory
            with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):result=self.medir()
        self.assertEqual(abrir.call_count,10)
        self.assertEqual(len(result['filas']),3)
        self.assertEqual(result['contadores']['caracteres_evaluados'],30)
        self.assertEqual(result['familias_holdout_evaluadas'],2)
        self.assertEqual(stdout.getvalue()+stderr.getvalue(),'')
        created={p.relative_to(self.root) for p in self.root.rglob('*')}-before
        self.assertEqual({p.suffix for p in created if (self.root/p).is_file()},{'.json'})
        for p in created:
            if (self.root/p).is_file():
                content=(self.root/p).read_text()
                for token in (PRIVADO,'Ab0','archivo','bbox','texto','imagen','fuente','Arvo'):
                    self.assertNotIn('"'+token+'"',content)
                self.assertNotIn(PRIVADO,content)
        self.assertEqual(sum((self.root/p).is_file() for p in created),2)
    def test_rechaza_repeticion_incluso_sello_reordenado(self):
        records=self.corpus();self.medir()
        guardar(self.sello,list(reversed(records)))
        with patch('medir_examen.fitz.open') as abrir:
            with self.assertRaisesRegex(ErrorExamen,'YA_INICIADO'):
                self.medir(salida=self.root/'otras-metricas.json')
            abrir.assert_not_called()
    def test_metadata_incorrecta_gasta_intento_y_no_publica_parcial(self):
        records=self.corpus();records[0]['n_paginas']=2;guardar(self.sello,records)
        with self.assertRaisesRegex(ErrorExamen,'PAGINAS'):self.medir()
        self.assertFalse((self.root/'metricas.json').exists())
        marker=next((self.root/'control').glob('*.json'))
        self.assertEqual(leer(marker)['estado'],'FALLIDO_NO_REPETIR')
        with self.assertRaisesRegex(ErrorExamen,'YA_INICIADO'):self.medir()
    def test_rechaza_tipo_de_sello_incorrecto(self):
        records=self.corpus();records[0]['tipo']='escaneado';guardar(self.sello,records)
        with self.assertRaisesRegex(ErrorExamen,'TIPO_NO_COINCIDE'):self.medir()
    def test_sin_referencia_no_fabrica_metricas(self):
        self.corpus(scan=True);r=self.medir()
        self.assertEqual(r['estado'],'NO_EVALUABLE')
        self.assertEqual(r['escaneados']['paginas'],10)
        self.assertTrue(all(x['top1'] is None and x['deltaE2000'] is None for x in r['filas']))
    def test_fuga_origen_y_pesos_distintos_rechazan_antes_de_pdf(self):
        records=self.corpus();self._pesos([records[0]['sha256']])
        with patch('medir_examen.fitz.open') as abrir:
            with self.assertRaisesRegex(ErrorExamen,'ORIGEN_EXAMEN'):self.medir()
            abrir.assert_not_called()
        self._pesos()
        with self.assertRaisesRegex(ErrorExamen,'PESOS_SHA'):self.medir(sintetico_sha='0'*64)
    def test_prerregistro_alterado_no_lee_carpeta(self):
        self.corpus()
        with patch('medir_examen.preparar') as preparar_mock:
            with self.assertRaisesRegex(ErrorExamen,'PRERREGISTRO'):self.medir(prerregistro_sha='0'*64)
            preparar_mock.assert_not_called()
    def test_excepcion_no_filtra_datos_ni_traceback(self):
        self.corpus()
        with patch('medir_examen.fitz.open',side_effect=RuntimeError(PRIVADO)):
            with self.assertRaises(ErrorExamen) as e:self.medir()
        self.assertEqual(str(e.exception),'EVALUACION_FALLIDA')
        self.assertNotIn(PRIVADO,next((self.root/'control').glob('*.json')).read_text())
    def test_holdout_antiguo_deshabilitado_antes_de_leer_plan(self):
        from preparar_examen import preparar as antiguo
        with patch('preparar_examen.leer') as read:
            with self.assertRaisesRegex(ValueError,'deshabilitado'):
                antiguo(self.root/'inexistente',self.root/'salida','holdout',True)
            read.assert_not_called()

    def test_catalogo_real_congelado(self):
        from generar_sintetico import GLIFOS
        catalogo=self.root/'catalogo'
        rows=[dict(familia=f['familia'],familia_sha256=familia_sha(f['familia']),
            fuente_sha256=f['sha256'],texto=c,dpi=96,tamano_pt=24)
            for f in leer(ROOT/'fuentes.lock.json')['fuentes'] for c in GLIFOS]
        guardar(catalogo/'galeria.json',rows)
        guardar(catalogo/'manifest.json',dict(galeria_sha256=sha256(catalogo/'galeria.json'),
            fuentes_lock_sha256=sha256(ROOT/'fuentes.lock.json')))
        verificar_galeria(catalogo,sha256(catalogo/'galeria.json'))
        with self.assertRaisesRegex(ErrorExamen,'GALERIA_SHA'):
            verificar_galeria(catalogo,'0'*64)

    def test_afinado_distinto_y_familia_holdout_rechazados(self):
        self.corpus()
        ck=leer(self.fino);ck['pesos_iniciales_sha256']='0'*64;guardar(self.fino,ck)
        with self.assertRaisesRegex(ErrorExamen,'MISMA_CNN'):self.medir()
        self._pesos()
        ck=leer(self.sint);ck['familias']=['Arvo'];ck['familias_train_sha256']=[familia_sha('Arvo')]
        guardar(self.sint,ck)
        with self.assertRaisesRegex(ErrorExamen,'FAMILIA_HOLDOUT'):self.medir()

    def test_cambio_entre_inventario_y_apertura_rechazado(self):
        self.corpus()
        original_preparar=preparar
        def mutar(*args):
            inv=original_preparar(*args)
            next(iter(inv.rutas.values())).write_bytes(b'alterado')
            return inv
        with patch('medir_examen.preparar',side_effect=mutar):
            with self.assertRaisesRegex(ErrorExamen,'CAMBIO'):self.medir()
        self.assertFalse((self.root/'metricas.json').exists())

    def test_abstencion_cuenta_como_fallo(self):
        a=Agregados();a.agregar(None,'Arvo',18,[0,0,0]);r=a.resumen()
        self.assertEqual(r['top1'],0);self.assertEqual(r['top5'],0);self.assertIsNone(r['deltaE2000'])

from PIL.Image import Image as PILImage
ImageSave=PILImage.save

if __name__=='__main__':unittest.main()
