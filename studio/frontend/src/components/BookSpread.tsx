import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ArchiveBlock } from '../board/archivo';
import { paragraphs, slideCounter, slideIndex } from '../board/archivo';
import { MediaObject } from './MediaObject';

/**
 * Pliego de dos páginas para abrir un proyecto del archivo.
 *
 * Es una traducción tipográfica del archivador de la referencia: dos hojas
 * blancas, lomo punteado y anillas dibujadas en CSS. Los medios van a la
 * izquierda con zonas de cursor; el código, el estado y el texto, a la derecha.
 * Modal: atrapa Esc y las flechas para que el tablero no las reciba.
 */
export const BookSpread: React.FC<{
  block: ArchiveBlock;
  onClose: () => void;
}> = ({ block, onClose }) => {
  const [slide, setSlide] = useState(0);
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const length = block.items.length;

  useEffect(() => {
    sheetRef.current?.focus();
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, []);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Tab' || event.metaKey || event.ctrlKey || event.altKey) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (length < 2) return;
      if (event.key === 'ArrowLeft') setSlide((current) => slideIndex(current, length, -1));
      if (event.key === 'ArrowRight') setSlide((current) => slideIndex(current, length, 1));
    };
    window.addEventListener('keydown', handleKey, true);
    return () => window.removeEventListener('keydown', handleKey, true);
  }, [length, onClose]);

  const safeSlide = length > 0 ? Math.min(length - 1, slide) : 0;
  const move = (delta: number) => setSlide((current) => slideIndex(current, length, delta));

  const overlay = (
    <div
      className="archivo-spread"
      role="dialog"
      aria-modal="true"
      aria-label={`Proyecto: ${block.title || block.code || 'sin título'}`}
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div className="spread-sheet" tabIndex={-1} ref={sheetRef}>
        <div className="spread-head">
          <span className="spread-head-meta">
            <span>{block.code || '—'}</span>
            <span className="spread-head-title">{block.title || 'Sin título'}</span>
            {block.status && <span className="spread-head-status">{block.status.toUpperCase()}</span>}
          </span>
          <span className="spread-head-actions">
            <span className="spread-counter" aria-live="polite">{slideCounter(safeSlide, length)}</span>
            <button type="button" className="spread-close" onClick={onClose} aria-label="Cerrar el pliego" title="Cerrar (Esc)">ⓧ</button>
          </span>
        </div>

        <div className="spread-pages">
          <div className="spread-page spread-page-media">
            {length > 0 ? (
              <div className="spread-carousel">
                {block.items.map((item, index) => (
                  <div className={`spread-slide ${index === safeSlide ? 'active' : ''}`} key={item.id} aria-hidden={index !== safeSlide}>
                    <MediaObject card={item} playing={index === safeSlide} className="spread-media-object" />
                  </div>
                ))}
                {length > 1 && (
                  <>
                    <button type="button" className="spread-zone previous" onClick={() => move(-1)} aria-label="Diapositiva anterior" />
                    <button type="button" className="spread-zone next" onClick={() => move(1)} aria-label="Diapositiva siguiente" />
                  </>
                )}
              </div>
            ) : (
              <p className="spread-empty">Este proyecto no tiene medios.</p>
            )}
            <div className="spread-page-foot">
              <span className="spread-page-number">{length > 0 ? `${safeSlide + 1} · ${length}` : '0 · 0'}</span>
              {length > 1 && <span>clic en la mitad izquierda o derecha</span>}
            </div>
          </div>

          <div className="spread-binding" aria-hidden="true">
            <span /><span /><span /><span /><span />
          </div>

          <div className="spread-page spread-page-text">
            <div className="spread-meta">
              <div className="spread-code">{block.code || '\u00A0'}</div>
              <div className="spread-title">{block.title || '\u00A0'}</div>
              <div className="spread-status">{block.status ? block.status.toUpperCase() : '\u00A0'}</div>
            </div>
            <div className="spread-text">
              {paragraphs(block.text).map((part, index) => <p key={`${block.id}-spread-${index}`}>{part}</p>)}
              {!block.text && <p className="spread-empty">Sin texto. Doble clic en una nota del proyecto para escribirlo.</p>}
            </div>
            {block.url && (
              <p className="spread-link">
                <a href={block.url} target="_blank" rel="noreferrer">{block.url}</a>
              </p>
            )}
            <div className="spread-page-foot">
              <span className="spread-page-number">{block.code || 'Prometeo'}</span>
              <span><span className="spread-key">← →</span> diapositiva · <span className="spread-key">Esc</span> cerrar</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return typeof document === 'undefined' ? overlay : createPortal(overlay, document.body);
};
