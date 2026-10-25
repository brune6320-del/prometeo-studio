import { cloneBoardForImport, createBoard, createCard, type BoardCard, type BoardDocument, type BoardRelation } from './model';
import { nuevaTareaId } from './tareas';

export interface Plantilla {
  id: string;
  nombre: string;
  descripcion: string;
  creada?: string;
  builtin: boolean;
  board: BoardDocument;
}

const STORAGE_KEY = 'prometeo-studio-plantillas-v1';
const MAX_PLANTILLAS = 24;

function tableroCon(nombre: string, cards: BoardCard[], relations: BoardRelation[] = []): BoardDocument {
  const board = createBoard(nombre);
  return { ...board, cards, relations };
}

function moodboard(): BoardDocument {
  const notas = [
    { title: 'Paleta', body: '# Paleta\n\n**Cálida** · papel, arena, salvia y rosa.\n\n- Un color dominante\n- Un acento\n- Un neutro', x: 120, y: 120, color: 'sand' as const },
    { title: 'Referencias', body: 'Arrastra imágenes aquí.\n\n> Lo que te hace mirar dos veces.', x: 420, y: 120, color: 'paper' as const },
    { title: 'Texto', body: '- Palabra clave\n- Frase que se queda\n- Lo que no queremos', x: 120, y: 430, color: 'sage' as const },
    { title: 'Material', body: 'Imágenes, vídeos y enlaces sueltos. Sin marco de nota.', x: 720, y: 120, color: 'rose' as const },
  ];
  const cards = notas.map((nota) => ({ ...createCard('note', nota.x, nota.y), title: nota.title, body: nota.body, color: nota.color }));
  return tableroCon('Moodboard', cards);
}

function proyecto(): BoardDocument {
  const columnas: Array<{ title: string; x: number; items: string[] }> = [
    { title: 'Por hacer', x: 120, items: ['Definir el encargo', 'Reunir referencias'] },
    { title: 'En curso', x: 460, items: ['Primera propuesta'] },
    { title: 'Hecho', x: 800, items: [] },
  ];
  const cards: BoardCard[] = [];
  const relations: BoardRelation[] = [];
  for (const columna of columnas) {
    const column = {
      ...createCard('columna', columna.x, 110),
      title: columna.title,
      width: 300,
      datos: { hijos: [] as string[], plegada: false },
    };
    cards.push(column);
    const hijos: string[] = [];
    columna.items.forEach((item, indice) => {
      const tarea = {
        ...createCard('tareas', columna.x + 12, 160 + indice * 120),
        title: item,
        width: 270,
        datos: { tareas: [{ id: nuevaTareaId(), texto: item, hecha: false, nivel: 0 }] },
      };
      cards.push(tarea);
      hijos.push(tarea.id);
    });
    column.datos = { hijos, plegada: false };
  }
  const brief = { ...createCard('note', 120, 620), title: 'Brief', body: '# Brief\n\n**Objetivo**\n\n**Público**\n\n**Entrega**' };
  const referencias = { ...createCard('link', 460, 620), title: 'Referencias', url: 'https://example.com' };
  cards.push(brief, referencias);
  return tableroCon('Proyecto', cards, relations);
}

function estudio(): BoardDocument {
  const idea = { ...createCard('note', 140, 140), title: 'Idea', body: '# Idea\n\nUna frase que explique el proyecto.\n\n- Qué es\n- Para quién\n- Por qué ahora' };
  const tareas = {
    ...createCard('tareas', 140, 440),
    title: 'Siguientes pasos',
    datos: { tareas: [
      { id: nuevaTareaId(), texto: 'Elegir una dirección', hecha: false, nivel: 0 },
      { id: nuevaTareaId(), texto: 'Hacer una prueba pequeña', hecha: false, nivel: 1 },
    ] },
  };
  const columna = {
    ...createCard('columna', 480, 140),
    title: 'Material',
    width: 300,
    datos: { hijos: [tareas.id], plegada: false },
  };
  return tableroCon('Estudio', [idea, tareas, columna], []);
}

export const PLANTILLAS_BUILTIN: Plantilla[] = [
  { id: 'vacio', nombre: 'En blanco', descripcion: 'Un tablero vacío, sin tarjetas.', builtin: true, board: createBoard('Nuevo tablero') },
  { id: 'moodboard', nombre: 'Moodboard', descripcion: 'Paleta, referencias, texto y material libre.', builtin: true, board: moodboard() },
  { id: 'proyecto', nombre: 'Proyecto', descripcion: 'Tres columnas de tareas plegables y un brief.', builtin: true, board: proyecto() },
  { id: 'estudio', nombre: 'Estudio', descripcion: 'Idea, próximos pasos y una columna de material.', builtin: true, board: estudio() },
];

export function materializar(board: BoardDocument, nombre?: string): { cards: BoardCard[]; relations: BoardRelation[]; title: string } {
  const copy = cloneBoardForImport(board);
  return { cards: copy.cards, relations: copy.relations, title: nombre ?? board.title };
}

function guardadas(): Plantilla[] {
  if (typeof window === 'undefined' || !window.localStorage) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.flatMap((entry) => {
      if (typeof entry !== 'object' || entry === null) return [];
      const item = entry as Partial<Plantilla>;
      if (typeof item.id !== 'string' || typeof item.nombre !== 'string' || typeof item.board !== 'object' || item.board === null) return [];
      return [{
        id: item.id,
        nombre: item.nombre.slice(0, 80),
        descripcion: typeof item.descripcion === 'string' ? item.descripcion.slice(0, 200) : 'Plantilla guardada',
        creada: typeof item.creada === 'string' ? item.creada : undefined,
        builtin: false,
        board: item.board as BoardDocument,
      }];
    });
  } catch {
    return [];
  }
}

export function listarPlantillas(): Plantilla[] {
  return [...guardadas(), ...PLANTILLAS_BUILTIN];
}

export function guardarPlantilla(board: BoardDocument): Plantilla[] {
  if (typeof window === 'undefined' || !window.localStorage) return guardadas();
  const actuales = guardadas();
  const plantilla: Plantilla = {
    id: `plantilla-${Date.now().toString(36)}`,
    nombre: board.title.slice(0, 80),
    descripcion: `${board.cards.length} tarjetas guardadas desde un tablero`,
    creada: new Date().toISOString(),
    builtin: false,
    board: JSON.parse(JSON.stringify(board)) as BoardDocument,
  };
  const siguiente = [plantilla, ...actuales].slice(0, MAX_PLANTILLAS);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(siguiente));
  return siguiente;
}

export function eliminarPlantilla(id: string): Plantilla[] {
  if (typeof window === 'undefined' || !window.localStorage) return guardadas();
  const siguiente = guardadas().filter((item) => item.id !== id);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(siguiente));
  return siguiente;
}
