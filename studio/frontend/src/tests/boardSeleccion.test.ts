import { describe, expect, it } from 'vitest';
import { createBoard, createCard, type BoardCard } from '../board/model';
import { emptyBoardHistory, recordBoardChange, undoBoardChange } from '../board/history';
import {
  borrarTarjetas,
  claveDeRafaga,
  duplicarSeleccion,
  moverTarjetas,
  reordenarTarjetas,
  seleccionarTodoElTablero,
  tarjetasAMover,
} from '../board/seleccion';

function nota(id: string, x = 100, y = 100): BoardCard {
  return { ...createCard('note', x, y), id, title: id, body: `cuerpo ${id}` };
}

function marco(id: string, hijos: string[], x = 0, y = 0): BoardCard {
  return {
    ...createCard('marco', x, y),
    id,
    title: id,
    datos: { alto: 360, hijos, vista: 'libre' },
  };
}

describe('T-2 · borrar, mover y ordenar como una herramienta profesional', () => {
  it('Cmd+A + Supr deja el tablero vacío y un solo deshacer lo devuelve idéntico', () => {
    const board = createBoard('t');
    board.cards = [nota('n1'), nota('n2', 400), nota('n3', 700), marco('f1', ['n2'])];
    board.relations = [{ id: 'r1', from: 'n1', to: 'n2' }];
    const ids = seleccionarTodoElTablero(board);
    expect(ids).toHaveLength(4);

    const vacio = borrarTarjetas(board, ids);
    expect(vacio.cards).toHaveLength(0);
    expect(vacio.relations).toHaveLength(0);

    const history = recordBoardChange(emptyBoardHistory(), board, vacio);
    expect(history.undo).toHaveLength(1);
    const restaurado = undoBoardChange(history, vacio).board!;
    expect(restaurado.cards).toEqual(board.cards);
    expect(restaurado.relations).toEqual(board.relations);
  });

  it('borra 500 tarjetas en una sola pasada y en menos de 100 ms', () => {
    const board = createBoard('500');
    board.cards = Array.from({ length: 500 }, (_, indice) => nota(`n${indice}`, indice * 12, indice * 8));
    board.relations = Array.from({ length: 200 }, (_, indice) => ({
      id: `r${indice}`,
      from: `n${indice}`,
      to: `n${indice + 1}`,
    }));
    const ids = board.cards.map((card) => card.id);
    const inicio = performance.now();
    const vacio = borrarTarjetas(board, ids);
    const transcurrido = performance.now() - inicio;

    expect(vacio.cards).toHaveLength(0);
    expect(vacio.relations).toHaveLength(0);
    expect(transcurrido).toBeLessThan(100);
  });

  it('al borrar un hijo lo saca de su marco; al borrar el marco deja a sus hijos', () => {
    const board = createBoard('marcos');
    board.cards = [marco('f1', ['n1', 'n2']), nota('n1'), nota('n2')];

    const sinHijo = borrarTarjetas(board, ['n1']);
    const frame = sinHijo.cards.find((card) => card.id === 'f1')!;
    expect(frame.datos?.hijos).toEqual(['n2']);
    expect(sinHijo.cards.map((card) => card.id)).toEqual(['f1', 'n2']);

    const sinMarco = borrarTarjetas(board, ['f1']);
    expect(sinMarco.cards.map((card) => card.id)).toEqual(['n1', 'n2']);
  });

  it('mover un marco arrastra a sus hijos y respeta las bloqueadas', () => {
    const board = createBoard('mover');
    board.cards = [marco('f1', ['n1', 'n2'], 10, 20), nota('n1', 30, 40), { ...nota('n2', 50, 60), locked: true }];
    const ids = tarjetasAMover(board, ['f1']);
    expect(ids.sort()).toEqual(['f1', 'n1']);

    const movido = moverTarjetas(board, ids, 10, -5);
    expect(movido.cards.find((card) => card.id === 'f1')).toMatchObject({ x: 20, y: 15 });
    expect(movido.cards.find((card) => card.id === 'n1')).toMatchObject({ x: 40, y: 35 });
    expect(movido.cards.find((card) => card.id === 'n2')).toMatchObject({ x: 50, y: 60 });
  });

  it('duplicar remapea ids, hijos de marcos y relaciones internas', () => {
    const board = createBoard('duplicar');
    board.cards = [marco('f1', ['n1']), nota('n1'), nota('n2')];
    board.relations = [{ id: 'r1', from: 'n1', to: 'n2' }];
    const { board: copia, newIds } = duplicarSeleccion(board, ['f1', 'n1']);

    expect(newIds).toHaveLength(2);
    expect(copia.cards).toHaveLength(5);
    const frame = copia.cards.find((card) => card.id === newIds[0])!;
    expect(frame.datos?.hijos).toEqual([newIds[1]]);
    expect(frame.x).toBe(board.cards[0].x + 24);
    // La relación con n2 queda fuera: n2 no forma parte de la copia.
    expect(copia.relations).toEqual(board.relations);
  });

  it('trae adelante un paso y conserva el orden relativo', () => {
    const cards = ['a', 'b', 'c', 'd'].map((id) => nota(id));
    const unPaso = reordenarTarjetas(cards, ['a'], 'adelante');
    expect(unPaso.map((card) => card.id)).toEqual(['b', 'a', 'c', 'd']);
    const frente = reordenarTarjetas(cards, ['a', 'c'], 'frente');
    expect(frente.map((card) => card.id)).toEqual(['b', 'd', 'a', 'c']);
    const fondo = reordenarTarjetas(cards, ['a', 'c'], 'fondo');
    expect(fondo.map((card) => card.id)).toEqual(['a', 'c', 'b', 'd']);
    const atras = reordenarTarjetas(cards, ['d'], 'atras');
    expect(atras.map((card) => card.id)).toEqual(['a', 'b', 'd', 'c']);
  });

  it('las pulsaciones de flecha dentro de 500 ms comparten paso de historial', () => {
    let clave = '';
    let ultima = 0;
    const claves: string[] = [];
    for (let i = 0; i < 10; i += 1) {
      const ahora = ultima + 40;
      clave = claveDeRafaga(clave, ultima, ahora);
      ultima = ahora;
      claves.push(clave);
    }
    expect(new Set(claves).size).toBe(1);
    const trasPausa = claveDeRafaga(clave, ultima, ultima + 600);
    expect(trasPausa).not.toBe(clave);
  });

  it('una relación cualquiera de las tarjetas borradas desaparece', () => {
    const board = createBoard('relaciones');
    board.cards = [nota('a'), nota('b'), nota('c')];
    board.relations = [
      { id: 'r1', from: 'a', to: 'b' },
      { id: 'r2', from: 'b', to: 'c' },
    ];
    const despues = borrarTarjetas(board, ['b']);
    expect(despues.relations).toEqual([]);
    expect(despues.cards.map((card) => card.id)).toEqual(['a', 'c']);
  });
});

describe('T-2 · seleccionar todo', () => {
  it('toma solo las tarjetas del tablero activo y omite las ocultas dentro de marcos', () => {
    const board = createBoard('activo');
    board.cards = [nota('visible'), nota('oculta'), nota('otra')];
    const ids = seleccionarTodoElTablero(board, new Set(['oculta']));
    expect(ids).toEqual(['visible', 'otra']);
  });

  it('un tablero anidado es una tarjeta del activo, no sus tarjetas internas', () => {
    const board = createBoard('activo');
    board.cards = [nota('nota'), { ...nota('anidado'), type: 'tablero', datos: { boardId: 'otro' } }];
    const otro = createBoard('otro');
    otro.cards = [nota('interna')];
    // El documento activo no contiene las tarjetas del otro tablero.
    expect(seleccionarTodoElTablero(board)).toEqual(['nota', 'anidado']);
    expect(board.cards.some((card) => card.id === 'interna')).toBe(false);
  });
});
