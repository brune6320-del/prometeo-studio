import { LayoutGrid } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';

export const ABRIR_TABLERO_EVENT = 'prometeo:abrir-tablero';

export function leerTableroAnidado(card: BoardCard): { boardId: string; boardTitle: string } {
  const raw = typeof card.datos === 'object' && card.datos !== null ? card.datos : {};
  return {
    boardId: typeof raw.boardId === 'string' ? raw.boardId : '',
    boardTitle: typeof raw.boardTitle === 'string' ? raw.boardTitle : card.title || 'Tablero',
  };
}

/** Tablero dentro de tablero: la tarjeta guarda solo el id; abrirla cambia de tablero. */
export const tableroTool: BoardTool<BoardCard> = {
  id: 'tablero',
  nombre: 'Tablero anidado',
  tipo: 'tarjeta',
  icono: LayoutGrid,
  crear: (x, y) => ({
    ...createCard('tablero', x, y),
    title: 'Tablero',
    width: 280,
    datos: { boardId: '', boardTitle: '' },
  }),
  validar: esTarjetaDe('tablero'),
  Vista: ({ datos }) => {
    const { boardId, boardTitle } = leerTableroAnidado(datos);
    return (
      <div
        className="board-nested"
        onClick={(event) => event.stopPropagation()}
        onPointerDown={(event) => event.stopPropagation()}
        onDoubleClick={() => { if (boardId) window.dispatchEvent(new CustomEvent(ABRIR_TABLERO_EVENT, { detail: { boardId } })); }}
      >
        <span className="board-nested-icon" aria-hidden="true"><LayoutGrid size={22} /></span>
        <strong>{boardTitle || 'Tablero sin nombre'}</strong>
        <span>{boardId ? 'Doble clic para abrirlo o usa el botón.' : 'Aún no apunta a un tablero.'}</span>
        {boardId && (
          <button
            type="button"
            className="board-nested-open"
            onClick={() => window.dispatchEvent(new CustomEvent(ABRIR_TABLERO_EVENT, { detail: { boardId } }))}
          >
            Abrir tablero
          </button>
        )}
      </div>
    );
  },
};
