#!/usr/bin/env node
/**
 * V-4 · Noche de entropía (lote).
 *
 * Genera combinaciones y collages PNG con la misma lógica de la pizarra
 * (`src/board/vanguardia`), un muro `index.html` que se abre con doble clic y
 * un importador de gustos parciales en la app.
 *
 * Uso:
 *   npm run entropia -- --n 50 --semilla 2026 --proyecto <export.json>
 *   npm run entropia -- --n 12 --semilla 2026 --proyecto <export.json> --titulos
 *
 * Nunca escribe la DEEPSEEK_API_KEY en disco: solo la lee del entorno.
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { chromium } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(__dirname, '..');
const SALIDA_BASE = path.join(os.homedir(), 'Desktop', 'deepseek-trabajo', 'entropia');
const LIENZO = { ancho: 900, alto: 640 };
const NAVEGADOR = process.env.PROMETEO_E2E_CHROMIUM_PATH
  || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser';
const MODELO_DEEPSEEK = 'deepseek-chat';
const MAX_TITULOS_A_LA_VEZ = 4;

function uso() {
  return [
    'Uso: npm run entropia -- [opciones]',
    '',
    '  --n <entero>        Collages del lote (1-200; por defecto 50).',
    '  --semilla <texto>   Semilla base del lote (por defecto la fecha de hoy).',
    '  --proyecto <ruta>   Export JSON del proyecto o tablero. Si falta, usa la semilla de referentes.',
    '  --salida <ruta>     Carpeta de salida. Por defecto ~/Desktop/deepseek-trabajo/entropia/AAAA-MM-DD/.',
    '  --titulos           Pide a DeepSeek un título de hasta 6 palabras por collage.',
    '  --ayuda             Muestra esta ayuda.',
  ].join('\n');
}

function fechaLocal() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function parseArgs(argv) {
  const opciones = {
    n: 50,
    semilla: fechaLocal(),
    proyecto: '',
    salida: '',
    titulos: false,
    ayuda: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--ayuda' || arg === '-h' || arg === '--help') {
      opciones.ayuda = true;
      continue;
    }
    if (arg === '--titulos') {
      opciones.titulos = true;
      continue;
    }
    const valor = (nombre) => {
      const actual = argv[i + 1];
      if (actual === undefined || actual.startsWith('--')) throw new Error(`Falta el valor de ${nombre}.`);
      i += 1;
      return actual;
    };
    if (arg === '--n') {
      const raw = valor('--n');
      const n = Number(raw);
      if (!Number.isInteger(n)) throw new Error(`--n debe ser un entero (recibí «${raw}»).`);
      opciones.n = n;
    } else if (arg === '--semilla') {
      opciones.semilla = valor('--semilla');
    } else if (arg === '--proyecto') {
      opciones.proyecto = valor('--proyecto');
    } else if (arg === '--salida') {
      opciones.salida = valor('--salida');
    } else {
      throw new Error(`Opción desconocida: ${arg}`);
    }
  }
  if (!opciones.salida) opciones.salida = path.join(SALIDA_BASE, fechaLocal());
  return opciones;
}

function expandirHome(ruta) {
  return ruta.startsWith('~/') ? path.join(os.homedir(), ruta.slice(2)) : ruta;
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function texto(value, fallback = '') {
  return typeof value === 'string' ? value.trim() : fallback;
}

function pareceTablero(value) {
  return isRecord(value) && Array.isArray(value.cards);
}

/** Acepta el export de un tablero, un tablero suelto o un proyecto con varios tableros. */
function extraerTableros(json) {
  if (pareceTablero(json)) return [json];
  if (Array.isArray(json)) return json.filter(pareceTablero);
  if (!isRecord(json)) return [];
  if (pareceTablero(json.board)) return [json.board];
  for (const clave of ['boards', 'tableros']) {
    if (Array.isArray(json[clave])) {
      const tableros = json[clave].filter(pareceTablero);
      if (tableros.length) return tableros;
    }
  }
  if (isRecord(json.proyecto)) {
    const anidados = extraerTableros(json.proyecto);
    if (anidados.length) return anidados;
  }
  return [];
}

function normalizarTablero(board, indice) {
  return {
    id: texto(board.id, `tablero-${indice + 1}`).slice(0, 120),
    title: texto(board.title, `Tablero ${indice + 1}`).slice(0, 200),
    cards: board.cards,
  };
}

