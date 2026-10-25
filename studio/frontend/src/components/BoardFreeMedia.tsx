import React from 'react';
import { Lock, LockOpen, Pause, Play, X } from 'lucide-react';
import type { BoardCard } from '../board/model';
import { metricas } from '../motion/metricas';
import { TituloEnSitio, TextoEnSitio } from './InlineEdit';

export interface RecorteMedia {
  escala: number;
  x: number;
  y: number;
}

/** Lee el recorte guardado sin confiar en el almacenamiento. */
export function leerRecorte(card: BoardCard): RecorteMedia {
  const raw = card.datos?.recorte;
  if (typeof raw !== 'object' || raw === null) return { escala: 1, x: 0.5, y: 0.5 };
  const datos = raw as Partial<RecorteMedia>;
  const limitar = (valor: unknown, min: number, max: number, fallback: number) =>
    typeof valor === 'number' && Number.isFinite(valor) ? Math.max(min, Math.min(max, valor)) : fallback;
  return {
    escala: limitar(datos.escala, 1, 3, 1),
    x: limitar(datos.x, 0, 1, 0.5),
    y: limitar(datos.y, 0, 1, 0.5),
  };
}

function leerAlt(card: BoardCard): string {
  return typeof card.datos?.alt === 'string' ? card.datos.alt : '';
}

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
  onReplaceMedia?: (cardId: string, file: File) => void;
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
  onReplaceMedia,
}: BoardFreeMediaProps) {
  metricas.rendersTarjeta += 1;
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const inicioRef = React.useRef<{ x: number; y: number } | null>(null);
  const movidoRef = React.useRef(false);
  const [reproduciendo, setReproduciendo] = React.useState(false);
  const [editandoRecorte, setEditandoRecorte] = React.useState(false);
  const recorte = leerRecorte(card);
  const alt = leerAlt(card);

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
            alt={alt || card.title || card.media.name}
            draggable={false}
            style={{
              objectFit: 'cover',
              objectPosition: `${recorte.x * 100}% ${recorte.y * 100}%`,
              transform: `scale(${recorte.escala})`,
            }}
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

      <div className={`board-free-media-caption ${selected ? 'is-editable' : ''}`}>
        {selected ? (
          <>
            <TituloEnSitio value={card.title} onCommit={(title) => onPatch(card.id, { title })} ariaLabel="Título de la imagen" className="board-free-media-title" />
            <TextoEnSitio value={card.body} onCommit={(body) => onPatch(card.id, { body })} placeholder="Pie de imagen" ariaLabel="Pie de la imagen" maxLength={2000} />
            <input
              className="board-free-media-alt"
              value={alt}
              placeholder="Texto alternativo"
              aria-label="Texto alternativo de la imagen"
              maxLength={300}
              onClick={(event) => event.stopPropagation()}
              onPointerDown={(event) => event.stopPropagation()}
              onChange={(event) => onPatch(card.id, { datos: { ...card.datos, alt: event.target.value.slice(0, 300) } })}
            />
            <div className="board-free-media-tools" onPointerDown={(event) => event.stopPropagation()}>
              <button type="button" onClick={() => fileInputRef.current?.click()} aria-label="Reemplazar imagen">Reemplazar</button>
              <button
                type="button"
                onClick={() => setEditandoRecorte((valor) => !valor)}
                aria-expanded={editandoRecorte}
                aria-label={editandoRecorte ? 'Terminar recorte' : 'Recortar imagen'}
              >{editandoRecorte ? 'Listo' : 'Recortar'}</button>
            </div>
            {editandoRecorte && !esVideo && (
              <div className="board-free-media-crop" onPointerDown={(event) => event.stopPropagation()}>
                <label>Zoom<input type="range" min="1" max="3" step="0.05" value={recorte.escala} aria-label="Zoom del recorte" onChange={(event) => onPatch(card.id, { datos: { ...card.datos, recorte: { ...recorte, escala: Number(event.target.value) } } })} /></label>
                <label>Horizontal<input type="range" min="0" max="1" step="0.01" value={recorte.x} aria-label="Posición horizontal del recorte" onChange={(event) => onPatch(card.id, { datos: { ...card.datos, recorte: { ...recorte, x: Number(event.target.value) } } })} /></label>
                <label>Vertical<input type="range" min="0" max="1" step="0.01" value={recorte.y} aria-label="Posición vertical del recorte" onChange={(event) => onPatch(card.id, { datos: { ...card.datos, recorte: { ...recorte, y: Number(event.target.value) } } })} /></label>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,video/*"
              hidden
              aria-label="Archivo para reemplazar la imagen"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = '';
                if (file) onReplaceMedia?.(card.id, file);
              }}
            />
          </>
        ) : (
          <>
            <strong>{card.title || card.media?.name || 'Sin título'}</strong>
            {card.body && <span>{card.body}</span>}
          </>
        )}
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
