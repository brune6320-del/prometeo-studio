import type { BoardCard, BoardDocument, BoardRelation } from './model';
import { duplicateCards } from './model';

/**
 * Portapapeles interno del tablero. El del sistema solo lleva una marca corta:
 * así copiar una tarjeta con una imagen de 12 MB no bloquea el portapapeles y
 * un texto o una imagen externos siguen teniendo prioridad al pegar.
 */
export const PREFIJO_PORTAPAPELES = 'prometeo-studio/tarjetas:';

interface ContenidoCopiado {
  token: string;
  cards: BoardCard[];
  relations: BoardRelation[];
  pegados: number;
}

let contenido: ContenidoCopiado | null = null;
let contador = 0;

export interface TarjetasPegadas {
  board: BoardDocument;
  newIds: string[];
}

function nuevoToken(): string {
  contador += 1;
  const aleatorio = globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${contador}`;
  return aleatorio.slice(0, 40);
}

/** Guarda una copia de la selección y devuelve la marca para el portapapeles del sistema. */
export function copiarTarjetas(board: BoardDocument, ids: readonly string[]): string | null {
  const seleccionadas = new Set(ids);
  const cards = board.cards.filter((card) => seleccionadas.has(card.id));
  if (!cards.length) return null;
  const token = nuevoToken();
  contenido = {
    token,
    cards,
    relations: board.relations.filter(
      (relation) => seleccionadas.has(relation.from) && seleccionadas.has(relation.to),
    ),
    pegados: 0,
  };
  return `${PREFIJO_PORTAPAPELES}${token}`;
}

export function hayTarjetasCopiadas(): boolean {
  return Boolean(contenido?.cards.length);
}

export function esMarcaDeTarjetas(texto: string): boolean {
  return texto.trimStart().startsWith(PREFIJO_PORTAPAPELES);
}

/** Pega la copia interna con ids nuevos y relaciones internas remapeadas. */
export function pegarTarjetas(board: BoardDocument, paso = 24): TarjetasPegadas | null {
  if (!contenido?.cards.length) return null;
  contenido.pegados += 1;
  const offset = paso * contenido.pegados;
  const dup = duplicateCards(
    contenido.cards,
    contenido.relations,
    contenido.cards.map((card) => card.id),
    { x: offset, y: offset },
  );
  return {
    board: {
      ...board,
      cards: [...board.cards, ...dup.cards],
      relations: [...board.relations, ...dup.relations],
    },
    newIds: dup.newIds,
  };
}

/** Solo para pruebas: deja el portapapeles interno vacío. */
export function vaciarPortapapeles(): void {
  contenido = null;
}
