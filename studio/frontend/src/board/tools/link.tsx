import { Link2 } from 'lucide-react';
import { createCard, isSafeExternalUrl, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';
import { CuerpoTexto } from './parts';

export const linkTool: BoardTool<BoardCard> = {
  id: 'link',
  nombre: 'Enlace',
  tipo: 'tarjeta',
  icono: Link2,
  crear: (x, y) => createCard('link', x, y),
  validar: esTarjetaDe('link'),
  Vista: ({ datos, editar }) => (
    <>
      <div className="board-card-link">
        <Link2 size={13} aria-hidden="true" />
        {datos.url && isSafeExternalUrl(datos.url) ? <a href={datos.url} target="_blank" rel="noreferrer">{datos.url}</a> : <span>Añade una dirección web segura</span>}
      </div>
      <CuerpoTexto datos={datos} editar={editar} placeholder="Escribe una idea…" />
    </>
  ),
};
