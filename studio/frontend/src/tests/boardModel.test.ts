import { describe, expect, it } from 'vitest';
import {
  boardFilename,
  boardToMarkdown,
  cloneBoardForImport,
  createBoard,
  isSafeExternalUrl,
  makeBoardExport,
  markdownToBoard,
  normalizeBoard,
  parseBoardImport,
} from '../board/model';

describe('modelo de tablero visual', () => {
  it('acepta enlaces web seguros y rechaza protocolos ejecutables', () => {
    expect(isSafeExternalUrl('https://example.com/page')).toBe(true);
    expect(isSafeExternalUrl('http://localhost:5173')).toBe(true);
    expect(isSafeExternalUrl('javascript:alert(1)')).toBe(false);
    expect(isSafeExternalUrl('file:///etc/passwd')).toBe(false);
  });

  it('normaliza tarjetas y descarta relaciones rotas o duplicadas', () => {
    const board = normalizeBoard({
      schemaVersion: 1,
      id: 'b1',
      title: 'Proyecto',
      cards: [
        { id: 'a', type: 'note', title: 'A', x: 25, y: 40, body: 'Idea' },
        { id: 'b', type: 'note', title: 'B', x: 340, y: 40, body: '' },
      ],
      relations: [
        { id: 'r1', from: 'a', to: 'b' },
        { id: 'r2', from: 'b', to: 'a' },
        { id: 'r3', from: 'a', to: 'missing' },
        { id: 'r4', from: 'a', to: 'a' },
      ],
    });

    expect(board?.cards).toHaveLength(2);
    expect(board?.relations).toHaveLength(1);
    expect(board?.cards[0]).toMatchObject({ id: 'a', title: 'A', x: 25, y: 40, body: 'Idea' });
  });

  it('exporta e importa una copia JSON con identificadores nuevos y relaciones intactas', () => {
    const board = createBoard('Investigación');
    board.cards = [
      { id: 'card-a', type: 'note', title: 'Pregunta', body: '¿Qué sabemos?', x: -20, y: 30, width: 260, color: 'paper' },
      { id: 'card-b', type: 'link', title: 'Fuente', body: '', url: 'https://example.com', x: 300, y: 40, width: 260, color: 'sage' },
    ];
    board.relations = [{ id: 'rel-a', from: 'card-a', to: 'card-b' }];

    const imported = parseBoardImport(makeBoardExport(board));
    expect(imported).toMatchObject({ title: 'Investigación', cards: board.cards, relations: board.relations });

    const copy = cloneBoardForImport(imported!);
    expect(copy.id).not.toBe(board.id);
    expect(copy.title).toBe('Investigación (importado)');
    expect(copy.cards.map((card) => card.id)).not.toEqual(board.cards.map((card) => card.id));
    expect(copy.relations[0].from).toBe(copy.cards[0].id);
    expect(copy.relations[0].to).toBe(copy.cards[1].id);
  });

  it('conserva texto, enlaces y relaciones en un ciclo Markdown para Obsidian', () => {
    const board = createBoard('Lecturas');
    board.cards = [
      { id: 'one', type: 'note', title: 'Idea central', body: 'Un resumen breve.', x: 0, y: 0, width: 260, color: 'sand' },
      { id: 'two', type: 'link', title: 'Artículo', body: 'Revisar la sección 2.', url: 'https://example.com/article', x: 320, y: 0, width: 260, color: 'paper' },
    ];
    board.relations = [{ id: 'r', from: 'one', to: 'two' }];

    const markdown = boardToMarkdown(board);
    const imported = markdownToBoard(markdown);

    expect(markdown).toContain('[[Artículo]]');
    expect(imported?.title).toBe('Lecturas');
    expect(imported?.cards[0]).toMatchObject({ title: 'Idea central', body: 'Un resumen breve.' });
    expect(imported?.cards[1]).toMatchObject({ type: 'link', title: 'Artículo', url: 'https://example.com/article', body: 'Revisar la sección 2.' });
    expect(imported?.relations).toHaveLength(1);
  });

  it('genera nombres de archivo portables', () => {
    expect(boardFilename('Plan de acción: Perú / 2026', 'md')).toBe('Plan-de-accion-Peru-2026.md');
  });
});
