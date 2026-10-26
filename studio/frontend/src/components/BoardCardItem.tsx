import React, { useState } from 'react';
import { Link2, Lock, LockOpen, Settings2, X } from 'lucide-react';
import type { BoardCard } from '../board/model';
import { BoardCardContent } from '../board/tools/CardView';
import type { BoardToolActions } from '../board/tools/registry';
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
  onDragStart: (card: BoardCard, event: React.PointerEvent<HTMLElement>, force?: boolean) => void;
  onDragMove: (event: React.PointerEvent<HTMLDivElement>) => void;
  onDragEnd: (event: React.PointerEvent<HTMLDivElement>) => void;
  onWidthResizeStart?: (card: BoardCard, event: React.PointerEvent<HTMLElement>) => void;
  onWidthResizeMove?: (event: React.PointerEvent<HTMLElement>) => void;
  onWidthResizeEnd?: (event: React.PointerEvent<HTMLElement>) => void;
  onDelete: (cardId: string) => void;
  onSettings: (card: BoardCard, event: React.MouseEvent<HTMLElement>) => void;
  onPatch: (cardId: string, patch: Partial<BoardCard>) => void;
  onReplace: (card: BoardCard) => void;
  onHover: (cardId: string, over: boolean) => void;
  onBlurCapture: () => void;
  acciones?: BoardToolActions;
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
  onWidthResizeStart,
  onWidthResizeMove,
  onWidthResizeEnd,
  onDelete,
  onSettings,
  onPatch,
  onReplace,
  onHover,
  onBlurCapture,
  acciones,
}: BoardCardItemProps) {
  metricas.rendersTarjeta += 1;
  const [cercaDelBorde, setCercaDelBorde] = useState(false);
  const iniciarArrastre = (event: React.PointerEvent<HTMLElement>, force = false) => {
    if (card.locked) return;
    if (!force) {
      const target = event.target as HTMLElement;
      if (target.closest('input,button,a,textarea,select,[contenteditable="true"],.board-inline-input')) return;
    }
    onDragStart(card, event, force);
  };
  const moverConProximidad = (event: React.PointerEvent<HTMLElement>) => {
    if (!card.locked) {
      const rect = event.currentTarget.getBoundingClientRect();
      const distancia = Math.min(
        event.clientX - rect.left,
        rect.right - event.clientX,
        event.clientY - rect.top,
        rect.bottom - event.clientY,
      );
      const cerca = distancia <= 12;
      if (cerca !== cercaDelBorde) setCercaDelBorde(cerca);
    }
    onDragMove(event as React.PointerEvent<HTMLDivElement>);
  };
  const estilo = card.estilo;
  const estiloTarjeta: React.CSSProperties = {
    left: card.x,
    top: card.y,
    width: card.width,
    ...(estilo?.opacity !== undefined ? { opacity: estilo.opacity } : {}),
    ...(estilo?.background ? { background: estilo.background } : {}),
    ...(estilo?.textColor ? { color: estilo.textColor } : {}),
    ...(estilo?.fontFamily ? { fontFamily: estilo.fontFamily } : {}),
    ...(estilo?.fontSize ? { fontSize: `${estilo.fontSize}px` } : {}),
    ...(estilo?.borderColor || estilo?.borderWidth !== undefined
      ? {
          borderColor: estilo?.borderColor,
          borderWidth: estilo?.borderWidth,
          borderStyle: estilo?.borderStyle ?? 'solid',
        }
      : {}),
    ...(estilo?.shadow ? { boxShadow: estilo.shadow === 'none' ? 'none' : estilo.shadow === 'fuerte' ? 'var(--shadow-2)' : 'var(--shadow-1)' } : {}),
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
        style={estiloTarjeta}
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
      className={`board-card color-${card.color} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''} ${connectionSource ? 'connection-source' : ''} ${connectionTarget ? 'connection-target' : ''} ${dragging ? 'dragging' : ''} ${settling ? 'settling' : ''} ${card.locked ? 'is-locked' : ''} ${cercaDelBorde ? 'connect-near' : ''}`}
      style={estiloTarjeta}
      onPointerDownCapture={(event) => {
        if ((event.metaKey || event.ctrlKey) && !card.locked) {
          event.stopPropagation();
          iniciarArrastre(event, true);
        }
      }}
      onPointerDown={(event) => {
        if (!event.metaKey && !event.ctrlKey) iniciarArrastre(event);
      }}
      onPointerMove={moverConProximidad}
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
      <div className={`board-card-head ${card.locked ? 'is-locked' : ''}`} onPointerMove={onDragMove} onPointerUp={onDragEnd} onPointerCancel={onDragEnd} title={card.locked ? 'Tarjeta bloqueada' : 'Arrastra desde cualquier parte para mover la tarjeta'}>
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
      <BoardCardContent card={card} editar={onReplace} acciones={acciones} />
      {!card.locked && onWidthResizeStart && (
        <span
          role="presentation"
          className="board-card-width-handle"
          onPointerDown={(event) => { event.stopPropagation(); event.preventDefault(); onWidthResizeStart(card, event); }}
          onPointerMove={onWidthResizeMove}
          onPointerUp={onWidthResizeEnd}
          onPointerCancel={onWidthResizeEnd}
          title="Arrastra para cambiar el ancho"
        />
      )}
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
      {selected && (
        <button
          type="button"
          className="board-card-settings"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => { event.stopPropagation(); onSettings(card, event); }}
          aria-label={`Ajustes de ${card.title || 'la tarjeta'}`}
          title="Ajustes de esta tarjeta: color, tipografía, borde, sombra, opacidad, bloqueo y conversión"
        >
          <Settings2 size={13} />
        </button>
      )}
      {!card.locked && cercaDelBorde && (['n', 'e', 's', 'w'] as const).map((dir) => (
        <button
          key={dir}
          type="button"
          className={`board-connect-dot dot-${dir}`}
          data-dot={dir}
          onPointerDown={(event) => {
            event.stopPropagation();
            event.preventDefault();
            onConnectStart(card, event);
          }}
          onClick={(event) => event.stopPropagation()}
          aria-label={`Conectar desde el borde ${dir} de ${card.title || 'la tarjeta'}`}
          title="Arrastra desde este punto hasta otra tarjeta para unirlas"
        />
      ))}
    </article>
  );
});
