import React from 'react';
import { ChevronDown, ChevronRight, Lock, LockOpen, Settings2, X } from 'lucide-react';
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
  onSettings: (card: BoardCard, event: React.MouseEvent<HTMLElement>) => void;
  onToggleFold: (cardId: string) => void;
  onReorderChild: (columnId: string, childId: string, targetId: string) => void;
  onDetachChild: (columnId: string, childId: string) => void;
  onResizeStart: (card: BoardCard, direction: string, event: React.PointerEvent<HTMLElement>) => void;
  onResizeMove: (event: React.PointerEvent<HTMLElement>) => void;
  onResizeEnd: (event: React.PointerEvent<HTMLElement>) => void;
}

const DIRECCIONES_COLUMNA = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'];

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
  onSettings,
  onToggleFold,
  onReorderChild,
  onDetachChild,
  onResizeStart,
  onResizeMove,
  onResizeEnd,
}) => {
  const data = readColumnData(card);
  const porId = new Map(childrenCards.map((child) => [child.id, child]));
  const ordenadas = data.ordenExplicito
    ? data.hijos.map((id) => porId.get(id)).filter((item): item is BoardCard => Boolean(item))
    : [...childrenCards].sort((a, b) => (a.y - b.y) || a.title.localeCompare(b.title));
  return (
    <article
      data-card-id={card.id}
      data-card-type="columna"
      data-columna-plegada={data.plegada ? 'si' : 'no'}
      tabIndex={-1}
      aria-selected={selected}
      aria-label={`Columna: ${card.title || 'sin título'}`}
      className={`board-column ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''} ${dragging ? 'dragging' : ''} ${settling ? 'settling' : ''} ${dropTarget ? 'drop-target' : ''} ${data.plegada ? 'is-folded' : ''} ${card.locked ? 'is-locked' : ''}`}
      style={{ left: card.x, top: card.y, width: card.width, ...(data.alto ? { height: data.alto } : {}) }}
      onPointerMove={onDragMove}
      onPointerUp={onDragEnd}
      onPointerCancel={onDragEnd}
      onClick={(event) => onSelect(card, event)}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(card, event);
        }
      }}
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
        {selected && (
          <button
            type="button"
            className="board-column-settings"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => { event.stopPropagation(); onSettings(card, event); }}
            aria-label={`Ajustes de ${card.title || 'la columna'}`}
            title="Ajustes de esta columna"
          ><Settings2 size={13} /></button>
        )}
        <button className="board-column-delete" onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); onDelete(card.id); }} aria-label="Eliminar columna" title="Eliminar la columna y dejar sus tarjetas"><X size={13} /></button>
      </div>
      {!data.plegada && (
        <div className="board-column-body">
          {ordenadas.length === 0 && <p className="board-column-empty">Arrastra tarjetas aquí para ordenarlas.</p>}
          {ordenadas.map((hijo) => (
            <div
              className="board-column-item"
              key={hijo.id}
              data-column-child={hijo.id}
              draggable
              onDragStart={(event) => {
                event.stopPropagation();
                event.dataTransfer.effectAllowed = 'move';
                event.dataTransfer.setData('application/x-prometeo-column-child', JSON.stringify({ columnId: card.id, cardId: hijo.id }));
              }}
              onDragOver={(event) => { event.preventDefault(); event.stopPropagation(); event.dataTransfer.dropEffect = 'move'; }}
              onDrop={(event) => {
                event.preventDefault();
                event.stopPropagation();
                const origen = event.dataTransfer.getData('application/x-prometeo-column-child');
                if (!origen) return;
                try {
                  const dataOrigen = JSON.parse(origen) as { columnId?: string; cardId?: string };
                  if (dataOrigen.columnId === card.id && dataOrigen.cardId && dataOrigen.cardId !== hijo.id) {
                    onReorderChild(card.id, dataOrigen.cardId, hijo.id);
                  }
                } catch {
                  /* un arrastre externo no reordena */
                }
              }}
            >
              <span className="board-column-item-type">{hijo.type === 'tareas' ? '☑' : hijo.type === 'link' ? '↗' : hijo.type === 'media' ? '▣' : '·'}</span>
              <span className="board-column-item-title">{hijo.title || 'Sin título'}</span>
              <button
                type="button"
                className="board-column-item-detach"
                draggable={false}
                onClick={(event) => { event.stopPropagation(); onDetachChild(card.id, hijo.id); }}
                aria-label={`Sacar ${hijo.title || 'tarjeta'} de la columna`}
                title="Sacar de la columna"
              >↗</button>
            </div>
          ))}
        </div>
      )}
      {data.plegada && <div className="board-column-folded-hint">{ordenadas.length} {ordenadas.length === 1 ? 'tarjeta plegada' : 'tarjetas plegadas'}</div>}
      {!card.locked && DIRECCIONES_COLUMNA.map((direccion) => (
        <span
          key={direccion}
          role="presentation"
          className={`board-column-resize ${direccion}`}
          onPointerDown={(event) => { event.stopPropagation(); event.preventDefault(); onResizeStart(card, direccion, event); }}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          onPointerCancel={onResizeEnd}
        />
      ))}
    </article>
  );
};
