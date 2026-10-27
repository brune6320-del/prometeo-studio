"""Laboratorio D-12. Todas las salidas privadas deben estar fuera del repositorio."""
import argparse
import json
from pathlib import Path
from .fuente import construir, completar_mayuscula
from .editar import editar
from .restaurar import restaurar
from .ab import preparar, evaluar


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='accion',required=True)
    f=sub.add_parser('fuente');f.add_argument('pdf');f.add_argument('adn');f.add_argument('salida')
    f.add_argument('--propio',action='store_true');f.add_argument('--excluir-span',type=int,action='append',default=[])
    f.add_argument('--pagina',type=int,default=1);f.add_argument('--fuente-xref',type=int)
    c=sub.add_parser('completar');c.add_argument('fuente');c.add_argument('salida')
    c.add_argument('--destino',required=True);c.add_argument('--modelo',required=True);c.add_argument('--altura',required=True)
    e=sub.add_parser('editar');e.add_argument('pdf');e.add_argument('adn');e.add_argument('fuente');e.add_argument('salida')
    e.add_argument('--propio',action='store_true');e.add_argument('--pagina',type=int,default=1)
    e.add_argument('--span',type=int,required=True);e.add_argument('--texto')
    e.add_argument('--region',nargs=4,type=float,required=True)
    e.add_argument('--excluir-region',nargs=4,type=float,action='append',default=[])
    e.add_argument('--metodo',choices=['simple','estilo'],default='simple')
    r=sub.add_parser('restaurar');r.add_argument('edicion');r.add_argument('salida')
    b=sub.add_parser('ab');b.add_argument('pares_json');b.add_argument('participante');b.add_argument('custodio')
    v=sub.add_parser('evaluar-ab');v.add_argument('respuestas');v.add_argument('clave')
    a=ap.parse_args()
    if a.accion=='fuente':
        result=construir(a.pdf,a.adn,a.salida,propio=a.propio,pagina=a.pagina,excluir_spans=a.excluir_span,fuente_xref=a.fuente_xref)
    elif a.accion=='completar':
        result=completar_mayuscula(a.fuente,a.salida,destino=a.destino,modelo_minuscula=a.modelo,referencia_altura=a.altura)
    elif a.accion=='editar':
        result=editar(a.pdf,a.adn,a.fuente,a.salida,propio=a.propio,pagina=a.pagina,span_id=a.span,texto=a.texto,
                      autorizado=a.region,excluidas=a.excluir_region,metodo=a.metodo)
    elif a.accion=='restaurar':result=restaurar(a.edicion,a.salida)
    elif a.accion=='ab':result=preparar(json.loads(Path(a.pares_json).read_text()),a.participante,a.custodio)
    else:result=evaluar(a.respuestas,a.clave)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
