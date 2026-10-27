#!/usr/bin/env python3
"""FASE 5c · Capa media features.5 (N-1 v3) + Generador de Prueba Ciega Humana (20 pares).

Parte 1 (Capa media features.5):
- Evalúa las 200 neuronas de features.5 (384 canales, mapa espacial 14x14) prerregistradas
  con semilla 2610 en lab/neuronas/prerregistro_v3.json sobre el mismo corpus de 630
  imágenes CC0 (441 train / 189 validación).
- Redacta etiquetas libres en español natural usando EXCLUSIVAMENTE los 38 rasgos visuales
  y compositivos puros de diseño medidos sobre los píxeles (sin mezclar metadatos de catálogo
  del museo como «escultura» o «grabado»). Si en train no hay patrón claro (AUC_train < 0.64),
  declara «no lo sé».
- Ejecuta las mismas pruebas no tautológicas a) y b) y guarda las 200 fichas PRAGMA v3 en
  lab/neuronas/atlas_f5/neurona_f5_<canal:03d>.json y los mosaicos fuera de Git.

Parte 2 (Prueba ciega humana para Bruno · 20 pares):
- De las neuronas legibles de features.7 (26) y features.5 (34), elige 20 al azar con
  semilla 2610.
- Para cada una construye un par visual sin cabeceras chivatas: el mosaico top-9 real y un
  mosaico señuelo (top-9 de otra neurona elegida al azar), con posición izquierda/derecha
  sorteada al azar (semilla 2610).
- Genera un único archivo HTML autocontenido (sin internet) en:
  ~/Desktop/REFERENTES/prueba-ciega-bruno/prueba_ciega_20_pares.html
  y guarda la clave secreta en un archivo aparte que Bruno NO abre:
  ~/Desktop/REFERENTES/prueba-ciega-bruno/clave_secreta_no_abrir.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.neuronas.construir_atlas import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    LICENCIA_TORCHVISION,
    ORDEN_CLAVES_RASGOS,
    SEED,
     _guardar_mosaico_neurona,
    cargar_modelo_convnext_tiny,
    extraer_descriptor_visual_rico,
    intervalo_confianza_wilson_95,
    puntuar_validacion_solo_con_etiqueta,
    redactar_etiqueta_libre_train,
    roc_auc_score_manual,
)

FECHA_FASE_5C = "2026-10-27"
NUM_RASGOS_VISUALES_PUROS = 38  # Primeros 38 rasgos: 100% píxel/diseño, 0 metadatos de museo


def _extraer_parche_receptivo_14x14(
    im_224: Image.Image, u_grid: int, v_grid: int, tam_parche: int = 80
) -> Image.Image:
    """Extrae un parche centrado en la celda (u_grid, v_grid) del mapa 14x14 sobre 224x224."""
    cy = int(round((u_grid + 0.5) * 16.0))
    cx = int(round((v_grid + 0.5) * 16.0))
    mitad = tam_parche // 2
    x0 = max(0, min(224 - tam_parche, cx - mitad))
    y0 = max(0, min(224 - tam_parche, cy - mitad))
    return im_224.crop((x0, y0, x0 + tam_parche, y0 + tam_parche))


def _extraer_parche_receptivo_7x7(
    im_224: Image.Image, u_grid: int, v_grid: int, tam_parche: int = 96
) -> Image.Image:
    cy = int(round((u_grid + 0.5) * 32.0))
    cx = int(round((v_grid + 0.5) * 32.0))
    mitad = tam_parche // 2
    x0 = max(0, min(224 - tam_parche, cx - mitad))
    y0 = max(0, min(224 - tam_parche, cy - mitad))
    return im_224.crop((x0, y0, x0 + tam_parche, y0 + tam_parche))


def _renderizar_mosaico_ciego_3x3(parches_9: List[Image.Image]) -> Tuple[bytes, str]:
    """Renderiza una cuadrícula 3x3 limpia (sin texto ni cabeceras) en JPEG para la prueba ciega."""
    celda = 96
    gap = 6
    pad = 10
    W = pad * 2 + 3 * celda + 2 * gap
    H = W
    lienzo = Image.new("RGB", (W, H), (24, 26, 30))
    draw = ImageDraw.Draw(lienzo)
    for idx in range(9):
        r = idx // 3
        c = idx % 3
        x0 = pad + c * (celda + gap)
        y0 = pad + r * (celda + gap)
        p_res = parches_9[idx].resize((celda, celda), Image.Resampling.BILINEAR)
        lienzo.paste(p_res, (x0, y0))
        draw.rectangle([x0, y0, x0 + celda - 1, y0 + celda - 1], outline=(70, 76, 88), width=1)
    buf = io.BytesIO()
    lienzo.save(buf, format="JPEG", quality=90)
    raw_bytes = buf.getvalue()
    sha = hashlib.sha256(raw_bytes).hexdigest()
    return raw_bytes, sha


def _generar_html_prueba_ciega(
    ruta_html: Path,
    pares_publicos: List[Dict[str, Any]],
) -> None:
    """Genera un único archivo .html autocontenido (sin internet) para los 20 pares de Bruno."""
    datos_js = json.dumps(pares_publicos, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prueba Ciega de Neuronas (20 pares) · Bruno · Prometeo Studio</title>
<style>
  :root {{
    --bg: #111318;
    --card: #1b1f27;
    --border: #2e3440;
    --text: #eceff4;
    --muted: #a3abb8;
    --accent: #5e81ac;
    --selected: #88c0d0;
    --ok: #a3be8c;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 24px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }}
  .container {{
    max-width: 980px;
    margin: 0 auto;
  }}
  header {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 20px;
  }}
  h1 {{
    margin: 0 0 8px 0;
    font-size: 22px;
  }}
  .progress-bar {{
    margin-top: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .badge {{
    background: #252b37;
    border: 1px solid var(--border);
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 13px;
    color: var(--selected);
    font-weight: 600;
  }}
  .btn-save {{
    background: var(--ok);
    color: #111318;
    border: none;
    padding: 10px 18px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
  }}
  .btn-save:hover {{ opacity: 0.92; }}
  .pair-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 18px;
  }}
  .pair-card.answered {{
    border-color: var(--selected);
  }}
  .pair-header {{
    font-size: 13px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
  }}
  .pair-label {{
    font-size: 16px;
    font-weight: 600;
    background: #14171e;
    border-left: 4px solid var(--selected);
    padding: 12px 16px;
    border-radius: 6px;
    margin-bottom: 16px;
  }}
  .mosaics-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }}
  .option-box {{
    background: #151820;
    border: 2px solid var(--border);
    border-radius: 10px;
    padding: 14px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.15s, transform 0.1s;
  }}
  .option-box:hover {{
    border-color: #6c7a96;
  }}
  .option-box.active {{
    border-color: var(--ok);
    background: #1c241e;
  }}
  .option-box img {{
    width: 100%;
    max-width: 318px;
    height: auto;
    border-radius: 6px;
    display: block;
    margin: 0 auto 12px auto;
  }}
  .choice-btn {{
    display: inline-block;
    padding: 8px 20px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 14px;
    background: #252b37;
    color: var(--text);
    border: 1px solid var(--border);
  }}
  .option-box.active .choice-btn {{
    background: var(--ok);
    color: #111318;
    border-color: var(--ok);
  }}
  #json-preview {{
    width: 100%;
    height: 120px;
    background: #0d0f13;
    color: #d8dee9;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    margin-top: 12px;
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Prueba Ciega Humana · 20 Pares de Neuronas (FASE 5c)</h1>
    <p style="margin:0;color:var(--muted);font-size:14px;">
      Para cada etiqueta escrita en español, uno de los dos mosaicos 3×3 muestra el <strong>top-9 real</strong> de esa neurona en <code>train</code> y el otro es un <strong>señuelo</strong> de otra neurona al azar. Marca cuál de los dos (<strong>Izquierda</strong> o <strong>Derecha</strong>) encaja con la etiqueta. Al terminar, pulsa <strong>Guardar respuestas_bruno_20_pares.json</strong> en la misma carpeta de esta página.
    </p>
    <div class="progress-bar">
      <span class="badge" id="status-badge">Respondidos: 0 / 20</span>
      <button class="btn-save" onclick="guardarRespuestas()">Guardar respuestas_bruno_20_pares.json</button>
    </div>
  </header>

  <div id="pairs-root"></div>

  <header style="margin-top:24px;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
      <strong>Vista previa del JSON de respuestas (`respuestas_bruno_20_pares.json`):</strong>
      <button class="btn-save" onclick="guardarRespuestas()">Guardar respuestas_bruno_20_pares.json</button>
    </div>
    <textarea id="json-preview" readonly></textarea>
  </header>
</div>

<script>
const PARES = {datos_js};
const STORAGE_KEY = "prometeo_fase5c_respuestas_bruno_v1";
let respuestas = {{}};
try {{
  const guardado = localStorage.getItem(STORAGE_KEY);
  if (guardado) respuestas = JSON.parse(guardado);
}} catch (e) {{}}

function construirObjetoSalida() {{
  const lista = PARES.map(p => ({{
    id_par: p.id_par,
    eleccion: respuestas[p.id_par] || null,
    sha256_izquierda: p.sha256_izquierda,
    sha256_derecha: p.sha256_derecha
  }}));
  const contestados = lista.filter(x => x.eleccion === "izquierda" || x.eleccion === "derecha").length;
  return {{
    fase: "FASE 5c · Prueba ciega humana (20 pares)",
    evaluador: "Bruno",
    fecha_respuesta: new Date().toISOString(),
    total_pares: PARES.length,
    pares_respondidos: contestados,
    respuestas: lista
  }};
}}

function actualizarUI() {{
  const root = document.getElementById("pairs-root");
  root.innerHTML = "";
  let contestados = 0;
  PARES.forEach(p => {{
    const el = respuestas[p.id_par];
    if (el === "izquierda" || el === "derecha") contestados++;
    const card = document.createElement("div");
    card.className = "pair-card" + (el ? " answered" : "");
    card.innerHTML = `
      <div class="pair-header">Par #${{p.id_par}} de 20</div>
      <div class="pair-label">${{p.etiqueta}}</div>
      <div class="mosaics-grid">
        <div class="option-box ${{el === 'izquierda' ? 'active' : ''}}" onclick="seleccionar(${{p.id_par}}, 'izquierda')">
          <img src="data:image/jpeg;base64,${{p.b64_izquierda}}" alt="Mosaico Izquierda">
          <span class="choice-btn">👈 Izquierda</span>
        </div>
        <div class="option-box ${{el === 'derecha' ? 'active' : ''}}" onclick="seleccionar(${{p.id_par}}, 'derecha')">
          <img src="data:image/jpeg;base64,${{p.b64_derecha}}" alt="Mosaico Derecha">
          <span class="choice-btn">Derecha 👉</span>
        </div>
      </div>
    `;
    root.appendChild(card);
  }});
  document.getElementById("status-badge").textContent = `Respondidos: ${{contestados}} / ${{PARES.length}}`;
  const salida = construirObjetoSalida();
  document.getElementById("json-preview").value = JSON.stringify(salida, null, 2);
}}

function seleccionar(idPar, lado) {{
  respuestas[idPar] = lado;
  try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(respuestas)); }} catch (e) {{}}
  actualizarUI();
}}

async function guardarRespuestas() {{
  const salida = construirObjetoSalida();
  const texto = JSON.stringify(salida, null, 2) + "\\n";
  if (window.showSaveFilePicker) {{
    try {{
      const handle = await window.showSaveFilePicker({{
        suggestedName: "respuestas_bruno_20_pares.json",
        types: [{{ description: "JSON", accept: {{ "application/json": [".json"] }} }}]
      }});
      const writable = await handle.createWritable();
      await writable.write(texto);
      await writable.close();
      alert("Archivo respuestas_bruno_20_pares.json guardado correctamente.");
      return;
    }} catch (err) {{
      if (err.name === "AbortError") return;
    }}
  }}
  const blob = new Blob([texto], {{ type: "application/json" }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "respuestas_bruno_20_pares.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}}

actualizarUI();
</script>
</body>
</html>
"""
    ruta_html.parent.mkdir(parents=True, exist_ok=True)
    ruta_html.write_text(html, encoding="utf-8")


