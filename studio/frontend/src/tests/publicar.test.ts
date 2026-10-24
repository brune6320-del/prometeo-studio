import { describe, expect, it } from 'vitest';
import type { BoardCard } from '../board/model';
import {
  buildPublishPage,
  buildPublishZip,
  collectPublishPieces,
  fitImageSize,
  publishFileName,
  publishSlug,
  PUBLISH_JS,
  PUBLISH_MAX_IMAGE_EDGE,
  PUBLISH_MAX_JS_BYTES,
  type PublishMediaEntry,
  type PublishView,
} from '../board/publicar';

function card(id: string, type: BoardCard['type'], patch: Partial<BoardCard> = {}): BoardCard {
  return { id, type, title: id, body: '', x: 100, y: 100, width: 290, color: 'paper', ...patch };
}

function media(id: string, title: string, kind: 'image' | 'video' | 'audio' | 'file' = 'image'): BoardCard {
  const mimeType = kind === 'image' ? 'image/png' : kind === 'video' ? 'video/mp4' : kind === 'audio' ? 'audio/mpeg' : 'application/pdf';
  return card(id, 'media', {
    title,
    media: { name: `${id}.${kind === 'image' ? 'png' : kind === 'video' ? 'mp4' : kind === 'audio' ? 'mp3' : 'pdf'}`, mimeType, dataUrl: `data:${mimeType};base64,AAAA`, kind },
  });
}

function build(view: PublishView, cards: BoardCard[], childIds: string[]) {
  const pieces = collectPublishPieces(cards, childIds, view);
  const entries: PublishMediaEntry[] = pieces.map((piece, index) => ({
    cardId: piece.id,
    filename: publishFileName(index, piece, 'png'),
    width: 1200,
    height: 800,
  }));
  return buildPublishPage({ frameTitle: 'Luna', view, cards, childIds, media: entries });
}

const CHILDREN: BoardCard[] = [
  card('nota', 'note', { title: 'Estudio', body: 'Nota fija.\n\nSegundo párrafo.' }),
  card('etiqueta', 'etiqueta', { title: 'EN EXHIBICIÓN', body: 'DE-P01.01' }),
  media('m1', 'Pareidolía'),
  media('m2', 'Pareidolía · detalle'),
  card('link', 'link', { title: 'Referencia', url: 'https://example.test/obra?token=tok123&lang=es' }),
];
const IDS = CHILDREN.map((item) => item.id);

describe('publicar: HTML seguro y sin red', () => {
  it('no filtra rutas locales ni tokens, y no incrusta data URLs', () => {
    const withPath = [...CHILDREN, card('fuga', 'note', { title: '/Users/bruno/privado', body: 'Copia en /Users/bruno/Projects/x.png y Bearer abc.def.ghi' })];
    const page = build('archivo', withPath, [...IDS, 'fuga']);
    expect(page.html).not.toContain('/Users/');
    expect(page.html).not.toContain('tok123');
    expect(page.html).not.toContain('abc.def.ghi');
    expect(page.html).toContain('[ruta local]');
    expect(page.html).not.toContain('data:image');
    expect(page.html).not.toMatch(/(src|href)="\//);
    expect(page.html).toContain('href="#b1"');
    expect(page.html).toContain('<time class="clock" data-clock>');
    expect(page.html).toContain('data-carousel');
    expect(page.html).toContain('href="style.css"');
    expect(page.html).toContain('src="app.js"');
  });

  it('la vista Muro y la Mesa llevan caja de luz y rutas relativas', () => {
    const muro = build('muro', CHILDREN, IDS);
    expect(muro.html).toContain('data-lightbox');
    expect(muro.html).toContain('data-lb');
    expect(muro.html).toContain('src="media/01-pareidolia.png"');
    const mesa = build('mesa', CHILDREN, IDS);
    expect(mesa.html).toContain('--rot:');
    expect(mesa.html).not.toContain('/Users/');
  });
});

describe('publicar: un archivo por pieza', () => {
  it('genera un nombre único y relativo por cada pieza de la vista', () => {
    for (const view of ['archivo', 'muro', 'mesa'] as const) {
      const page = build(view, CHILDREN, IDS);
      expect(page.media).toHaveLength(2);
      const names = page.media.map((entry) => entry.filename);
      expect(new Set(names).size).toBe(names.length);
      for (const name of names) {
        expect(name.startsWith('media/')).toBe(true);
        expect(page.html).toContain(`src="${name}"`);
      }
    }
    expect(collectPublishPieces(CHILDREN, IDS, 'muro').map((piece) => piece.id)).toEqual(['m1', 'm2']);
    expect(publishSlug('Pareidolía · detalle')).toBe('pareidolia-detalle');
  });
});

describe('publicar: JS mínimo', () => {
  it('ocupa 8 KB como máximo y resuelve reloj, carrusel y caja de luz', () => {
    const bytes = new TextEncoder().encode(PUBLISH_JS).length;
    expect(bytes).toBeLessThanOrEqual(PUBLISH_MAX_JS_BYTES);
    expect(PUBLISH_JS).toContain('[data-clock]');
    expect(PUBLISH_JS).toContain('[data-carousel]');
    expect(PUBLISH_JS).toContain('[data-lightbox]');
  });
});

describe('publicar: imágenes ≤1600 px', () => {
  it('reduce solo lo que excede el máximo, conservando la proporción', () => {
    expect(fitImageSize(2400, 1200)).toEqual({ width: 1600, height: 800 });
    expect(fitImageSize(1200, 2400)).toEqual({ width: 800, height: 1600 });
    expect(fitImageSize(800, 600)).toEqual({ width: 800, height: 600 });
    expect(fitImageSize(0, 0).width).toBe(1);
    expect(PUBLISH_MAX_IMAGE_EDGE).toBe(1600);
  });
});

describe('publicar: ZIP de respaldo', () => {
  it('empaqueta index.html, style.css, app.js y media/ en un ZIP válido', () => {
    const encoder = new TextEncoder();
    const zip = buildPublishZip([
      { name: 'index.html', bytes: encoder.encode('<h1>Luna</h1>') },
      { name: 'style.css', bytes: encoder.encode('body{}') },
      { name: 'app.js', bytes: encoder.encode('void 0;') },
      { name: 'media/01-pieza.png', bytes: new Uint8Array([137, 80, 78, 71]) },
    ]);
    expect(Array.from(zip.slice(0, 4))).toEqual([0x50, 0x4b, 0x03, 0x04]);
    expect(zip.length).toBeGreaterThan(100);
    const text = new TextDecoder().decode(zip);
    expect(text).toContain('index.html');
    expect(text).toContain('style.css');
    expect(text).toContain('app.js');
    expect(text).toContain('media/01-pieza.png');
    expect(Array.from(zip.slice(-22, -18))).toEqual([0x50, 0x4b, 0x05, 0x06]);
  });
});