function slug(value) {
  return String(value)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'sin-nombre';
}

function proyectoDesdeSemilla(semillaReferentes) {
  const cards = semillaReferentes.map((item) => ({
    id: `referente-${slug(item.id)}`,
    type: 'referente',
    title: item.nombre,
    body: item.que,
    datos: {
      nombre: item.nombre,
      etiquetas: item.verificar ? ['por verificar'] : [],
      imagenes: [],
    },
  }));
  return {
    tableros: [{ id: 'semilla', title: 'Biblioteca (semilla)', cards }],
    nombre: 'Semilla de referentes',
    sha256: sha256(JSON.stringify(semillaReferentes)),
    origen: '(semilla interna)',
  };
}

function proyectoDesdeArchivo(ruta) {
  const absoluto = path.resolve(expandirHome(ruta));
  const raw = fs.readFileSync(absoluto, 'utf8');
  let json;
  try {
    json = JSON.parse(raw);
  } catch {
    throw new Error(`El proyecto no es un JSON válido: ${absoluto}`);
  }
  const tableros = extraerTableros(json).map(normalizarTablero);
  if (!tableros.length) {
    throw new Error('El JSON no tiene tableros con tarjetas. Exporta el tablero desde Prometeo (Exportar JSON).');
  }
  const nombre = tableros.length === 1
    ? tableros[0].title
    : path.basename(absoluto, path.extname(absoluto));
  return {
    tableros,
    nombre: texto(nombre, 'Proyecto sin nombre').slice(0, 200),
    sha256: sha256(raw),
    origen: absoluto,
  };
}

function jsonSeguro(value) {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}

function escapar(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[character]));
}

