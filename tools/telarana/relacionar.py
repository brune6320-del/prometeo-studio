"""Correspondencia geométrica y textura; hipótesis explicable, no identidad garantizada."""
import cv2
import numpy as np


def relacionar(a, b):
    cv2.setNumThreads(1); cv2.setRNGSeed(2610)
    aa = cv2.cvtColor(np.asarray(a.convert('RGB')), cv2.COLOR_RGB2GRAY)
    bb = cv2.cvtColor(np.asarray(b.convert('RGB')), cv2.COLOR_RGB2GRAY)
    detector = cv2.ORB_create(nfeatures=3000, edgeThreshold=12, fastThreshold=10)
    ka, da = detector.detectAndCompute(aa, None); kb, db = detector.detectAndCompute(bb, None)
    result = dict(metodo='ORB + affine parcial RANSAC; semilla 2610', coincidencias=0,
        inliers=0, proporcion_inliers=0., error_mediano_px=None, textura_correlacion=None,
        matriz_a_b=None, misma_figura_propuesta=False, estado='sin_evidencia_suficiente')
    if da is None or db is None or len(db) < 2: return result
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    good = [m for pair in pairs if len(pair)==2 for m,n in [pair] if m.distance < .75*n.distance]
    # Un punto destino no se cuenta varias veces como apoyo independiente.
    unique = {}
    for m in sorted(good, key=lambda m:m.distance): unique.setdefault(m.trainIdx, m)
    good = list(unique.values()); result['coincidencias'] = len(good)
    if len(good) < 8: return result
    src = np.float32([ka[m.queryIdx].pt for m in good]); dst = np.float32([kb[m.trainIdx].pt for m in good])
    matrix, mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
        ransacReprojThreshold=3., maxIters=2000, confidence=.99, refineIters=10)
    if matrix is None: return result
    valid = mask.ravel().astype(bool); count = int(valid.sum())
    error = np.linalg.norm(src @ matrix[:,:2].T + matrix[:,2] - dst, axis=1)
    # ORB localiza a precisión subpíxel aproximada. Comparar textura a escala
    # de 1 px evita que una traslación <1 px destruya correlación por aliasing.
    smooth_a = cv2.GaussianBlur(aa, (5,5), 1.)
    smooth_b = cv2.GaussianBlur(bb, (5,5), 1.)
    warped = cv2.warpAffine(smooth_a, matrix, (bb.shape[1], bb.shape[0]))
    overlap = cv2.warpAffine(np.ones_like(aa), matrix, (bb.shape[1], bb.shape[0]), flags=cv2.INTER_NEAREST).astype(bool)
    # Excluir papel casi blanco; no permitir que el fondo domine la comparación.
    overlap = cv2.erode(overlap.astype('uint8'), np.ones((5,5),np.uint8)).astype(bool)
    ink = overlap & ((warped < 240) | (smooth_b < 240))
    texture = 0.
    if ink.sum() >= 64 and np.std(warped[ink]) > 1 and np.std(smooth_b[ink]) > 1:
        texture = float(np.corrcoef(warped[ink], smooth_b[ink])[0,1])
    proposed = count >= 8 and count/len(good) >= .6 and float(np.median(error[valid])) <= 3 and texture >= .7
    result.update(inliers=count, proporcion_inliers=count/len(good), error_mediano_px=float(np.median(error[valid])),
        textura_correlacion=texture, matriz_a_b=matrix.tolist(), misma_figura_propuesta=bool(proposed),
        estado='propuesta_para_revisar' if proposed else 'sin_evidencia_suficiente',
        pixeles_textura=int(ink.sum()), textura_sigma_px=1., advertencia='Semejanza no demuestra identidad semántica; no probabilidad calibrada.')
    return result
