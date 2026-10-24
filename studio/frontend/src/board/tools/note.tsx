import { StickyNote } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';
import { CuerpoTexto } from './parts';

export const noteTool: BoardTool<BoardCard> = {
  id: 'note',
  nombre: 'Nota',
  tipo: 'tarjeta',
  icono: StickyNote,
  crear: (x, y) => createCard('note', x, y),
  validar: esTarjetaDe('note'),
  Vista: ({ datos, editar }) => (
    <CuerpoTexto datos={datos} editar={editar} placeholder="Escribe una idea…" />
  ),
};
