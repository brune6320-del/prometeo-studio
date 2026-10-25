import { Sparkles } from 'lucide-react';
import { EntropiaVista } from './entropiaVista';
import { createCard, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import {
  esMarcoEntropia,
  leerEntropia,
  NOMBRE_ENTROPIA,
} from '../vanguardia/entropia';

export const entropiaTool: BoardTool<BoardCard> = {
  id: 'entropia',
  nombre: NOMBRE_ENTROPIA,
  tipo: 'marco',
  icono: Sparkles,
  crear: (x, y) => ({
    ...createCard('marco', x, y),
    title: 'Entropía',
    width: 620,
    datos: {
      alto: 460,
      hijos: [],
      vista: 'libre',
      modo: 'entropia',
    },
  }),
  validar: (datos): datos is BoardCard =>
    typeof datos === 'object' && datos !== null && esMarcoEntropia(datos as BoardCard),
  Vista: ({ datos }) => <EntropiaVista datos={leerEntropia(datos)} fuentes={[]} />,
  exportarMarkdown: (datos) => {
    const collage = leerEntropia(datos);
    if (!collage) return `## ${datos.title || 'Entropía'}\n\nSin tirada guardada.\n`;
    return [
      `## ${datos.title || 'Entropía'}`,
      '',
      `Semilla: ${collage.semilla}`,
      `Regla: ${collage.reglaNombre || collage.regla}`,
      `Restricción: ${collage.restriccion}`,
      `Fuentes: ${collage.fuentes.join(', ')}`,
      '',
    ].join('\n');
  },
};
