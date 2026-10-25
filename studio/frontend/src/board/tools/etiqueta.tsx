import { Tag } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';
import { TextoEnSitio } from '../../components/InlineEdit';

/** Herramienta de ejemplo: probar que basta este archivo y una línea de registro. */
export const etiquetaTool: BoardTool<BoardCard> = {
  id: 'etiqueta',
  nombre: 'Etiqueta',
  tipo: 'tarjeta',
  icono: Tag,
  crear: (x, y) => ({ ...createCard('etiqueta', x, y), title: 'Nueva etiqueta', width: 200 }),
  validar: esTarjetaDe('etiqueta'),
  Vista: ({ datos, editar }) => (
    <TextoEnSitio
      value={datos.body}
      onCommit={(body) => editar({ ...datos, body })}
      placeholder="ETIQUETA"
      ariaLabel="Texto de la etiqueta"
      className="board-card-etiqueta"
      maxLength={120}
    />
  ),
};
