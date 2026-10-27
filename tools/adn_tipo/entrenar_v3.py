"""Ejecutor prospectivo v3. CPU: solo humo de una época; CUDA: Drive y presupuesto.

No lee holdout.json, no evalúa d10-examen y no modifica el ejecutor v2.
"""
from __future__ import annotations
import argparse
import fcntl
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import random
import shutil
import time
from pathlib import Path
import numpy as np
import torch
from skimage.color import deltaE_ciede2000
from comun import ROOT, SEED, familia_sha, guardar, leer, particion, sha256
from modelo import TipoNet, cargar_imagen, cargar_pesos, tensor
from protocolo_v3 import PRERREGISTRO_SHA, Parada, digest, dividir, es_sha


def datos(dataset):
    dataset = Path(dataset)
    manifest = leer(dataset/'manifest.json')
    if sha256(dataset/'train.json') != manifest['train_sha256']:
        raise ValueError('Train alterado')
    rows = leer(dataset/'train.json')
    if not rows:
        raise ValueError('Train vacío')
    for r in rows:
        if (r['familia_sha256'] != familia_sha(r['familia']) or r.get('split') != 'train'
                or particion(r['familia_sha256']) != 'train'):
            raise ValueError('Familia holdout o identidad incorrecta en train')
        if r.get('dpi') != 96:
            raise ValueError('Normalización a 96 DPI requerida')
        lab = np.asarray(r['tinta_lab'], dtype=float)
        if (lab.shape != (3,) or not np.isfinite(lab).all() or not 0 <= lab[0] <= 100.01
                or np.any(np.abs(lab[1:]) > 128) or not 0 < r['tamano_pt'] <= 1000):
            raise ValueError('Etiquetas físicas inválidas')
    split = dividir(rows, manifest['dominio'])
    split['train_sha256'] = manifest['train_sha256']
    return rows, manifest, split


def componentes(clase, pred, yy, rr):
    ce = torch.nn.functional.cross_entropy(clase, yy)
    size = torch.nn.functional.mse_loss(pred[:, 0], rr[:, 0])
    color = torch.nn.functional.mse_loss(pred[:, 1:], rr[:, 1:])
    return ce + size + 4 * color, ce, size, color


def validar(net, x, y, reg, ids, device, batch, comprobar_tiempo):
    net.eval(); sums = np.zeros(4); preds = []; classes = []
    with torch.inference_mode():
        for start in range(0, len(ids), batch):
            comprobar_tiempo()
            ix = ids[start:start+batch]
            _, cls, pred = net(x[ix].to(device))
            parts = componentes(cls, pred, y[ix].to(device), reg[ix].to(device))
            sums += np.array([float(v) for v in parts]) * len(ix)
            preds.extend(pred.cpu().tolist()); classes.extend(cls.argmax(1).cpu().tolist())
    pred = np.asarray(preds) * [24, 100, 128, 128]
    truth = reg[ids].numpy() * [24, 100, 128, 128]
    de = deltaE_ciede2000(truth[:, 1:], pred[:, 1:])
    metrics = dict(zip(('score', 'ce', 'mse_tamano_normalizado', 'mse_lab_normalizado'), (sums/len(ids)).tolist()))
    metrics.update(n=len(ids), mae_tamano_pt=float(np.abs(pred[:, 0]-truth[:, 0]).mean()),
                   mae_lab=np.abs(pred[:, 1:]-truth[:, 1:]).mean(0).tolist(),
                   deltaE2000=float(de.mean()), deltaE2000_p95=float(np.percentile(de, 95)),
                   accuracy_clase_auxiliar=float((np.asarray(classes) == y[ids].numpy()).mean()))
    # Son predicciones reales de validación, nunca se fabrican curvas desde fórmulas.
    return metrics, dict(indices=ids, prediccion_tamano_lab=pred.tolist(),
                        etiqueta_tamano_lab=truth.tolist(), clase_predicha=classes,
                        clase_etiqueta=y[ids].tolist())


