import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { BoardCard } from '../board/model';
import {
  buildArchive,
  formatClock,
  paragraphs,
  slideCounter,
  slideIndex,
  type ArchiveBlock,
} from '../board/archivo';
import { BookSpread } from './BookSpread';
import { MediaObject } from './MediaObject';

/**
 * Vista «Archivo» de un marco: tres columnas como ireneguerra.xyz.
 * Izquierda fija (primera nota hija + reloj vivo), centro con el feed de bloques
 * y carrusel, derecha con el índice. Los hijos se leen, nunca se mueven ni se copian.
 *
 * Segunda pasada G4: solo reproduce el vídeo de la diapositiva activa, contador
 * `1 / 3`, flechas del teclado, pliego de dos páginas al doble clic y barra móvil.
 */
export const ArchivoView: React.FC<{
  frameTitle: string;
  cards: readonly BoardCard[];
  childIds: readonly string[];
  fullscreen?: boolean;
}> = ({ frameTitle, cards, childIds, fullscreen = false }) => {
  const layout = useMemo(() => buildArchive(cards, childIds), [cards, childIds]);
  const [clock, setClock] = useState(() => formatClock(new Date()));
  const [slides, setSlides] = useState<Record<string, number>>({});
  const [activeBlockId, setActiveBlockId] = useState<string | null>(null);
  const [spread, setSpread] = useState<ArchiveBlock | null>(null);
  const feedRef = useRef<HTMLDivElement | null>(null);
  const noteRef = useRef<HTMLElement | null>(null);
  const indexRef = useRef<HTMLElement | null>(null);

  const firstCarousel = layout.blocks.find((block) => block.items.length > 0) ?? null;
  const activeBlock = layout.blocks.find((block) => block.id === activeBlockId)
    ?? firstCarousel
    ?? layout.blocks[0]
    ?? null;

  useEffect(() => {
    const timer = window.setInterval(() => setClock(formatClock(new Date())), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const moveSlide = useCallback((block: ArchiveBlock, delta: number) => {
    setActiveBlockId(block.id);
    setSlides((current) => ({
      ...current,
      [block.id]: slideIndex(current[block.id] ?? 0, block.items.length, delta),
    }));
  }, []);

  const scrollToBlock = (index: number) => {
    const target = feedRef.current?.querySelectorAll<HTMLElement>('.archivo-block')[index];
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const block = layout.blocks[index];
    if (block) setActiveBlockId(block.id);
  };

  const handleArrow = useCallback((event: React.KeyboardEvent | KeyboardEvent) => {
    if (!activeBlock || activeBlock.items.length < 2) return;
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    event.stopPropagation();
    moveSlide(activeBlock, event.key === 'ArrowLeft' ? -1 : 1);
  }, [activeBlock, moveSlide]);

  // A pantalla completa el foco puede estar fuera de la vista: se escucha la ventana.
  // El pliego se monta después y para la propagación; además se comprueba aquí.
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (event: KeyboardEvent) => {
      if (spread) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, select, textarea, [contenteditable="true"]')) return;
      handleArrow(event);
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [fullscreen, spread, handleArrow]);

  const openSpread = (block: ArchiveBlock) => {
    if (block.items.length === 0) return;
    setActiveBlockId(block.id);
    setSpread(block);
  };

  return (
    <div
      className={`board-archivo ${fullscreen ? 'is-fullscreen' : ''}`}
      role="group"
      aria-label={`Archivo: ${frameTitle || 'marco'}`}
      tabIndex={fullscreen ? -1 : 0}
      onKeyDown={(event) => {
        if (spread) return;
        handleArrow(event);
      }}
    >
      <div className="archivo-columns">
        <aside className="archivo-col archivo-note" aria-label="Nota fija" ref={noteRef}>
          <div className="archivo-label">{layout.note?.title || 'Nota'}</div>
          <div className="archivo-rule" />
          <div className="archivo-note-body">
            {layout.note ? (
              paragraphs(layout.note.body).map((part, index) => <p key={`${layout.note!.id}-${index}`}>{part}</p>)
            ) : (
              <p className="archivo-empty">Sin nota fija. La primera nota del marco se muestra aquí.</p>
            )}
          </div>
          <time className="archivo-clock">{clock}</time>
        </aside>

        <section className="archivo-col archivo-feed" aria-label={`Feed de ${frameTitle || 'proyectos'}`}>
          <div className="archivo-label">{frameTitle || 'Archivo'}</div>
          <div className="archivo-rule" />
          <div className="archivo-feed-scroll" ref={feedRef}>
            {layout.blocks.length === 0 && (
              <p className="archivo-empty">Añade medios al marco para llenar el feed.</p>
            )}
            {layout.blocks.map((block, blockIndex) => {
              const active = slides[block.id] ?? 0;
              return (
                <article
                  className={`archivo-block ${activeBlock?.id === block.id ? 'is-active' : ''}`}
                  key={block.id}
                  onDoubleClick={(event) => {
                    event.stopPropagation();
                    openSpread(block);
                  }}
                  title={block.items.length > 0 ? 'Doble clic: abrir el proyecto en un pliego' : undefined}
                >
                  {block.items.length > 0 && (
                    <div className="archivo-carousel">
                      {block.items.map((item, slide) => (
                        <div className={`archivo-slide ${slide === active ? 'active' : ''}`} key={item.id} aria-hidden={slide !== active}>
                          <MediaObject card={item} playing={slide === active} />
                        </div>
                      ))}
                      {block.items.length > 1 && (
                        <>
                          <button
                            type="button"
                            className="archivo-zone previous"
                            onClick={(event) => { if (event.detail <= 1) moveSlide(block, -1); }}
                            aria-label={`Diapositiva anterior del bloque ${blockIndex + 1}`}
                          />
                          <button
                            type="button"
                            className="archivo-zone next"
                            onClick={(event) => { if (event.detail <= 1) moveSlide(block, 1); }}
                            aria-label={`Diapositiva siguiente del bloque ${blockIndex + 1}`}
                          />
                        </>
                      )}
                      <span className="archivo-counter" aria-live="polite">{slideCounter(active, block.items.length)}</span>
                      {block.items.length > 1 && <span className="archivo-carousel-hint" aria-hidden="true">‹ clic · clic ›</span>}
                    </div>
                  )}
                  <div className="archivo-block-meta">
                    <div className="archivo-block-id">
                      <div className="archivo-code">{block.code || '\u00A0'}</div>
                      <div className="archivo-title">{block.title || block.items[0]?.title || '\u00A0'}</div>
                      <div className="archivo-status">{block.status ? block.status.toUpperCase() : '\u00A0'}</div>
                    </div>
                    <div className="archivo-block-text">
                      {paragraphs(block.text).map((part, index) => <p key={`${block.id}-text-${index}`}>{part}</p>)}
                      {block.url && <p className="archivo-block-link">{block.url}</p>}
                    </div>
                  </div>
                  <div className="archivo-block-rule" />
                </article>
              );
            })}
            {layout.blocks.length > 0 && (
              <footer className="archivo-feed-footer">
                <span>© {frameTitle || 'Archivo'} · {layout.blocks.length} {layout.blocks.length === 1 ? 'proyecto' : 'proyectos'}</span>
                <span className="archivo-keys"><span className="archivo-key">← →</span> diapositiva · doble clic: proyecto</span>
              </footer>
            )}
          </div>
        </section>

        <aside className="archivo-col archivo-index" aria-label="Índice" ref={indexRef}>
          <div className="archivo-label">Índice</div>
          <div className="archivo-rule" />
          <div className="archivo-index-scroll">
            <div className="archivo-index-heading">Proyectos</div>
            {layout.blocks.map((block, blockIndex) => (
              <button
                type="button"
                className="archivo-index-entry"
                key={`${block.id}-index`}
                onClick={() => scrollToBlock(blockIndex)}
              >
                <span className="archivo-index-code">{block.code || '—'}</span>
                <span className="archivo-index-title">{block.title || block.items[0]?.title || 'Sin título'}</span>
                {block.status && <span className="archivo-index-status">{block.status.toUpperCase()}</span>}
              </button>
            ))}
            {layout.blocks.length === 0 && <p className="archivo-empty">Sin entradas.</p>}
          </div>
        </aside>
      </div>

      {fullscreen && (
        <nav className="archivo-mobilebar" aria-label="Secciones del archivo">
          <button type="button" onClick={() => feedRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>Feed</button>
          <button type="button" onClick={() => noteRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>Bio</button>
          <button type="button" onClick={() => indexRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>Índice</button>
        </nav>
      )}

      {spread && <BookSpread block={spread} onClose={() => setSpread(null)} />}
    </div>
  );
};
