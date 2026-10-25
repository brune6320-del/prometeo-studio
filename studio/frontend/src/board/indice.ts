import type { BoardCard } from './model';

export const INDICE_ROW_HEIGHT = 38;
export const INDICE_OVERSCAN = 6;

export interface VentanaIndice {
  inicio: number;
  fin: number;
  offsetSuperior: number;
  offsetInferior: number;
  altoTotal: number;
}

/**
 * Ventana de filas visibles para 500 tarjetas sin montar 500 botones.
 * `scrollTop` y `alto` están en píxeles; el resultado es un rango [inicio, fin).
 */
export function ventanaVirtual(
  total: number,
  scrollTop: number,
  alto: number,
  rowHeight = INDICE_ROW_HEIGHT,
  overscan = INDICE_OVERSCAN,
): VentanaIndice {
  const seguro = Math.max(0, Math.floor(total));
  const altoTotal = seguro * rowHeight;
  const primero = Math.max(0, Math.floor(Math.max(0, scrollTop) / rowHeight) - overscan);
  const visibles = Math.ceil(Math.max(0, alto) / rowHeight) + overscan * 2;
  const fin = Math.min(seguro, primero + visibles);
  return {
    inicio: primero,
    fin,
    offsetSuperior: primero * rowHeight,
    offsetInferior: Math.max(0, altoTotal - fin * rowHeight),
    altoTotal,
  };
}

/** El índice lista de arriba (último pintado) a abajo (primero), como una pila de papel. */
export function ordenDePintado(cards: readonly BoardCard[]): BoardCard[] {
  return [...cards].reverse();
}

export function coincideBusqueda(card: BoardCard, query: string): boolean {
  const texto = query.trim().toLocaleLowerCase();
  if (!texto) return true;
  return `${card.title} ${card.body} ${card.url ?? ''} ${card.type}`
    .toLocaleLowerCase()
    .includes(texto);
}
