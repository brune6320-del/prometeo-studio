"""Comparación prerregistrada; no transforma ausencia de examen en victoria."""
import argparse
from comun import guardar, leer

def comparar(vecino,modelos):
    base=leer(vecino);filas=[base]
    for path in modelos:
        m=leer(path)
        for k in ('sha256_holdout','sha256_galeria','n','dominio'):
            if m[k]!=base[k]: raise ValueError('Resultados no comparables: '+k)
        mejora=m['top1']-base['top1']
        supera=(m['cobertura']==1 and m['top1']>=.8 and mejora>=.05 and m['top5']>=.95
            and m['error_tamano_pt'] is not None and m['error_tamano_pt']['media']<=1
            and m['deltaE2000'] is not None and m['deltaE2000']['media']<=3)
        m={**m,'mejora_top1':mejora,'supera_umbrales_prerregistrados':supera}
        filas.append(m)
    return dict(version=1,filas=filas,real='NO VERIFICADO' if base['dominio']=='sintetico' else 'evaluado por tercero')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('vecino');p.add_argument('modelos',nargs='+');p.add_argument('--salida',required=True)
    a=p.parse_args();guardar(a.salida,comparar(a.vecino,a.modelos))
