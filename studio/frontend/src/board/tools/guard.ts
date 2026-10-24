import type { BoardCard, BoardCardType } from '../model';

/** Comprobación mínima compartida por los validadores de las herramientas. */
export function esTarjetaDe(tipo: BoardCardType) {
  return (datos: unknown): datos is BoardCard =>
    typeof datos === 'object' && datos !== null && (datos as BoardCard).type === tipo;
}