function htmlCollage(item, titulo, indice, fuentesPorId, total) {
  const datos = item.datos;
  const ancho = datos.ancho || LIENZO.ancho;
  const alto = datos.alto || LIENZO.alto;
  const nombres = datos.fuentes.map((id) => fuentesPorId.get(id)?.nombre || id);
  const piezas = datos.disposicion.map((pieza) => {
    const fuente = fuentesPorId.get(pieza.id);
    const recorte = pieza.recorte ?? { x: 0, y: 0, w: 1, h: 1 };
    const recorteW = recorte.w > 0 ? recorte.w : 1;
    const recorteH = recorte.h > 0 ? recorte.h : 1;
    const estilo = [
      `left:${(pieza.x / ancho) * 100}%`,
      `top:${(pieza.y / alto) * 100}%`,
      `width:${(pieza.w / ancho) * 100}%`,
      `height:${(pieza.h / alto) * 100}%`,
      `z-index:${Math.trunc(pieza.z) + 1}`,
      pieza.rot ? `transform:rotate(${pieza.rot}deg)` : '',
    ].filter(Boolean).join(';');
    if (fuente?.imagen?.src) {
      const img = [
        `left:${(-recorte.x / recorteW) * 100}%`,
        `top:${(-recorte.y / recorteH) * 100}%`,
        `width:${(1 / recorteW) * 100}%`,
        `height:${(1 / recorteH) * 100}%`,
      ].join(';');
      return `<div class="pieza" data-id="${escapar(pieza.id)}" style="${estilo}"><img src="${escapar(fuente.imagen.src)}" alt="${escapar(fuente.nombre)}" style="${img}"></div>`;
    }
    return `<div class="pieza sin-imagen" data-id="${escapar(pieza.id)}" style="${estilo}"><span class="nombre">${escapar(fuente?.nombre || pieza.id)}</span></div>`;
  }).join('');

  const tituloVisible = titulo || `Collage ${String(indice).padStart(3, '0')}`;
  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>${escapar(tituloVisible)} · Entropía</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #17171b; }
  body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; }
  .hoja { width: 1000px; padding: 32px 50px 28px; background: #f7f3ea; color: #1d1c1a; }
  .cabecera { display: flex; align-items: baseline; justify-content: space-between; gap: 24px; height: 46px; }
  .kicker { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 10px; letter-spacing: .16em; text-transform: uppercase; color: #8a857b; }
  h1 { margin: 2px 0 0; font-family: ui-serif, Georgia, "Times New Roman", serif; font-weight: 600; font-size: 25px; line-height: 1.05; letter-spacing: -.015em; }
  .numero { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; color: #8a857b; white-space: nowrap; }
  .lienzo { position: relative; width: ${ancho}px; height: ${alto}px; margin-top: 12px; overflow: hidden; border-radius: 8px; background: #e9e4da; box-shadow: inset 0 0 0 1px rgba(0,0,0,.16); }
  .lienzo::after { content: ""; position: absolute; inset: 0; z-index: 0; pointer-events: none; opacity: .32; background-image: repeating-linear-gradient(0deg, rgba(120,110,95,.07) 0 1px, transparent 1px 3px), repeating-linear-gradient(90deg, rgba(255,255,255,.16) 0 1px, transparent 1px 5px); }
  .pieza { position: absolute; overflow: hidden; background: #f4f0e9; box-shadow: 0 7px 18px rgba(0,0,0,.30), 0 1px 2px rgba(0,0,0,.22); transform-origin: center; }
  .pieza img { display: block; max-width: none; object-fit: cover; }
  .pieza.sin-imagen { display: grid; place-items: center; padding: 8px; background: repeating-linear-gradient(135deg, #f4f0e9 0 8px, #ebe4d8 8px 16px); }
  .pieza .nombre { max-width: 100%; color: #4f4b44; font-size: 15px; font-weight: 600; line-height: 1.12; text-align: center; text-wrap: balance; }
  .pie { display: flex; align-items: baseline; justify-content: space-between; gap: 24px; margin-top: 14px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 10px; line-height: 1.35; color: #7d776d; }
  .pie .semilla { color: #2f2c27; }
  .pie .fuentes { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 520px; }
  .regla { color: #8c4e2f; }
</style>
</head>
<body>
  <article class="hoja">
    <header class="cabecera">
      <div>
        <p class="kicker">Entropía · Prometeo</p>
        <h1>${escapar(tituloVisible)}</h1>
      </div>
      <span class="numero">${String(indice).padStart(3, '0')} / ${String(total).padStart(3, '0')}</span>
    </header>
    <div class="lienzo" aria-label="Collage">${piezas}</div>
    <footer class="pie">
      <span><span class="semilla">${escapar(datos.semilla)}</span> · <span class="regla">${escapar(datos.reglaNombre || datos.regla)}</span> · ${escapar(datos.restriccion)}</span>
      <span class="fuentes">${escapar(nombres.join(' · '))}</span>
    </footer>
  </article>
</body>
</html>`;
}

function htmlMuro(lote) {
  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Noche de entropía · ${escapar(lote.semilla)}</title>
<style>
  :root { color-scheme: dark; --fondo: #141418; --papel: #1e1e24; --linea: #33333c; --texto: #ece9e2; --tenue: #9b978f; --naranja: #ff8a52; --rojo: #ff7a7a; --verde: #9fd6b0; }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--fondo); color: var(--texto); }
  body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; }
  button { font: inherit; color: inherit; }
  .barra { position: sticky; top: 0; z-index: 10; display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 18px 26px 14px; background: rgba(20,20,24,.94); border-bottom: 1px solid var(--linea); backdrop-filter: blur(10px); }
  .kicker { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 10px; letter-spacing: .16em; text-transform: uppercase; color: var(--tenue); }
  h1 { margin: 3px 0 4px; font-family: ui-serif, Georgia, "Times New Roman", serif; font-weight: 500; font-size: 30px; letter-spacing: -.02em; }
  .sub { margin: 0; color: var(--tenue); font-size: 12px; }
  .sub b { color: var(--texto); font-weight: 600; }
  .acciones { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
  .cuenta { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; color: var(--tenue); white-space: nowrap; }
  button { border: 1px solid var(--linea); border-radius: 7px; background: #24242b; padding: 7px 11px; font-size: 12px; cursor: pointer; }
  button:hover { border-color: #55555f; }
  button.primario { border-color: rgba(255,138,82,.7); background: rgba(255,138,82,.14); color: #ffd6c2; font-weight: 700; }
  button.primario:hover { background: rgba(255,138,82,.24); }
  .filtros { display: flex; gap: 7px; padding: 14px 26px 0; flex-wrap: wrap; }
  .filtros button[aria-pressed="true"] { border-color: var(--naranja); background: rgba(255,138,82,.12); color: #ffd6c2; }
  .ayuda { margin: 12px 26px 0; color: var(--tenue); font-size: 12px; line-height: 1.5; min-height: 18px; }
  kbd { display: inline-block; min-width: 19px; padding: 1px 5px; border: 1px solid var(--linea); border-bottom-width: 2px; border-radius: 4px; background: #222228; color: var(--texto); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; text-align: center; }
  .muro { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 18px; padding: 18px 26px 46px; max-width: 1800px; margin: 0 auto; }
  .carta { position: relative; margin: 0; border: 1px solid var(--linea); border-radius: 10px; background: var(--papel); overflow: hidden; cursor: pointer; outline: none; transition: border-color .12s, transform .12s; }
  .carta:hover { border-color: #4a4a55; transform: translateY(-1px); }
  .carta.actual { border-color: var(--naranja); box-shadow: 0 0 0 2px rgba(255,138,82,.28); }
  .carta.like { border-color: rgba(217,79,79,.75); }
  .carta.nope { border-color: rgba(120,128,140,.75); }
  .carta.like::after, .carta.nope::after { position: absolute; top: 9px; left: 9px; z-index: 2; border-radius: 5px; padding: 3px 7px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; background: rgba(15,15,18,.82); }
  .carta.like::after { content: "♥"; color: var(--rojo); border: 1px solid rgba(217,79,79,.6); }
  .carta.nope::after { content: "✕"; color: #c3c7d0; border: 1px solid rgba(160,166,178,.45); }
  .carta img { display: block; width: 100%; aspect-ratio: 1000 / 786; object-fit: cover; background: #e9e4da; }
  .cuerpo { padding: 11px 12px 12px; }
  .titulo { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
  .titulo strong { font-size: 14px; line-height: 1.25; }
  .titulo span { color: var(--tenue); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 10px; }
  .meta { margin: 5px 0 0; color: var(--tenue); font-size: 11px; line-height: 1.35; }
  .meta .regla { color: #e0a07e; }
  .pie-carta { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 9px; }
  .semilla { color: #a8a39a; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 10px; }
  .votos { display: flex; gap: 6px; }
  .votos button { padding: 3px 8px; font-size: 13px; line-height: 1.3; }
  .votos button[data-voto="nope"] { color: #c3c7d0; }
  .votos button[data-voto="like"] { color: var(--rojo); }
  .votos button[aria-pressed="true"] { background: #303038; border-color: #6a6a76; }
  .oculta { display: none !important; }
  .vacio { padding: 40px 26px; color: var(--tenue); }
  .nota { margin: 0 26px; padding: 10px 12px; border: 1px solid var(--linea); border-radius: 8px; background: #1b1b21; color: var(--tenue); font-size: 12px; line-height: 1.5; }
  footer.pie-muro { padding: 0 26px 38px; color: #6f6b64; font-size: 11px; line-height: 1.5; }
  @media (max-width: 720px) { .barra { align-items: flex-start; flex-direction: column; } .acciones { justify-content: flex-start; } h1 { font-size: 24px; } }
</style>
</head>
<body>
  <header class="barra">
    <div>
      <p class="kicker">Prometeo · Noche de entropía</p>
      <h1>Noche de entropía</h1>
      <p class="sub">Semilla <b>${escapar(lote.semilla)}</b> · ${lote.n} collages · ${escapar(lote.proyecto.nombre)}</p>
    </div>
    <div class="acciones">
      <span class="cuenta" id="cuenta"></span>
      <button type="button" id="exportar" class="primario">Exportar gustos-parcial.json</button>
      <button type="button" id="limpiar">Limpiar marcas</button>
    </div>
  </header>
  <nav class="filtros" aria-label="Filtrar collages">
    <button type="button" data-filtro="todos" aria-pressed="true">Todos (${lote.n})</button>
    <button type="button" data-filtro="like" aria-pressed="false">♥</button>
    <button type="button" data-filtro="nope" aria-pressed="false">✕</button>
    <button type="button" data-filtro="sin" aria-pressed="false">Sin marcar</button>
  </nav>
  <p class="ayuda"><kbd>←</kbd> ✕ · <kbd>→</kbd> ♥ · clic para elegir · <span id="aviso">Las marcas se guardan en este navegador.</span></p>
  <main class="muro" id="muro"></main>
  <footer class="pie-muro">Sin dependencias ni red: las imágenes son las de este lote. Al exportar se descarga <b>gustos-parcial.json</b>; en Prometeo, «Importar gustos» lo suma al proyecto.</footer>
  <script>
  const LOTE = ${jsonSeguro(lote)};
  const CLAVE = 'prometeo-entropia:' + LOTE.semilla + ':' + LOTE.n;
  const estado = { marcas: {}, actual: 0, filtro: 'todos', memoria: false };

  function cargar() {
    try {
      const raw = localStorage.getItem(CLAVE);
      const value = raw ? JSON.parse(raw) : {};
      const marcas = {};
      for (const item of LOTE.items) {
        const voto = value && value[item.indice];
        if (voto === 'like' || voto === 'nope') marcas[item.indice] = voto;
      }
      estado.memoria = true;
      return marcas;
    } catch {
      estado.memoria = false;
      return {};
    }
  }

  function guardar() {
    try { localStorage.setItem(CLAVE, JSON.stringify(estado.marcas)); estado.memoria = true; }
    catch { estado.memoria = false; }
  }

  function aviso(texto) { document.getElementById('aviso').textContent = texto; }

  function escapar(value) {
    return String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function visible(item) {
    if (estado.filtro === 'todos') return true;
    if (estado.filtro === 'sin') return !estado.marcas[item.indice];
    return estado.marcas[item.indice] === estado.filtro;
  }

  function pintar() {
    const muro = document.getElementById('muro');
    const visibles = LOTE.items.filter(visible);
    muro.innerHTML = visibles.length ? visibles.map((item) => {
      const voto = estado.marcas[item.indice] || '';
      const titulo = item.titulo || ('Collage ' + String(item.indice).padStart(3, '0'));
      const fuentes = item.referentes.map((f) => escapar(f.nombre)).join(' · ');
      return '<article class="carta ' + voto + (estado.actual === item.indice ? ' actual' : '') + '" data-i="' + item.indice + '" tabindex="0" role="button" aria-label="' + escapar(titulo) + '. Pulsa ← para ✕ o → para ♥.">'
        + '<img loading="lazy" src="' + escapar(item.archivo) + '" alt="' + escapar(titulo) + '">'
        + '<div class="cuerpo">'
        + '<div class="titulo"><strong>' + escapar(titulo) + '</strong><span>' + String(item.indice).padStart(3, '0') + '</span></div>'
        + '<p class="meta"><span class="regla">' + escapar(item.reglaNombre) + '</span> · ' + escapar(item.restriccion) + '</p>'
        + '<p class="meta">' + fuentes + '</p>'
        + '<div class="pie-carta"><span class="semilla">' + escapar(item.semilla) + '</span><span class="votos">'
        + '<button type="button" data-voto="nope" aria-pressed="' + (voto === 'nope') + '" aria-label="No me gusta">✕</button>'
        + '<button type="button" data-voto="like" aria-pressed="' + (voto === 'like') + '" aria-label="Me gusta">♥</button>'
        + '</span></div></div></article>';
    }).join('') : '<p class="vacio">No hay collages con este filtro.</p>';
    const like = Object.values(estado.marcas).filter((v) => v === 'like').length;
    const nope = Object.values(estado.marcas).filter((v) => v === 'nope').length;
    document.getElementById('cuenta').textContent = like + ' ♥ · ' + nope + ' ✕ · ' + (LOTE.n - like - nope) + ' sin marcar';
    document.querySelectorAll('[data-filtro]').forEach((boton) => {
      boton.setAttribute('aria-pressed', String(boton.dataset.filtro === estado.filtro));
    });
    const actual = muro.querySelector('[data-i="' + estado.actual + '"]');
    if (actual) actual.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function elegir(indice) {
    estado.actual = indice;
    pintar();
  }

  function marcar(indice, voto) {
    estado.marcas[indice] = voto;
    guardar();
    const visibles = LOTE.items.filter(visible);
    const siguiente = visibles.find((item) => item.indice > indice && !estado.marcas[item.indice])
      || visibles.find((item) => !estado.marcas[item.indice])
      || visibles.find((item) => item.indice > indice)
      || visibles[0];
    estado.actual = siguiente ? siguiente.indice : indice;
    if (!estado.memoria) aviso('Este navegador no dejó guardar las marcas: exporta antes de cerrar.');
    pintar();
  }

  function mover(delta) {
    const visibles = LOTE.items.filter(visible);
    if (!visibles.length) return;
    const posicion = visibles.findIndex((item) => item.indice === estado.actual);
    const siguiente = posicion < 0 ? 0 : (posicion + delta + visibles.length) % visibles.length;
    estado.actual = visibles[siguiente].indice;
    pintar();
  }

  function exportar() {
    const marcados = LOTE.items.filter((item) => estado.marcas[item.indice]).map((item) => ({
      semilla: item.semilla,
      regla: item.regla,
      herramienta: item.herramienta,
      restriccion: item.restriccion,
      referentes: item.referentes.map((f) => f.id),
      voto: estado.marcas[item.indice],
    }));
    if (!marcados.length) {
      aviso('Marca al menos un collage antes de exportar.');
      return;
    }
    const payload = {
      format: 'prometeo-entropia-gustos',
      version: 1,
      proyecto: LOTE.proyecto.nombre,
      semilla: LOTE.semilla,
      exportado: new Date().toISOString(),
      items: marcados,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2) + '\\n'], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = 'gustos-parcial.json';
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    const like = marcados.filter((item) => item.voto === 'like').length;
    const nope = marcados.length - like;
    aviso('Exportados ' + like + ' ♥ y ' + nope + ' ✕ en gustos-parcial.json.');
  }

  document.addEventListener('click', (event) => {
    const boton = event.target.closest('button[data-voto]');
    const carta = event.target.closest('.carta');
    if (boton && carta) {
      event.stopPropagation();
      marcar(Number(carta.dataset.i), boton.dataset.voto);
      return;
    }
    if (carta) elegir(Number(carta.dataset.i));
  });

  document.addEventListener('keydown', (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key === 'ArrowLeft') { event.preventDefault(); marcar(estado.actual, 'nope'); }
    else if (event.key === 'ArrowRight') { event.preventDefault(); marcar(estado.actual, 'like'); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); mover(-1); }
    else if (event.key === 'ArrowDown') { event.preventDefault(); mover(1); }
  });

  document.querySelectorAll('[data-filtro]').forEach((boton) => {
    boton.addEventListener('click', () => {
      estado.filtro = boton.dataset.filtro;
      const visibles = LOTE.items.filter(visible);
      const actual = LOTE.items.find((item) => item.indice === estado.actual);
      if (visibles.length && (!actual || !visible(actual))) {
        estado.actual = visibles[0].indice;
      }
      pintar();
    });
  });

  document.getElementById('exportar').addEventListener('click', exportar);
  document.getElementById('limpiar').addEventListener('click', () => {
    if (!Object.keys(estado.marcas).length) return;
    if (!confirm('¿Quitar todas las marcas de este lote?')) return;
    estado.marcas = {};
    guardar();
    pintar();
    aviso('Marcas limpiadas.');
  });

  estado.marcas = cargar();
  const primero = LOTE.items.find((item) => !estado.marcas[item.indice]);
  estado.actual = (primero || LOTE.items[0]).indice;
  if (!estado.memoria) aviso('Este navegador no permite guardar marcas en localStorage; exporta antes de cerrar.');
  pintar();
  </script>
</body>
</html>`;
}

async function pedirTitulo(item, fuentesPorId, apiKey) {
  const nombres = item.datos.fuentes.map((id) => fuentesPorId.get(id)?.nombre || id);
  const body = {
    model: MODELO_DEEPSEEK,
    temperature: 0.9,
    max_tokens: 24,
    stream: false,
    messages: [
      {
        role: 'system',
        content: 'Eres editor de una revista de diseño. Escribes títulos muy cortos, concretos y sin adornos.',
      },
      {
        role: 'user',
        content: [
          'Pon un título a este collage.',
          'Regla: ' + (item.datos.reglaNombre || item.datos.regla),
          'Restricción: ' + (item.datos.restriccion || 'sin restricción'),
          'Fuentes: ' + nombres.join('; '),
          'Devuelve SOLO el título, de 2 a 6 palabras, sin comillas ni punto final.',
        ].join('\n'),
      },
    ],
  };
  const response = await fetch('https://api.deepseek.com/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(45_000),
  });
  if (!response.ok) throw new Error(`DeepSeek respondió HTTP ${response.status}`);
  const json = await response.json();
  const content = json?.choices?.[0]?.message?.content;
  if (typeof content !== 'string' || !content.trim()) throw new Error('DeepSeek devolvió un título vacío');
  return content;
}

async function titulosDeepSeek(items, fuentesPorId, tituloCorto, tituloDeRespaldo) {
  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) {
    throw new Error('Pediste --titulos pero falta DEEPSEEK_API_KEY en el entorno. No se escribió ninguna clave.');
  }
  const titulos = items.map(() => ({ titulo: '', origen: 'respaldo' }));
  for (let inicio = 0; inicio < items.length; inicio += MAX_TITULOS_A_LA_VEZ) {
    const bloque = items.slice(inicio, inicio + MAX_TITULOS_A_LA_VEZ);
    await Promise.all(bloque.map(async (item) => {
      const posicion = item.indice - 1;
      try {
        const bruto = await pedirTitulo(item, fuentesPorId, apiKey);
        titulos[posicion] = { titulo: tituloCorto(bruto, tituloDeRespaldo(item.datos)), origen: 'deepseek' };
        console.log(`  título ${item.indice}/${items.length}: ${titulos[posicion].titulo}`);
      } catch (error) {
        titulos[posicion] = { titulo: tituloDeRespaldo(item.datos), origen: 'respaldo' };
        console.warn(`  título ${item.indice}/${items.length}: falló (${error instanceof Error ? error.message : String(error)}); uso respaldo.`);
      }
    }));
  }
  return titulos;
}

async function main() {
  let opciones;
  try {
    opciones = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    console.error(uso());
    process.exitCode = 1;
    return;
  }
  if (opciones.ayuda) {
    console.log(uso());
    return;
  }
  if (opciones.titulos && !process.env.DEEPSEEK_API_KEY) {
    console.error('Pediste --titulos pero falta DEEPSEEK_API_KEY en el entorno. No se escribió nada.');
    process.exitCode = 2;
    return;
  }

  const servidor = await createServer({
    root: FRONTEND_ROOT,
    server: { middlewareMode: true },
    appType: 'custom',
    logLevel: 'error',
  });

  let navegador = null;
  try {
    const { SEMILLA_REFERENTES } = await servidor.ssrLoadModule('/src/board/referentes/semilla.ts');
    const { listBoardTools } = await servidor.ssrLoadModule('/src/board/tools/registry.ts');
    const { fuentesDeProyecto } = await servidor.ssrLoadModule('/src/board/vanguardia/fuentes.ts');
    const { crearLote, tituloCorto, tituloDeRespaldo } = await servidor.ssrLoadModule('/src/board/vanguardia/lote.ts');

    const proyecto = opciones.proyecto ? proyectoDesdeArchivo(opciones.proyecto) : proyectoDesdeSemilla(SEMILLA_REFERENTES);
    const { fuentes, procedencia } = fuentesDeProyecto(proyecto.tableros);
    if (fuentes.length < 2) {
      throw new Error(`Entropía necesita al menos 2 referentes y el proyecto tiene ${fuentes.length}.`);
    }
    const herramientas = listBoardTools().map((tool) => ({ id: tool.id, nombre: tool.nombre }));
    const items = crearLote({
      semillaBase: opciones.semilla,
      n: opciones.n,
      fuentes,
      herramientas,
      tamano: LIENZO,
    });

    const salida = path.resolve(expandirHome(opciones.salida));
    fs.mkdirSync(salida, { recursive: true });

    const cuentas = { referente: 0, marco: 0, tablero: 0, tipografico: 0 };
    for (const fuente of fuentes) cuentas[procedencia[fuente.id] || 'tipografico'] += 1;

    console.log(`Entropía · lote V-4`);
    console.log(`Semilla ${opciones.semilla} · ${opciones.n} collages · ${fuentes.length} referentes`);
    console.log(`Proyecto: ${proyecto.origen}`);
    console.log(`Imágenes: ${cuentas.referente} de referente, ${cuentas.marco} de marco, ${cuentas.tablero} de tablero, ${cuentas.tipografico} tipográficas`);
    console.log(`Salida: ${salida}`);

    let titulos = items.map(() => ({ titulo: '', origen: 'sin-titulo' }));
    if (opciones.titulos) titulos = await titulosDeepSeek(items, new Map(fuentes.map((f) => [f.id, f])), tituloCorto, tituloDeRespaldo);

    navegador = await chromium.launch({ executablePath: NAVEGADOR, headless: true });
    const contexto = await navegador.newContext({ viewport: { width: 1100, height: 900 }, deviceScaleFactor: 1 });
    const pagina = await contexto.newPage();

    const archivos = [];
    for (const item of items) {
      const indice = item.indice;
      const archivo = `${String(indice).padStart(3, '0')}-${item.datos.semilla}.png`;
      const html = htmlCollage(item, titulos[indice - 1].titulo, indice, new Map(fuentes.map((f) => [f.id, f])), items.length);
      await pagina.setContent(html, { waitUntil: 'load' });
      await pagina.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(Array.from(document.images, (img) => img.complete
          ? Promise.resolve()
          : new Promise((resolve) => { img.onload = resolve; img.onerror = resolve; })));
      });
      const destino = path.join(salida, archivo);
      await pagina.locator('.hoja').screenshot({ path: destino, type: 'png', animations: 'disabled' });
      const bytes = fs.readFileSync(destino);
      archivos.push({ indice, archivo, sha256: sha256(bytes) });
      console.log(`  ${String(indice).padStart(3, '0')}/${items.length} · ${item.datos.semilla} · ${item.datos.reglaNombre || item.datos.regla}`);
    }
    await contexto.close();
    await navegador.close();
    navegador = null;

    const porId = new Map(fuentes.map((fuente) => [fuente.id, fuente]));
    const lote = {
      format: 'prometeo-entropia-lote',
      version: 1,
      semilla: opciones.semilla,
      n: items.length,
      lienzo: LIENZO,
      proyecto: {
        nombre: proyecto.nombre,
        sha256: proyecto.sha256,
        tableros: proyecto.tableros.length,
        referentes: fuentes.length,
        imagenes: cuentas,
      },
      items: items.map((item, posicion) => {
        const datos = item.datos;
        const archivo = archivos[posicion];
        return {
          indice: item.indice,
          semilla: datos.semilla,
          titulo: titulos[posicion].titulo || '',
          archivo: archivo.archivo,
          sha256: archivo.sha256,
          regla: datos.regla,
          reglaNombre: datos.reglaNombre,
          restriccion: datos.restriccion,
          herramienta: datos.herramienta,
          herramientaNombre: herramientas.find((tool) => tool.id === datos.herramienta)?.nombre || datos.herramienta,
          azarPuro: datos.azarPuro,
          referentes: datos.fuentes.map((id) => ({
            id,
            nombre: porId.get(id)?.nombre || id,
            imagen: procedencia[id] || 'tipografico',
          })),
        };
      }),
    };

    const titulosJson = opciones.titulos ? {
      format: 'prometeo-entropia-titulos',
      version: 1,
      semilla: opciones.semilla,
      items: titulos.map((titulo, posicion) => ({
        indice: posicion + 1,
        semilla: items[posicion].datos.semilla,
        ...titulo,
      })),
    } : null;
    if (titulosJson) {
      fs.writeFileSync(path.join(salida, 'titulos.json'), `${JSON.stringify(titulosJson, null, 2)}\n`);
    }

    const html = htmlMuro(lote);
    fs.writeFileSync(path.join(salida, 'index.html'), html);
    const indexSha = sha256(html);

    const manifest = {
      ...lote,
      index: { archivo: 'index.html', sha256: indexSha },
      ...(titulosJson ? { titulos: { archivo: 'titulos.json', sha256: sha256(fs.readFileSync(path.join(salida, 'titulos.json'))) } } : {}),
    };
    fs.writeFileSync(path.join(salida, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);

    console.log('');
    console.log(`Hecho: ${items.length} PNG + index.html + manifest.json`);
    console.log(`Muro: ${path.join(salida, 'index.html')}`);
    console.log(`Manifiesto: ${path.join(salida, 'manifest.json')}`);
    if (!opciones.titulos) console.log('Sin --titulos: los collages se llaman «Collage NNN».');
  } finally {
    if (navegador) await navegador.close().catch(() => {});
    await servidor.close();
  }
}

main().catch((error) => {
  console.error(`Entropía falló: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
