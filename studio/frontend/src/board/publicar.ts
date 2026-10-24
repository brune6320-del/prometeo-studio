import type { BoardCard, BoardMedia } from './model';
import { buildArchive, paragraphs, type ArchiveBlock } from './archivo';
import { buildMuro } from './vistas/muro';
import { buildMesaPieces } from './vistas/mesa';

/**
 * Publicación local de un marco (H-6).
 *
 * Convierte la vista actual del marco (Archivo, Muro o Mesa de luz) en una carpeta
 * estática: index.html + style.css + app.js + media/. Todas las rutas son relativas
 * y el resultado se abre con doble clic, sin servidor y sin subir nada a internet.
 *
 * Este módulo no lee la sesión, ni el host nativo, ni ninguna credencial: el HTML
 * solo contiene el contenido visible del marco y referencias a `media/`.
 */

export type PublishView = 'archivo' | 'muro' | 'mesa';

export const PUBLISH_MAX_IMAGE_EDGE = 1600;
export const PUBLISH_MAX_JS_BYTES = 8 * 1024;
export const PUBLISH_MEDIA_DIR = 'media';

export interface PublishMediaEntry {
  cardId: string;
  /** Ruta relativa tal como aparece en el HTML: `media/01-pieza.jpg`. */
  filename: string;
  width?: number;
  height?: number;
}

export interface PublishPageInput {
  frameTitle: string;
  view: PublishView;
  cards: readonly BoardCard[];
  childIds: readonly string[];
  media: readonly PublishMediaEntry[];
}

export interface PublishPage {
  html: string;
  css: string;
  js: string;
  media: readonly PublishMediaEntry[];
}

