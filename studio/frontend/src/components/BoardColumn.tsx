import React from 'react';
import { ChevronDown, ChevronRight, Lock, LockOpen, X } from 'lucide-react';
import type { BoardCard } from '../board/model';
import { readColumnData } from '../board/columnas';
import { TituloEnSitio } from './InlineEdit';

interface Modificadores {
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
}

export interface BoardColumnProps {
  card: BoardCard;
  childrenCards: BoardCard[];
  selected: boolean;
  dimmed: boolean;
  dragging: boolean;
  settling: boolean;
  dropTarget: boolean;
  onSelect: (card: BoardCard, modifiers: Modificadores) => void;
  onDragStart: (card: BoardCard, event: React.PointerEvent<HTMLElement>) => void;
  onDragMove: (event: React.PointerEvent<HTMLElement>) => void;
  onDragEnd: (event: React.PointerEvent<HTMLElement>) => void;
  onDelete: (cardId: string) => void;
  onPatch: (cardId: string, patch: Partial<BoardCard>) => void;
  onToggleFold: (cardId: string) => void;
}

/**
 * Columna contenedora: ordena sus tarjetas por altura y se puede plegar.
 * Las tarjetas siguen viviendo en el tablero; la columna solo guarda sus ids.
 */
export const BoardColumn: React.FC<BoardColumnProps> = ({
  card,
  childrenCards,
  selected,
  dimmed,
  dragging,
  settling,
  dropTarget,
  onSelect,
  onDragStart,
  onDragMove,
  onDragEnd,
  onDelete,
  onPatch,
  onToggleFold,
}) => {
  const data = readColumnData(card);
  const ordenadas = [...childrenCards].sort((a, b) => (a.y - b.y) || a.title.localeCompare(b.title));
  return (
    <article
      data-card-id={card.id}
      data-card-type="columna"
      data-columna-plegada={data.plegada ? 'si' : 'no'}
      tabIndex={0}
      aria-label={`Columna: ${card.title || 'sin título'}`}
      className={`board-column ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''} ${dragging ? 'dragging' : ''} ${settling ? 'settling' : ''} ${dropTarget ? 'drop-target' : ''} ${data.plegada ? 'is-folded' : ''} ${card.locked ? 'is-locked' : ''}`}
      style={{ left: card.x, top: card.y, width: card.width }}
      onClick={(event) => onSelect(card, event)}
      onPointerEnter={(event) => event.stopPropagation()}
    >
      <div className="board-column-head" onPointerDown={(event) => onDragStart(card, event)} onPointerMove={onDragMove} onPointerUp={onDragEnd} onPointerCancel={onDragEnd} title="Arrastra para mover la columna">
        <button
          type="button"
          className="board-column-fold"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => { event.stopPropagation(); onToggleFold(card.id); }}
          aria-label={data.plegada ? 'Desplegar columna' : 'Plegar columna'}
          title={data.plegada ? 'Desplegar' : 'Plegar'}
        >
          {data.plegada ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        </button>
        <TituloEnSitio value={card.title} onCommit={(title) => onPatch(card.id, { title })} ariaLabel="Título de la columna" className="board-column-title" />
        <span className="board-column-count">{ordenadas.length}</span>
        <button
          type="button"
          className="board-column-lock"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => { event.stopPropagation(); onPatch(card.id, { locked: !card.locked }); }}
          aria-label={card.locked ? 'Desbloquear columna' : 'Bloquear columna'}
          title={card.locked ? 'Desbloquear' : 'Bloquear posición y borrado'}
        >
          {card.locked ? <Lock size={12} /> : <LockOpen size={12} />}
        </button>
        <button className="board-column-delete" onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); onDelete(card.id); }} aria-label="Eliminar columna" title="Eliminar la columna y dejar sus tarjetas"><X size={13} /></button>
      </div>
      {!data.plegada && (
        <div className="board-column-body">
          {ordenadas.length === 0 && <p className="board-column-empty">Arrastra tarjetas aquí para ordenarlas.</p>}
          {ordenadas.map((hijo) => (
            <div className="board-column-item" key={hijo.id} data-column-child={hijo.id}>
              <span className="board-column-item-type">{hijo.type === 'tareas' ? '☑' : hijo.type === 'link' ? '↗' : hijo.type === 'media' ? '▣' : '·'}</span>
              <span className="board-column-item-title">{hijo.title || 'Sin título'}</span>
            </div>
          ))}
        </div>
      )}
      {data.plegada && <div className="board-column-folded-hint">{ordenadas.length} {ordenadas.length === 1 ? 'tarjeta plegada' : 'tarjetas plegadas'}</div>}
    </article>
  );
};
