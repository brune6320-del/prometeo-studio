import React from 'react';

interface Modificadores {
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
}
import { Link2, X } from 'lucide-react';
import type { BoardCard } from '../board/model';
import { BoardCardContent } from '../board/tools/CardView';
import { TituloEnSitio } from './InlineEdit';
import { metricas } from '../motion/metricas';

export interface BoardCardItemProps {
  card: BoardCard;
  selected: boolean;
  dimmed: boolean;
  dragging: boolean;
  settling: boolean;
  connectionSource: boolean;
  connectMode: boolean;
  colors: Array<BoardCard['color']>;
  onSelect: (card: BoardCard, modifiers: Modificadores) => void;
  onConnect: (cardId: string) => void;
  onDragStart: (card: BoardCard, event: React.PointerEvent<HTMLDivElement>) => void;
  onDragMove: (event: React.PointerEvent<HTMLDivElement>) => void;
  onDragEnd: (event: React.PointerEvent<HTMLDivElement>) => void;
  onDelete: (cardId: string) => void;
  onPatch: (cardId: string, patch: Partial<BoardCard>) => void;
  onReplace: (card: BoardCard) => void;
  onHover: (cardId: string, over: boolean) => void;
  onBlurCapture: () => void;
}

export const BoardCardItem = React.memo(function BoardCardItem({
  card,
  selected,
  dimmed,
  dragging,
  settling,
  connectionSource,
  connectMode,
  colors,
  onSelect,
  onConnect,
  onDragStart,
  onDragMove,
  onDragEnd,
  onDelete,
  onPatch,
  onReplace,
  onHover,
  onBlurCapture,
}: BoardCardItemProps) {
  metricas.rendersTarjeta += 1;
  return (
    <article
      data-card-id={card.id}
      data-card-type={card.type}
      tabIndex={0}
      aria-label={`Tarjeta: ${card.title || 'sin título'}`}
      className={`board-card color-${card.color} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''} ${connectionSource ? 'connection-source' : ''} ${dragging ? 'dragging' : ''} ${settling ? 'settling' : ''}`}
      style={{ left: card.x, top: card.y, width: card.width }}
      onClick={(event) => {
        if (connectMode) {
          const target = event.target as HTMLElement;
          if (target.closest('input,textarea,button,a,video,audio')) return;
          onConnect(card.id);
        } else onSelect(card, event);
      }}
      onPointerEnter={card.type === 'referente' ? () => onHover(card.id, true) : undefined}
      onPointerLeave={card.type === 'referente' ? () => onHover(card.id, false) : undefined}
      onBlurCapture={onBlurCapture}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(card, event);
        }
      }}
    >
      <div className="board-card-head" onPointerDown={(event) => onDragStart(card, event)} onPointerMove={onDragMove} onPointerUp={onDragEnd} onPointerCancel={onDragEnd} title="Arrastra para mover la tarjeta">
        <span className="board-drag-grip" aria-hidden="true">⠿</span>
        <TituloEnSitio value={card.title} onCommit={(title) => onPatch(card.id, { title })} ariaLabel="Título de tarjeta" className="board-card-title" />
        <button className={`board-connect-button ${connectMode ? 'visible' : ''}`} onClick={(event) => { event.stopPropagation(); onConnect(card.id); }} title="Elegir para relacionar" aria-label="Relacionar esta tarjeta"><Link2 size={13} /></button>
        <button className="board-card-delete" onClick={(event) => { event.stopPropagation(); onDelete(card.id); }} aria-label="Eliminar tarjeta"><X size={14} /></button>
      </div>
      <div className="board-card-color-row" aria-label="Color de tarjeta">
        {colors.map((color) => <button key={color} className={`board-color-swatch ${color} ${card.color === color ? 'current' : ''}`} onClick={() => onPatch(card.id, { color })} aria-label={`Color ${color}`} aria-pressed={card.color === color} />)}
      </div>
      <BoardCardContent card={card} editar={onReplace} />
    </article>
  );
});