/** Recorte de una ruta absoluta o de un token que no debe salir del equipo. */
export function sanitizePublishedHtml(html: string): string {
  return html
    .replace(/\/Users\/[^\s"'<>]+/g, '[ruta local]')
    .replace(/\/home\/[^\s"'<>]+/g, '[ruta local]')
    .replace(/([?&](?:token|access_token|api_token|api_key|key)=)[^&\s"'<>]+/gi, '$1[oculto]')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [oculto]');
}

export function publishSlug(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
}

/** Extensión deducida del MIME y, si no basta, del nombre original. */
export function publishExtension(media: BoardMedia): string {
  const byMime: Record<string, string> = {
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/webp': 'webp',
    'image/gif': 'gif',
    'image/svg+xml': 'svg',
    'image/avif': 'avif',
    'video/mp4': 'mp4',
    'video/webm': 'webm',
    'video/quicktime': 'mov',
    'audio/mpeg': 'mp3',
    'audio/wav': 'wav',
    'audio/ogg': 'ogg',
    'audio/mp4': 'm4a',
    'application/pdf': 'pdf',
  };
  const known = byMime[media.mimeType.toLowerCase()];
  if (known) return known;
  const fromName = /\.([a-z0-9]{1,6})$/i.exec(media.name);
  return fromName ? fromName[1].toLowerCase() : 'bin';
}

export function publishFileName(index: number, card: BoardCard, extension: string): string {
  const base = publishSlug(card.title) || publishSlug(card.media?.name ?? '') || 'pieza';
  return `${PUBLISH_MEDIA_DIR}/${String(index + 1).padStart(2, '0')}-${base}.${extension}`;
}

/** Encaja una imagen dentro del máximo conservando la proporción (1600 px por defecto). */
export function fitImageSize(width: number, height: number, maxEdge = PUBLISH_MAX_IMAGE_EDGE): { width: number; height: number } {
  const safeWidth = Number.isFinite(width) && width > 0 ? width : 1;
  const safeHeight = Number.isFinite(height) && height > 0 ? height : 1;
  const limit = Math.max(1, Number.isFinite(maxEdge) ? maxEdge : PUBLISH_MAX_IMAGE_EDGE);
  const scale = Math.min(1, limit / Math.max(safeWidth, safeHeight));
  return {
    width: Math.max(1, Math.round(safeWidth * scale)),
    height: Math.max(1, Math.round(safeHeight * scale)),
  };
}

function isMediaPiece(card: BoardCard): boolean {
  return card.type === 'media' && Boolean(card.media);
}

/** Piezas que la vista elegida usa de verdad: un archivo por pieza, sin huérfanos. */
export function collectPublishPieces(cards: readonly BoardCard[], childIds: readonly string[], view: PublishView): BoardCard[] {
  if (view === 'archivo') {
    return buildArchive(cards, childIds).blocks.flatMap((block) => block.items).filter(isMediaPiece);
  }
  return buildMuro(cards, childIds).map((item) => item.card).filter(isMediaPiece);
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    if (char === '&') return '&amp;';
    if (char === '<') return '&lt;';
    if (char === '>') return '&gt;';
    if (char === '"') return '&quot;';
    return '&#39;';
  });
}

function safeUrl(value: string): string {
  const trimmed = value.trim();
  return /^(https?:|mailto:)/i.test(trimmed) ? trimmed : '';
}

function paragraphHtml(value: string): string {
  return paragraphs(value).map((part) => `<p>${escapeHtml(part)}</p>`).join('');
}

function mediaByCard(media: readonly PublishMediaEntry[]): Map<string, PublishMediaEntry> {
  return new Map(media.map((entry) => [entry.cardId, entry]));
}

function mediaHtml(card: BoardCard, entry: PublishMediaEntry | undefined): string {
  const media = card.media;
  if (!media || !entry) return `<span class="missing">${escapeHtml(card.title || 'Sin medio')}</span>`;
  const src = escapeHtml(entry.filename);
  const size = entry.width && entry.height ? ` width="${entry.width}" height="${entry.height}"` : '';
  const label = escapeHtml(card.title || media.name);
  if (media.kind === 'image') return `<img src="${src}" alt="${label}"${size} loading="lazy" draggable="false">`;
  if (media.kind === 'video') return `<video src="${src}" controls muted loop playsinline preload="metadata" aria-label="${label}"></video>`;
  if (media.kind === 'audio') return `<audio src="${src}" controls preload="metadata" aria-label="${label}"></audio>`;
  return `<a class="file" href="${src}" download="${escapeHtml(media.name)}">${escapeHtml(media.name)}</a>`;
}

function pieceAttrs(card: BoardCard, entry: PublishMediaEntry | undefined): string {
  if (!entry) return '';
  return ` data-lb data-kind="${escapeHtml(card.media?.kind ?? 'file')}" data-full="${escapeHtml(entry.filename)}" data-title="${escapeHtml(card.title || card.media?.name || '')}"`;
}

function renderPiece(card: BoardCard, entry: PublishMediaEntry | undefined, code: string, title: string, extra = ''): string {
  return `<button class="piece" type="button"${pieceAttrs(card, entry)}${extra}>`
    + `<span class="piece-media">${mediaHtml(card, entry)}</span>`
    + `<span class="piece-meta"><span class="code">${escapeHtml(code || '—')}</span><span class="piece-title">${escapeHtml(title || 'Sin título')}</span></span>`
    + '</button>';
}

function renderCarousel(block: ArchiveBlock, media: Map<string, PublishMediaEntry>): string {
  if (block.items.length === 0) return '';
  const slides = block.items.map((item, index) => {
    const entry = media.get(item.id);
    return `<figure class="slide${index === 0 ? ' is-active' : ''}" data-slide>${mediaHtml(item, entry)}</figure>`;
  }).join('');
  const controls = block.items.length > 1
    ? '<button class="zone prev" type="button" data-prev aria-label="Anterior">←</button>'
      + '<button class="zone next" type="button" data-next aria-label="Siguiente">→</button>'
    : '';
  return `<div class="carousel" data-carousel tabindex="0" role="group" aria-label="Carrusel">${slides}${controls}</div>`;
}

function renderArchivo(input: PublishPageInput, media: Map<string, PublishMediaEntry>): string {
  const layout = buildArchive(input.cards, input.childIds);
  const note = layout.note;
  const blocks = layout.blocks.map((block, index) => {
    const anchor = `b${index + 1}`;
    const status = block.status ? `<div class="status">${escapeHtml(block.status.toUpperCase())}</div>` : '';
    const link = safeUrl(block.url)
      ? `<p class="block-link"><a href="${escapeHtml(safeUrl(block.url))}" rel="noreferrer">${escapeHtml(block.url)}</a></p>`
      : '';
    return `<article class="block" id="${anchor}">
${renderCarousel(block, media)}
<div class="block-meta">
<div class="ident"><div class="code">${escapeHtml(block.code || '')}</div><div class="block-title">${escapeHtml(block.title || block.items[0]?.title || '')}</div>${status}</div>
<div class="block-text">${paragraphHtml(block.text)}${link}</div>
</div>
<hr class="dotted">
</article>`;
  }).join('\n');

  const index = layout.blocks.map((block, position) => {
    const title = block.title || block.items[0]?.title || 'Sin título';
    return `<li><a href="#b${position + 1}"><span class="code">${escapeHtml(block.code || '—')}</span><span>${escapeHtml(title)}</span></a></li>`;
  }).join('');

  return `<div class="page archivo">
<aside class="col note">
<div class="kicker">${escapeHtml(note?.title || 'Nota')}</div><hr class="dotted">
<div class="note-body">${note ? paragraphHtml(note.body) : '<p>Añade una nota al marco para abrir el archivo.</p>'}</div>
<time class="clock" data-clock>--:--:--</time>
</aside>
<main class="col feed">
<div class="kicker">${escapeHtml(input.frameTitle || 'Archivo')}</div><hr class="dotted">
<div class="feed-scroll">${blocks || '<p class="empty">Este marco no tiene piezas todavía.</p>'}</div>
</main>
<aside class="col index">
<div class="kicker">Índice</div><hr class="dotted">
<ol class="index-list">${index || '<li class="empty">Sin entradas.</li>'}</ol>
</aside>
</div>`;
}

function renderMuro(input: PublishPageInput, media: Map<string, PublishMediaEntry>): string {
  const items = buildMuro(input.cards, input.childIds);
  const pieces = items.map((item) => renderPiece(item.card, media.get(item.id), item.code, item.title)).join('\n');
  return `<div class="page muro">
<header class="strip"><span>Muro</span><span>${items.length} ${items.length === 1 ? 'pieza' : 'piezas'}</span></header>
<div class="muro-grid">${pieces || '<p class="empty">Este marco no tiene piezas todavía.</p>'}</div>
</div>`;
}

function renderMesa(input: PublishPageInput, media: Map<string, PublishMediaEntry>): string {
  const pieces = buildMesaPieces(input.cards, input.childIds, 7);
  const html = pieces.map((piece) => {
    const extra = ` style="--rot:${piece.rotation}deg;--aspect:${Math.max(0.2, piece.aspect)}"`;
    return renderPiece(piece.card, media.get(piece.id), piece.code, piece.title, extra);
  }).join('\n');
  return `<div class="page mesa">
<header class="strip"><span>Mesa de luz</span><span>${pieces.length} ${pieces.length === 1 ? 'pieza' : 'piezas'}</span></header>
<div class="mesa-surface">${html || '<p class="empty">Este marco no tiene piezas todavía.</p>'}</div>
</div>`;
}

export function buildPublishPage(input: PublishPageInput): PublishPage {
  const media = mediaByCard(input.media);
  const body = input.view === 'archivo'
    ? renderArchivo(input, media)
    : input.view === 'muro'
      ? renderMuro(input, media)
      : renderMesa(input, media);
  const title = escapeHtml(input.frameTitle || 'Archivo');
  const html = sanitizePublishedHtml(`<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<link rel="stylesheet" href="style.css">
</head>
<body class="view-${input.view}">
${body}
<div class="lightbox" data-lightbox hidden>
<div class="lb-head"><span class="code" data-lb-code></span><strong data-lb-title></strong><span class="lb-count" data-lb-count></span><button type="button" class="lb-close" data-lb-close aria-label="Cerrar">ⓧ</button></div>
<div class="lb-stage"><button type="button" class="lb-nav" data-lb-prev aria-label="Anterior">←</button><div class="lb-media" data-lb-media></div><button type="button" class="lb-nav" data-lb-next aria-label="Siguiente">→</button></div>
<div class="lb-hint">← → recorrer · Esc cerrar</div>
</div>
<script src="app.js"></script>
</body>
</html>
`);
  return { html, css: PUBLISH_CSS, js: PUBLISH_JS, media: input.media };
}

export const PUBLISH_CSS = `:root{--ink:#111;--muted:#8a8a86;--rule:#d6d2c8;--paper:#fff;--wall:#faf8f3;--table:#f3eee4;--mono:"Diatype Mono Variable","JetBrains Mono","IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;--sans:"Helvetica Neue",Helvetica,Arial,sans-serif}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;background:var(--paper);color:var(--ink);font:12.96px/1.5 var(--sans);-webkit-font-smoothing:antialiased}
img,video{display:block;max-width:100%}
button{font:inherit;color:inherit;text-align:left}
a{color:inherit}
.code,.clock,.strip,.status,.kicker{font-family:var(--mono);letter-spacing:-.02em}
.code{font-size:.72rem;color:#55534e}
.kicker{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:#55534e}
.dotted{border:0;border-top:1px dotted var(--rule);margin:8px 0}
.empty{color:var(--muted);font-family:var(--mono);font-size:.75rem}
.missing{display:block;padding:18px;color:var(--muted);font-family:var(--mono);font-size:.75rem;background:#f1efe9}
.page{min-height:100vh}
.archivo{display:grid;grid-template-columns:25% 50% 25%}
.col{padding:14px 16px;border-right:1px solid var(--rule);min-width:0}
.col:last-child{border-right:0}
.note{display:flex;flex-direction:column;position:sticky;top:0;height:100vh}
.note-body{flex:1 1 auto;overflow:auto;font-size:.86rem}
.note-body p,.block-text p{margin:0 0 .7em}
.clock{margin-top:10px;color:var(--muted);font-size:.72rem}
.feed{height:100vh;display:flex;flex-direction:column;overflow:hidden}
.feed-scroll{flex:1 1 auto;overflow:auto;padding-right:4px}
.block{margin:0 0 20px}
.carousel{position:relative;background:#efede7;margin:6px 0 8px;outline-offset:3px}
.slide{display:none;margin:0;min-height:80px}
.slide.is-active{display:block}
.slide img{width:100%;max-height:64vh;object-fit:contain;margin:0 auto}
.slide video{width:100%;max-height:64vh;background:#000}
.slide audio{width:100%;padding:24px}
.slide .file{padding:28px;display:block}
.zone{position:absolute;top:0;bottom:0;width:18%;border:0;background:transparent;cursor:pointer;font-size:22px;color:#fff;opacity:0;transition:opacity .15s}
.carousel:hover .zone,.zone:focus-visible{opacity:.85;background:rgba(20,20,20,.22)}
.zone.prev{left:0}
.zone.next{right:0}
.block-meta{display:grid;grid-template-columns:34% 66%;gap:12px}
.ident .block-title{font-size:.84rem;margin:2px 0}
.status{font-size:.66rem;color:var(--muted);text-transform:uppercase}
.block-text{font-size:.8rem;color:#34322e}
.block-link{word-break:break-all;font-family:var(--mono);font-size:.68rem;color:#3c5a70}
.index{position:sticky;top:0;height:100vh;overflow:auto}
.index-list{list-style:none;margin:0;padding:0;font-size:.74rem}
.index-list li{margin:0 0 3px}
.index-list a{display:flex;gap:8px;text-decoration:none;padding:3px 4px;border-radius:4px}
.index-list a:hover{background:#f1efe9}
.strip{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid var(--rule);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em}
.muro{background:var(--wall)}
.muro-grid{columns:4 180px;column-gap:10px;padding:14px}
.piece{display:block;width:100%;break-inside:avoid;margin:0 0 10px;padding:0;border:0;background:transparent;cursor:zoom-in}
.piece-media{display:block;background:#e9e6de;overflow:hidden}
.piece-media img{width:100%;height:auto}
.piece-media video,.piece-media audio{width:100%}
.piece-media .file{display:block;padding:18px;font-family:var(--mono);font-size:.7rem;word-break:break-all}
.piece-meta{display:flex;flex-direction:column;gap:1px;padding:5px 2px}
.piece-title{font-size:.76rem;line-height:1.3}
.mesa{background:var(--table)}
.mesa-surface{display:flex;flex-wrap:wrap;align-content:flex-start;justify-content:center;gap:26px 20px;padding:38px 24px}
.mesa .piece{width:clamp(130px,21vw,190px);margin:0;padding:7px 7px 5px;background:#fff;box-shadow:0 7px 16px rgba(40,34,24,.18),0 1px 2px rgba(40,34,24,.14);transform:rotate(var(--rot,0deg))}
.mesa .piece-media img{width:100%;height:auto}
.lightbox{position:fixed;inset:0;z-index:99;display:flex;flex-direction:column;background:#fff;padding:14px 18px}
.lightbox[hidden]{display:none}
.lb-head{display:flex;align-items:center;gap:12px;font-size:.78rem}
.lb-head strong{font-size:.86rem}
.lb-count{margin-left:auto;color:var(--muted);font-family:var(--mono);font-size:.72rem}
.lb-close{border:0;background:transparent;font-size:19px;cursor:pointer;padding:2px 6px}
.lb-stage{flex:1 1 auto;display:flex;align-items:center;gap:10px;min-height:0}
.lb-media{flex:1 1 auto;height:100%;display:flex;align-items:center;justify-content:center;min-width:0}
.lb-media img,.lb-media video{max-width:100%;max-height:100%;object-fit:contain}
.lb-media audio{width:min(520px,100%)}
.lb-nav{flex:0 0 46px;height:64px;border:0;background:transparent;font-size:26px;cursor:pointer;color:#6d6a64}
.lb-nav:hover{color:#111}
.lb-hint{text-align:center;color:var(--muted);font-family:var(--mono);font-size:.68rem;padding:6px 0}
@media(max-width:760px){.archivo{grid-template-columns:1fr}.note,.feed,.index{position:static;height:auto}.col{border-right:0;border-bottom:1px solid var(--rule)}.feed{height:auto}.feed-scroll{overflow:visible}.block-meta{grid-template-columns:1fr}.muro-grid{columns:2 140px}}
`;

export const PUBLISH_JS = `(function(){
"use strict";
function pad(n){return String(n).padStart(2,"0");}
function tick(){var d=new Date();var t=pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds());document.querySelectorAll("[data-clock]").forEach(function(el){el.textContent=t;});}
tick();setInterval(tick,1000);
document.querySelectorAll("[data-carousel]").forEach(function(box){
  var slides=Array.prototype.slice.call(box.querySelectorAll("[data-slide]"));
  if(slides.length<2)return;
  var at=0;
  function show(next){slides[at].classList.remove("is-active");at=(next+slides.length)%slides.length;slides[at].classList.add("is-active");}
  var prev=box.querySelector("[data-prev]"),next=box.querySelector("[data-next]");
  if(prev)prev.addEventListener("click",function(){show(at-1);});
  if(next)next.addEventListener("click",function(){show(at+1);});
  box.addEventListener("keydown",function(event){if(event.key==="ArrowLeft"){event.preventDefault();show(at-1);}else if(event.key==="ArrowRight"){event.preventDefault();show(at+1);}});
});
var box=document.querySelector("[data-lightbox]");
var triggers=Array.prototype.slice.call(document.querySelectorAll("[data-lb]"));
if(box&&triggers.length){
  var frame=box.querySelector("[data-lb-media]"),title=box.querySelector("[data-lb-title]"),code=box.querySelector("[data-lb-code]"),count=box.querySelector("[data-lb-count]"),at=0;
  function fill(index){
    at=(index+triggers.length)%triggers.length;
    var item=triggers[at],src=item.getAttribute("data-full"),kind=item.getAttribute("data-kind"),node;
    frame.textContent="";
    if(kind==="video"){node=document.createElement("video");node.controls=true;node.autoplay=true;node.muted=true;node.loop=true;node.src=src;}
    else if(kind==="audio"){node=document.createElement("audio");node.controls=true;node.autoplay=true;node.src=src;}
    else if(kind==="file"){node=document.createElement("a");node.href=src;node.download=src.split("/").pop();node.textContent=item.getAttribute("data-title")||"Descargar";}
    else{node=document.createElement("img");node.src=src;node.alt=item.getAttribute("data-title")||"";}
    frame.appendChild(node);
    title.textContent=item.getAttribute("data-title")||"";
    code.textContent=item.querySelector(".code")?item.querySelector(".code").textContent:"";
    count.textContent=(at+1)+" / "+triggers.length;
    box.hidden=false;
    document.body.style.overflow="hidden";
  }
  function close(){box.hidden=true;frame.textContent="";document.body.style.overflow="";}
  triggers.forEach(function(item,index){item.addEventListener("click",function(){fill(index);});});
  box.querySelector("[data-lb-close]").addEventListener("click",close);
  box.querySelector("[data-lb-prev]").addEventListener("click",function(){fill(at-1);});
  box.querySelector("[data-lb-next]").addEventListener("click",function(){fill(at+1);});
  box.addEventListener("mousedown",function(event){if(event.target===box)close();});
  document.addEventListener("keydown",function(event){
    if(!box.hidden&&event.key==="Escape"){event.preventDefault();close();}
    else if(!box.hidden&&event.key==="ArrowLeft"){event.preventDefault();fill(at-1);}
    else if(!box.hidden&&event.key==="ArrowRight"){event.preventDefault();fill(at+1);}
  });
}
})();
`;

interface WritableFile {
  createWritable(): Promise<{ write(data: Blob | Uint8Array | string): Promise<void>; close(): Promise<void> }>;
}

interface WritableDirectory {
  getDirectoryHandle(name: string, options?: { create?: boolean }): Promise<WritableDirectory>;
  getFileHandle(name: string, options?: { create?: boolean }): Promise<WritableFile>;
}

type PickerWindow = Window & {
  showDirectoryPicker?: (options?: { mode?: 'read' | 'readwrite' }) => Promise<WritableDirectory>;
};

export interface PublishResult {
  cancelled: boolean;
  folder: string;
  files: number;
  media: number;
  /** true cuando el navegador no permite elegir carpeta y se descargó un ZIP. */
  zip: boolean;
}

export interface PreparedAsset {
  cardId: string;
  bytes: Blob;
  extension: string;
  width?: number;
  height?: number;
}

export interface PublishZipFile {
  name: string;
  bytes: Uint8Array;
}

let crcTable: Uint32Array | null = null;

function crc32(bytes: Uint8Array): number {
  if (!crcTable) {
    crcTable = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let value = n;
      for (let bit = 0; bit < 8; bit += 1) value = (value & 1) ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1);
      crcTable[n] = value >>> 0;
    }
  }
  let crc = 0xffffffff;
  for (const byte of bytes) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

/** ZIP sin compresión (método «store»), suficiente para entregar la carpeta publicada. */
export function buildPublishZip(files: readonly PublishZipFile[]): Uint8Array {
  const encoder = new TextEncoder();
  const local: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;

  for (const file of files) {
    const name = encoder.encode(file.name);
    const crc = crc32(file.bytes);
    const head = new Uint8Array(30 + name.length);
    const view = new DataView(head.buffer);
    view.setUint32(0, 0x04034b50, true);
    view.setUint16(4, 20, true);
    view.setUint16(6, 0x0800, true);
    view.setUint32(14, crc, true);
    view.setUint32(18, file.bytes.length, true);
    view.setUint32(22, file.bytes.length, true);
    view.setUint16(26, name.length, true);
    head.set(name, 30);
    local.push(head, file.bytes);

    const entry = new Uint8Array(46 + name.length);
    const entryView = new DataView(entry.buffer);
    entryView.setUint32(0, 0x02014b50, true);
    entryView.setUint16(4, 20, true);
    entryView.setUint16(6, 20, true);
    entryView.setUint16(8, 0x0800, true);
    entryView.setUint32(16, crc, true);
    entryView.setUint32(20, file.bytes.length, true);
    entryView.setUint32(24, file.bytes.length, true);
    entryView.setUint16(28, name.length, true);
    entryView.setUint32(42, offset, true);
    entry.set(name, 46);
    central.push(entry);

    offset += head.length + file.bytes.length;
  }

  const centralSize = central.reduce((total, part) => total + part.length, 0);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(8, files.length, true);
  endView.setUint16(10, files.length, true);
  endView.setUint32(12, centralSize, true);
  endView.setUint32(16, offset, true);

  const total = offset + centralSize + end.length;
  const zip = new Uint8Array(total);
  let cursor = 0;
  for (const part of [...local, ...central, end]) {
    zip.set(part, cursor);
    cursor += part.length;
  }
  return zip;
}

function dataUrlBlob(dataUrl: string): Blob {
  const comma = dataUrl.indexOf(',');
  const meta = dataUrl.slice(5, comma);
  const mime = meta.split(';')[0] || 'application/octet-stream';
  const binary = atob(dataUrl.slice(comma + 1));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: mime });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('No se pudo leer una imagen del marco.'));
    image.src = src;
  });
}

