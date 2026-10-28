#!/usr/bin/env python3
"""FASE 5d (v3c) · «El salón»: generador con visto bueno condicional de Claude (CPU, 0 Colab).

Lee lab/neuronas/prerregistro_v3c.json (sha256 = 90e0aa75...) y genera:
1. Un único archivo HTML móvil y autocontenido (sin internet, apto para WhatsApp/AirDrop) en:
   ~/Desktop/REFERENTES/el-salon/salon_sensaciones.html
   con los tres cambios condicionales de Claude:
   - Cambio 1 (Control de brillo): guarda en la clave secreta el ΔL* (CIE Lab) y qué polo
     (`polo_pos` o `polo_neg`) es el más claro y cuál el más oscuro para cada par.
   - Cambio 2 (Sorteo izquierda/derecha por persona desde el apodo): la página calcula una
     semilla determinista FNV-1a a partir del `apodo` + 2810 y sortea con PRNG `mulberry32`
     la posición izquierda/derecha de forma equilibrada (10/10 en las 20 neuronas, 2/2 en
     controles, 1/1 en atención, 6/6 en Parte 1, 3/3 en Parte 3) para cada persona, guardando
     en el JSON descargado `semilla_apodo`, `lado_polo_pos_mostrado`,
     `sha256_mostrado_izquierda`, `sha256_mostrado_derecha` y `eleccion`.
   - Cambio 3 (♥ de Bruno separados de los demás): etiqueta explícitamente en el JSON si el
     participante es Bruno (`es_bruno_n2_d8`) para que `analizar_salon.py` cuente para N-2 y
     D-8 exclusivamente los ♥ de Bruno y guarde los de los demás en archivo aparte.
2. La clave secreta en ~/Desktop/REFERENTES/el-salon/clave_salon_no_abrir.json.
3. Las 3 capturas de muestra en ~/Desktop/REFERENTES/el-salon/ejemplos_claude/.
4. El manifiesto público `lab/neuronas/diseno_salon_v3b.json` en Git.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True

SHA256_PRERREG_V3B_ESPERADO = (
    "0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa"
)
SHA256_PRERREG_V3C_ESPERADO = (
    "90e0aa75132c4742bf6dac453dc3f830e39f8748b8e71e394b43d8487ea11bd5"
)


def calcular_semilla_apodo(apodo: str, semilla_base: int = 2810) -> int:
    """Hash FNV-1a de 32 bits determinista (idéntico en Python y en JavaScript) a partir del apodo."""
    limpio = apodo.strip().lower()
    h = 2166136261
    for ch in limpio.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return (h + semilla_base) & 0xFFFFFFFF


def sortear_lados_equilibrados_mulberry32(semilla: int, n_pares: int) -> List[str]:
    """Replica exactamente en Python el sorteo equilibrado (mitad izquierda, mitad derecha)
    ejecutado por mulberry32 en el navegador del participante."""
    mitad = n_pares // 2
    arr = ["izquierda"] * mitad + ["derecha"] * (n_pares - mitad)
    state = semilla & 0xFFFFFFFF

    def next_float() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        res = (t ^ (t >> 14)) & 0xFFFFFFFF
        return res / 4294967296.0

    for i in range(len(arr) - 1, 0, -1):
        j = int(next_float() * (i + 1))
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def _rgb_to_lab_mean(im_pil: Image.Image) -> np.ndarray:
    arr = (
        np.asarray(im_pil.convert("RGB").resize((112, 112)), dtype=np.float64) / 255.0
    )
    mask = arr > 0.04045
    lin = np.where(mask, ((arr + 0.055) / 1.055) ** 2.4, arr / 12.92)
    R, G, B = lin[:, :, 0], lin[:, :, 1], lin[:, :, 2]
    X = (0.4124564 * R + 0.3575761 * G + 0.1804375 * B) / 0.95047
    Y = (0.2126729 * R + 0.7151522 * G + 0.0721750 * B) / 1.00000
    Z = (0.0193339 * R + 0.1191920 * G + 0.9503041 * B) / 1.08883

    def f(t: np.ndarray) -> np.ndarray:
        return np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16.0 / 116.0)

    fx, fy, fz = f(X), f(Y), f(Z)
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return np.array([float(L.mean()), float(a.mean()), float(b.mean())])


def _recortar_224(im_pil: Image.Image) -> Image.Image:
    w0, h0 = im_pil.size
    if w0 < h0:
        nw = 236
        nh = max(236, int(round(h0 * 236.0 / w0)))
    else:
        nh = 236
        nw = max(236, int(round(w0 * 236.0 / h0)))
    im_236 = im_pil.resize((nw, nh), Image.Resampling.BILINEAR)
    left = (nw - 224) // 2
    top = (nh - 224) // 2
    return im_236.crop((left, top, left + 224, top + 224))


def _renderizar_mosaico_3x3_jpeg(
    imagenes_9: List[Image.Image], calidad: int = 84
) -> Tuple[bytes, str, Image.Image]:
    celda = 96
    gap = 5
    pad = 8
    W = pad * 2 + 3 * celda + 2 * gap
    H = W
    lienzo = Image.new("RGB", (W, H), (20, 22, 27))
    draw = ImageDraw.Draw(lienzo)
    for idx in range(9):
        r = idx // 3
        c = idx % 3
        x0 = pad + c * (celda + gap)
        y0 = pad + r * (celda + gap)
        tile = imagenes_9[idx].resize((celda, celda), Image.Resampling.BILINEAR)
        lienzo.paste(tile, (x0, y0))
        draw.rectangle(
            [x0, y0, x0 + celda - 1, y0 + celda - 1], outline=(64, 70, 82), width=1
        )
    buf = io.BytesIO()
    lienzo.save(buf, format="JPEG", quality=calidad)
    raw = buf.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    return raw, sha, lienzo


def _renderizar_miniatura_obra_jpeg(
    im_224: Image.Image, tam: int = 168, calidad: int = 82
) -> Tuple[bytes, str]:
    im_res = im_224.resize((tam, tam), Image.Resampling.BILINEAR)
    buf = io.BytesIO()
    im_res.save(buf, format="JPEG", quality=calidad)
    raw = buf.getvalue()
    return raw, hashlib.sha256(raw).hexdigest()


def _guardar_captura_par_claude(
    ruta_png: Path,
    num_ejemplo: int,
    pregunta: str,
    eje: str,
    id_neurona: str,
    delta_e: float,
    lado_predicho: str,
    img_izq: Image.Image,
    img_der: Image.Image,
) -> str:
    W = 720
    H = 470
    lienzo = Image.new("RGB", (W, H), (17, 19, 24))
    draw = ImageDraw.Draw(lienzo)
    font = ImageFont.load_default()
    for r_ttf in sorted(
        Path(
            "/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/corpus-editorial/muestras"
        ).glob("*.ttf")
    ):
        try:
            font = ImageFont.truetype(str(r_ttf), 14)
            break
        except Exception:
            pass

    draw.rounded_rectangle(
        [16, 14, W - 16, 86],
        radius=10,
        fill=(27, 31, 39),
        outline=(46, 52, 64),
        width=1,
    )
    draw.text(
        (32, 22),
        f"EL SALÓN · Parte 2 (Sentir) · Ejemplo #{num_ejemplo} para revisión de Claude",
        fill=(136, 192, 208),
        font=font,
    )
    draw.text(
        (32, 43),
        f"Pregunta en pantalla: «{pregunta}»",
        fill=(236, 239, 244),
        font=font,
    )
    draw.text(
        (32, 64),
        f"[Eje: {eje} | Neurona: {id_neurona} | Contraste CIE Lab dE={delta_e:.2f} | Predice: {lado_predicho.upper()}]",
        fill=(163, 190, 140),
        font=font,
    )

    tam_m = 304
    izq_res = img_izq.resize((tam_m, tam_m), Image.Resampling.BILINEAR)
    der_res = img_der.resize((tam_m, tam_m), Image.Resampling.BILINEAR)

    x_izq = 34
    x_der = W - 34 - tam_m
    y_mos = 104

    lienzo.paste(izq_res, (x_izq, y_mos))
    lienzo.paste(der_res, (x_der, y_mos))

    col_izq = (163, 190, 140) if lado_predicho == "izquierda" else (76, 86, 106)
    col_der = (163, 190, 140) if lado_predicho == "derecha" else (76, 86, 106)
    draw.rectangle(
        [x_izq - 2, y_mos - 2, x_izq + tam_m + 1, y_mos + tam_m + 1],
        outline=col_izq,
        width=2,
    )
    draw.rectangle(
        [x_der - 2, y_mos - 2, x_der + tam_m + 1, y_mos + tam_m + 1],
        outline=col_der,
        width=2,
    )

    draw.rounded_rectangle(
        [x_izq, y_mos + tam_m + 12, x_izq + tam_m, H - 14],
        radius=8,
        fill=(37, 43, 55),
        outline=col_izq,
        width=1,
    )
    draw.text(
        (x_izq + 92, y_mos + tam_m + 24),
        "Opción A · IZQUIERDA",
        fill=(236, 239, 244),
        font=font,
    )

    draw.rounded_rectangle(
        [x_der, y_mos + tam_m + 12, x_der + tam_m, H - 14],
        radius=8,
        fill=(37, 43, 55),
        outline=col_der,
        width=1,
    )
    draw.text(
        (x_der + 98, y_mos + tam_m + 24),
        "Opción B · DERECHA",
        fill=(236, 239, 244),
        font=font,
    )

    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    lienzo.save(ruta_png, format="PNG")
    return hashlib.sha256(ruta_png.read_bytes()).hexdigest()


def _construir_html_salon_v3c(
    ruta_html: Path,
    parte1_raw: List[Dict[str, Any]],
    neuronas20_raw: List[Dict[str, Any]],
    controles4_raw: List[Dict[str, Any]],
    atencion2_raw: List[Dict[str, Any]],
    parte3_raw: List[Dict[str, Any]],
    parte4_raw: List[Dict[str, Any]],
) -> None:
    payload_json = json.dumps(
        {
            "parte1_raw": parte1_raw,
            "neuronas20_raw": neuronas20_raw,
            "controles4_raw": controles4_raw,
            "atencion2_raw": atencion2_raw,
            "parte3_raw": parte3_raw,
            "parte4_raw": parte4_raw,
        },
        ensure_ascii=False,
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>El Salón · Prueba de Sensaciones Visuales (v3c)</title>
<style>
  :root {{
    --bg: #111318;
    --card: #1b1f27;
    --border: #2e3440;
    --text: #eceff4;
    --muted: #a3abb8;
    --accent: #88c0d0;
    --ok: #a3be8c;
    --heart: #bf616a;
  }}
  * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
  body {{
    margin: 0;
    padding: 14px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.45;
  }}
  .app {{ max-width: 680px; margin: 0 auto; }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 16px;
  }}
  h1 {{ font-size: 21px; margin: 0 0 8px 0; }}
  h2 {{ font-size: 18px; margin: 0 0 8px 0; color: var(--accent); }}
  p {{ margin: 0 0 12px 0; font-size: 15px; color: var(--muted); }}
  .question-box {{
    font-size: 19px;
    font-weight: 700;
    color: var(--text);
    background: #14171e;
    border-left: 4px solid var(--accent);
    padding: 12px 14px;
    border-radius: 8px;
    margin: 10px 0 14px 0;
  }}
  .pair-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }}
  @media (max-width: 480px) {{
    .pair-grid {{ grid-template-columns: 1fr 1fr; gap: 8px; }}
  }}
  .mosaic-btn {{
    background: #151820;
    border: 2px solid var(--border);
    border-radius: 12px;
    padding: 8px;
    text-align: center;
    cursor: pointer;
    user-select: none;
  }}
  .mosaic-btn:active, .mosaic-btn.selected {{
    border-color: var(--ok);
    background: #1d2620;
  }}
  .mosaic-btn img {{
    width: 100%;
    height: auto;
    border-radius: 8px;
    display: block;
    margin-bottom: 8px;
  }}
  .side-label {{
    display: inline-block;
    padding: 8px 14px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 15px;
    background: #252b37;
    color: var(--text);
    width: 100%;
  }}
  .btn-primary {{
    background: var(--accent);
    color: #111318;
    border: none;
    padding: 12px 20px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 16px;
    width: 100%;
    cursor: pointer;
    margin-top: 10px;
  }}
  .btn-ok {{
    background: var(--ok);
    color: #111318;
    border: none;
    padding: 14px 20px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 16px;
    width: 100%;
    cursor: pointer;
    margin-top: 10px;
  }}
  input[type="text"], input[type="number"], select, textarea {{
    width: 100%;
    padding: 11px 12px;
    background: #12151b;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: 16px;
    margin-bottom: 12px;
  }}
  .timer-bar {{
    height: 6px;
    background: var(--accent);
    border-radius: 4px;
    transition: width 0.1s linear;
    margin-bottom: 10px;
  }}
  .hidden-curtain {{
    height: 210px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #14171e;
    border: 1px dashed var(--border);
    border-radius: 8px;
    margin-bottom: 8px;
    color: var(--muted);
    font-weight: 600;
    font-size: 14px;
    padding: 12px;
  }}
  .tinder-card {{ text-align: center; padding: 12px; }}
  .tinder-card img {{
    width: 100%;
    max-width: 280px;
    border-radius: 12px;
    border: 1px solid var(--border);
    margin: 0 auto 14px auto;
    display: block;
  }}
  .tinder-actions {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }}
  .btn-pass {{
    background: #2e3440;
    color: var(--text);
    border: 1px solid #4c566a;
    padding: 14px;
    border-radius: 12px;
    font-size: 18px;
    font-weight: 700;
    cursor: pointer;
  }}
  .btn-heart {{
    background: var(--heart);
    color: #fff;
    border: none;
    padding: 14px;
    border-radius: 12px;
    font-size: 18px;
    font-weight: 700;
    cursor: pointer;
  }}
  .top-pill {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    color: var(--muted);
    margin-bottom: 8px;
  }}
</style>
</head>
<body>
<div class="app" id="app-root"></div>

<script>
const RAW = {payload_json};

function calcularSemillaApodo(apodo) {{
  const limpio = (apodo || "").trim().toLowerCase();
  const bytes = new TextEncoder().encode(limpio);
  let h = 2166136261 >>> 0;
  for (let i = 0; i < bytes.length; i++) {{
    h ^= bytes[i];
    h = Math.imul(h, 16777619) >>> 0;
  }}
  return (h + 2810) >>> 0;
}}

function sortearLadosEquilibrados(semilla, nPares) {{
  const mitad = Math.floor(nPares / 2);
  const arr = [];
  for (let i = 0; i < mitad; i++) arr.push("izquierda");
  for (let i = mitad; i < nPares; i++) arr.push("derecha");
  let st = semilla >>> 0;
  function nextFloat() {{
    st = (st + 0x6D2B79F5) >>> 0;
    let t = st;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ (t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0))) >>> 0;
    const res = (t ^ (t >>> 14)) >>> 0;
    return res / 4294967296.0;
  }}
  for (let i = arr.length - 1; i > 0; i--) {{
    const j = Math.floor(nextFloat() * (i + 1));
    const tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
  }}
  return arr;
}}

function armarParConLado(rawItem, ladoPoloPos) {{
  if (ladoPoloPos === "izquierda") {{
    return {{
      ...rawItem,
      lado_polo_pos_mostrado: "izquierda",
      b64_izquierda: rawItem.b64_polo_pos,
      b64_derecha: rawItem.b64_polo_neg,
      sha256_mostrado_izquierda: rawItem.sha256_polo_pos,
      sha256_mostrado_derecha: rawItem.sha256_polo_neg
    }};
  }}
  return {{
    ...rawItem,
    lado_polo_pos_mostrado: "derecha",
    b64_izquierda: rawItem.b64_polo_neg,
    b64_derecha: rawItem.b64_polo_pos,
    sha256_mostrado_izquierda: rawItem.sha256_polo_neg,
    sha256_mostrado_derecha: rawItem.sha256_polo_pos
  }};
}}

let DATA = {{ parte1: [], parte2: [], parte3: [], parte4: RAW.parte4_raw }};

let state = {{
  step: "parte0",
  apodo: "",
  semilla_apodo: 0,
  edad_aprox: "",
  trabaja_diseno: "",
  consiente: false,
  idx1: 0,
  oculto1: false,
  tStart1: 0,
  timer1: null,
  resp1: [],
  idx2: 0,
  tStart2: 0,
  resp2: [],
  idx3: 0,
  resp3: [],
  idx4: 0,
  resp4: [],
  corazones: 0,
  comentario_cierre: ""
}};

function prepararSesionParaApodo(apodo) {{
  const seed = calcularSemillaApodo(apodo);
  state.semilla_apodo = seed;

  const lados1 = sortearLadosEquilibrados((seed + 101) >>> 0, RAW.parte1_raw.length);
  DATA.parte1 = RAW.parte1_raw.map((it, i) => armarParConLado(it, lados1[i]));

  const lados20 = sortearLadosEquilibrados(seed, RAW.neuronas20_raw.length);
  const n20 = RAW.neuronas20_raw.map((it, i) => armarParConLado(it, lados20[i]));

  const ladosCtrl = sortearLadosEquilibrados((seed + 202) >>> 0, RAW.controles4_raw.length);
  const c4 = RAW.controles4_raw.map((it, i) => armarParConLado(it, ladosCtrl[i]));

  const ladosAt = sortearLadosEquilibrados((seed + 303) >>> 0, RAW.atencion2_raw.length);
  const a2 = RAW.atencion2_raw.map((it, i) => armarParConLado(it, ladosAt[i]));

  const p2 = n20.slice();
  p2.splice(4, 0, c4[0]);
  p2.splice(8, 0, a2[0]);
  p2.splice(12, 0, c4[1]);
  p2.splice(17, 0, c4[2]);
  p2.splice(20, 0, a2[1]);
  p2.splice(24, 0, c4[3]);
  DATA.parte2 = p2;

  const lados3 = sortearLadosEquilibrados((seed + 404) >>> 0, RAW.parte3_raw.length);
  DATA.parte3 = RAW.parte3_raw.map((it, i) => armarParConLado(it, lados3[i]));
}}

function render() {{
  const root = document.getElementById("app-root");
  if (state.step === "parte0") {{
    root.innerHTML = `
      <div class="card">
        <h1>El Salón · Prueba de Sensaciones</h1>
        <p>¡Hola! Esta sesión dura unos <strong>10 minutos</strong> en tu celular. Queremos saber qué te transmiten distintas imágenes a simple vista.</p>
        <p>• Es <strong>100% anónimo</strong>.<br>• <strong>No hay respuestas buenas ni malas</strong>: importa lo que tú sientas.<br>• Puedes parar y salir cuando quieras.</p>
        <label style="font-size:14px;font-weight:600;">Tu apodo o iniciales:</label>
        <input type="text" id="in-apodo" placeholder="Ej. Bruno, Majo, Invitado1..." value="${{state.apodo}}">
        <label style="font-size:14px;font-weight:600;">Edad aproximada:</label>
        <input type="number" id="in-edad" placeholder="Ej. 32" value="${{state.edad_aprox}}">
        <label style="font-size:14px;font-weight:600;">¿Trabajas o estudias en diseño, arquitectura o arte?</label>
        <select id="in-diseno">
          <option value="">Selecciona una opción...</option>
          <option value="si" ${{state.trabaja_diseno === 'si' ? 'selected' : ''}}>Sí (diseño / arte)</option>
          <option value="no" ${{state.trabaja_diseno === 'no' ? 'selected' : ''}}>No (otro campo)</option>
        </select>
        <label style="display:flex;align-items:center;gap:10px;font-size:14px;margin:8px 0 14px 0;cursor:pointer;">
          <input type="checkbox" id="in-consent" style="width:20px;height:20px;" ${{state.consiente ? 'checked' : ''}}>
          <span>Acepto participar de forma voluntaria y anónima.</span>
        </label>
        <button class="btn-primary" onclick="iniciarParte1()">Empezar Parte 1 (Primer golpe de vista)</button>
      </div>
    `;
    return;
  }}

  if (state.step === "parte1") {{
    const item = DATA.parte1[state.idx1];
    root.innerHTML = `
      <div class="card">
        <div class="top-pill">
          <span>Parte 1 de 4 · Primer golpe de vista (5 s)</span>
          <span>Par ${{state.idx1 + 1}} / ${{DATA.parte1.length}}</span>
        </div>
        <div class="timer-bar" id="bar-5s" style="width:${{state.oculto1 ? '0%' : '100%'}};"></div>
        <div class="question-box">${{item.pregunta}}</div>
        <p style="font-size:13px;">Mira ambos lados durante 5 segundos y toca el que más se te haya quedado en la cabeza.</p>
        <div class="pair-grid">
          <div class="mosaic-btn" onclick="responderParte1('izquierda')">
            ${{state.oculto1
              ? '<div class="hidden-curtain">Tiempo cumplido (5 s)<br>Toca para elegir IZQUIERDA</div>'
              : `<img src="data:image/jpeg;base64,${{item.b64_izquierda}}" alt="Izquierda">`}}
            <span class="side-label">👈 Izquierda</span>
          </div>
          <div class="mosaic-btn" onclick="responderParte1('derecha')">
            ${{state.oculto1
              ? '<div class="hidden-curtain">Tiempo cumplido (5 s)<br>Toca para elegir DERECHA</div>'
              : `<img src="data:image/jpeg;base64,${{item.b64_derecha}}" alt="Derecha">`}}
            <span class="side-label">Derecha 👉</span>
          </div>
        </div>
      </div>
    `;
    return;
  }}

  if (state.step === "parte2") {{
    const item = DATA.parte2[state.idx2];
    root.innerHTML = `
      <div class="card">
        <div class="top-pill">
          <span>Parte 2 de 4 · Sentir</span>
          <span>Par ${{state.idx2 + 1}} / ${{DATA.parte2.length}}</span>
        </div>
        <div class="question-box">${{item.pregunta}}</div>
        <div class="pair-grid">
          <div class="mosaic-btn" onclick="responderParte2('izquierda')">
            <img src="data:image/jpeg;base64,${{item.b64_izquierda}}" alt="Izquierda">
            <span class="side-label">👈 Izquierda</span>
          </div>
          <div class="mosaic-btn" onclick="responderParte2('derecha')">
            <img src="data:image/jpeg;base64,${{item.b64_derecha}}" alt="Derecha">
            <span class="side-label">Derecha 👉</span>
          </div>
        </div>
      </div>
    `;
    return;
  }}

  if (state.step === "parte3") {{
    const item = DATA.parte3[state.idx3];
    root.innerHTML = `
      <div class="card">
        <div class="top-pill">
          <span>Parte 3 de 4 · Ponerle nombre</span>
          <span>Par ${{state.idx3 + 1}} / ${{DATA.parte3.length}}</span>
        </div>
        <div class="question-box">${{item.pregunta}}</div>
        <div class="pair-grid" style="margin-bottom:14px;">
          <div class="mosaic-btn" style="cursor:default;">
            <img src="data:image/jpeg;base64,${{item.b64_izquierda}}" alt="Izquierda">
            <span class="side-label">Lado Izquierdo</span>
          </div>
          <div class="mosaic-btn" style="cursor:default;">
            <img src="data:image/jpeg;base64,${{item.b64_derecha}}" alt="Derecha">
            <span class="side-label">Lado Derecho</span>
          </div>
        </div>
        <input type="text" id="in-nombre3" placeholder="Escribe 2 o 3 palabras (ej. oscuro vs brillante, quieto vs movido)...">
        <button class="btn-primary" onclick="responderParte3()">Siguiente</button>
      </div>
    `;
    return;
  }}

  if (state.step === "parte4") {{
    const item = DATA.parte4[state.idx4];
    root.innerHTML = `
      <div class="card">
        <div class="top-pill">
          <span>Parte 4 de 4 · Gusto personal (♥: ${{state.corazones}})</span>
          <span>Imagen ${{state.idx4 + 1}} / ${{DATA.parte4.length}}</span>
        </div>
        <div class="question-box" style="font-size:17px;">¿Te gusta esta pieza para tu tablero visual?</div>
        <div class="tinder-card">
          <img src="data:image/jpeg;base64,${{item.b64_img}}" alt="Obra">
          <div class="tinder-actions">
            <button class="btn-pass" onclick="responderParte4(false)">✕ Paso</button>
            <button class="btn-heart" onclick="responderParte4(true)">♥ Me gusta</button>
          </div>
        </div>
      </div>
    `;
    return;
  }}

  if (state.step === "cierre") {{
    const payload = construirResultadoFinal();
    const jsonStr = JSON.stringify(payload, null, 2);
    root.innerHTML = `
      <div class="card">
        <h2>¡Muchas gracias, ${{state.apodo}}!</h2>
        <p><strong>¿Para qué era este experimento? (Transparencia sin engaño):</strong> Estamos estudiando si las unidades internas («neuronas») de un modelo de visión por computador agrupan las imágenes según sensaciones que cualquier persona percibe a simple vista (como calidez, orden, peso o calma), y reuniendo tus ♥ (${{state.corazones}} marcados).</p>
        <label style="font-size:14px;font-weight:600;">Última pregunta abierta: ¿Qué te sorprendió de la sesión?</label>
        <textarea id="in-cierre" rows="3" placeholder="Escribe libremente (opcional)..." oninput="actualizarCierre(this.value)">${{state.comentario_cierre}}</textarea>
        <button class="btn-ok" onclick="descargarJSON()">📥 Descargar mis respuestas (.json)</button>
        <button class="btn-primary" onclick="compartirJSON()" style="margin-top:8px;">📤 Compartir por WhatsApp / AirDrop</button>
        <p style="font-size:12px;margin-top:12px;">Si estás en celular, envía el archivo descargado a Bruno para que lo guarde en la carpeta de respuestas del salón.</p>
        <textarea id="out-json-box" rows="5" readonly style="font-family:monospace;font-size:11px;margin-top:8px;">${{jsonStr}}</textarea>
      </div>
    `;
    return;
  }}
}}

function iniciarParte1() {{
  const apodo = (document.getElementById("in-apodo").value || "").trim();
  const edad = (document.getElementById("in-edad").value || "").trim();
  const diseno = document.getElementById("in-diseno").value;
  const consent = document.getElementById("in-consent").checked;
  if (!apodo) {{ alert("Por favor escribe un apodo."); return; }}
  if (!edad) {{ alert("Por favor indica tu edad aproximada."); return; }}
  if (!diseno) {{ alert("Por favor indica si trabajas en diseño/arte (sí/no)."); return; }}
  if (!consent) {{ alert("Debes aceptar participar voluntariamente para continuar."); return; }}
  state.apodo = apodo;
  state.edad_aprox = parseInt(edad, 10) || edad;
  state.trabaja_diseno = diseno;
  state.consiente = true;
  prepararSesionParaApodo(apodo);
  state.step = "parte1";
  state.idx1 = 0;
  lanzarRelojParte1();
}}

function lanzarRelojParte1() {{
  if (state.timer1) clearTimeout(state.timer1);
  state.oculto1 = false;
  state.tStart1 = performance.now();
  render();
  state.timer1 = setTimeout(() => {{
    state.oculto1 = true;
    render();
  }}, 5000);
}}

function responderParte1(lado) {{
  if (state.timer1) clearTimeout(state.timer1);
  const elapsed = Math.round(performance.now() - state.tStart1);
  const item = DATA.parte1[state.idx1];
  state.resp1.push({{
    orden: item.orden,
    id_item: item.id_item,
    semilla_apodo: state.semilla_apodo,
    lado_polo_pos_mostrado: item.lado_polo_pos_mostrado,
    sha256_mostrado_izquierda: item.sha256_mostrado_izquierda,
    sha256_mostrado_derecha: item.sha256_mostrado_derecha,
    eleccion: lado,
    tiempo_ms: elapsed,
    respondio_tras_ocultar_5s: state.oculto1
  }});
  state.idx1++;
  if (state.idx1 < DATA.parte1.length) {{
    lanzarRelojParte1();
  }} else {{
    state.step = "parte2";
    state.idx2 = 0;
    state.tStart2 = performance.now();
    render();
  }}
}}

function responderParte2(lado) {{
  const elapsed = Math.round(performance.now() - state.tStart2);
  const item = DATA.parte2[state.idx2];
  state.resp2.push({{
    orden_presentacion: state.idx2 + 1,
    id_item: item.id_item,
    tipo_item: item.tipo_item,
    pregunta: item.pregunta,
    semilla_apodo: state.semilla_apodo,
    lado_polo_pos_mostrado: item.lado_polo_pos_mostrado,
    sha256_mostrado_izquierda: item.sha256_mostrado_izquierda,
    sha256_mostrado_derecha: item.sha256_mostrado_derecha,
    eleccion: lado,
    tiempo_ms: elapsed
  }});
  state.idx2++;
  if (state.idx2 < DATA.parte2.length) {{
    state.tStart2 = performance.now();
    render();
  }} else {{
    state.step = "parte3";
    state.idx3 = 0;
    render();
  }}
}}

function responderParte3() {{
  const txt = (document.getElementById("in-nombre3").value || "").trim();
  if (!txt) {{ alert("Escribe 2 o 3 palabras para describir la diferencia."); return; }}
  const item = DATA.parte3[state.idx3];
  state.resp3.push({{
    orden: item.orden,
    id_item: item.id_item,
    semilla_apodo: state.semilla_apodo,
    lado_polo_pos_mostrado: item.lado_polo_pos_mostrado,
    sha256_mostrado_izquierda: item.sha256_mostrado_izquierda,
    sha256_mostrado_derecha: item.sha256_mostrado_derecha,
    palabras_usuario: txt
  }});
  state.idx3++;
  if (state.idx3 < DATA.parte3.length) {{
    render();
  }} else {{
    state.step = "parte4";
    state.idx4 = 0;
    render();
  }}
}}

function responderParte4(gusta) {{
  const item = DATA.parte4[state.idx4];
  if (gusta) state.corazones++;
  state.resp4.push({{
    id_pieza: item.id_pieza,
    sha256_imagen: item.sha256_imagen,
    corazon: gusta
  }});
  state.idx4++;
  if (state.idx4 < DATA.parte4.length) {{
    render();
  }} else {{
    state.step = "cierre";
    render();
  }}
}}

function actualizarCierre(val) {{
  state.comentario_cierre = val;
  const box = document.getElementById("out-json-box");
  if (box) box.value = JSON.stringify(construirResultadoFinal(), null, 2);
}}

function construirResultadoFinal() {{
  const esBruno = (state.apodo || "").trim().toLowerCase() === "bruno";
  return {{
    fase: "FASE 5d · El Salón (Prueba de sensaciones con personas · v3c)",
    version_prerregistro: "3.2.0 (v3c)",
    fecha_iso: new Date().toISOString(),
    participante: {{
      apodo: state.apodo,
      semilla_apodo: state.semilla_apodo,
      es_bruno_n2_d8: esBruno,
      edad_aproximada: state.edad_aprox,
      trabaja_en_diseno_o_arte: state.trabaja_diseno,
      consentimiento_informado: state.consiente
    }},
    parte_1_primer_golpe_vista: state.resp1,
    parte_2_sentir: state.resp2,
    parte_3_ponerle_nombre: state.resp3,
    parte_4_gusto: {{
      cuenta_para_n2_y_d8: esBruno,
      total_corazones: state.corazones,
      total_evaluadas: state.resp4.length,
      votos: state.resp4
    }},
    cierre: {{
      que_te_sorprendio: state.comentario_cierre
    }}
  }};
}}

function nombreArchivoLimpio() {{
  const limpio = (state.apodo || "participante").replace(/[^a-zA-Z0-9_-]/g, "_").toLowerCase();
  return `salon_respuesta_${{limpio}}.json`;
}}

function descargarJSON() {{
  const texto = JSON.stringify(construirResultadoFinal(), null, 2) + "\\n";
  const blob = new Blob([texto], {{ type: "application/json" }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombreArchivoLimpio();
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}}

async function compartirJSON() {{
  const texto = JSON.stringify(construirResultadoFinal(), null, 2) + "\\n";
  const fname = nombreArchivoLimpio();
  if (navigator.share) {{
    try {{
      const file = new File([texto], fname, {{ type: "application/json" }});
      if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
        await navigator.share({{ files: [file], title: "Respuestas El Salón", text: `Respuestas de ${{state.apodo}}` }});
        return;
      }}
      await navigator.share({{ title: fname, text: texto }});
      return;
    }} catch (e) {{}}
  }}
  descargarJSON();
}}

render();
</script>
</body>
</html>
"""
    ruta_html.parent.mkdir(parents=True, exist_ok=True)
    ruta_html.write_text(html, encoding="utf-8")


