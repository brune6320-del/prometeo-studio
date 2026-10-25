import { useState } from 'react';
import { CheckSquare, Plus, Trash2 } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';
import { escribirTareas, leerTareas, nuevaTareaId, type Tarea } from '../tareas';

const TareasVista = ({ datos, editar }: { datos: BoardCard; editar: (datos: BoardCard) => void }) => {
  const tareas = leerTareas(datos);
  const [borradores, setBorradores] = useState<Record<string, string>>({});

  const guardar = (siguiente: Tarea[]) => editar(escribirTareas(datos, siguiente));
  const cambiar = (id: string, patch: Partial<Tarea>) => guardar(tareas.map((tarea) => tarea.id === id ? { ...tarea, ...patch } : tarea));
  const anadir = () => guardar([...tareas, { id: nuevaTareaId(), texto: '', hecha: false, nivel: 0 }]);

  return (
    <div className="board-tasks" onPointerDown={(event) => event.stopPropagation()} onClick={(event) => event.stopPropagation()}>
      <ul className="board-tasks-list">
        {tareas.map((tarea, indice) => (
          <li key={tarea.id} className={`board-task ${tarea.hecha ? 'is-done' : ''}`} style={{ paddingLeft: tarea.nivel * 16 }}>
            <input
              type="checkbox"
              checked={tarea.hecha}
              aria-label={`Tarea ${tarea.texto || indice + 1}`}
              onChange={(event) => cambiar(tarea.id, { hecha: event.target.checked })}
            />
            <input
              className="board-task-text"
              value={borradores[tarea.id] ?? tarea.texto}
              placeholder="Nueva tarea"
              aria-label="Texto de la tarea"
              onChange={(event) => setBorradores((actual) => ({ ...actual, [tarea.id]: event.target.value }))}
              onBlur={() => {
                const texto = borradores[tarea.id];
                if (texto === undefined) return;
                setBorradores((actual) => { const next = { ...actual }; delete next[tarea.id]; return next; });
                if (texto.trim() !== tarea.texto) cambiar(tarea.id, { texto: texto.trim() });
              }}
              onKeyDown={(event) => {
                event.stopPropagation();
                if (event.key === 'Enter') {
                  event.preventDefault();
                  (event.target as HTMLInputElement).blur();
                  guardar([...tareas, { id: nuevaTareaId(), texto: '', hecha: false, nivel: tarea.nivel }]);
                } else if (event.key === 'Tab') {
                  event.preventDefault();
                  cambiar(tarea.id, { nivel: Math.max(0, Math.min(2, tarea.nivel + (event.shiftKey ? -1 : 1))) });
                }
              }}
            />
            <button type="button" className="board-task-delete" onClick={() => guardar(tareas.filter((item) => item.id !== tarea.id))} aria-label="Eliminar tarea"><Trash2 size={12} /></button>
          </li>
        ))}
      </ul>
      {tareas.length === 0 && <p className="board-tasks-empty">Sin tareas. Añade la primera.</p>}
      <button type="button" className="board-tasks-add" onClick={anadir}><Plus size={12} /> Añadir tarea</button>
    </div>
  );
};

export const tareasTool: BoardTool<BoardCard> = {
  id: 'tareas',
  nombre: 'Lista de tareas',
  tipo: 'tarjeta',
  icono: CheckSquare,
  crear: (x, y) => ({
    ...createCard('tareas', x, y),
    title: 'Tareas',
    width: 290,
    datos: { tareas: [{ id: nuevaTareaId(), texto: 'Primera tarea', hecha: false, nivel: 0 }] },
  }),
  validar: esTarjetaDe('tareas'),
  Vista: ({ datos, editar }) => <TareasVista datos={datos} editar={editar} />,
  exportarMarkdown: (datos) => {
    const tareas = leerTareas(datos);
    return [`## ${datos.title || 'Tareas'}`, '', ...tareas.map((tarea) => `${'  '.repeat(tarea.nivel)}- [${tarea.hecha ? 'x' : ' '}] ${tarea.texto}`), ''].join('\n');
  },
};