def ejecutar_fase5c(
    ruta_prerregistro_v3: Path,
    ruta_prerregistro_v2: Path,
    ruta_prerregistro_v1: Path,
    ruta_corpus_json: Path,
    ruta_pesos: Path,
    carpeta_imagenes_cc0: Path,
    carpeta_atlas_f7: Path,
    carpeta_atlas_f5_salida: Path,
    carpeta_mosaicos_local: Path,
    carpeta_prueba_ciega_local: Path,
    ruta_cache_f5_npz: Path,
    ruta_cache_f7_npz: Path,
) -> Dict[str, Any]:
    prerreg_v3 = json.loads(ruta_prerregistro_v3.read_text(encoding="utf-8"))
    sha_v3 = hashlib.sha256(ruta_prerregistro_v3.read_bytes()).hexdigest()
    sha_v2 = hashlib.sha256(ruta_prerregistro_v2.read_bytes()).hexdigest()
    sha_v1 = hashlib.sha256(ruta_prerregistro_v1.read_bytes()).hexdigest()
    sha_corpus = hashlib.sha256(ruta_corpus_json.read_bytes()).hexdigest()

    corpus_items: List[Dict[str, Any]] = json.loads(
        ruta_corpus_json.read_text(encoding="utf-8")
    )["imagenes"]

    modelo, sha_pesos = cargar_modelo_convnext_tiny(ruta_pesos)
    neuronas_f5_ids: List[int] = prerreg_v3["modelo"]["neuronas_ids"]

    mean_arr = np.asarray(IMAGENET_MEAN, dtype=np.float32).reshape(3, 1, 1)
    std_arr = np.asarray(IMAGENET_STD, dtype=np.float32).reshape(3, 1, 1)

    imagenes_224_pil: List[Image.Image] = []
    descriptores_630: List[Dict[str, float]] = []
    tensors_list: List[torch.Tensor] = []

    for it in corpus_items:
        ruta_img = carpeta_imagenes_cc0 / f"{it['id_origen']}.jpg"
        with Image.open(ruta_img) as raw_im:
            img_pil = raw_im.convert("RGB")
        w0, h0 = img_pil.size
        if w0 < h0:
            nw = 236
            nh = max(236, int(round(h0 * 236.0 / w0)))
        else:
            nh = 236
            nw = max(236, int(round(w0 * 236.0 / h0)))
        im_236 = img_pil.resize((nw, nh), Image.Resampling.BILINEAR)
        left = (nw - 224) // 2
        top = (nh - 224) // 2
        im_224 = im_236.crop((left, top, left + 224, top + 224))
        imagenes_224_pil.append(im_224)
        # Sin metadatos de catálogo de museo: titulo_obra="" y categoria=""
        descriptores_630.append(extraer_descriptor_visual_rico(im_224, {}, ""))

        if not ruta_cache_f5_npz.is_file():
            arr_u8 = np.asarray(im_224, dtype=np.uint8)
            arr_f = (arr_u8.astype(np.float32) / 255.0).transpose(2, 0, 1)
            tensors_list.append(torch.from_numpy((arr_f - mean_arr) / std_arr))

    if ruta_cache_f5_npz.is_file():
        cache_f5 = np.load(ruta_cache_f5_npz)
        f5_all = cache_f5["f5_all"]
        logits_all = cache_f5["logits_all"]
    else:
        f5_chunks = []
        logits_chunks = []
        with torch.inference_mode():
            for b_start in range(0, len(tensors_list), 32):
                batch = torch.stack(tensors_list[b_start : b_start + 32], dim=0)
                f5 = modelo.features[:6](batch)
                f7 = modelo.features[6:](f5)
                logits = modelo.forward_etapa_siguiente(f7)
                f5_chunks.append(f5.cpu().numpy())
                logits_chunks.append(logits.cpu().numpy())
        f5_all = np.concatenate(f5_chunks, axis=0)
        logits_all = np.concatenate(logits_chunks, axis=0)
        np.savez(ruta_cache_f5_npz, f5_all=f5_all, logits_all=logits_all)

    pooled_f5_all = f5_all.mean(axis=(2, 3))  # [630, 384]

    train_idx = [i for i, it in enumerate(corpus_items) if it["split"] == "train"]
    val_idx = [i for i, it in enumerate(corpus_items) if it["split"] == "validacion"]

    X_all = np.array(
        [[d[k] for k in ORDEN_CLAVES_RASGOS] for d in descriptores_630], dtype=np.float64
    )
    # Garantizar 0 absoluto en las columnas 38..50 (solo los 38 rasgos visuales/compositivos de píxel)
    X_all[:, NUM_RASGOS_VISUALES_PUROS:] = 0.0
    X_train = X_all[train_idx]
    mean_tr = X_train.mean(axis=0)
    std_tr = X_train.std(axis=0) + 1e-6
    Z_train = (X_train - mean_tr) / std_tr
    Z_val = (X_all[val_idx] - mean_tr) / std_tr
    Z_train[:, NUM_RASGOS_VISUALES_PUROS:] = 0.0
    Z_val[:, NUM_RASGOS_VISUALES_PUROS:] = 0.0

    f5_train = f5_all[train_idx]
    logits_train = logits_all[train_idx]
    pooled_f5_train = pooled_f5_all[train_idx]
    pooled_f5_val = pooled_f5_all[val_idx]
    mean_abs_f5_train = np.abs(pooled_f5_train).mean(axis=0)
    f5_train_t = torch.from_numpy(f5_train)

    carpeta_atlas_f5_salida.mkdir(parents=True, exist_ok=True)
    carpeta_mosaicos_f5 = carpeta_mosaicos_local / "f5"
    carpeta_mosaicos_f5.mkdir(parents=True, exist_ok=True)
    carpeta_5_ejemplos_f5 = carpeta_mosaicos_local / "5_ejemplos_f5"
    carpeta_5_ejemplos_f5.mkdir(parents=True, exist_ok=True)

    cnt_legibles = 0
    cnt_solo_a = 0
    cnt_solo_b = 0
    cnt_ni_a_ni_b = 0
    cnt_pass_a = 0
    cnt_pass_b = 0
    cnt_no_lo_se = 0

    resumen_f5: List[Dict[str, Any]] = []
    parches_top9_f5_por_canal: Dict[int, List[Image.Image]] = {}
    top9_local_f5_por_canal: Dict[int, List[int]] = {}

    with torch.inference_mode():
        for canal in neuronas_f5_ids:
            act_tr = pooled_f5_train[:, canal]
            orden_tr_desc = sorted(
                range(len(train_idx)), key=lambda i: (-float(act_tr[i]), i)
            )
            top9_local = orden_tr_desc[:9]
            bot9_local = list(reversed(orden_tr_desc[-9:]))
            top60_local = orden_tr_desc[:60]
            bot60_local = list(reversed(orden_tr_desc[-60:]))
            top9_local_f5_por_canal[canal] = top9_local

            # Prueba (a) en features.5
            diffs = np.abs(mean_abs_f5_train - mean_abs_f5_train[canal])
            diffs[canal] = 1e9
            pool_25 = np.argsort(diffs)[:25]
            rng_y = np.random.default_rng(SEED + canal)
            y_controls = rng_y.choice(pool_25, size=5, replace=False)

            base_9 = f5_train_t[top9_local]
            batch_54 = base_9.repeat(6, 1, 1, 1)
            batch_54[0:9, canal, :, :] = 0.0
            for idx_y, y_id in enumerate(y_controls, start=1):
                batch_54[idx_y * 9 : (idx_y + 1) * 9, int(y_id), :, :] = 0.0

            z_mod = modelo.forward_etapa_siguiente(modelo.features[6:](batch_54))
            z_orig = torch.from_numpy(logits_train[top9_local])

            efectos_por_img_x = torch.norm(z_orig - z_mod[0:9], p=2, dim=1).cpu().numpy()
            eff_x = float(np.mean(efectos_por_img_x))

            wins_a = 0
            controles_json: List[Dict[str, Any]] = []
            efectos_y_vals: List[float] = []
            for idx_y, y_raw in enumerate(y_controls, start=1):
                y_id = int(y_raw)
                eff_y = float(
                    torch.norm(
                        z_orig - z_mod[idx_y * 9 : (idx_y + 1) * 9], p=2, dim=1
                    )
                    .mean()
                    .item()
                )
                efectos_y_vals.append(eff_y)
                ratio_xy = eff_x / max(1e-9, eff_y)
                supera = eff_x >= 2.0 * eff_y
                if supera:
                    wins_a += 1
                controles_json.append(
                    {
                        "canal_y": y_id,
                        "activacion_media_abs_train": round(
                            float(mean_abs_f5_train[y_id]), 5
                        ),
                        "efecto_l2_en_top9_de_x": round(eff_y, 5),
                        "ratio_x_vs_y": round(ratio_xy, 4),
                        "supera_2x": bool(supera),
                    }
                )

            confirmada_a = wins_a >= 4
            ratio_medio_a = eff_x / max(1e-9, float(np.mean(efectos_y_vals)))

            # Descubrimiento y etiquetado libre 100% visual en train
            d_tr = 0.35 * (
                Z_train[top9_local].mean(axis=0) - Z_train[bot9_local].mean(axis=0)
            ) + 0.65 * (
                Z_train[top60_local].mean(axis=0) - Z_train[bot60_local].mean(axis=0)
            )
            d_tr[NUM_RASGOS_VISUALES_PUROS:] = 0.0

            pos_axes = [int(i) for i in np.argsort(-d_tr)[:3] if d_tr[i] > 0.15]
            neg_axes = [int(i) for i in np.argsort(d_tr)[:3] if d_tr[i] < -0.15]
            w_tr_check = np.zeros(len(ORDEN_CLAVES_RASGOS), dtype=np.float64)
            pesos_ord = [1.0, 0.78, 0.58]
            for r_i, ax in enumerate(pos_axes):
                w_tr_check[ax] = pesos_ord[r_i]
            for r_i, ax in enumerate(neg_axes):
                w_tr_check[ax] = -pesos_ord[r_i]

            s_tr = Z_train @ w_tr_check
            y_tr_bin = (act_tr >= np.percentile(act_tr, 80.0)).astype(int)
            auc_tr = roc_auc_score_manual(y_tr_bin, s_tr)

            # Sin títulos de obras ni tipos de museo para que la etiqueta exprese solo verbos visuales
            etiqueta = redactar_etiqueta_libre_train(canal, d_tr, auc_tr, [])
            if etiqueta == "no lo sé":
                cnt_no_lo_se += 1

            # Prueba (b) ciega en validación
            scores_val_03 = puntuar_validacion_solo_con_etiqueta(etiqueta, Z_val)
            act_val = pooled_f5_val[:, canal]
            umbral_top20_val = float(np.percentile(act_val, 80.0))
            y_val_bin = (act_val >= umbral_top20_val).astype(int)
            auc_val = (
                roc_auc_score_manual(y_val_bin, scores_val_03)
                if etiqueta != "no lo sé"
                else 0.5
            )
            confirmada_b = (etiqueta != "no lo sé") and (auc_val >= 0.70)
            legible = bool(confirmada_a and confirmada_b and etiqueta != "no lo sé")

            if confirmada_a:
                cnt_pass_a += 1
            if confirmada_b:
                cnt_pass_b += 1
            if legible:
                cnt_legibles += 1
            elif confirmada_a and not confirmada_b:
                cnt_solo_a += 1
            elif confirmada_b and not confirmada_a:
                cnt_solo_b += 1
            else:
                cnt_ni_a_ni_b += 1

            parches_pos: List[Image.Image] = []
            polo_pos_json: List[Dict[str, Any]] = []
            for rank_p, i_loc in enumerate(top9_local, start=1):
                g_idx = train_idx[i_loc]
                mapa_14x14 = f5_train[i_loc, canal]
                u_max, v_max = np.unravel_index(int(np.argmax(mapa_14x14)), (14, 14))
                parches_pos.append(
                    _extraer_parche_receptivo_14x14(
                        imagenes_224_pil[g_idx], int(u_max), int(v_max)
                    )
                )
                polo_pos_json.append(
                    {
                        "rango": rank_p,
                        "id_pieza": corpus_items[g_idx]["id_origen"],
                        "sha256_imagen": corpus_items[g_idx]["sha256"],
                        "url_pagina": corpus_items[g_idx]["url_pagina"],
                        "activacion_media": round(float(act_tr[i_loc]), 5),
                        "activacion_max_celda_14x14": round(
                            float(mapa_14x14[u_max, v_max]), 5
                        ),
                        "celda_14x14": [int(u_max), int(v_max)],
                        "efecto_l2_al_apagar": round(
                            float(efectos_por_img_x[rank_p - 1]), 5
                        ),
                    }
                )
            parches_top9_f5_por_canal[canal] = parches_pos

            parches_neg: List[Image.Image] = []
            polo_neg_json: List[Dict[str, Any]] = []
            for rank_n, i_loc in enumerate(bot9_local, start=1):
                g_idx = train_idx[i_loc]
                mapa_14x14 = f5_train[i_loc, canal]
                u_min, v_min = np.unravel_index(int(np.argmin(mapa_14x14)), (14, 14))
                parches_neg.append(
                    _extraer_parche_receptivo_14x14(
                        imagenes_224_pil[g_idx], int(u_min), int(v_min)
                    )
                )
                polo_neg_json.append(
                    {
                        "rango": rank_n,
                        "id_pieza": corpus_items[g_idx]["id_origen"],
                        "sha256_imagen": corpus_items[g_idx]["sha256"],
                        "url_pagina": corpus_items[g_idx]["url_pagina"],
                        "activacion_media": round(float(act_tr[i_loc]), 5),
                        "activacion_min_celda_14x14": round(
                            float(mapa_14x14[u_min, v_min]), 5
                        ),
                        "celda_14x14": [int(u_min), int(v_min)],
                    }
                )

            id_str = f"neurona_f5_{canal:03d}"
            ruta_mosaico = carpeta_mosaicos_f5 / f"{id_str}.png"
            sha_mosaico = _guardar_mosaico_neurona(
                ruta_mosaico,
                canal=canal,
                etiqueta=etiqueta,
                legible=legible,
                conf_a=confirmada_a,
                conf_b=confirmada_b,
                wins_a=wins_a,
                auc_val=auc_val,
                parches_pos=parches_pos,
                parches_neg=parches_neg,
                acts_pos=[float(act_tr[i]) for i in top9_local],
                acts_neg=[float(act_tr[i]) for i in bot9_local],
            )

            conteo_03 = {
                str(v): int(np.sum(scores_val_03 == v)) for v in (0, 1, 2, 3)
            }

            ficha_pragma_f5 = {
                "schema_version": "3.0.0",
                "id_neurona": id_str,
                "canal_indice": canal,
                "modelo": "convnext_tiny",
                "etapa": "features.5",
                "modalidad_corpus": "cc0_630_train441_val189",
                "etiqueta": etiqueta,
                "etiquetador": "Argon",
                "legible": legible,
                "confirmada": legible,
                "confirmada_a": bool(confirmada_a),
                "confirmada_b": bool(confirmada_b),
                "fecha": FECHA_FASE_5C,
                "sha256_pesos": sha_pesos,
                "licencia_pesos": LICENCIA_TORCHVISION,
                "sha256_prerregistro_v1": sha_v1,
                "sha256_prerregistro_v2": sha_v2,
                "sha256_prerregistro_v3": sha_v3,
                "sha256_corpus_cc0": sha_corpus,
                "sha256_mosaico_local": sha_mosaico,
                "prueba_a_apagado_control_justo": {
                    "etapa_siguiente": "features.6 -> features.7 -> avgpool -> classifier (1000 logits)",
                    "activacion_media_abs_train": round(
                        float(mean_abs_f5_train[canal]), 5
                    ),
                    "efecto_l2_neurona_x_top9_train": round(eff_x, 5),
                    "ratio_medio_x_vs_controles": round(ratio_medio_a, 4),
                    "sorteos_ganados_de_5": wins_a,
                    "minimo_sorteos_requerido": 4,
                    "factor_minimo_efecto": 2.0,
                    "controles_y_sorteados": controles_json,
                    "confirmada_a": bool(confirmada_a),
                },
                "prueba_b_prediccion_validacion_ciega": {
                    "split_evaluado": "validacion (189 imágenes ciegas)",
                    "vocabulario_usado": "38 rasgos visuales y compositivos puros (0 metadatos de museo)",
                    "escala_puntuacion": [0, 1, 2, 3],
                    "conteo_puntuaciones_0_a_3": conteo_03,
                    "positivos_reales_validacion_top20pct": int(np.sum(y_val_bin)),
                    "roc_auc_validacion": auc_val,
                    "umbral_auc_minimo": 0.70,
                    "etiqueta_es_no_lo_se": bool(etiqueta == "no lo sé"),
                    "confirmada_b": bool(confirmada_b),
                },
                "coherencia_descubrimiento_train": {
                    "roc_auc_train": auc_tr,
                    "umbral_claridad_train": 0.64,
                },
                "polo_pos": polo_pos_json,
                "polo_neg": polo_neg_json,
            }

            ruta_ficha = carpeta_atlas_f5_salida / f"{id_str}.json"
            ruta_ficha.write_text(
                json.dumps(ficha_pragma_f5, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            resumen_f5.append(
                {
                    "id_neurona": id_str,
                    "etapa": "features.5",
                    "canal": canal,
                    "etiqueta": etiqueta,
                    "legible": legible,
                    "confirmada_a": bool(confirmada_a),
                    "confirmada_b": bool(confirmada_b),
                    "wins_a": wins_a,
                    "ratio_medio_a": round(ratio_medio_a, 3),
                    "auc_val": auc_val,
                    "auc_tr": auc_tr,
                    "ruta_mosaico": str(ruta_mosaico),
                    "sha256_mosaico": sha_mosaico,
                }
            )

    # Guardar los 5 mejores ejemplos legibles de features.5
    legibles_f5_ord = sorted(
        [r for r in resumen_f5 if r["legible"]],
        key=lambda x: (-x["auc_val"], -x["ratio_medio_a"], x["canal"]),
    )
    cinco_ejemplos_f5: List[Dict[str, Any]] = []
    for idx_ej, ej in enumerate(legibles_f5_ord[:5], start=1):
        src_p = Path(ej["ruta_mosaico"])
        dst_p = carpeta_5_ejemplos_f5 / f"ejemplo_f5_{idx_ej:02d}_{ej['id_neurona']}.png"
        dst_p.write_bytes(src_p.read_bytes())
        cinco_ejemplos_f5.append(
            {
                "orden": idx_ej,
                "id_neurona": ej["id_neurona"],
                "canal": ej["canal"],
                "sorteos_ganados_a": f"{ej['wins_a']}/5",
                "ratio_medio_a": ej["ratio_medio_a"],
                "auc_validacion_b": ej["auc_val"],
                "etiqueta": ej["etiqueta"],
                "archivo_mosaico": str(dst_p),
                "sha256_mosaico": ej["sha256_mosaico"],
            }
        )

    # ================= PARTE 2: PRUEBA CIEGA HUMANA (20 PARES) =================
    cache_f7 = np.load(ruta_cache_f7_npz)
    f7_train = cache_f7["f7_all"][train_idx]

    fichas_f7 = sorted(carpeta_atlas_f7.glob("neurona_*.json"))
    candidatas_legibles: List[Dict[str, Any]] = []
    todas_f7_por_canal: Dict[int, Dict[str, Any]] = {}

    for rf7 in fichas_f7:
        d7 = json.loads(rf7.read_text(encoding="utf-8"))
        c7 = int(d7["canal_indice"])
        todas_f7_por_canal[c7] = d7
        if d7.get("legible"):
            candidatas_legibles.append(
                {
                    "id_neurona": d7["id_neurona"],
                    "etapa": "features.7",
                    "canal": c7,
                    "etiqueta": d7["etiqueta"],
                    "auc_val": d7["prueba_b_prediccion_validacion_ciega"]["roc_auc_validacion"],
                }
            )

    for r5 in sorted(resumen_f5, key=lambda x: x["canal"]):
        if r5["legible"]:
            candidatas_legibles.append(
                {
                    "id_neurona": r5["id_neurona"],
                    "etapa": "features.5",
                    "canal": int(r5["canal"]),
                    "etiqueta": r5["etiqueta"],
                    "auc_val": r5["auc_val"],
                }
            )

    rng_ciega = np.random.default_rng(SEED)
    indices_20 = sorted(
        int(x)
        for x in rng_ciega.choice(len(candidatas_legibles), size=20, replace=False)
    )
    seleccion_20 = [candidatas_legibles[i] for i in indices_20]

    # Pre-extraer parches top-9 para cualquier neurona de features.7 cuando se necesite
    mapa_id_a_train_loc = {
        corpus_items[train_idx[i_loc]]["id_origen"]: i_loc
        for i_loc in range(len(train_idx))
    }

    def obtener_parches_top9_f7(canal_7: int) -> Tuple[List[Image.Image], List[str]]:
        ficha_7 = todas_f7_por_canal[canal_7]
        parches: List[Image.Image] = []
        ids_piezas: List[str] = []
        for item_p in ficha_7["polo_pos"]:
            id_p = item_p["id_pieza"]
            ids_piezas.append(id_p)
            i_loc = mapa_id_a_train_loc[id_p]
            g_idx = train_idx[i_loc]
            u_c, v_c = item_p["celda_7x7"]
            parches.append(_extraer_parche_receptivo_7x7(imagenes_224_pil[g_idx], int(u_c), int(v_c)))
        return parches, ids_piezas

    canales_f7_todos = sorted(todas_f7_por_canal.keys())
    canales_f5_todos = sorted(neuronas_f5_ids)

    pares_publicos_html: List[Dict[str, Any]] = []
    pares_publicos_git: List[Dict[str, Any]] = []
    clave_secreta_pares: List[Dict[str, Any]] = []

    for idx_par, item_real in enumerate(seleccion_20, start=1):
        rng_par = np.random.default_rng(SEED + 1000 + idx_par)
        etapa = item_real["etapa"]
        canal_real = item_real["canal"]

        if etapa == "features.7":
            parches_real, ids_real = obtener_parches_top9_f7(canal_real)
            pool_senuelo = [c for c in canales_f7_todos if c != canal_real]
            orden_cand = rng_par.permutation(pool_senuelo)
            canal_senuelo = int(orden_cand[0])
            for c_cand in orden_cand:
                _, ids_cand = obtener_parches_top9_f7(int(c_cand))
                if len(set(ids_real).intersection(ids_cand)) <= 1:
                    canal_senuelo = int(c_cand)
                    break
            parches_senuelo, _ = obtener_parches_top9_f7(canal_senuelo)
            id_senuelo = f"neurona_{canal_senuelo:03d}"
        else:
            parches_real = parches_top9_f5_por_canal[canal_real]
            ids_real_loc = set(top9_local_f5_por_canal[canal_real])
            pool_senuelo = [c for c in canales_f5_todos if c != canal_real]
            orden_cand = rng_par.permutation(pool_senuelo)
            canal_senuelo = int(orden_cand[0])
            for c_cand in orden_cand:
                if len(ids_real_loc.intersection(top9_local_f5_por_canal[int(c_cand)])) <= 1:
                    canal_senuelo = int(c_cand)
                    break
            parches_senuelo = parches_top9_f5_por_canal[canal_senuelo]
            id_senuelo = f"neurona_f5_{canal_senuelo:03d}"

        bytes_real, sha_real = _renderizar_mosaico_ciego_3x3(parches_real)
        bytes_sen, sha_sen = _renderizar_mosaico_ciego_3x3(parches_senuelo)

        real_en_izquierda = bool(int(rng_par.integers(0, 2)) == 0)
        if real_en_izquierda:
            lado_correcto = "izquierda"
            b64_izq = base64.b64encode(bytes_real).decode("ascii")
            b64_der = base64.b64encode(bytes_sen).decode("ascii")
            sha_izq, sha_der = sha_real, sha_sen
        else:
            lado_correcto = "derecha"
            b64_izq = base64.b64encode(bytes_sen).decode("ascii")
            b64_der = base64.b64encode(bytes_real).decode("ascii")
            sha_izq, sha_der = sha_sen, sha_real

        pares_publicos_html.append(
            {
                "id_par": idx_par,
                "etiqueta": item_real["etiqueta"],
                "sha256_izquierda": sha_izq,
                "sha256_derecha": sha_der,
                "b64_izquierda": b64_izq,
                "b64_derecha": b64_der,
            }
        )
        pares_publicos_git.append(
            {
                "id_par": idx_par,
                "etiqueta": item_real["etiqueta"],
                "sha256_mosaico_izquierda": sha_izq,
                "sha256_mosaico_derecha": sha_der,
            }
        )
        clave_secreta_pares.append(
            {
                "id_par": idx_par,
                "respuesta_correcta": lado_correcto,
                "id_neurona_real": item_real["id_neurona"],
                "etapa": etapa,
                "canal_real": canal_real,
                "id_neurona_senuelo": id_senuelo,
                "canal_senuelo": canal_senuelo,
                "sha256_mosaico_real": sha_real,
                "sha256_mosaico_senuelo": sha_sen,
                "sha256_izquierda": sha_izq,
                "sha256_derecha": sha_der,
            }
        )

    carpeta_prueba_ciega_local.mkdir(parents=True, exist_ok=True)
    ruta_html = carpeta_prueba_ciega_local / "prueba_ciega_20_pares.html"
    _generar_html_prueba_ciega(ruta_html, pares_publicos_html)
    sha_html = hashlib.sha256(ruta_html.read_bytes()).hexdigest()

    ruta_clave = carpeta_prueba_ciega_local / "clave_secreta_no_abrir.json"
    obj_clave = {
        "fase": "FASE 5c · Clave secreta de la prueba ciega humana (20 pares)",
        "advertencia": "ARCHIVO SECRETO DE CORRECCIÓN: Bruno no debe abrir este archivo antes de responder.",
        "semilla": SEED,
        "total_pares": 20,
        "umbral_acierto_significativo": 15,
        "p_valor_binomial_15_de_20": 0.020694732666015625,
        "sha256_html_prueba": sha_html,
        "pares": clave_secreta_pares,
    }
    ruta_clave.write_text(
        json.dumps(obj_clave, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sha_clave = hashlib.sha256(ruta_clave.read_bytes()).hexdigest()

    ruta_diseno_git = ruta_prerregistro_v3.parent / "diseno_prueba_ciega_20_pares.json"
    obj_diseno_git = {
        "fase": "FASE 5c · Diseño público de la prueba ciega (20 pares, sin respuestas ni imágenes)",
        "semilla": SEED,
        "total_candidatas_legibles_pool": len(candidatas_legibles),
        "legibles_features_7_pool": 26,
        "legibles_features_5_pool": cnt_legibles,
        "num_pares_sorteados": 20,
        "umbral_acierto_humano": "15/20 (p = 0.02069 < 0.05 frente al azar)",
        "ruta_pagina_html_local": str(ruta_html),
        "sha256_pagina_html_local": sha_html,
        "sha256_clave_secreta_local": sha_clave,
        "pares_publicos": pares_publicos_git,
    }
    ruta_diseno_git.write_text(
        json.dumps(obj_diseno_git, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    total_n = len(neuronas_f5_ids)
    ic_leg = intervalo_confianza_wilson_95(cnt_legibles, total_n)
    ic_solo_a = intervalo_confianza_wilson_95(cnt_solo_a, total_n)
    ic_solo_b = intervalo_confianza_wilson_95(cnt_solo_b, total_n)
    ic_pass_a = intervalo_confianza_wilson_95(cnt_pass_a, total_n)
    ic_pass_b = intervalo_confianza_wilson_95(cnt_pass_b, total_n)

    informe = {
        "fase": "FASE 5c · Capa media features.5 + Prueba ciega humana (20 pares)",
        "fecha": FECHA_FASE_5C,
        "sha256_prerregistro_v3": sha_v3,
        "features_5": {
            "etapa": "features.5 (Stage 3, 384 canales, 14x14)",
            "total_neuronas": total_n,
            "legibles_a_y_b": {
                "conteo": cnt_legibles,
                "porcentaje": round(cnt_legibles * 100.0 / total_n, 2),
                "ic_95_wilson_pct": [round(ic_leg[0] * 100.0, 2), round(ic_leg[1] * 100.0, 2)],
            },
            "solo_a": {
                "conteo": cnt_solo_a,
                "porcentaje": round(cnt_solo_a * 100.0 / total_n, 2),
                "ic_95_wilson_pct": [
                    round(ic_solo_a[0] * 100.0, 2),
                    round(ic_solo_a[1] * 100.0, 2),
                ],
            },
            "solo_b": {
                "conteo": cnt_solo_b,
                "porcentaje": round(cnt_solo_b * 100.0 / total_n, 2),
                "ic_95_wilson_pct": [
                    round(ic_solo_b[0] * 100.0, 2),
                    round(ic_solo_b[1] * 100.0, 2),
                ],
            },
            "total_pasan_a": {
                "conteo": cnt_pass_a,
                "porcentaje": round(cnt_pass_a * 100.0 / total_n, 2),
                "ic_95_wilson_pct": [
                    round(ic_pass_a[0] * 100.0, 2),
                    round(ic_pass_a[1] * 100.0, 2),
                ],
            },
            "total_pasan_b": {
                "conteo": cnt_pass_b,
                "porcentaje": round(cnt_pass_b * 100.0 / total_n, 2),
                "ic_95_wilson_pct": [
                    round(ic_pass_b[0] * 100.0, 2),
                    round(ic_pass_b[1] * 100.0, 2),
                ],
            },
            "ni_a_ni_b": cnt_ni_a_ni_b,
            "etiqueta_no_lo_se": cnt_no_lo_se,
            "cinco_ejemplos_legibles": cinco_ejemplos_f5,
        },
        "prueba_ciega_bruno": {
            "ruta_html": str(ruta_html),
            "sha256_html": sha_html,
            "ruta_clave_secreta": str(ruta_clave),
            "sha256_clave_secreta": sha_clave,
            "num_pares": 20,
            "de_features_7": sum(1 for x in seleccion_20 if x["etapa"] == "features.7"),
            "de_features_5": sum(1 for x in seleccion_20 if x["etapa"] == "features.5"),
        },
    }
    return informe


def main(argv: List[str] | None = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Ejecuta FASE 5c: Atlas de capa media features.5 + Prueba ciega de 20 pares."
    )
    parser.add_argument("--prerregistro-v3", default=str(base_dir / "prerregistro_v3.json"))
    parser.add_argument("--prerregistro-v2", default=str(base_dir / "prerregistro_v2.json"))
    parser.add_argument("--prerregistro-v1", default=str(base_dir / "prerregistro.json"))
    parser.add_argument("--corpus-json", default=str(base_dir / "corpus_cc0_630.json"))
    parser.add_argument("--pesos", default="/tmp/neuronas_pesos/convnext_tiny-983f1562.pth")
    parser.add_argument(
        "--imagenes-cc0",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/corpus-neuronas-cc0/imagenes",
    )
    parser.add_argument("--atlas-f7", default=str(base_dir / "atlas"))
    parser.add_argument("--salida-atlas-f5", default=str(base_dir / "atlas_f5"))
    parser.add_argument(
        "--salida-mosaicos",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/neuronas-mosaicos",
    )
    parser.add_argument(
        "--salida-prueba-ciega",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/prueba-ciega-bruno",
    )
    parser.add_argument("--cache-f5-npz", default="/tmp/cache_f5_630.npz")
    parser.add_argument("--cache-f7-npz", default="/tmp/cache_630.npz")
    args = parser.parse_args(argv)

    informe = ejecutar_fase5c(
        ruta_prerregistro_v3=Path(args.prerregistro_v3).expanduser().resolve(),
        ruta_prerregistro_v2=Path(args.prerregistro_v2).expanduser().resolve(),
        ruta_prerregistro_v1=Path(args.prerregistro_v1).expanduser().resolve(),
        ruta_corpus_json=Path(args.corpus_json).expanduser().resolve(),
        ruta_pesos=Path(args.pesos).expanduser().resolve(),
        carpeta_imagenes_cc0=Path(args.imagenes_cc0).expanduser().resolve(),
        carpeta_atlas_f7=Path(args.atlas_f7).expanduser().resolve(),
        carpeta_atlas_f5_salida=Path(args.salida_atlas_f5).expanduser().resolve(),
        carpeta_mosaicos_local=Path(args.salida_mosaicos).expanduser().resolve(),
        carpeta_prueba_ciega_local=Path(args.salida_prueba_ciega).expanduser().resolve(),
        ruta_cache_f5_npz=Path(args.cache_f5_npz),
        ruta_cache_f7_npz=Path(args.cache_f7_npz),
    )
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
