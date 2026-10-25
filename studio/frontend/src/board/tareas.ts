import type { BoardCard } from './model';

export interface Tarea {
  id: string;
  texto: string;
  hecha: boolean;
  /** Sangría de una tarea dentro de otra (Tab / Shift+Tab), como en Milanote. */
  nivel: number;
}

export const MAX_TAREAS = 100;
const MAX_TEXTO = 400;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

let fallback = 0;
export function nuevaTareaId(): string {
  return `tarea-${globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${++fallback}`}`;
}

export function tareaVacia(texto = ''): Tarea {
  return { id: nuevaTareaId(), texto, hecha: false, nivel: 0 };
}

export function normalizarTareas(value: unknown): Tarea[] {
  if (!Array.isArray(value)) return [];
  const vistos = new Set<string>();
  return value.slice(0, MAX_TAREAS).flatMap((entry) => {
    if (!isRecord(entry)) return [];
    const texto = typeof entry.texto === 'string' ? entry.texto.slice(0, MAX_TEXTO) : '';
    let id = typeof entry.id === 'string' ? entry.id.slice(0, 100) : nuevaTareaId();
    if (vistos.has(id)) id = nuevaTareaId();
    vistos.add(id);
    const nivel = typeof entry.nivel === 'number' && Number.isFinite(entry.nivel)
      ? Math.max(0, Math.min(2, Math.floor(entry.nivel)))
      : 0;
    return [{ id, texto, hecha: entry.hecha === true, nivel }];
  });
}

export function leerTareas(card: BoardCard): Tarea[] {
  const raw = isRecord(card.datos) ? card.datos : {};
  return normalizarTareas(raw.tareas);
}

export function escribirTareas(card: BoardCard, tareas: Tarea[]): BoardCard {
  return { ...card, datos: { ...card.datos, tareas: normalizarTareas(tareas) } };
}

export function tareasMarkdown(tareas: Tarea[]): string {
  return tareas.map((tarea) => `${'  '.repeat(tarea.nivel)}- [${tarea.hecha ? 'x' : ' '}] ${tarea.texto}`).join('\n');
}
