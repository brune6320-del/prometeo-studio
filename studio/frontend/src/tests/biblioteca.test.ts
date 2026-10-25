import { describe, expect, it } from 'vitest';
import { createBoard, normalizeBoard } from '../board/model';
import { readFrameData } from '../board/frames';
import {
  agregarImagenDesdeUrl,
  idMarcoVideo,
  idTarjetaReferente,
  importarBiblioteca,
  tipoImagenDesdeUrl,
} from '../board/referentes/biblioteca';
import { leerReferente, referenteVacio } from '../board/referentes/model';
import { SEMILLA_REFERENTES } from '../board/referentes/semilla';
import { getBoardTool } from '../board/tools/registry';
import type { BoardCard } from '../board/model';

const REFERENTES_POR_VIDEO: Record<string, number> = {
  'media 11': 5,
  'media 13': 6,
  'media 5': 1,
};

describe('tablero Biblioteca a partir de la semilla', () => {
  it('importar dos veces no duplica y conserva los ids', () => {
    const first = importarBiblioteca([], SEMILLA_REFERENTES);
    expect(first.created).toBe(true);
    expect(first.board.title).toBe('Biblioteca');
    expect(first.referentes).toBe(12);
    expect(first.marcos).toBe(3);

    const referentes = first.board.cards.filter((card) => card.type === 'referente');
    const marcos = first.board.cards.filter((card) => card.type === 'marco');
    expect(referentes).toHaveLength(12);
    expect(marcos).toHaveLength(3);
    expect(new Set(first.board.cards.map((card) => card.id)).size).toBe(first.board.cards.length);

    const second = importarBiblioteca([first.board], SEMILLA_REFERENTES);
    expect(second.created).toBe(false);
    expect(second.board.id).toBe(first.board.id);
    expect(second.board.cards.filter((card) => card.type === 'referente')).toHaveLength(12);
    expect(second.board.cards.filter((card) => card.type === 'marco')).toHaveLength(3);
    expect(second.board.cards.map((card) => card.id)).toEqual(first.board.cards.map((card) => card.id));
    expect(second.board.cards).toEqual(first.board.cards);
  });

  it('cada marco contiene los referentes de su vídeo y lo «por verificar» queda marcado', () => {
    const { board } = importarBiblioteca([], SEMILLA_REFERENTES);
    const byId = new Map(board.cards.map((card) => [card.id, card]));

    for (const [video, count] of Object.entries(REFERENTES_POR_VIDEO)) {
      const frame = board.cards.find((card) => card.id === idMarcoVideo(video))!;
      expect(frame).toBeDefined();
      expect(frame.title).toBe(video);
      expect(readFrameData(frame).hijos).toHaveLength(count);
      for (const childId of readFrameData(frame).hijos) {
        const child = byId.get(childId)!;
        expect(child.type).toBe('referente');
        expect(leerReferente(child).archivoOrigen).toBe(video);
        expect(child.x).toBeGreaterThanOrEqual(frame.x);
        expect(child.y).toBeGreaterThanOrEqual(frame.y);
        expect(child.x).toBeLessThan(frame.x + frame.width);
        expect(child.y).toBeLessThan(frame.y + readFrameData(frame).alto);
      }
    }

    for (const item of SEMILLA_REFERENTES) {
      const card = byId.get(idTarjetaReferente(item.id))!;
      const referente = leerReferente(card);
      expect(referente.nombre).toBe(item.nombre);
      expect(referente.url).toBe(item.url ?? '');
      expect(referente.licencia).toBe(item.licencia);
      expect(referente.etiquetas.includes('por verificar')).toBe(item.verificar);
      expect(referente.imagenes).toEqual([]);
    }
  });

  it('pegar una URL de imagen guarda el medio con fuente y fecha', () => {
    const url = 'https://images.example.com/collage/pareidolia.png?download=1';
    const base = { ...referenteVacio(), nombre: 'Pareidolia' };
    const next = agregarImagenDesdeUrl(base, url, '2026-10-24')!;

    expect(next.imagenes).toHaveLength(1);
    expect(next.imagenes[0]).toMatchObject({
      name: 'pareidolia.png',
      mimeType: 'image/png',
      dataUrl: url,
      kind: 'image',
      fuente: url,
      fecha: '2026-10-24',
    });
    expect(tipoImagenDesdeUrl(url)).toBe('image/png');

    // Pegar la misma URL otra vez no crea un medio duplicado.
    expect(agregarImagenDesdeUrl(next, url, '2026-10-25')!.imagenes).toHaveLength(1);
    // Una URL no segura no se guarda.
    expect(agregarImagenDesdeUrl(base, 'javascript:alert(1)')).toBeNull();

    // La fuente y la fecha sobreviven a guardar y volver a cargar el tablero.
    const tool = getBoardTool('referente')!;
    const board = createBoard('Biblioteca');
    const card = { ...tool.crear(0, 0), title: 'Pareidolia', datos: { ...next } } as BoardCard;
    board.cards.push(card);
    const loaded = normalizeBoard(JSON.parse(JSON.stringify(board)))!;
    const saved = leerReferente(loaded.cards[0]);
    expect(saved.imagenes[0]).toMatchObject({ dataUrl: url, fuente: url, fecha: '2026-10-24' });
  });
});