function canvasBlob(canvas: HTMLCanvasElement, mimeType: string): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('No se pudo reducir una imagen.'))), mimeType, 0.86);
  });
}

/** Imagen ≤1600 px: si ya cabe se conserva tal cual; si no, se reduce en memoria. */
export async function preparePublishAsset(card: BoardCard): Promise<PreparedAsset> {
  const media = card.media;
  if (!media) throw new Error('Pieza sin medio.');
  if (media.kind !== 'image') {
    return { cardId: card.id, bytes: dataUrlBlob(media.dataUrl), extension: publishExtension(media) };
  }
  let image: HTMLImageElement;
  try {
    image = await loadImage(media.dataUrl);
  } catch {
    return { cardId: card.id, bytes: dataUrlBlob(media.dataUrl), extension: publishExtension(media) };
  }
  const target = fitImageSize(image.naturalWidth, image.naturalHeight);
  if (target.width === image.naturalWidth && target.height === image.naturalHeight) {
    return { cardId: card.id, bytes: dataUrlBlob(media.dataUrl), extension: publishExtension(media), ...target };
  }
  const canvas = document.createElement('canvas');
  canvas.width = target.width;
  canvas.height = target.height;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('El navegador no puede reducir imágenes.');
  context.drawImage(image, 0, 0, target.width, target.height);
  const keepPng = /png|webp|gif|svg/i.test(media.mimeType);
  const outputMime = keepPng ? 'image/png' : 'image/jpeg';
  const bytes = await canvasBlob(canvas, outputMime);
  return { cardId: card.id, bytes, extension: keepPng ? 'png' : 'jpg', ...target };
}

