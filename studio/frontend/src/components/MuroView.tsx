import React, { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import type { BoardCard } from '../board/model';
import { slideCounter } from '../board/archivo';
import {
  buildMuro,
  distributeMuroColumns,
  muroColumnCount,
  muroOrder,
  stepIndex,
} from '../board/vistas/muro';
import { MediaObject } from './MediaObject';

/**
 * Vista «Muro» de un marco: hojas de contacto en columnas con el código de cada
 * pieza. Un clic abre una caja de luz blanca; ← → recorren y Esc cierra.
 * Solo pinta los hijos: no los mueve, no los copia y no los borra.
 */
export const MuroView: React.FC<{
  frameTitle: string;
  cards: readonly BoardCard[];
  childIds: readonly string[];
  width: number;
}> = ({ frameTitle, cards, childIds, width }) => {
  const items = useMemo(() => buildMuro(cards, childIds), [cards, childIds]);
  const columns = useMemo(
    () => distributeMuroColumns(items, muroColumnCount(Math.max(120, width - 16))),
    [items, width],
  );
  const order = useMemo(() => muroOrder(columns), [columns]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const activeIndex = activeId ? order.findIndex((item) => item.id === activeId) : -1;
  const activeItem = activeIndex >= 0 ? order[activeIndex] : null;

  useEffect(() => {
    if (!activeItem) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) {
        event.stopImmediatePropagation();
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        setActiveId(null);
      } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        const next = stepIndex(activeIndex, order.length, event.key === 'ArrowLeft' ? -1 : 1);
        const target = order[next];
        if (target) setActiveId(target.id);
      }
      // La caja de luz es modal: el tablero no debe recibir atajos mientras esté abierta.
      event.stopImmediatePropagation();
    };
    window.addEventListener('keydown', handleKey, true);
    return () => window.removeEventListener('keydown', handleKey, true);
  }, [activeIndex, activeItem, order]);

  const overlay = activeItem && typeof document !== 'undefined'
    ? createPortal(
      <div
        className="board-muro-lightbox"
        role="dialog"
        aria-modal="true"
        aria-label={`Caja de luz: ${activeItem.title}`}
        onMouseDown={(event) => { if (event.target === event.currentTarget) setActiveId(null); }}
      >
        <div className="muro-lightbox-head">
          <div className="muro-lightbox-meta">
            <span className="muro-code">{activeItem.code || '—'}</span>
            <strong>{activeItem.title}</strong>
            <span className="muro-lightbox-count">{slideCounter(activeIndex, order.length)}</span>
          </div>
          <button type="button" className="muro-lightbox-close" onClick={() => setActiveId(null)} aria-label="Cerrar caja de luz" title="Cerrar (Esc)">ⓧ</button>
        </div>
        <div className="muro-lightbox-stage">
          <button
            type="button"
            className="muro-lightbox-zone previous"
            onClick={() => {
              const target = order[stepIndex(activeIndex, order.length, -1)];
              if (target) setActiveId(target.id);
            }}
            aria-label="Pieza anterior (mitad izquierda)"
          />
          <button
            type="button"
            className="muro-lightbox-zone next"
            onClick={() => {
              const target = order[stepIndex(activeIndex, order.length, 1)];
              if (target) setActiveId(target.id);
            }}
            aria-label="Pieza siguiente (mitad derecha)"
          />
          <button
            type="button"
            className="muro-lightbox-nav previous"
            onClick={() => {
              const target = order[stepIndex(activeIndex, order.length, -1)];
              if (target) setActiveId(target.id);
            }}
            aria-label="Pieza anterior"
          >←</button>
          <div className="muro-lightbox-media">{renderMedia(activeItem.card, true)}</div>
          <button
            type="button"
            className="muro-lightbox-nav next"
            onClick={() => {
              const target = order[stepIndex(activeIndex, order.length, 1)];
              if (target) setActiveId(target.id);
            }}
            aria-label="Pieza siguiente"
          >→</button>
        </div>
        <div className="muro-lightbox-hint"><span>clic izquierda / derecha</span> o <span>← →</span> · <span>Esc</span> cerrar</div>
      </div>,
      document.body,
    )
    : null;

  return (
    <div className="board-muro" role="group" aria-label={`Muro: ${frameTitle || 'marco'}`}>
      <div className="muro-strip">
        <span>Muro</span>
        <span>{items.length} {items.length === 1 ? 'pieza' : 'piezas'}</span>
      </div>
      <div className="muro-scroll">
        {items.length === 0 ? (
          <p className="muro-empty">Añade medios al marco para llenar el muro.</p>
        ) : (
          <div className="muro-grid">
            {columns.map((column, columnIndex) => (
              <div className="muro-column" key={`muro-column-${columnIndex}`}>
                {column.map((item) => (
                  <button
                    type="button"
                    className="muro-thumb"
                    key={item.id}
                    onClick={() => setActiveId(item.id)}
                    aria-label={`Abrir ${item.title}${item.code ? `, ${item.code}` : ''}`}
                    style={{ '--muro-aspect': String(item.aspect) } as CSSProperties}
                  >
                    <span className="muro-thumb-media">{renderMedia(item.card)}</span>
                    <span className="muro-thumb-meta">
                      <span className="muro-code">{item.code || '—'}</span>
                      <span className="muro-title">{item.title}</span>
                    </span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
      {overlay}
    </div>
  );
};

function renderMedia(card: BoardCard, lightbox = false): React.ReactNode {
  return (
    <MediaObject
      card={card}
      playing={lightbox}
      controls={lightbox}
      className={lightbox ? 'muro-lightbox-object' : 'muro-thumb-object'}
    />
  );
}
