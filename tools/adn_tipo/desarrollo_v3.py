"""Mide vecino y padre en validación interna TRAIN antes de entrenar v3.

No es examen ni estimación de generalización del padre: pudo ver este train.
"""
from pathlib import Path
import argparse
import time
import numpy as np
from skimage.color import deltaE_ciede2000
from comun import guardar, sha256
from entrenar_v3 import datos
from medir import Buscador
from modelo import cargar_imagen
from protocolo_v3 import digest


def preparar(dataset, padre, galeria, salida):
    root, salida = Path(dataset), Path(salida)
    rows, manifest, split = datos(root)
    if salida.exists():
        raise ValueError('No sobrescribir desarrollo')
    salida.mkdir(parents=True, exist_ok=False)
    evidence = []
    for name, weights in (('vecino', None), ('padre', padre)):
        start = time.perf_counter()
        search = Buscador(galeria, weights, 'cpu')
        predictions = []; errors = []; colors = []; top1 = []
        for i in split['validacion']:
            r = rows[i]; pred = search.predecir(cargar_imagen(root, r), r['texto'], r['dpi'])
            predictions.append(dict(indice=i, prediccion=pred,
                etiqueta={k:r[k] for k in ('familia', 'texto', 'tamano_pt', 'tinta_lab')}))
            top1.append(bool(pred and pred['fuente'] == r['familia']))
            if pred:
                errors.append(abs(pred['tamano_pt']-r['tamano_pt']))
                colors.append(float(deltaE_ciede2000(np.array(pred['tinta_lab']), np.array(r['tinta_lab']))))
        file = salida/f'{name}.json'
        guardar(file, dict(rol=name, train_sha256=manifest['train_sha256'], split_sha256=digest(split),
            pesos_sha256=sha256(weights) if weights else None, n=len(top1), top1=float(np.mean(top1)),
            cobertura=len(errors)/len(top1), mae_tamano_pt=float(np.mean(errors)) if errors else None,
            deltaE2000=float(np.mean(colors)) if colors else None,
            galeria_sha256=sha256(Path(galeria)/'galeria.json'),
            segundos=time.perf_counter()-start, coste_usd=None, dispositivo='cpu',
            predicciones=predictions), exclusivo=True)
        evidence.append(dict(archivo=file.name, sha256=sha256(file), rol=name))
    report = dict(estado='DESARROLLO_MEDIDO', train_sha256=manifest['train_sha256'],
        split_sha256=digest(split), padre_sha256=sha256(padre), evidencias=evidence,
        revisado_por=None, techo_o_suelo=None,
        maestro='Etiquetas del renderizador/A; referencia, no examinador',
        advertencia='Desarrollo interno train; no promoción. Revisar techo/suelo antes de GPU.')
    guardar(salida/'desarrollo.json', report, exclusivo=True)
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dataset'); ap.add_argument('--padre', required=True)
    ap.add_argument('--galeria', required=True); ap.add_argument('--salida', required=True)
    a = ap.parse_args(); print(preparar(a.dataset, a.padre, a.galeria, a.salida))
