import { Tag } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';

/** Herramienta de ejemplo: probar que basta este archivo y una línea de registro. */
export const etiquetaTool: BoardTool<BoardCard> = {
  id: 'etiqueta',
  nombre: 'Etiqueta',
  tipo: 'tarjeta',
  icono: Tag,
  crear: (x, y) => ({ ...createCard('etiqueta', x, y), title: 'Nueva etiqueta', width: 200 }),
  validar: esTarjetaDe('etiqueta'),
  Vista: ({ datos, editar }) => (
    <textarea
      className="board-card-body"
      value={datos.body}
      maxLength={120}
      onChange={(event) => editar({ ...datos, body: event.target.value })}
      placeholder="ETIQUETA"
      aria-label="Texto de la etiqueta"
      style={{
        color: '#9a9aa2',
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
      }}
    />
  ),
};
