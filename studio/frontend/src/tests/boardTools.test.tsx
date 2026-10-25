import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { BoardCard } from '../board/model';
import { createBoard, makeBoardExport, normalizeBoard, parseBoardImport } from '../board/model';
import { emptyBoardHistory, recordBoardChange, undoBoardChange } from '../board/history';
import { BoardCardContent } from '../board/tools/CardView';
import { BoardToolMenu } from '../board/tools/menu';
import { getBoardTool, listBoardTools } from '../board/tools/registry';

const LEGACY_BOARD = {
  schemaVersion: 1,
  id: 'b-legacy',
  title: 'Tablero antiguo',
  createdAt: '2026-01-02T03:04:05.000Z',
  updatedAt: '2026-01-02T03:04:05.000Z',
  cards: [
    { id: 'n1', type: 'note', title: 'Nota', body: 'Idea vieja', x: 10, y: 20, width: 260, color: 'paper' },
    { id: 'l1', type: 'link', title: 'Fuente', body: '', url: 'https://example.com/a', x: 300, y: 20, width: 260, color: 'sage' },
    {
      id: 'm1',
      type: 'media',
      title: 'Imagen',
      body: 'Comentario',
      x: 600,
      y: 20,
      width: 290,
      color: 'rose',
      media: { name: 'x.png', mimeType: 'image/png', dataUrl: 'data:image/png;base64,AAAA', kind: 'image' },
    },
  ],
  relations: [{ id: 'r1', from: 'n1', to: 'l1' }],
};

const NOOP = () => {};
const renderContent = (card: BoardCard) =>
  renderToStaticMarkup(<BoardCardContent card={card} editar={NOOP} />);

describe('registro de herramientas del tablero', () => {
  it('registra note, link, media, etiqueta, referente, marco y entropía con su contrato', () => {
    expect(listBoardTools().map((tool) => tool.id)).toEqual(['note', 'link', 'media', 'etiqueta', 'referente', 'marco', 'entropia']);
    for (const id of ['note', 'link', 'media', 'etiqueta', 'referente', 'marco', 'entropia']) {
      const tool = getBoardTool(id);
      expect(tool).toBeDefined();
      expect(tool?.tipo).toBe(id === 'marco' || id === 'entropia' ? 'marco' : 'tarjeta');
      expect(tool?.nombre).toBeTruthy();
      expect(tool?.icono).toBeTruthy();
      expect(tool?.validar(tool?.crear(0, 0))).toBe(true);
    }
    expect(getBoardTool('muro')).toBeUndefined();
  });

  it('el menú se arma desde el registro y muestra las 7 herramientas', () => {
    const html = renderToStaticMarkup(<BoardToolMenu onChoose={NOOP} />);
    expect((html.match(/role="menuitem"/g) ?? []).length).toBe(7);
    for (const nombre of ['Nota', 'Enlace', 'Multimedia', 'Etiqueta', 'Referente', 'Marco', 'Entropía']) {
      expect(html).toContain(nombre);
    }
  });

  it('crear con cualquier herramienta y deshacer devuelve el tablero a su estado anterior', () => {
    for (const id of ['note', 'link', 'media', 'etiqueta', 'referente', 'marco', 'entropia']) {
      const tool = getBoardTool(id);
      const before = createBoard('Prueba');
      const card = tool!.crear(120, 80);
      const after = { ...before, cards: [card] };

      const history = recordBoardChange(emptyBoardHistory(), before, after);
      expect(history.undo).toHaveLength(1);

      const undone = undoBoardChange(history, after);
      expect(undone.board?.cards).toEqual([]);
      expect(undone.history.redo).toHaveLength(1);
    }
  });

  it('un tablero viejo carga igual (snapshot)', () => {
    const board = normalizeBoard(LEGACY_BOARD);
    expect(board).not.toBeNull();
    expect(board).toMatchSnapshot();
    expect(renderContent(board!.cards[0])).toMatchSnapshot();
    expect(renderContent(board!.cards[1])).toMatchSnapshot();
    expect(renderContent(board!.cards[2])).toMatchSnapshot();
  });

  it('un tipo desconocido no se pierde al guardar', () => {
    const loaded = normalizeBoard({
      schemaVersion: 1,
      id: 'b-futuro',
      title: 'Tablero futuro',
      cards: [
        {
          id: 'u1',
          type: 'muro',
          title: 'Muro importado',
          body: 'Datos de una herramienta que aún no existe',
          x: 42,
          y: 84,
          width: 300,
          color: 'sand',
          url: 'https://example.com/muro',
          alto: 300,
          capas: [{ id: 'capa-1', opacidad: 0.5 }],
        },
      ],
      relations: [],
    });

    expect(loaded?.cards[0].type).toBe('muro');

    // Guardar y volver a abrir: structured clone de IndexedDB equivale a este ciclo JSON.
    const saved = JSON.parse(JSON.stringify(makeBoardExport(loaded!)));
    const reloaded = parseBoardImport(saved);

    expect(reloaded?.cards[0]).toEqual(loaded!.cards[0]);
    expect(reloaded?.cards[0].type).toBe('muro');
    expect(reloaded?.cards[0].body).toBe('Datos de una herramienta que aún no existe');
    expect(reloaded?.cards[0].url).toBe('https://example.com/muro');
    expect(reloaded?.cards[0].datos).toEqual({ alto: 300, capas: [{ id: 'capa-1', opacidad: 0.5 }] });

    const html = renderContent(reloaded!.cards[0]);
    expect(html).toContain('Herramienta no instalada');
    expect(html).toContain('muro');
    expect(html).toContain('Datos de una herramienta que aún no existe');
  });
});
