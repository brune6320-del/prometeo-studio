import React, { useMemo, useState, type CSSProperties } from 'react';
import type { BoardCard } from '../board/model';
import { buildMesaPieces, layoutJustifiedRows } from '../board/vistas/mesa';

/**
 * Vista «Mesa de luz» de un marco: las piezas vistas desde arriba, con sombra
 * suave y un giro leve derivado de una semilla fija. «Ordenar en muro» las
 * coloca en filas justificadas sin tocar las posiciones reales del tablero.
 */
export const MesaView: React.FC<{
  frameTitle: string;
  cards: readonly BoardCard[];
  childIds: readonly string[];
  width: number;
  seed?: number;
}> = ({ frameTitle, cards, childIds, width, seed = 7 }) => {
  const pieces = useMemo(() => buildMesaPieces(cards, childIds, seed), [cards, childIds, seed]);
  const pieceById = useMemo(() => new Map(pieces.map((piece) => [piece.id, piece])), [pieces]);
  const contentWidth = Math.max(120, width - 16);
  const wall = useMemo(() => layoutJustifiedRows(pieces, contentWidth, 112, 8), [pieces, contentWidth]);
  const [arranged, setArranged] = useState(false);
  const pieceWidth = Math.max(96, Math.min(170, (contentWidth - 24) / 3));

  return (
    <div className="board-mesa" role="group" aria-label={`Mesa de luz: ${frameTitle || 'marco'}`}>
      <div className="mesa-toolbar">
        <span className="mesa-label">Mesa de luz · {pieces.length} {pieces.length === 1 ? 'pieza' : 'piezas'}</span>
        <button
          type="button"
          className="mesa-action"
          onClick={() => setArranged((current) => !current)}
          aria-pressed={arranged}
        >
          {arranged ? 'Volver a la mesa' : 'Ordenar en muro'}
        </button>
      </div>
      <div className="mesa-scroll">
        {pieces.length === 0 ? (
          <p className="mesa-empty">Añade medios al marco para llenar la mesa.</p>
        ) : arranged ? (
          <div className="mesa-wall" style={{ height: wall.height }}>
            {wall.rows.flatMap((row) => row.items.map((item) => {
              const piece = pieceById.get(item.id);
              if (!piece) return null;
              return (
                <figure
                  className="mesa-wall-piece"
                  key={item.id}
                  style={{ left: item.x, top: item.y, width: item.width, height: item.height }}
                >
                  <div className="mesa-media">{renderMedia(piece.card)}</div>
                  <figcaption className="mesa-wall-code">{piece.code || '—'}</figcaption>
                </figure>
              );
            }))}
          </div>
        ) : (
          <div className="mesa-surface">
            {pieces.map((piece) => (
              <figure
                className="mesa-piece"
                key={piece.id}
                style={{
                  width: pieceWidth,
                  '--mesa-rotation': `${piece.rotation}deg`,
                  '--mesa-offset-x': `${piece.offsetX}px`,
                  '--mesa-offset-y': `${piece.offsetY}px`,
                  '--mesa-aspect': String(piece.aspect),
                } as CSSProperties}
              >
                <div className="mesa-media">{renderMedia(piece.card)}</div>
                <figcaption className="mesa-caption">
                  <span className="muro-code">{piece.code || '—'}</span>
                  <span>{piece.title}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

function renderMedia(card: BoardCard): React.ReactNode {
  const media = card.media;
  if (!media) return <span className="mesa-media-missing">{card.title || 'Sin medio'}</span>;
  if (media.kind === 'image') {
    return <img src={media.dataUrl} alt={card.title || media.name} draggable={false} />;
  }
  if (media.kind === 'video') {
    return <video src={media.dataUrl} muted loop playsInline preload="metadata" aria-label={card.title || media.name} />;
  }
  if (media.kind === 'audio') {
    return (
      <span className="mesa-media-file">
        <span>{media.name}</span>
        <audio src={media.dataUrl} controls preload="metadata" />
      </span>
    );
  }
  return (
    <span className="mesa-media-file">
      <a href={media.dataUrl} download={media.name}>{media.name}</a>
    </span>
  );
}