async function writeText(dir: WritableDirectory, name: string, content: string): Promise<void> {
  const handle = await dir.getFileHandle(name, { create: true });
  const writable = await handle.createWritable();
  await writable.write(content);
  await writable.close();
}

async function writeBlob(dir: WritableDirectory, name: string, bytes: Blob): Promise<void> {
  const handle = await dir.getFileHandle(name, { create: true });
  const writable = await handle.createWritable();
  await writable.write(bytes);
  await writable.close();
}

interface PreparedPublish {
  pieces: BoardCard[];
  assets: PreparedAsset[];
  entries: PublishMediaEntry[];
  page: PublishPage;
}

async function preparePublishedFiles(
  frameTitle: string,
  view: PublishView,
  cards: readonly BoardCard[],
  childIds: readonly string[],
): Promise<PreparedPublish> {
  const pieces = collectPublishPieces(cards, childIds, view);
  const assets: PreparedAsset[] = [];
  for (const card of pieces) assets.push(await preparePublishAsset(card));
  const entries: PublishMediaEntry[] = assets.map((asset, index) => ({
    cardId: asset.cardId,
    filename: publishFileName(index, pieces[index], asset.extension),
    width: asset.width,
    height: asset.height,
  }));
  return { pieces, assets, entries, page: buildPublishPage({ frameTitle, view, cards, childIds, media: entries }) };
}

