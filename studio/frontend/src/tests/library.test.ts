import { describe, expect, it } from 'vitest';
import { listBoardTools } from '../board/tools/registry';
import {
  ALL_TOOLS,
  TOOL_LIBRARY,
  filterToolLibrary,
  libraryEntryFor,
  missingLibraryEntries,
} from '../board/tools/library';

describe('biblioteca de herramientas', () => {
  it('cada herramienta registrada tiene una entrada de catálogo', () => {
    const ids = listBoardTools().map((tool) => tool.id);
    expect(missingLibraryEntries(ids)).toEqual([]);
    expect(new Set(TOOL_LIBRARY.map((entry) => entry.id)).size).toBe(TOOL_LIBRARY.length);
  });

  it('busca por nombre, descripción y palabras clave sin acentos', () => {
    expect(filterToolLibrary('video').map((entry) => entry.id)).toContain('media');
    expect(filterToolLibrary('CODIGO').map((entry) => entry.id)).toEqual(['etiqueta']);
    expect(filterToolLibrary('código').map((entry) => entry.id)).toEqual(['etiqueta']);
    expect(filterToolLibrary('checklist').map((entry) => entry.id)).toEqual(['tareas']);
  });

  it('filtra por categoría y combina con la búsqueda', () => {
    const referencias = filterToolLibrary('', 'Referencias').map((entry) => entry.id);
    expect(referencias).toEqual(['link', 'referente']);
    expect(filterToolLibrary('marco', 'Referencias')).toEqual([]);
    expect(filterToolLibrary('marco', ALL_TOOLS).map((entry) => entry.id)).toEqual(['marco']);
  });

  it('sin coincidencias devuelve vacío y una entrada desconocida tiene respaldo', () => {
    expect(filterToolLibrary('zzzz')).toEqual([]);
    expect(libraryEntryFor('inventada', 'Herramienta rara')).toMatchObject({
      id: 'inventada',
      nombre: 'Herramienta rara',
      categoria: 'Estructura',
    });
  });
});