def entrenar(dataset, salida, *, device='cpu', humo=False, inicial=None,
             control=False, presupuesto=None, desarrollo=None):
    salida = Path(salida)
    if salida.exists():
        raise ValueError('No sobrescribir una generación')
    if sha256(ROOT/'PRERREGISTRO-v3.md') != PRERREGISTRO_SHA:
        raise ValueError('Prerregistro v3 alterado')
    if device not in ('cpu', 'cuda') or (device == 'cpu') != bool(humo):
        raise ValueError('CPU solo con humo; CUDA sin humo')
    rows, manifest, split = datos(dataset)
    if device == 'cuda':
        if not torch.cuda.is_available():
            raise ValueError('CUDA no disponible')
        drive = Path('/content/drive').resolve()
        if not drive.is_dir() or drive not in salida.resolve().parents:
            raise ValueError('CUDA requiere salida en Drive montado')
        if not presupuesto or not desarrollo:
            raise ValueError('Faltan presupuesto real y baseline de desarrollo revisado')
        p = leer(presupuesto); d = leer(desarrollo)
        values = [p.get(k) for k in ('unidades_disponibles', 'unidades_por_hora', 'segundos_maximos')]
        if any(type(v) not in (int, float) or not np.isfinite(v) or v <= 0 for v in values):
            raise ValueError('Presupuesto requiere números positivos conocidos')
        unidades, tarifa, max_s = values
        if unidades > 20 or max_s*tarifa/3600 > unidades or not p.get('saldo_verificado_por'):
            raise ValueError('Tope compartido o saldo no verificado')
        # La tarifa no es el contador real. El notebook exige supervisión de Bruno.
        if (d.get('train_sha256') != manifest['train_sha256'] or d.get('split_sha256') != digest(split)
                or not es_sha(d.get('padre_sha256')) or not d.get('revisado_por')
                or d.get('techo_o_suelo') is not False or d.get('estado') != 'DESARROLLO_MEDIDO'):
            raise ValueError('Desarrollo no revisado o no comparable; no entrenar')
        evidencias = d.get('evidencias', [])
        if len(evidencias) != 2 or {e.get('rol') for e in evidencias} != {'padre', 'vecino'}:
            raise ValueError('Faltan predicciones separadas del padre y vecino')
        for e in evidencias:
            base = Path(desarrollo).resolve().parent
            file = (base/e['archivo']).resolve()
            if base not in file.parents or sha256(file) != e['sha256']:
                raise ValueError('Evidencia de desarrollo alterada')
            evidence = leer(file)
            if (evidence['train_sha256'] != manifest['train_sha256']
                    or evidence['split_sha256'] != digest(split)
                    or evidence['n'] != len(split['validacion'])
                    or len(evidence['predicciones']) != evidence['n']
                    or (e['rol'] == 'padre' and evidence['pesos_sha256'] != d['padre_sha256'])):
                raise ValueError('Predicciones de desarrollo incompatibles')
    else:
        p = {}; max_s = 120
    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
    torch.set_num_threads(2); torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    previous = None
    familias = sorted({r['familia'] for r in rows})
    if inicial:
        if manifest['dominio'] != 'nativo_train':
            raise ValueError('Afinado exige nativo_train')
        net, previous = cargar_pesos(inicial, device)
        if not set(familias) <= set(previous['familias']):
            raise ValueError('Familia nativa fuera de vocabulario')
        familias = previous['familias']
        val_orig = {rows[i]['sha256_origen'] for i in split['validacion']}
        if val_orig & set(previous['origenes_train']):
            raise ValueError('Padre ya vio documento de validación nativa')
    else:
        if manifest['dominio'] != 'sintetico':
            raise ValueError('Primera etapa requiere sintético')
        net = TipoNet(len(familias)).to(device)
    holdout_sha = previous['holdout_sha256'] if previous else manifest.get('holdout_sha256')
    if not es_sha(holdout_sha):
        raise ValueError('Falta SHA completo de holdout en metadatos; no abrirlo')
    x = torch.stack([tensor(cargar_imagen(dataset, r)) for r in rows])
    y = torch.tensor([familias.index(r['familia']) for r in rows])
    reg = torch.tensor([[r['tamano_pt']/24, *(np.asarray(r['tinta_lab'])/[100,128,128])]
                        for r in rows], dtype=torch.float32)
    train_ids = split['train']; val_ids = split['validacion']
    train_y, train_reg = y[train_ids].clone(), reg[train_ids].clone()
    if control:
        perm = torch.randperm(len(train_ids), generator=torch.Generator().manual_seed(SEED))
        train_y, train_reg = train_y[perm], train_reg[perm]
    loader = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(x[train_ids], train_y, train_reg),
        batch_size=64, shuffle=True, num_workers=0, generator=torch.Generator().manual_seed(SEED))
    optimizer = torch.optim.Adam(net.parameters(), lr=1e-4 if inicial else 1e-3)
    max_epochs = 1 if humo else 100 if inicial else 300
    origenes = sorted({r['sha256_origen'] for r in rows if r.get('sha256_origen')}
                      | set(previous['origenes_train'] if previous else []))
    family_hashes = sorted({r['familia_sha256'] for r in rows}
                          | set(previous['familias_train_sha256'] if previous else []))
    salida.mkdir(parents=True, exist_ok=False)
    guardar(salida/'split.json', split, exclusivo=True)
    guardar(salida/'config.json', dict(prerregistro_sha256=PRERREGISTRO_SHA, seed=SEED,
        train_sha256=manifest['train_sha256'], split_sha256=digest(split), humo=humo, control=control,
        max_epocas=max_epochs, paciencia=25, min_delta=1e-4, presupuesto=p,
        desarrollo_sha256=sha256(desarrollo) if desarrollo else None), exclusivo=True)
    inicio = time.perf_counter(); history = []; stop = Parada(); best = None

    def tiempo():
        if time.perf_counter()-inicio >= max_s:
            raise TimeoutError('Tope temporal alcanzado; corrida incompleta, no promover')

    # Bloqueo común del dispositivo para todas las ejecuciones v3 de este host.
    # No descubre trabajos externos: el operador también verifica que no haya otro GPU job.
    lockpath = Path('/tmp')/'prometeo-adn-v3-training.lock'
    with lockpath.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Otro proceso v3 está activo') from exc
        try:
            for epoch in range(1, max_epochs+1):
                net.train(); total = 0.; count = 0
                for xx, yy, rr in loader:
                    tiempo()
                    xx, yy, rr = xx.to(device), yy.to(device), rr.to(device)
                    emb, cls, pred = net(xx)
                    loss = componentes(cls, pred, yy, rr)[0]
                    sim = emb @ emb.T
                    same = yy[:, None] == yy[None, :]
                    pos = same & ~torch.eye(len(yy), dtype=torch.bool, device=device)
                    neg = ~same
                    contrast = 0*sim.sum()
                    if pos.any(): contrast = contrast + (1-sim[pos]).mean()
                    if neg.any(): contrast = contrast + torch.relu(sim[neg]-.3).mean()
                    loss = loss + .2*contrast
                    if not torch.isfinite(loss):
                        raise ValueError('Loss no finita: detener')
                    optimizer.zero_grad(); loss.backward(); optimizer.step()
                    total += float(loss.detach())*len(xx); count += len(xx)
                metrics, predictions = validar(net, x, y, reg, val_ids, device, 64, tiempo)
                improved, end = stop.observar(epoch, metrics['score'])
                generation = salida/f'epoca-{epoch:04d}'
                generation.mkdir(exist_ok=False)
                ck = dict(state={k:v.detach().cpu() for k,v in net.state_dict().items()},
                    optimizer=optimizer.state_dict(), familias=familias,
                    familias_train_sha256=family_hashes, origenes_train=origenes,
                    holdout_sha256=holdout_sha, train_sha256=manifest['train_sha256'],
                    etapa='afinado_A' if inicial else 'solo_sintetico', protocolo='v3',
                    control_placebo=control, humo=humo, epoca=epoch,
                    pesos_iniciales_sha256=sha256(inicial) if inicial else None,
                    split_sha256=digest(split), prerregistro_sha256=PRERREGISTRO_SHA)
                # Un archivo nuevo por época. Flush/fsync antes de continuar.
                with (generation/'pesos.pt').open('xb') as stream:
                    torch.save(ck, stream); stream.flush(); os.fsync(stream.fileno())
                guardar(generation/'predicciones.json', predictions, exclusivo=True)
                row = dict(epoca=epoch, loss_train=total/count, validacion=metrics,
                           pesos_sha256=sha256(generation/'pesos.pt'),
                           predicciones_sha256=sha256(generation/'predicciones.json'),
                           segundos_acumulados=time.perf_counter()-inicio)
                guardar(generation/'metricas.json', row, exclusivo=True)
                history.append(row)
                if improved: best = generation/'pesos.pt'
                print(f'epoca {epoch}: score validacion={metrics["score"]:.6f}', flush=True)
                tiempo()
                if end: break
            if device == 'cuda': torch.cuda.synchronize()
            assert best is not None
            shutil.copyfile(best, salida/'pesos.pt')
            elapsed = time.perf_counter()-inicio
            report = dict(version=3, estado='HUMO_NO_EVIDENCIA' if humo else 'TESTED_NO_VERIFIED',
                etapa=ck['etapa'], control_placebo=control, seed=SEED, epocas=len(history),
                epoca_seleccionada=stop.epoca_mejor, historial=history, dispositivo=device,
                gpu=torch.cuda.get_device_name(0) if device=='cuda' else None,
                segundos=elapsed, unidades_gpu_reales=0 if humo else None,
                unidades_gpu_estimadas=0 if humo else elapsed*p['unidades_por_hora']/3600,
                coste_usd=None, n=len(rows), n_train=len(train_ids), n_validacion=len(val_ids),
                parametros=sum(v.numel() for v in net.parameters()),
                sha256_pesos=sha256(salida/'pesos.pt'), sha256_train=manifest['train_sha256'],
                sha256_holdout=holdout_sha, sha256_prerregistro=PRERREGISTRO_SHA,
                criterio_seleccion='validacion_interna_train', mejora_vs_baseline=None,
                examen_real='NO EJECUTADO', promocion=False)
            guardar(salida/'entrenamiento.json', report, exclusivo=True)
            return report
        except Exception as exc:
            guardar(salida/'FALLO.json', dict(estado='INCOMPLETO_NO_PROMOVER', tipo=type(exc).__name__,
                epocas_guardadas=len(history), segundos=time.perf_counter()-inicio), exclusivo=True)
            raise


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dataset', type=Path); ap.add_argument('--salida', type=Path, required=True)
    ap.add_argument('--device', choices=['cpu','cuda'], default='cpu'); ap.add_argument('--humo', action='store_true')
    ap.add_argument('--inicial', type=Path); ap.add_argument('--control', action='store_true')
    ap.add_argument('--presupuesto', type=Path); ap.add_argument('--desarrollo', type=Path)
    a = ap.parse_args()
    print(entrenar(a.dataset, a.salida, device=a.device, humo=a.humo, inicial=a.inicial,
                   control=a.control, presupuesto=a.presupuesto, desarrollo=a.desarrollo))
