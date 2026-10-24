import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { BoardCard } from '../board/model';
import { buildArchive, formatClock, paragraphs, slideIndex, type ArchiveBlock } from '../board/archivo';

/**
 * Vista «Archivo» de un marco: tres columnas como ireneguerra.xyz.
 * Izquierda fija (primera nota hija + reloj vivo), centro con el feed de bloques
 * y carrusel, derecha con el índice. Los hijos se leen, nunca se mueven ni se copian.
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
  const feedRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(formatClock(new Date())), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const moveSlide = (block: ArchiveBlock, delta: number) => {
    setSlides((current) => ({
      ...current,
      [block.id]: slideIndex(current[block.id] ?? 0, block.items.length, delta),
    }));
  };

  const scrollToBlock = (index: number) => {
    const target = feedRef.current?.querySelectorAll<HTMLElement>('.archivo-block')[index];
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className={`board-archivo ${fullscreen ? 'is-fullscreen' : ''}`} role="group" aria-label={`Archivo: ${frameTitle || 'marco'}`}>
      <div className="archivo-columns">
        <aside className="archivo-col archivo-note" aria-label="Nota fija">
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
                <article className="archivo-block" key={block.id}>
                  {block.items.length > 0 && (
                    <div className="archivo-carousel">
                      {block.items.map((item, slide) => (
                        <div className={`archivo-slide ${slide === active ? 'active' : ''}`} key={item.id} aria-hidden={slide !== active}>
                          {renderMedia(item)}
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
              <footer className="archivo-feed-footer">© {frameTitle || 'Archivo'} · {layout.blocks.length} {layout.blocks.length === 1 ? 'proyecto' : 'proyectos'}</footer>
            )}
          </div>
        </section>

        <aside className="archivo-col archivo-index" aria-label="Índice">
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
    </div>
  );
};

function renderMedia(card: BoardCard): React.ReactNode {
  const media = card.media;
  if (!media) return <div className="archivo-media-missing">{card.title || 'Sin medio'}</div>;
  if (media.kind === 'image') {
    return <img src={media.dataUrl} alt={card.title || media.name} draggable={false} />;
  }
  if (media.kind === 'video') {
    return <video src={media.dataUrl} muted loop autoPlay playsInline preload="metadata" aria-label={card.title || media.name} />;
  }
  if (media.kind === 'audio') {
    return (
      <div className="archivo-media-file">
        <span>{media.name}</span>
        <audio src={media.dataUrl} controls preload="metadata" />
      </div>
    );
  }
  return (
    <div className="archivo-media-file">
      <a href={media.dataUrl} download={media.name}>{media.name}</a>
    </div>
  );
}
