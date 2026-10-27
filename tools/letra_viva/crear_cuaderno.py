"""Genera un cuaderno autocontenido de baseline; no simula un entrenador."""
import hashlib
import json
from pathlib import Path


def crear():
    root=Path(__file__).parent
    names=['__init__.py','comun.py','fuente.py','editar.py','restaurar.py','ab.py','ab.html',
           '__main__.py','test_letra_viva.py','PRERREGISTRO.md','LICENCIAS.json','requirements-c3.txt']
    payload={n:(root/n).read_text() for n in names}
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in payload.items()}
    cells=[]
    def md(s):cells.append(dict(cell_type='markdown',metadata={},source=s.splitlines(True)))
    def code(s):cells.append(dict(cell_type='code',execution_count=None,outputs=[],metadata={},source=s.splitlines(True)))
    md('# D-12 · baseline reproducible y bloqueo de entrenamiento\n\n'
       'Este cuaderno NO contiene un entrenador neuronal ejecutable. Incluye extracción, '
       'TTF, composición simple, edición, restauración y A/B. CPU; GPU consumida por este '
       'cuaderno: 0. No descarga pesos ni instala paquetes. No abrir el examen d10-examen. '
       'Solo documentos propios. Un único origen de desarrollo no constituye reserva.\n\n'
       'D-12 sigue BLOQUEADA para generación neuronal, LPIPS y evaluación independiente. '
       'No lanzar GPU hasta resolver licencias y pesos autorizados, corpus y saldo '
       'compartido D-10/D-12 <=20 unidades. Futuro entrenador: padre/maestro/simple/placebo, '
       'curvas de predicciones, checkpoints a Drive antes de seguir, olvido y custodio.')
    code('from pathlib import Path\nimport json, hashlib, sys\n'
         'ROOT = Path("/content/letra-viva-c3")\n'
         'PAYLOAD = '+repr(payload)+'\nHASHES = '+repr(hashes)+'\n'
         'for name, source in PAYLOAD.items():\n'
         '    assert hashlib.sha256(source.encode()).hexdigest() == HASHES[name]\n'
         '    target = ROOT / "tools" / "letra_viva" / name\n'
         '    target.parent.mkdir(parents=True, exist_ok=True)\n'
         '    if target.exists() and target.read_text() != source:\n'
         '        raise RuntimeError("Salida de código existente distinta; conservar antes de continuar")\n'
         '    target.write_text(source)\n'
         'sys.path.insert(0,str(ROOT))\nprint(json.dumps(HASHES,indent=2))\n')
    md('## Entorno\n\nReutilizar un entorno autorizado con PyMuPDF, NumPy, Pillow, OpenCV, '
       'scikit-image y fontTools. No se instala PyMuPDF AGPL/comercial ni se cambia torch. '
       'Si falta algo, detener y resolver el entorno; la autorización vigente en la Mac '
       'solo cubre su venv C3. Ejecutar en CPU. La celda siguiente solo verifica importaciones.')
    code('import pymupdf, numpy, PIL, cv2, skimage, fontTools\nimport unittest\n'
         'suite=unittest.defaultTestLoader.loadTestsFromName("tools.letra_viva.test_letra_viva")\n'
         'assert unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()\n')
    md('## Drive y documento de desarrollo\n\nBruno configura rutas y revisa la región. '
       'El SHA fijado es el plano ya autorizado, sin reservas. No cargar documentos ajenos '
       'ni firmados/sellados. Las coordenadas de ejemplo corresponden únicamente a ese SHA. '
       'Cada ejecución crea una carpeta nueva en Drive.')
    code('from google.colab import drive\ndrive.mount("/content/drive")\n'
         'from datetime import datetime, timezone\n'
         'from tools.letra_viva.comun import sha256, guardar\n'
         'BASE=Path("/content/drive/MyDrive/Prometeo/LetraViva")\n'
         'PDF=BASE/"entrada/plano-demo.pdf"\nADN=BASE/"entrada/plano-demo.adn.json"\n'
         'ES_PROPIO=False  # Bruno confirma su autoría y revisión de exclusiones\n'
         'assert ES_PROPIO, "Confirmar documento propio antes de procesar"\n'
         'assert sha256(PDF)=="ff05702c3fe241d53bcab7fdcd37a925bb619e54313b6074bdedc68e32e9b1a9"\n'
         'RUN=BASE/"salidas"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")\n'
         'RUN.mkdir(parents=True,exist_ok=False)\n'
         'REGION=[1801.19384765625,251.4849853515625,1887.8385009765625,276.5003662109375]\n'
         'EXCLUIDAS=[]  # Definir firmas/sellos rasterizados y otras zonas intocables\n')
    code('from tools.letra_viva.fuente import construir, completar_mayuscula\n'
         'from fontTools.ttLib import TTFont\n'
         'report=construir(PDF,ADN,RUN/"fuente",excluir_spans=[18],propio=ES_PROPIO)\n'
         'FONT=RUN/"fuente"/report["fuente"]\n'
         'with TTFont(FONT) as ft:\n    cmap=ft.getBestCmap()\n'
         'if ord("X") not in cmap:\n'
         '    completar_mayuscula(FONT,RUN/"baseline-completa.ttf",destino="X",modelo_minuscula="x",referencia_altura="A")\n'
         '    FONT=RUN/"baseline-completa.ttf"\nprint("FUENTE SHA256",sha256(FONT))\n')
    code('from tools.letra_viva.editar import editar\n'
         'from tools.letra_viva.restaurar import restaurar\n'
         'from tools.letra_viva.ab import preparar\n'
         'results={}\n'
         'for method in ("simple","estilo"):\n'
         '    results[method]=editar(PDF,ADN,FONT,RUN/method,propio=ES_PROPIO,span_id=18,autorizado=REGION,excluidas=EXCLUIDAS,metodo=method)\n'
         'restaurar(RUN/"estilo",RUN/"restaurada.png")\n'
         'ab=preparar([dict(original=RUN/"estilo/parche-antes.png",rehecha=RUN/"estilo/parche-despues.png",sha256_origen=sha256(PDF))],RUN/"PARTICIPANTE",RUN/"CUSTODIO")\n'
         'guardar(RUN/"comparacion.json",dict(resultados=results,ab=ab,gpu_unidades=0,entrenamiento=False,dominio="DESARROLLO"))\n'
         'manifest={str(p.relative_to(RUN)):sha256(p) for p in sorted(RUN.rglob("*")) if p.is_file()}\n'
         'guardar(RUN/"manifest.json",manifest)\n'
         'print(json.dumps({m:r["metricas"] for m,r in results.items()},indent=2))\n'
         'print("MANIFEST SHA256",sha256(RUN/"manifest.json"))\n')
    md('## Entrenamiento pendiente — no ejecutar como si existiera\n\n'
       'FontDiffuser: restricción no comercial. MX-Font: MIT con excepción FUNIT '
       'CC-BY-NC-SA. Los SHA de evidencia están en LICENCIAS.json; pesos SHA=null '
       'porque no se descargaron. Falta seleccionar una vía compatible y autorizar '
       'el artefacto exacto. No hay curva, checkpoint neuronal ni mejora generativa. '
       'La baseline perdedora se conserva. Custodio independiente aporta reserva '
       'nueva después del congelado. No usar la reserva como entrenamiento.')
    code('estado=dict(fase="D-12",estado="BLOQUEADA",pesos_sha256=None,entrenador_implementado=False,\n'
         '    faltantes=["licencias de código/pesos compatibles", "permiso de descarga de pesos",\n'
         '               "corpus autorizado", "reserva independiente", "saldo Colab compartido"],\n'
         '    gpu_unidades_consumidas=0)\nprint(json.dumps(estado,ensure_ascii=False,indent=2))\n'
         'guardar(RUN/"bloqueo-entrenamiento.json",estado)\n')
    nb=dict(nbformat=4,nbformat_minor=5,metadata=dict(kernelspec=dict(display_name='Python 3',language='python',name='python3')),cells=cells)
    for i,c in enumerate(cells):c['id']=f'd12-{i:02d}'
    (root/'colab.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n')
    return nb


if __name__=='__main__':crear()
