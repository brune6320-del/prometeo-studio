import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { BoardCard } from '../board/model';
import { createBoard, createCard, makeBoardExport, normalizeBoard, parseBoardImport } from '../board/model';
import {
  normalizarReferente,
  referenteMarkdown,
  type Referente,
} from '../board/referentes/model';
import { getBoardTool } from '../board/tools/registry';
import { BoardCardContent } from '../board/tools/CardView';

const NOOP = () => {};

const REFERENTE: Referente = {
  nombre: 'Pareidolia',
  url: 'https://example.com/pareidolia',
  archivoOrigen: 'pareidolia-luna.png',
  autor: 'Irene Guerra',
  anio: '1972',
  licencia: 'CC BY-NC 4.0',
  porQue: 'Me sirve el gesto de mirar dos veces la misma mancha.',
  etiquetas: ['collage', 'archivo', 'pareidolia'],
  imagenes: [
    { name: 'pareidolia.png', mimeType: 'image/png', dataUrl: 'data:image/png;base64,AAAA', kind: 'image' },
  ],
  vistoEn: ['2026-10-01', '2026-09-15'],
  lecturas: [
    { fecha: '2026-09-15', proyecto: 'Luna', ojos: 'archivista', texto: 'Lectura vieja.', modelo: 'deepseek', aceptada: true },
    { fecha: '2026-10-02', proyecto: 'Collage', ojos: 'collagista dadá', texto: 'El corte es la idea.', modelo: 'deepseek', aceptada: false },
  ],
};

describe('herramienta Referente', () => {
  it('valida su tarjeta y rechaza otras herramientas', () => {
    const tool = getBoardTool('referente');
    expect(tool).toBeDefined();
    const card = tool!.crear(80, 120);
    expect(tool!.validar(card)).toBe(true);
    expect(tool!.validar(createCard('note', 0, 0))).toBe(false);
    expect(tool!.validar({ ...card, datos: { nombre: 3 } })).toBe(false);
    expect(tool!.exportarMarkdown).toBeTypeOf('function');

    const Vista = tool!.Vista;
    const html = renderToStaticMarkup(<Vista datos={{ ...card, datos: { ...REFERENTE } }} editar={NOOP} />);
    expect(html).toContain('Pareidolia');
    expect(html).toContain('pareidolia-luna.png · 1972');
    expect(html).toContain('Por qué lo guardé');
    expect(html).toContain('El corte es la idea.');
  });

  it('va y vuelve de JSON sin perder campos', () => {
    const normalizado = normalizarReferente(REFERENTE);
    const vuelta = normalizarReferente(JSON.parse(JSON.stringify(normalizado)));
    expect(vuelta).toEqual(normalizado);
    expect(vuelta.imagenes[0].dataUrl).toBe('data:image/png;base64,AAAA');
    expect(vuelta.lecturas.map((lectura) => lectura.ojos)).toEqual(['archivista', 'collagista dadá']);

    const tool = getBoardTool('referente')!;
    const board = createBoard('Biblioteca');
    board.cards.push({ ...tool.crear(10, 20), title: 'Pareidolia', datos: normalizado });
    const saved = JSON.parse(JSON.stringify(makeBoardExport(board)));
    const loaded = parseBoardImport(saved)!;
    expect(loaded.cards[0].type).toBe('referente');
    expect(loaded.cards[0].datos).toEqual(normalizado);
    expect(normalizarReferente(loaded.cards[0].datos)).toEqual(normalizado);
  });

  it('un tablero viejo sin referentes carga igual', () => {
    const viejo = {
      schemaVersion: 1,
      id: 'b-viejo',
      title: 'Tablero antiguo',
      createdAt: '2026-01-02T03:04:05.000Z',
      updatedAt: '2026-01-02T03:04:05.000Z',
      cards: [
        { id: 'n1', type: 'note', title: 'Nota', body: 'Idea vieja', x: 10, y: 20, width: 260, color: 'paper' },
        { id: 'l1', type: 'link', title: 'Fuente', body: '', url: 'https://example.com/a', x: 300, y: 20, width: 260, color: 'sage' },
      ],
      relations: [{ id: 'r1', from: 'n1', to: 'l1' }],
    };

    const cargado = normalizeBoard(viejo)!;
    expect(cargado).toEqual(normalizeBoard(viejo));
    expect(cargado.cards.map((card) => card.type)).toEqual(['note', 'link']);
    expect(cargado.cards.some((card) => card.type === 'referente')).toBe(false);
    expect(cargado.relations).toHaveLength(1);

    const html = renderToStaticMarkup(<BoardCardContent card={cargado.cards[0] as BoardCard} editar={NOOP} />);
    expect(html).toContain('Idea vieja');
  });

  it('exporta Markdown con enlace a la fuente y la última lectura', () => {
    const tool = getBoardTool('referente')!;
    const card = { ...tool.crear(0, 0), title: REFERENTE.nombre, datos: REFERENTE };
    const markdown = tool.exportarMarkdown!(card);

    expect(markdown).toContain('## Pareidolia');
    expect(markdown).toContain('[Fuente](https://example.com/pareidolia)');
    expect(markdown).toContain('pareidolia-luna.png · 1972');
    expect(markdown).toContain('**Licencia:** CC BY-NC 4.0');
    expect(markdown).toContain('collage, archivo, pareidolia');
    expect(markdown).toContain('El corte es la idea.');
    expect(markdown).not.toContain('Lectura vieja.');

    const sinUrlSegura = referenteMarkdown({ ...REFERENTE, url: 'javascript:alert(1)' });
    expect(sinUrlSegura).not.toContain('[Fuente](');
    expect(sinUrlSegura).toContain('Fuente: javascript:alert(1)');
  });
});
