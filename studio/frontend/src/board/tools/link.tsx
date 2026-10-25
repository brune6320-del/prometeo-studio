import { Link2 } from 'lucide-react';
import { createCard, isSafeExternalUrl, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';
import { CuerpoTexto } from './parts';
import { UrlEnSitio } from '../../components/InlineEdit';
import { leerVistaPrevia } from '../vistaPrevia';

/**
 * Enlace con vista previa. Los metadatos (título, descripción, imagen og:) los
 * aporta el backend local; la tarjeta los guarda como datos y sigue siendo válida sin red.
 */
export const linkTool: BoardTool<BoardCard> = {
  id: 'link',
  nombre: 'Enlace',
  tipo: 'tarjeta',
  icono: Link2,
  crear: (x, y) => createCard('link', x, y),
  validar: esTarjetaDe('link'),
  Vista: ({ datos, editar }) => {
    const preview = leerVistaPrevia(datos);
    const seguro = Boolean(datos.url && isSafeExternalUrl(datos.url));
    if (preview) {
      return (
        <>
          <a
            className="board-link-preview"
            href={datos.url}
            target="_blank"
            rel="noreferrer"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => event.stopPropagation()}
          >
            {preview.imagen && <img src={preview.imagen} alt="" loading="lazy" draggable={false} onError={(event) => { event.currentTarget.hidden = true; }} />}
            <span className="board-link-preview-copy">
              <small>{preview.sitio || 'Enlace'}</small>
              <strong>{preview.titulo || datos.title}</strong>
              {preview.descripcion && <span>{preview.descripcion}</span>}
            </span>
          </a>
          <div className="board-link-url">
            <UrlEnSitio
              value={datos.url ?? ''}
              onCommit={(url) => editar({ ...datos, url })}
              ariaLabel="URL del enlace"
            />
            {seguro && <a href={datos.url} target="_blank" rel="noreferrer" aria-label="Abrir el enlace" title="Abrir en una pestaña nueva" onClick={(event) => event.stopPropagation()}>↗</a>}
          </div>
          <CuerpoTexto datos={datos} editar={editar} placeholder="Añade una nota…" />
        </>
      );
    }
    return (
      <>
        <div className="board-card-link">
          <Link2 size={13} aria-hidden="true" />
          <UrlEnSitio
            value={datos.url ?? ''}
            onCommit={(url) => editar({ ...datos, url })}
            ariaLabel="URL del enlace"
          />
          {seguro && <a href={datos.url} target="_blank" rel="noreferrer" aria-label="Abrir el enlace" title="Abrir en una pestaña nueva" onClick={(event) => event.stopPropagation()}>↗</a>}
        </div>
        <CuerpoTexto datos={datos} editar={editar} placeholder="Escribe una idea…" />
      </>
    );
  },
};
