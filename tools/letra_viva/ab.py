"""A/B local: participante sin clave; custodio separado. Nunca fabrica respuestas."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import shutil
from .comun import guardar,sha256


def preparar(pares, participante, custodio, seed=2610):
    participante,custodio=Path(participante),Path(custodio)
    if participante.exists() or custodio.exists():raise ValueError('No sobrescribir prueba A/B')
    if participante.resolve() in custodio.resolve().parents or custodio.resolve() in participante.resolve().parents:
        raise ValueError('Participante y custodio deben ser carpetas separadas')
    participante.mkdir(parents=True);custodio.mkdir(parents=True)
    rng=random.Random(seed);order=list(range(len(pares)));rng.shuffle(order)
    public=[];key=[]
    for n,i in enumerate(order):
        pair=pares[i];left_original=bool(rng.getrandbits(1))
        originals=[pair['original'],pair['rehecha']]
        if not left_original:originals.reverse()
        names=[]
        for side,path in zip(('A','B'),originals):
            name=f'{n:04d}-{side}.png';shutil.copyfile(path,participante/name);names.append(name)
        ident=f'{n:04d}';public.append(dict(id=ident,A=names[0],B=names[1]))
        key.append(dict(id=ident,original='A' if left_original else 'B',sha256_origen=pair['sha256_origen']))
    session=hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()
    guardar(custodio/'clave.json',dict(version=1,sesion=session,seed=seed,pares=key))
    guardar(participante/'pares.json',dict(version=1,sesion=session,pares=public))
    template=(Path(__file__).parent/'ab.html').read_text()
    # Datos estructurados; escapar '<' por si hubiera entradas externas futuras.
    payload=json.dumps(dict(sesion=session,pares=public)).replace('<','\\u003c')
    (participante/'index.html').write_text(template.replace('__DATOS__',payload))
    return dict(sesion=session,n=len(public),respuestas=0,resultado='PENDIENTE_BRUNO',
        clave_sha256=sha256(custodio/'clave.json'))


def evaluar(respuestas,clave):
    r=json.loads(Path(respuestas).read_text());k=json.loads(Path(clave).read_text())
    if r['sesion']!=k['sesion']:raise ValueError('Sesión incorrecta')
    truth={x['id']:x['original'] for x in k['pares']};answers=r['respuestas']
    if len({x['id'] for x in answers})!=len(answers):raise ValueError('Respuesta duplicada')
    if any(x['id'] not in truth or x['eleccion'] not in ('A','B') for x in answers):raise ValueError('Respuesta inválida')
    n=len(answers)
    if n==0:return dict(n=0,acierto=None,resultado='NO EVALUABLE')
    hits=sum(x['eleccion']==truth[x['id']] for x in answers);p=hits/n;z=1.959963984540054
    den=1+z*z/n;center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return dict(n=n,total=len(truth),aciertos=hits,acierto=p,wilson95=[center-half,center+half],
        origenes=len({x['sha256_origen'] for x in k['pares']}),meta_puntual=p<=.55,
        cumple_prerregistro=False,nota='Requiere reserva independiente, >=100 palabras y >=10 páginas; revisar agrupación por origen')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('respuestas');ap.add_argument('clave')
    a=ap.parse_args();print(json.dumps(evaluar(a.respuestas,a.clave),indent=2))
