/**
 * Catálogo de la biblioteca «+ Más».
 *
 * La lista de herramientas sale del registro; este archivo solo añade la
 * metadata que hace navegable el catálogo (categoría, descripción y palabras
 * clave). Una herramienta nueva sin entrada aquí sigue apareciendo en el menú
 * con sus datos mínimos, y `missingLibraryEntries` lo delata en los tests.
 */

export type ToolCategory = 'Escribir' | 'Medios' | 'Estructura' | 'Referencias' | 'Collage';

export interface ToolLibraryEntry {
  id: string;
  nombre: string;
  descripcion: string;
  categoria: ToolCategory;
  palabras: string[];
}

export const TOOL_CATEGORIES: readonly ToolCategory[] = ['Escribir', 'Medios', 'Estructura', 'Referencias', 'Collage'];
export const ALL_TOOLS = 'Todas';
export type ToolCategoryFilter = ToolCategory | typeof ALL_TOOLS;

export const TOOL_LIBRARY: readonly ToolLibraryEntry[] = [
  {
    id: 'note',
    nombre: 'Nota',
    descripcion: 'Una hoja de papel para escribir una idea, un párrafo o una cita. Se edita en el sitio.',
    categoria: 'Escribir',
    palabras: ['nota', 'texto', 'idea', 'papel', 'escribir'],
  },
  {
    id: 'link',
    nombre: 'Enlace',
    descripcion: 'Una URL con vista previa: título, descripción e imagen cuando el backend local puede leerla.',
    categoria: 'Referencias',
    palabras: ['url', 'enlace', 'web', 'referencia', 'vista previa'],
  },
  {
    id: 'media',
    nombre: 'Imagen o vídeo',
    descripcion: 'Una pieza suelta a resolución completa. También acepta audio y archivos; se puede soltar o pegar.',
    categoria: 'Medios',
    palabras: ['imagen', 'vídeo', 'video', 'audio', 'archivo', 'media'],
  },
  {
    id: 'etiqueta',
    nombre: 'Etiqueta',
    descripcion: 'Código y estado para ordenar un bloque del Archivo: área-proyecto.versión y su estado.',
    categoria: 'Estructura',
    palabras: ['etiqueta', 'código', 'codigo', 'estado', 'archivo'],
  },
  {
    id: 'referente',
    nombre: 'Referente',
    descripcion: 'Una pieza que la IA mira y devuelve en palabras: color, tipografía, gesto y materiales.',
    categoria: 'Referencias',
    palabras: ['referente', 'lectura', 'ia', 'color', 'tipografía', 'analizar'],
  },
  {
    id: 'marco',
    nombre: 'Marco',
    descripcion: 'Agrupa tarjetas y las muestra como Libre, Archivo, Muro o Mesa de luz sin moverlas.',
    categoria: 'Estructura',
    palabras: ['marco', 'vista', 'archivo', 'muro', 'mesa', 'agrupar'],
  },
  {
    id: 'entropia',
    nombre: 'Entropía',
    descripcion: 'Un collage generado por reglas con tus fuentes y gustos. Se tira, se guarda o se descarta.',
    categoria: 'Collage',
    palabras: ['entropía', 'entropia', 'collage', 'reglas', 'azar', 'mezcla'],
  },
  {
    id: 'columna',
    nombre: 'Columna',
    descripcion: 'Un contenedor con orden explícito que se pliega y conserva a sus hijos.',
    categoria: 'Estructura',
    palabras: ['columna', 'lista', 'contenedor', 'plegar', 'orden'],
  },
  {
    id: 'tareas',
    nombre: 'Tareas',
    descripcion: 'Una lista con casillas, texto y sangría para convertir una idea en pasos.',
    categoria: 'Escribir',
    palabras: ['tareas', 'checklist', 'lista', 'pasos', 'hacer'],
  },
  {
    id: 'tablero',
    nombre: 'Tablero anidado',
    descripcion: 'Una tarjeta que guarda el vínculo a otro tablero y lo abre sin perder el actual.',
    categoria: 'Estructura',
    palabras: ['tablero', 'anidado', 'vínculo', 'vinculo', 'proyecto'],
  },
];

function fold(value: string): string {
  return value
    .toLocaleLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '');
}

/** Filtra por texto y categoría sin depender del orden del registro. */
export function filterToolLibrary(
  query: string,
  category: ToolCategoryFilter = ALL_TOOLS,
  entries: readonly ToolLibraryEntry[] = TOOL_LIBRARY,
): ToolLibraryEntry[] {
  const needle = fold(query.trim());
  return entries.filter((entry) => {
    if (category !== ALL_TOOLS && entry.categoria !== category) return false;
    if (!needle) return true;
    const haystack = fold([entry.nombre, entry.descripcion, entry.categoria, ...entry.palabras].join(' '));
    return haystack.includes(needle);
  });
}

/** Entradas del registro que aún no tienen metadata de biblioteca. */
export function missingLibraryEntries(toolIds: readonly string[], entries: readonly ToolLibraryEntry[] = TOOL_LIBRARY): string[] {
  const known = new Set(entries.map((entry) => entry.id));
  return toolIds.filter((id) => !known.has(id));
}

/** Entrada de catálogo para una herramienta, con recuperación mínima si falta. */
export function libraryEntryFor(
  id: string,
  nombre: string,
  entries: readonly ToolLibraryEntry[] = TOOL_LIBRARY,
): ToolLibraryEntry {
  return entries.find((entry) => entry.id === id) ?? {
    id,
    nombre,
    descripcion: 'Herramienta del registro sin descripción de catálogo.',
    categoria: 'Estructura',
    palabras: [id],
  };
}
