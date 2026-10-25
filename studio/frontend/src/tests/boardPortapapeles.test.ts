import { beforeEach, describe, expect, it } from 'vitest';
import { createBoard, createCard } from '../board/model';
import {
  copiarTarjetas,
  esMarcaDeTarjetas,
  hayTarjetasCopiadas,
  PREFIJO_PORTAPAPELES,
  pegarTarjetas,
  pegarTarjetasEn,
  textoLegibleDeTarjetas,
  vaciarPortapapeles,
} from '../board/portapapeles';

function nota(id: string, x = 100, y = 100) {
  return { ...createCard('note', x, y), id, title: id, body: `cuerpo ${id}` };
}

describe('T-2 · portapapeles interno de tarjetas', () => {
  beforeEach(() => vaciarPortapapeles());

  it('copia y pega con ids nuevos y relaciones internas remapeadas', () => {
    const board = createBoard('t');
    board.cards = [nota('a'), nota('b', 400), nota('c', 700)];
    board.relations = [
      { id: 'r1', from: 'a', to: 'b' },
      { id: 'r2', from: 'b', to: 'c' },
    ];

    const marca = copiarTarjetas(board, ['a', 'b']);
    expect(marca?.startsWith(PREFIJO_PORTAPAPELES)).toBe(true);
    expect(hayTarjetasCopiadas()).toBe(true);

    const pegado = pegarTarjetas(board)!;
    expect(pegado.board.cards).toHaveLength(5);
    expect(pegado.newIds).toHaveLength(2);
    expect(pegado.board.relations).toHaveLength(3);
    const nuevas = pegado.board.relations.filter((relation) => pegado.newIds.includes(relation.from));
    expect(nuevas).toHaveLength(1);
    expect(nuevas[0].to).toBe(pegado.newIds[1]);
    expect(pegado.board.cards.find((card) => card.id === pegado.newIds[0])).toMatchObject({ x: 124, y: 124 });
  });

  it('pegar dos veces crea copias distintas y escalona la posición', () => {
    const board = createBoard('t');
    board.cards = [nota('a')];
    copiarTarjetas(board, ['a']);

    const primera = pegarTarjetas(board)!;
    const segunda = pegarTarjetas(primera.board)!;
    expect(primera.newIds[0]).not.toBe(segunda.newIds[0]);
    expect(segunda.board.cards.find((card) => card.id === segunda.newIds[0])).toMatchObject({ x: 148, y: 148 });
  });

  it('pegar en el cursor coloca la esquina del grupo en el punto indicado', () => {
    const board = createBoard('t');
    board.cards = [nota('a', 100, 100), nota('b', 400, 250)];
    copiarTarjetas(board, ['a', 'b']);
    const pegado = pegarTarjetasEn(board, { x: 900, y: 600 })!;
    const copias = pegado.board.cards.filter((card) => pegado.newIds.includes(card.id));
    expect(Math.min(...copias.map((card) => card.x))).toBe(900);
    expect(Math.min(...copias.map((card) => card.y))).toBe(600);
  });

  it('el portapapeles del sistema lleva texto legible además de la marca', () => {
    const board = createBoard('t');
    board.cards = [{ ...nota('a'), title: 'Alfa', body: 'cuerpo', url: 'https://example.com' }];
    const texto = textoLegibleDeTarjetas(board.cards);
    expect(texto).toContain('Prometeo Studio · 1 tarjeta');
    expect(texto).toContain('Alfa');
    expect(texto).toContain('cuerpo');
    expect(texto).toContain('https://example.com');
  });

  it('una marca del sistema se reconoce aunque el contenido interno se haya vaciado', () => {
    expect(esMarcaDeTarjetas(`${PREFIJO_PORTAPAPELES}abc`)).toBe(true);
    expect(esMarcaDeTarjetas('https://example.com')).toBe(false);
    expect(esMarcaDeTarjetas('')).toBe(false);
    vaciarPortapapeles();
    expect(hayTarjetasCopiadas()).toBe(false);
  });
});