function downloadZip(name: string, bytes: Uint8Array): void {
  const url = URL.createObjectURL(new Blob([bytes.buffer as ArrayBuffer], { type: 'application/zip' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/**
 * Pide una carpeta y escribe en ella la publicación. La elección ocurre antes de
 * preparar las imágenes para no perder el gesto del usuario. Si el navegador no
 * tiene selector de carpetas, entrega el mismo contenido como ZIP descargable.
 */
export async function publishFrameToDirectory(
  frameTitle: string,
  view: PublishView,
  cards: readonly BoardCard[],
  childIds: readonly string[],
): Promise<PublishResult> {
  const picker = (window as PickerWindow).showDirectoryPicker;
  let dir: WritableDirectory | null = null;
  if (picker) {
    try {
      dir = await picker({ mode: 'readwrite' });
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return { cancelled: true, folder: '', files: 0, media: 0, zip: false };
      }
      throw error;
    }
  }

  const prepared = await preparePublishedFiles(frameTitle, view, cards, childIds);

  if (!dir) {
    const files: PublishZipFile[] = [
      { name: 'index.html', bytes: new TextEncoder().encode(prepared.page.html) },
      { name: 'style.css', bytes: new TextEncoder().encode(prepared.page.css) },
      { name: 'app.js', bytes: new TextEncoder().encode(prepared.page.js) },
      ...await Promise.all(prepared.assets.map(async (asset, index) => ({
        name: prepared.entries[index].filename,
        bytes: new Uint8Array(await asset.bytes.arrayBuffer()),
      }))),
    ];
    downloadZip(`${publishSlug(frameTitle) || 'publicacion'}.zip`, buildPublishZip(files));
    return { cancelled: false, folder: 'ZIP descargado', files: files.length, media: prepared.assets.length, zip: true };
  }

  const mediaDir = await dir.getDirectoryHandle(PUBLISH_MEDIA_DIR, { create: true });
  await writeText(dir, 'index.html', prepared.page.html);
  await writeText(dir, 'style.css', prepared.page.css);
  await writeText(dir, 'app.js', prepared.page.js);
  for (let index = 0; index < prepared.assets.length; index += 1) {
    const entry = prepared.entries[index];
    const name = entry.filename.slice(PUBLISH_MEDIA_DIR.length + 1);
    await writeBlob(mediaDir, name, prepared.assets[index].bytes);
  }

  return {
    cancelled: false,
    folder: (dir as WritableDirectory & { name?: string }).name || 'carpeta elegida',
    files: 3 + prepared.entries.length,
    media: prepared.entries.length,
    zip: false,
  };
}