def generar_salon(
    ruta_prerregistro_v3c: Path,
    ruta_prerregistro_v3b: Path,
    ruta_corpus_json: Path,
    carpeta_imagenes_cc0: Path,
    carpeta_atlas_f7: Path,
    carpeta_atlas_f5: Path,
    carpeta_salida_salon: Path,
) -> Dict[str, Any]:
    sha_v3c = hashlib.sha256(ruta_prerregistro_v3c.read_bytes()).hexdigest()
    if sha_v3c != SHA256_PRERREG_V3C_ESPERADO:
        raise ValueError(
            f"SHA-256 de prerregistro_v3c.json alterado: {sha_v3c} != {SHA256_PRERREG_V3C_ESPERADO}"
        )
    sha_v3b = hashlib.sha256(ruta_prerregistro_v3b.read_bytes()).hexdigest()
    if sha_v3b != SHA256_PRERREG_V3B_ESPERADO:
        raise ValueError(
            f"SHA-256 de prerregistro_v3b.json alterado: {sha_v3b} != {SHA256_PRERREG_V3B_ESPERADO}"
        )

    prerreg = json.loads(ruta_prerregistro_v3c.read_text(encoding="utf-8"))
    seed_salon = int(prerreg["semilla_base_salon"])
    corpus_items = json.loads(ruta_corpus_json.read_text(encoding="utf-8"))["imagenes"]

    imagenes_224: Dict[str, Image.Image] = {}
    labs_por_id: Dict[str, np.ndarray] = {}
    sha_por_id: Dict[str, str] = {}
    train_ids: List[str] = []

    for it in corpus_items:
        id_orig = it["id_origen"]
        sha_por_id[id_orig] = it["sha256"]
        if it["split"] == "train":
            train_ids.append(id_orig)
        with Image.open(carpeta_imagenes_cc0 / f"{id_orig}.jpg") as raw_im:
            im_224 = _recortar_224(raw_im.convert("RGB"))
            imagenes_224[id_orig] = im_224
            labs_por_id[id_orig] = _rgb_to_lab_mean(im_224)

    fichas_por_id: Dict[str, Dict[str, Any]] = {}
    for p in sorted(carpeta_atlas_f7.glob("neurona_*.json")) + sorted(
        carpeta_atlas_f5.glob("neurona_f5_*.json")
    ):
        d = json.loads(p.read_text(encoding="utf-8"))
        fichas_por_id[d["id_neurona"]] = d

    piezas_vistas_en_sesion: List[str] = []

    def registrar_piezas(ids_9: List[str]) -> None:
        for pid in ids_9:
            if pid not in piezas_vistas_en_sesion:
                piezas_vistas_en_sesion.append(pid)

    def armar_polos_neurona(
        id_neurona: str,
    ) -> Tuple[str, str, str, str, Image.Image, Image.Image, float]:
        ficha = fichas_por_id[id_neurona]
        pos_ids = [x["id_pieza"] for x in ficha["polo_pos"]]
        neg_ids = [x["id_pieza"] for x in ficha["polo_neg"]]
        registrar_piezas(pos_ids[:3] + neg_ids[:2])

        lab_pos = np.mean([labs_por_id[i] for i in pos_ids], axis=0)
        lab_neg = np.mean([labs_por_id[i] for i in neg_ids], axis=0)
        delta_L = round(float(lab_pos[0] - lab_neg[0]), 2)

        bytes_pos, sha_pos, pil_pos = _renderizar_mosaico_3x3_jpeg(
            [imagenes_224[i] for i in pos_ids]
        )
        bytes_neg, sha_neg, pil_neg = _renderizar_mosaico_3x3_jpeg(
            [imagenes_224[i] for i in neg_ids]
        )
        return (
            base64.b64encode(bytes_pos).decode("ascii"),
            base64.b64encode(bytes_neg).decode("ascii"),
            sha_pos,
            sha_neg,
            pil_pos,
            pil_neg,
            delta_L,
        )

    # Parte 1: 12 pares (Primer golpe de vista, 5 s)
    parte1_raw: List[Dict[str, Any]] = []
    clave_parte1: List[Dict[str, Any]] = []
    for item1 in prerreg["estructura_sesion_v3c"][
        "parte_1_primer_golpe_vista_12_pares"
    ]:
        b64_p, b64_n, sha_p, sha_n, _, _, dL = armar_polos_neurona(item1["id_neurona"])
        id_it = f"p1_{item1['orden']:02d}"
        parte1_raw.append(
            {
                "orden": item1["orden"],
                "id_item": id_it,
                "pregunta": item1["pregunta"],
                "b64_polo_pos": b64_p,
                "b64_polo_neg": b64_n,
                "sha256_polo_pos": sha_p,
                "sha256_polo_neg": sha_n,
            }
        )
        clave_parte1.append(
            {
                "orden": item1["orden"],
                "id_item": id_it,
                "id_neurona": item1["id_neurona"],
                "delta_L": dL,
                "sha256_polo_pos": sha_p,
                "sha256_polo_neg": sha_n,
            }
        )

    # Parte 2: 20 neuronas reales
    neuronas20_raw: List[Dict[str, Any]] = []
    clave_neuronas_20: List[Dict[str, Any]] = []
    dir_ejemplos_claude = carpeta_salida_salon / "ejemplos_claude"
    dir_ejemplos_claude.mkdir(parents=True, exist_ok=True)
    capturas_claude: List[Dict[str, Any]] = []

    for item2 in prerreg["estructura_sesion_v3c"]["parte_2_sentir_20_neuronas"]:
        b64_p, b64_n, sha_p, sha_n, pil_p, pil_n, dL = armar_polos_neurona(
            item2["id_neurona"]
        )
        id_it = f"neurona_real_{item2['orden']:02d}"
        neuronas20_raw.append(
            {
                "id_item": id_it,
                "tipo_item": "neurona_real",
                "pregunta": item2["pregunta"],
                "b64_polo_pos": b64_p,
                "b64_polo_neg": b64_n,
                "sha256_polo_pos": sha_p,
                "sha256_polo_neg": sha_n,
            }
        )
        clave_neuronas_20.append(
            {
                "orden_neurona": item2["orden"],
                "id_item": id_it,
                "tipo_item": "neurona_real",
                "id_neurona": item2["id_neurona"],
                "etapa": item2["etapa"],
                "eje_sensacion": item2["eje_sensacion"],
                "pregunta": item2["pregunta"],
                "delta_e_lab": item2["delta_e_lab"],
                "delta_L": dL,
                "polo_mas_claro": item2["polo_mas_claro"],
                "polo_mas_oscuro": item2["polo_mas_oscuro"],
                "es_eje_solo_brillo": item2["es_eje_solo_brillo"],
                "sha256_polo_pos": sha_p,
                "sha256_polo_neg": sha_n,
            }
        )
        if item2["orden"] <= 3:
            lado_ej = item2["lado_predicho_sorteado"]
            img_izq = pil_p if lado_ej == "izquierda" else pil_n
            img_der = pil_n if lado_ej == "izquierda" else pil_p
            ruta_cap = (
                dir_ejemplos_claude
                / f"captura_par_{item2['orden']:02d}_{item2['id_neurona']}.png"
            )
            sha_cap = _guardar_captura_par_claude(
                ruta_cap,
                num_ejemplo=item2["orden"],
                pregunta=item2["pregunta"],
                eje=item2["eje_sensacion"],
                id_neurona=item2["id_neurona"],
                delta_e=item2["delta_e_lab"],
                lado_predicho=lado_ej,
                img_izq=img_izq,
                img_der=img_der,
            )
            capturas_claude.append(
                {
                    "ejemplo": item2["orden"],
                    "id_neurona": item2["id_neurona"],
                    "eje_sensacion": item2["eje_sensacion"],
                    "pregunta": item2["pregunta"],
                    "delta_e_lab": item2["delta_e_lab"],
                    "ruta_captura": str(ruta_cap),
                    "sha256_captura": sha_cap,
                }
            )

    # 4 Controles al azar (Regla 4)
    rng_ctrl = np.random.default_rng(seed_salon + 400)
    preguntas_ctrl = [
        "¿Cuál de los dos se siente más sereno?",
        "¿Cuál de los dos se siente más intenso?",
        "¿Cuál de los dos se siente más liviano?",
        "¿Cuál de los dos se siente más firme?",
    ]
    controles4_raw: List[Dict[str, Any]] = []
    clave_controles_4: List[Dict[str, Any]] = []
    for idx_c, preg_c in enumerate(preguntas_ctrl, start=1):
        sel_18 = rng_ctrl.choice(train_ids, size=18, replace=False)
        ids_a = list(sel_18[:9])
        ids_b = list(sel_18[9:])
        b_a, sha_a, _ = _renderizar_mosaico_3x3_jpeg([imagenes_224[i] for i in ids_a])
        b_b, sha_b, _ = _renderizar_mosaico_3x3_jpeg([imagenes_224[i] for i in ids_b])
        id_it = f"control_azar_{idx_c:02d}"
        controles4_raw.append(
            {
                "id_item": id_it,
                "tipo_item": "control_azar",
                "pregunta": preg_c,
                "b64_polo_pos": base64.b64encode(b_a).decode("ascii"),
                "b64_polo_neg": base64.b64encode(b_b).decode("ascii"),
                "sha256_polo_pos": sha_a,
                "sha256_polo_neg": sha_b,
            }
        )
        clave_controles_4.append(
            {
                "id_item": id_it,
                "tipo_item": "control_azar",
                "pregunta": preg_c,
                "sha256_polo_pos": sha_a,
                "sha256_polo_neg": sha_b,
            }
        )

    # 2 Controles de atención obvios (Regla 5): polo_pos es siempre la respuesta obvia correcta
    train_por_lum = sorted(train_ids, key=lambda pid: float(labs_por_id[pid][0]))
    oscuras_18 = train_por_lum[:18]
    claras_18 = list(reversed(train_por_lum[-18:]))

    atencion_cfg = [
        (
            "atencion_01",
            "¿Cuál de los dos se siente más oscuro?",
            oscuras_18[:9],
            claras_18[:9],
        ),
        (
            "atencion_02",
            "¿Cuál de los dos se siente más luminoso?",
            claras_18[9:18],
            oscuras_18[9:18],
        ),
    ]
    atencion2_raw: List[Dict[str, Any]] = []
    clave_atencion_2: List[Dict[str, Any]] = []
    for id_at, preg_at, ids_correcto, ids_opuesto in atencion_cfg:
        b_p, sha_p, _ = _renderizar_mosaico_3x3_jpeg(
            [imagenes_224[i] for i in ids_correcto]
        )
        b_n, sha_n, _ = _renderizar_mosaico_3x3_jpeg(
            [imagenes_224[i] for i in ids_opuesto]
        )
        atencion2_raw.append(
            {
                "id_item": id_at,
                "tipo_item": "control_atencion",
                "pregunta": preg_at,
                "b64_polo_pos": base64.b64encode(b_p).decode("ascii"),
                "b64_polo_neg": base64.b64encode(b_n).decode("ascii"),
                "sha256_polo_pos": sha_p,
                "sha256_polo_neg": sha_n,
            }
        )
        clave_atencion_2.append(
            {
                "id_item": id_at,
                "tipo_item": "control_atencion",
                "pregunta": preg_at,
                "sha256_polo_pos": sha_p,
                "sha256_polo_neg": sha_n,
            }
        )

    # Parte 3: 6 pares (Ponerle nombre en 2 o 3 palabras)
    parte3_raw: List[Dict[str, Any]] = []
    clave_parte3: List[Dict[str, Any]] = []
    for item3 in prerreg["estructura_sesion_v3c"]["parte_3_ponerle_nombre_6_pares"]:
        b64_p, b64_n, sha_p, sha_n, _, _, _ = armar_polos_neurona(item3["id_neurona"])
        id_it = f"p3_{item3['orden']:02d}"
        ficha3 = fichas_por_id[item3["id_neurona"]]
        parte3_raw.append(
            {
                "orden": item3["orden"],
                "id_item": id_it,
                "pregunta": item3["pregunta"],
                "b64_polo_pos": b64_p,
                "b64_polo_neg": b64_n,
                "sha256_polo_pos": sha_p,
                "sha256_polo_neg": sha_n,
            }
        )
        clave_parte3.append(
            {
                "orden": item3["orden"],
                "id_item": id_it,
                "id_neurona": item3["id_neurona"],
                "etapa": ficha3["etapa"],
                "etiqueta_interna_neurona": ficha3["etiqueta"],
                "sha256_polo_pos": sha_p,
                "sha256_polo_neg": sha_n,
            }
        )

    # Parte 4: Gusto (40 imágenes sueltas únicas de las que salieron en la sesión)
    piezas_40 = piezas_vistas_en_sesion[:40]
    parte4_raw: List[Dict[str, Any]] = []
    for pid in piezas_40:
        b_thumb, _ = _renderizar_miniatura_obra_jpeg(imagenes_224[pid])
        parte4_raw.append(
            {
                "id_pieza": pid,
                "sha256_imagen": sha_por_id[pid],
                "b64_img": base64.b64encode(b_thumb).decode("ascii"),
            }
        )

    carpeta_salida_salon.mkdir(parents=True, exist_ok=True)
    (carpeta_salida_salon / "respuestas").mkdir(parents=True, exist_ok=True)

    ruta_html = carpeta_salida_salon / "salon_sensaciones.html"
    _construir_html_salon_v3c(
        ruta_html,
        parte1_raw,
        neuronas20_raw,
        controles4_raw,
        atencion2_raw,
        parte3_raw,
        parte4_raw,
    )
    sha_html = hashlib.sha256(ruta_html.read_bytes()).hexdigest()

    ruta_clave = carpeta_salida_salon / "clave_salon_no_abrir.json"
    obj_clave = {
        "fase": "FASE 5d (v3c) · Clave secreta de El Salón",
        "sha256_prerregistro_v3b": sha_v3b,
        "sha256_prerregistro_v3c": sha_v3c,
        "sha256_html_salon": sha_html,
        "semilla_base_salon": seed_salon,
        "parte_1_clave": clave_parte1,
        "parte_2_neuronas_20_clave": clave_neuronas_20,
        "parte_2_controles_4_clave": clave_controles_4,
        "parte_2_atencion_2_clave": clave_atencion_2,
        "parte_3_clave": clave_parte3,
    }
    ruta_clave.write_text(
        json.dumps(obj_clave, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sha_clave = hashlib.sha256(ruta_clave.read_bytes()).hexdigest()

    ruta_diseno_git = ruta_prerregistro_v3c.parent / "diseno_salon_v3b.json"
    obj_diseno_git = {
        "fase": "FASE 5d (v3c) · Diseño público de El Salón (con los 3 cambios condicionales de Claude)",
        "sha256_prerregistro_v3b": sha_v3b,
        "sha256_prerregistro_v3c": sha_v3c,
        "semilla_base_salon": seed_salon,
        "ruta_html_local": str(ruta_html),
        "sha256_html_local": sha_html,
        "tamano_bytes_html_local": ruta_html.stat().st_size,
        "ruta_clave_secreta_local": str(ruta_clave),
        "sha256_clave_secreta_local": sha_clave,
        "carpeta_respuestas_participantes": str(carpeta_salida_salon / "respuestas"),
        "resumen_items": {
            "parte_1_golpe_vista_5s": len(parte1_raw),
            "parte_2_neuronas_reales": len(neuronas20_raw),
            "parte_2_controles_azar": len(controles4_raw),
            "parte_2_controles_atencion": len(atencion2_raw),
            "parte_2_total_presentados": len(neuronas20_raw)
            + len(controles4_raw)
            + len(atencion2_raw),
            "parte_3_ponerle_nombre": len(parte3_raw),
            "parte_4_gusto_imagenes": len(parte4_raw),
        },
        "tres_capturas_para_visto_bueno_claude": capturas_claude,
    }
    ruta_diseno_git.write_text(
        json.dumps(obj_diseno_git, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return obj_diseno_git


def main(argv: List[str] | None = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Genera la sesión web «El salón» (FASE 5d · v3c) a partir de prerregistro_v3c.json."
    )
    parser.add_argument(
        "--prerregistro-v3c", default=str(base_dir / "prerregistro_v3c.json")
    )
    parser.add_argument(
        "--prerregistro-v3b", default=str(base_dir / "prerregistro_v3b.json")
    )
    parser.add_argument("--corpus-json", default=str(base_dir / "corpus_cc0_630.json"))
    parser.add_argument(
        "--imagenes-cc0",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/corpus-neuronas-cc0/imagenes",
    )
    parser.add_argument("--atlas-f7", default=str(base_dir / "atlas"))
    parser.add_argument("--atlas-f5", default=str(base_dir / "atlas_f5"))
    parser.add_argument(
        "--salida-salon",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/el-salon",
    )
    args = parser.parse_args(argv)

    res = generar_salon(
        ruta_prerregistro_v3c=Path(args.prerregistro_v3c).expanduser().resolve(),
        ruta_prerregistro_v3b=Path(args.prerregistro_v3b).expanduser().resolve(),
        ruta_corpus_json=Path(args.corpus_json).expanduser().resolve(),
        carpeta_imagenes_cc0=Path(args.imagenes_cc0).expanduser().resolve(),
        carpeta_atlas_f7=Path(args.atlas_f7).expanduser().resolve(),
        carpeta_atlas_f5=Path(args.atlas_f5).expanduser().resolve(),
        carpeta_salida_salon=Path(args.salida_salon).expanduser().resolve(),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
