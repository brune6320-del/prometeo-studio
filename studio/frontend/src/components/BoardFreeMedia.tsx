import React from 'react';
import { Lock, LockOpen, Pause, Play, X } from 'lucide-react';
import type { BoardCard } from '../board/model';
import { metricas } from '../motion/metricas';

export type EsquinaMedia = 'nw' | 'ne' | 'sw' | 'se';

interface Modificadores {
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
}

export interface BoardFreeMediaProps {
  card: BoardCard;
  selected: boolean;
  dimmed: boolean;
  dragging: boolean;
  settling: boolean;
  onSelect: (card: BoardCard, modifiers: Modificadores) => void;
  onDragStart: (card: BoardCard, event: React.PointerEvent<HTMLElement>) => void;
  onDragMove: (event: React.PointerEvent<HTMLElement>) => void;
  onDragEnd: (event: React.PointerEvent<HTMLElement>) => void;
  onDelete: (cardId: string) => void;
  onPatch: (cardId: string, patch: Partial<BoardCard>) => void;
  onResizeStart: (card: BoardCard, corner: EsquinaMedia, event: React.PointerEvent<HTMLElement>) => void;
  onResizeMove: (event: React.PointerEvent<HTMLElement>) => void;
  onResizeEnd: (event: React.PointerEvent<HTMLElement>) => void;
  onNaturalSize: (cardId: string, width: number, height: number) => void;
}

const ESQUINAS: EsquinaMedia[] = ['nw', 'ne', 'sw', 'se'];

/**
 * Imagen o vídeo como objeto libre del tablero: sin marco de nota, sin borde de
 * tarjeta y sin fila de colores. El título y el comentario viven en una capa que
 * solo aparece al pasar el ratón, al enfocar o al seleccionar.
 */
export const BoardFreeMedia = React.memo(function BoardFreeMedia({
  card,
  selected,
  dimmed,
  dragging,
  settling,
  onSelect,
  onDragStart,
  onDragMove,
  onDragEnd,
  onDelete,
  onPatch,
  onResizeStart,
  onResizeMove,
  onResizeEnd,
  onNaturalSize,
}: BoardFreeMediaProps) {
  metricas.rendersTarjeta += 1;
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const inicioRef = React.useRef<{ x: number; y: number } | null>(null);
  const movidoRef = React.useRef(false);
  const [reproduciendo, setReproduciendo] = React.useState(false);

  const alternarVideo = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      void video.play().then(() => setReproduciendo(true)).catch(() => setReproduciendo(false));
    } else {
      video.pause();
      setReproduciendo(false);
    }
  };

  const esVideo = card.media?.kind === 'video';
  const alto = card.height;

  return (
    <article
      data-card-id={card.id}
      data-card-type="media"
      data-media-libre={card.media?.kind}
      data-alto={alto === undefined ? 'auto' : 'fijo'}
      tabIndex={-1}
      aria-selected={selected}
      aria-label={`${esVideo ? 'Vídeo' : 'Imagen'}: ${card.title || 'sin título'}`}
      className={`board-free-media ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''} ${dragging ? 'dragging' : ''} ${settling ? 'settling' : ''} ${card.locked ? 'is-locked' : ''}`}
      data-locked={card.locked ? 'si' : 'no'}
      style={{ left: card.x, top: card.y, width: card.width, height: alto }}
      onPointerDown={(event) => {
        inicioRef.current = { x: event.clientX, y: event.clientY };
        movidoRef.current = false;
        if (!card.locked) onDragStart(card, event);
      }}
      onPointerMove={(event) => {
        if (inicioRef.current && Math.hypot(event.clientX - inicioRef.current.x, event.clientY - inicioRef.current.y) > 3) {
          movidoRef.current = true;
        }
        onDragMove(event);
      }}
      onPointerUp={(event) => {
        onDragEnd(event);
        inicioRef.current = null;
      }}
      onPointerCancel={(event) => {
        onDragEnd(event);
        inicioRef.current = null;
      }}
      onClick={() => {
        if (movidoRef.current) {
          movidoRef.current = false;
          return;
        }
        if (esVideo) alternarVideo();
      }}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          if (esVideo) alternarVideo();
          else onSelect(card, event);
        }
      }}
      onDoubleClick={(event) => event.stopPropagation()}
    >
      <div className="board-free-media-frame">
        {card.media?.kind === 'image' && (
          <img
            src={card.media.dataUrl}
            alt={card.title || card.media.name}
            draggable={false}
            onLoad={(event) => {
              if (alto === undefined) onNaturalSize(card.id, event.currentTarget.naturalWidth, event.currentTarget.naturalHeight);
            }}
          />
        )}
        {esVideo && (
          <video
            ref={videoRef}
            src={card.media?.dataUrl}
            muted
            playsInline
            preload="metadata"
            aria-label={`Vídeo ${card.title || card.media?.name || ''}`}
            onLoadedMetadata={(event) => {
              if (alto === undefined) onNaturalSize(card.id, event.currentTarget.videoWidth, event.currentTarget.videoHeight);
            }}
            onPlay={() => setReproduciendo(true)}
            onPause={() => setReproduciendo(false)}
            onEnded={() => setReproduciendo(false)}
          />
        )}
        {esVideo && (
          <span className="board-free-media-play" aria-hidden="true">
            {reproduciendo ? <Pause size={14} /> : <Play size={14} />}
          </span>
        )}
      </div>

      <div className="board-free-media-caption" aria-hidden="true">
        <strong>{card.title || card.media?.name || 'Sin título'}</strong>
        {card.body && <span>{card.body}</span>}
      </div>

      <button
        type="button"
        className="board-free-media-lock"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => { event.stopPropagation(); onPatch(card.id, { locked: !card.locked }); }}
        aria-label={card.locked ? 'Desbloquear pieza' : 'Bloquear pieza'}
        title={card.locked ? 'Desbloquear' : 'Bloquear posición y borrado'}
      >
        {card.locked ? <Lock size={12} /> : <LockOpen size={12} />}
      </button>

      <button
        type="button"
        className="board-free-media-delete"
        disabled={card.locked}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => { event.stopPropagation(); onDelete(card.id); }}
        aria-label={`Eliminar ${card.title || 'pieza'}`}
        title="Eliminar"
      >
        <X size={14} />
      </button>

      {!card.locked && ESQUINAS.map((esquina) => (
        <span
          key={esquina}
          className={`board-free-media-handle ${esquina}`}
          role="presentation"
          onPointerDown={(event) => {
            event.stopPropagation();
            onResizeStart(card, esquina, event);
          }}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          onPointerCancel={onResizeEnd}
        />
      ))}
    </article>
  );
});
