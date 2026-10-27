import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from .fuente import contorno,medoid,componer_faltante,completar_mayuscula
from .editar import reponer_region,dentro,intersecta
from .ab import preparar,evaluar
from .restaurar import restaurar
from .comun import sha256,abrir_adn


class LetraTest(unittest.TestCase):
    def test_medoid_elige_muestra_central_real(self):
        a=np.zeros((10,10),np.uint8);b=a.copy();b[3:7,3:7]=255;c=b.copy();c[3,3]=0
        self.assertIn(medoid([dict(mask=x) for x in (a,b,c)]),(1,2))

    def test_contorno_con_hueco_se_conserva(self):
        mask=np.zeros((40,40),np.uint8);mask[5:35,5:35]=255;mask[12:28,12:28]=0
        glyph=contorno(mask,40,35)
        self.assertEqual(glyph.numberOfContours,2)
        ends=glyph.endPtsOfContours;coords=np.array(glyph.coordinates);areas=[];start=0
        for end in ends:
            p=coords[start:end+1];areas.append(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1)));start=end+1
        self.assertLess(areas[0]*areas[1],0)

    def test_solo_region_cambia_pixel_a_pixel(self):
        a=np.zeros((30,30,3),np.uint8);b=np.full_like(a,255)
        out=reponer_region(a,b,(5,6,10,12));self.assertEqual(int(np.any(out!=a,axis=2).sum()),30)
        out[6:12,5:10]=0;np.testing.assert_array_equal(a,out)

    def test_zonas_excluidas_y_contencion(self):
        self.assertTrue(intersecta([0,0,10,10],[9,9,12,12]))
        self.assertFalse(intersecta([0,0,10,10],[10,0,20,10]))
        self.assertFalse(dentro([0,0,10,10],[0,0,11,10]))

    def test_baseline_union_sin_entrenamiento(self):
        a=np.eye(10,dtype=np.uint8)*255;b=np.fliplr(a)
        out=componer_faltante(a,b,'union');self.assertEqual(np.count_nonzero(out),20)
        with self.assertRaises(ValueError):componer_faltante(a,b[:5],'union')

    def test_ttf_completada_reabre_sin_duplicar_glyphorder(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mask=np.eye(40,dtype=np.uint8)*255
            # Dos formas propias con área para comprobar contenedores, no estética.
            mask[10:30,10:30]=255;g=contorno(mask,40,35)
            fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(['.notdef','x','A'])
            fb.setupCharacterMap({120:'x',65:'A'});fb.setupGlyf({'.notdef':TTGlyphPen(None).glyph(),'x':g,'A':g})
            fb.setupHorizontalMetrics({n:(800,0) for n in ['.notdef','x','A']});fb.setupHorizontalHeader(ascent=1000,descent=-200)
            fb.setupNameTable(dict(familyName='Fixture',styleName='Regular'));fb.setupOS2();fb.setupPost();fb.setupMaxp();fb.save(root/'a.ttf')
            completar_mayuscula(root/'a.ttf',root/'b.ttf',destino='X',modelo_minuscula='x',referencia_altura='A')
            font=TTFont(root/'b.ttf');self.assertIn(ord('X'),font.getBestCmap());self.assertEqual(len(font.getGlyphOrder()),4)

    def test_ab_clave_separada_sin_respuestas_falsas(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);Image.new('RGB',(20,20),'white').save(root/'a.png');Image.new('RGB',(20,20),'gray').save(root/'b.png')
            r=preparar([dict(original=root/'a.png',rehecha=root/'b.png',sha256_origen='a'*64)],root/'participante',root/'custodio')
            self.assertEqual(r['respuestas'],0);self.assertFalse((root/'participante/clave.json').exists())
            public=json.loads((root/'participante/pares.json').read_text());self.assertNotIn('original',public['pares'][0])
            (root/'respuestas.json').write_text(json.dumps(dict(sesion=r['sesion'],respuestas=[])))
            self.assertIsNone(evaluar(root/'respuestas.json',root/'custodio/clave.json')['acierto'])

    def test_restauracion_exacta_y_rechazo_de_alteracion(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);original=np.zeros((20,20,3),np.uint8);after=original.copy();after[2:5,3:8]=255
            Image.fromarray(original).save(root/'pagina-antes.png');Image.fromarray(after).save(root/'pagina-despues.png')
            Image.fromarray(original[2:5,3:8]).save(root/'parche-antes.png')
            r=dict(region_px=[3,2,8,5],sha256_antes=sha256(root/'pagina-antes.png'),
                   sha256_despues=sha256(root/'pagina-despues.png'),sha256_parche_antes=sha256(root/'parche-antes.png'))
            (root/'edicion.json').write_text(json.dumps(r))
            self.assertTrue(restaurar(root,root/'restaurada.png')['pixel_identico'])
            Image.new('RGB',(5,3),'red').save(root/'parche-antes.png')
            with self.assertRaisesRegex(ValueError,'alterados'):restaurar(root,root/'fallo.png')
            self.assertFalse((root/'fallo.png').exists())

    def test_adn_de_otro_origen_rechazado(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'doc').write_bytes(b'propio');(root/'adn.json').write_text(json.dumps(dict(sha256_origen='0'*64)))
            with self.assertRaisesRegex(ValueError,'no corresponde'):abrir_adn(root/'doc',root/'adn.json')

    def test_ab_no_acepta_doble_voto(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'key.json').write_text(json.dumps(dict(sesion='s',pares=[dict(id='1',original='A')])))
            (root/'r.json').write_text(json.dumps(dict(sesion='s',respuestas=[dict(id='1',eleccion='A')]*2)))
            with self.assertRaisesRegex(ValueError,'duplicada'):evaluar(root/'r.json',root/'key.json')


if __name__=='__main__':unittest.main()
