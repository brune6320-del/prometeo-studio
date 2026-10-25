import React from 'react';
import { Link2, Lock, LockOpen, X } from 'lucide-react';
import type { BoardCard } from '../board/model';
import { BoardCardContent } from '../board/tools/CardView';
import { TituloEnSitio } from './InlineEdit';
import { metricas } from '../motion/metricas';

interface Modificadores {
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
}

export interface BoardCardItemProps {
  card: BoardCard;
  selected: boolean;
  dimmed: boolean;
  dragging: boolean;
  settling: boolean;
  connectionSource: boolean;
  connectionTarget?: boolean;
  connectMode: boolean;
  colors: Array<BoardCard['color']>;
  /** Por debajo del 35 % solo queda el título: menos DOM para mover y borrar cientos. */
  compact?: boolean;
  onSelect: (card: BoardCard, modifiers: Modificadores) => void;
  onConnect: (cardId: string) => void;
  onConnectStart: (card: BoardCard, event: React.PointerEvent<HTMLElement>) => void;
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
  connectionTarget = false,
  connectMode,
  colors,
  compact = false,
  onSelect,
  onConnect,
  onConnectStart,
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
  const iniciarArrastre = (event: React.PointerEvent<HTMLDivElement>) => {
    if (card.locked) return;
    onDragStart(card, event);
  };
  if (compact) {
    return (
      <article
        data-card-id={card.id}
        data-card-type={card.type}
        data-locked={card.locked ? 'si' : 'no'}
        tabIndex={-1}
        aria-selected={selected}
        aria-label={`Tarjeta: ${card.title || 'sin título'}`}
        className={`board-card board-card-compact color-${card.color} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''} ${card.locked ? 'is-locked' : ''}`}
        style={{ left: card.x, top: card.y, width: card.width }}
        onPointerDown={iniciarArrastre}
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
      >
        <span className="board-card-title">{card.title || 'Sin título'}</span>
      </article>
    );
  }
  return (
    <article
      data-card-id={card.id}
      data-card-type={card.type}
      data-locked={card.locked ? 'si' : 'no'}
      tabIndex={-1}
      aria-selected={selected}
      aria-label={`Tarjeta: ${card.title || 'sin título'}`}
      className={`board-card color-${card.color} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''} ${connectionSource ? 'connection-source' : ''} ${connectionTarget ? 'connection-target' : ''} ${dragging ? 'dragging' : ''} ${settling ? 'settling' : ''} ${card.locked ? 'is-locked' : ''}`}
      style={{ left: card.x, top: card.y, width: card.width }}
      onPointerMove={onDragMove}
      onPointerUp={onDragEnd}
      onPointerCancel={onDragEnd}
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
      <div className={`board-card-head ${card.locked ? 'is-locked' : ''}`} onPointerDown={iniciarArrastre} onPointerMove={onDragMove} onPointerUp={onDragEnd} onPointerCancel={onDragEnd} title={card.locked ? 'Tarjeta bloqueada' : 'Arrastra para mover la tarjeta'}>
        <span className="board-drag-grip" aria-hidden="true">{card.locked ? <Lock size={11} /> : '⠿'}</span>
        <TituloEnSitio value={card.title} onCommit={(title) => onPatch(card.id, { title })} ariaLabel="Título de tarjeta" className="board-card-title" />
        <button
          type="button"
          className="board-card-lock"
          onClick={(event) => { event.stopPropagation(); onPatch(card.id, { locked: !card.locked }); }}
          aria-label={card.locked ? 'Desbloquear tarjeta' : 'Bloquear tarjeta'}
          title={card.locked ? 'Desbloquear' : 'Bloquear posición y borrado'}
        >
          {card.locked ? <Lock size={12} /> : <LockOpen size={12} />}
        </button>
        <button className={`board-connect-button ${connectMode ? 'visible' : ''}`} onClick={(event) => { event.stopPropagation(); onConnect(card.id); }} title="Elegir para relacionar" aria-label="Relacionar esta tarjeta"><Link2 size={13} /></button>
        <button className="board-card-delete" onClick={(event) => { event.stopPropagation(); onDelete(card.id); }} aria-label="Eliminar tarjeta" disabled={card.locked}><X size={14} /></button>
      </div>
      <div className="board-card-color-row" aria-label="Color de tarjeta">
        {colors.map((color) => <button key={color} className={`board-color-swatch ${color} ${card.color === color ? 'current' : ''}`} onClick={() => onPatch(card.id, { color })} aria-label={`Color ${color}`} aria-pressed={card.color === color} />)}
      </div>
      <BoardCardContent card={card} editar={onReplace} />
      <button
        type="button"
        className="board-connector-handle"
        onPointerDown={(event) => { event.stopPropagation(); event.preventDefault(); onConnectStart(card, event); }}
        onClick={(event) => event.stopPropagation()}
        aria-label={`Conectar desde ${card.title || 'tarjeta'}`}
        title="Arrastra desde aquí hasta otra tarjeta para conectarlas"
      >
        <Link2 size={13} />
      </button>
    </article>
  );
});
