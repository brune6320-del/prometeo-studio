import { Frame } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import { DEFAULT_FRAME_HEIGHT, DEFAULT_FRAME_WIDTH, readFrameData } from '../frames';
import type { BoardTool } from './registry';

/**
 * Marco: una herramienta que contiene tarjetas por id. Se dibuja arrastrando en la
 * pizarra (el arrastre lo implementa BoardWorkspace) y su vista por defecto es Libre.
 */
export const marcoTool: BoardTool<BoardCard> = {
  id: 'marco',
  nombre: 'Marco',
  tipo: 'marco',
  icono: Frame,
  crear: (x, y) => ({
    ...createCard('marco', x, y),
    title: 'Marco',
    width: DEFAULT_FRAME_WIDTH,
    datos: { alto: DEFAULT_FRAME_HEIGHT, hijos: [], vista: 'libre' },
  }),
  validar: (datos): datos is BoardCard =>
    typeof datos === 'object' && datos !== null && (datos as BoardCard).type === 'marco',
  Vista: ({ datos, hijos }) => (
    <div className="board-frame-content">
      <span>{readFrameData(datos).hijos.length || hijos?.length || 0} tarjetas dentro · vista Libre</span>
    </div>
  ),
};
