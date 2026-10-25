import React, { useMemo, useState, type CSSProperties } from 'react';
import type { BoardCard } from '../board/model';
import { buildArchive, groupBlocksByYear, type ArchiveBlock } from '../board/archivo';
import { buildMesaPieces, layoutJustifiedRows } from '../board/vistas/mesa';
import { BookSpread } from './BookSpread';
import { MediaObject } from './MediaObject';

/**
 * Vista «Mesa de luz» de un marco: las piezas vistas desde arriba, con sombra
 * suave y un giro leve derivado de una semilla fija. El modo «Por año» las
 * agrupa en filas inspiradas en la referencia, con una tira horizontal y
 * «More →» para abrir el pliego del proyecto. No toca las posiciones reales.
 */
export const MesaView: React.FC<{
  frameTitle: string;
  cards: readonly BoardCard[];
  childIds: readonly string[];
  width: number;
  seed?: number;
}> = ({ frameTitle, cards, childIds, width, seed = 7 }) => {
  const pieces = useMemo(() => buildMesaPieces(cards, childIds, seed), [cards, childIds, seed]);
  const blocks = useMemo(() => buildArchive(cards, childIds).blocks, [cards, childIds]);
  const years = useMemo(() => groupBlocksByYear(blocks), [blocks]);
  const pieceById = useMemo(() => new Map(pieces.map((piece) => [piece.id, piece])), [pieces]);
  const contentWidth = Math.max(120, width - 16);
  const wall = useMemo(() => layoutJustifiedRows(pieces, contentWidth, 112, 8), [pieces, contentWidth]);
  const [arranged, setArranged] = useState(false);
  const [yearMode, setYearMode] = useState(false);
  const [spread, setSpread] = useState<ArchiveBlock | null>(null);
  const pieceWidth = Math.max(96, Math.min(170, (contentWidth - 24) / 3));

  return (
    <div className="board-mesa" role="group" aria-label={`Mesa de luz: ${frameTitle || 'marco'}`}>
      <div className="mesa-toolbar">
        <span className="mesa-label">Mesa de luz · {pieces.length} {pieces.length === 1 ? 'pieza' : 'piezas'}</span>
        <div className="mesa-modes" role="group" aria-label="Modo de la mesa">
          <button
            type="button"
            className="mesa-action"
            onClick={() => setYearMode(false)}
            aria-pressed={!yearMode}
          >Mesa</button>
          <button
            type="button"
            className="mesa-action"
            onClick={() => setYearMode(true)}
            aria-pressed={yearMode}
          >Por año</button>
          {!yearMode && (
            <button
              type="button"
              className="mesa-action"
              onClick={() => setArranged((current) => !current)}
              aria-pressed={arranged}
            >
              {arranged ? 'Volver a la mesa' : 'Ordenar en muro'}
            </button>
          )}
        </div>
      </div>
      <div className="mesa-scroll">
        {pieces.length === 0 ? (
          <p className="mesa-empty">Añade medios al marco para llenar la mesa.</p>
        ) : yearMode ? (
          <div className="mesa-years">
            {years.map((row) => (
              <section className="mesa-year" key={`year-${row.label}`}>
                <header className="mesa-year-head">
                  <span className="mesa-year-mark" aria-hidden="true">■</span>
                  <span className="mesa-year-label">{row.label}</span>
                  <span className="mesa-year-count">{row.blocks.length} {row.blocks.length === 1 ? 'proyecto' : 'proyectos'}</span>
                  <button type="button" className="mesa-year-more" onClick={() => setSpread(row.blocks[0])}>
                    More →
                  </button>
                </header>
                <div className="mesa-year-strip">
                  {row.blocks.flatMap((block) => block.items.map((item) => (
                    <button
                      type="button"
                      className="mesa-year-piece"
                      key={item.id}
                      onClick={() => setSpread(block)}
                      style={{ '--muro-aspect': String(pieceById.get(item.id)?.aspect ?? 1.4) } as CSSProperties}
                      aria-label={`Abrir ${block.title || 'proyecto'}: ${item.title || item.media?.name || 'pieza'}`}
                    >
                      <span className="mesa-year-media"><MediaObject card={item} playing /></span>
                      <span className="mesa-year-code">{block.code || '—'}</span>
                    </button>
                  )))}
                </div>
              </section>
            ))}
            <footer className="mesa-years-foot">© {frameTitle || 'Archivo'} · {years.length} {years.length === 1 ? 'año' : 'años'}</footer>
          </div>
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
                  <div className="mesa-media"><MediaObject card={piece.card} /></div>
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
                <div className="mesa-media"><MediaObject card={piece.card} /></div>
                <figcaption className="mesa-caption">
                  <span className="muro-code">{piece.code || '—'}</span>
                  <span>{piece.title}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        )}
      </div>
      {spread && <BookSpread block={spread} onClose={() => setSpread(null)} />}
    </div>
  );
};
