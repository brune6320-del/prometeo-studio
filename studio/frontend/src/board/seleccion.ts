import type { BoardCard, BoardDocument } from './model';
import { duplicateCards } from './model';
import { readColumnData } from './columnas';
import { readFrameData } from './frames';

export type OrdenTarjetas = 'adelante' | 'atras' | 'frente' | 'fondo';
export type ModoMarquesina = 'reemplazar' | 'sumar' | 'restar';

/** Contrato de A-1 · D1: la marquesina reemplaza; ⇧ suma; ⌥ resta. */
export function aplicarMarquesina(actual: readonly string[], dentro: readonly string[], modo: ModoMarquesina): string[] {
  if (modo === 'reemplazar') return [...new Set(dentro)];
  if (modo === 'sumar') return [...new Set([...actual, ...dentro])];
  const quitar = new Set(dentro);
  return actual.filter((id) => !quitar.has(id));
}

/** ⇧+clic y ⌘+clic alternan: nunca acumulan sin querer. */
export function alternarEnSeleccion(actual: readonly string[], id: string): string[] {
  return actual.includes(id) ? actual.filter((item) => item !== id) : [...actual, id];
}

/**
 * Tablero activo, no sus tableros anidados: cada documento guarda sus propias
 * tarjetas. Se omiten las que ya se pintan dentro de un marco con vista propia.
 */
export function seleccionarTodoElTablero(board: BoardDocument, ocultas?: ReadonlySet<string>): string[] {
  return board.cards.filter((card) => !ocultas?.has(card.id)).map((card) => card.id);
}

/**
 * Mover un marco o una columna mueve también a sus hijos, igual que arrastrarlos.
 * Las tarjetas bloqueadas nunca entran en el movimiento.
 */
export function tarjetasAMover(board: BoardDocument, ids: readonly string[]): string[] {
  const seleccionadas = new Set(ids);
  const porId = new Map(board.cards.map((card) => [card.id, card]));
  const mover = new Set<string>();
  for (const card of board.cards) {
    if (!seleccionadas.has(card.id) || card.locked) continue;
    mover.add(card.id);
    const hijos = card.type === 'marco'
      ? readFrameData(card).hijos
      : card.type === 'columna'
        ? readColumnData(card).hijos
        : [];
    for (const id of hijos) {
      const hijo = porId.get(id);
      if (hijo && !hijo.locked) mover.add(id);
    }
  }
  return [...mover];
}

export function moverTarjetas(board: BoardDocument, ids: readonly string[], dx: number, dy: number): BoardDocument {
  if (!ids.length) return board;
  const mover = new Set(ids);
  return {
    ...board,
    cards: board.cards.map((card) => mover.has(card.id) ? { ...card, x: card.x + dx, y: card.y + dy } : card),
  };
}

/**
 * Borrar N tarjetas es una sola operación: filtra la lista una vez, limpia las
 * referencias de marcos y columnas sin recorrer el tablero por cada id y borra
 * las relaciones que tocaban la selección.
 */
export function borrarTarjetas(board: BoardDocument, ids: readonly string[]): BoardDocument {
  if (!ids.length) return board;
  const borradas = new Set(ids);
  const cards: BoardCard[] = [];
  for (const card of board.cards) {
    if (borradas.has(card.id)) continue;
    if (card.type === 'marco') {
      const data = readFrameData(card);
      const hijos = data.hijos.filter((id) => !borradas.has(id));
      cards.push(hijos.length === data.hijos.length
        ? card
        : { ...card, datos: { ...card.datos, ...data, hijos } });
      continue;
    }
    if (card.type === 'columna') {
      const data = readColumnData(card);
      const hijos = data.hijos.filter((id) => !borradas.has(id));
      cards.push(hijos.length === data.hijos.length
        ? card
        : { ...card, datos: { ...card.datos, ...data, hijos } });
      continue;
    }
    cards.push(card);
  }
  return {
    ...board,
    cards,
    relations: board.relations.filter((relation) => !borradas.has(relation.from) && !borradas.has(relation.to)),
  };
}

export function duplicarSeleccion(
  board: BoardDocument,
  ids: readonly string[],
  offset = { x: 24, y: 24 },
): { board: BoardDocument; newIds: string[] } {
  const dup = duplicateCards(board.cards, board.relations, [...ids], offset);
  return {
    board: {
      ...board,
      cards: [...board.cards, ...dup.cards],
      relations: [...board.relations, ...dup.relations],
    },
    newIds: dup.newIds,
  };
}

/**
 * Cambia el orden de pintado (el final del array queda encima). Se conserva el
 * orden relativo entre las tarjetas seleccionadas.
 */
export function reordenarTarjetas(
  cards: BoardCard[],
  ids: readonly string[],
  modo: OrdenTarjetas,
): BoardCard[] {
  const seleccionadas = new Set(ids);
  if (!seleccionadas.size) return cards;

  if (modo === 'frente' || modo === 'fondo') {
    const dentro = cards.filter((card) => seleccionadas.has(card.id));
    const fuera = cards.filter((card) => !seleccionadas.has(card.id));
    return modo === 'frente' ? [...fuera, ...dentro] : [...dentro, ...fuera];
  }

  const siguiente = [...cards];
  if (modo === 'adelante') {
    for (let i = siguiente.length - 2; i >= 0; i -= 1) {
      if (seleccionadas.has(siguiente[i].id) && !seleccionadas.has(siguiente[i + 1].id)) {
        [siguiente[i], siguiente[i + 1]] = [siguiente[i + 1], siguiente[i]];
      }
    }
    return siguiente;
  }

  for (let i = 1; i < siguiente.length; i += 1) {
    if (seleccionadas.has(siguiente[i].id) && !seleccionadas.has(siguiente[i - 1].id)) {
      [siguiente[i], siguiente[i - 1]] = [siguiente[i - 1], siguiente[i]];
    }
  }
  return siguiente;
}

/**
 * Una ráfaga de flechas (≤ 500 ms entre pulsaciones) comparte la misma clave y,
 * por tanto, el mismo paso de deshacer. Una pausa abre un paso nuevo.
 */
export function claveDeRafaga(claveActual: string, ultimaVez: number, ahora: number, ventana = 500): string {
  if (claveActual && ahora - ultimaVez <= ventana) return claveActual;
  return `rafaga-${ahora}`;
}
