import { Columns3 } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import { COLUMN_WIDTH, readColumnData } from '../columnas';
import type { BoardTool } from './registry';

/** Columna contenedora; su vista real la pinta BoardColumn con las tarjetas resueltas. */
export const columnaTool: BoardTool<BoardCard> = {
  id: 'columna',
  nombre: 'Columna',
  tipo: 'tarjeta',
  icono: Columns3,
  crear: (x, y) => ({
    ...createCard('columna', x, y),
    title: 'Nueva columna',
    width: COLUMN_WIDTH,
    datos: { hijos: [], plegada: false },
  }),
  validar: (datos): datos is BoardCard =>
    typeof datos === 'object' && datos !== null && (datos as BoardCard).type === 'columna',
  Vista: ({ datos }) => (
    <div className="board-frame-content">
      <span>{readColumnData(datos).hijos.length} tarjetas en la columna</span>
    </div>
  ),
};
