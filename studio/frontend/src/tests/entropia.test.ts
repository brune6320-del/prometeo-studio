import { describe, expect, it } from 'vitest';
import type { BoardCard } from '../board/model';
import {
  esMarcoEntropia,
  leerEntropia,
  normalizarEntropia,
  nuevaSemilla,
  tirarEntropia,
  type FuenteEntropia,
} from '../board/vanguardia/entropia';
import { gustosVacios, PESO_MAXIMO } from '../board/vanguardia/gustos';
import { createBoardProject, normalizeBoardProject } from '../board/projectModel';

const FUENTES: FuenteEntropia[] = [
  { id: 'letterform', nombre: 'Letterform Archive', etiquetas: ['tipografía'] },
  { id: 'nypl', nombre: 'NYPL Digital Collections', etiquetas: ['mapas'] },
  { id: 'cooper-hewitt', nombre: 'Cooper Hewitt', etiquetas: ['diseño'] },
  { id: 'dover', nombre: 'Dover', etiquetas: ['grabado'] },
];

const HERRAMIENTAS = [
  { id: 'note', nombre: 'Nota' },
  { id: 'referente', nombre: 'Referente' },
  { id: 'entropia', nombre: 'Entropía' },
];

function tirar(semilla: string) {
  return tirarEntropia({
    semilla,
    fuentes: FUENTES,
    herramientas: HERRAMIENTAS,
    tamano: { ancho: 620, alto: 360 },
    gustos: gustosVacios(),
    creado: '2026-10-24T00:00:00.000Z',
  });
}

describe('entropía sobre la pizarra', () => {
  it('la misma semilla rehace el collage idéntico', () => {
    const primera = tirar('luna-2026');
    const segunda = tirar('luna-2026');
    expect(segunda).toEqual(primera);
    expect(primera.disposicion.length).toBe(primera.fuentes.length);
    expect(new Set(primera.fuentes).size).toBe(primera.fuentes.length);
    expect(primera.fuentes.length).toBeGreaterThanOrEqual(2);
    expect(primera.fuentes.length).toBeLessThanOrEqual(3);
  });

  it('guarda semilla, regla, restricción y fuentes y sobrevive a JSON', () => {
    const tirada = tirar('procedencia');
    expect(tirada.semilla).toBe('procedencia');
    expect(tirada.regla).toBeTruthy();
    expect(tirada.restriccion).toBeTruthy();
    expect(tirada.fuentes.every((id) => FUENTES.some((fuente) => fuente.id === id))).toBe(true);

    const vuelta = normalizarEntropia(JSON.parse(JSON.stringify(tirada)));
    expect(vuelta).toEqual(tirada);
    expect(normalizarEntropia({ ...tirada, modo: 'otro' })).toBeNull();
    expect(normalizarEntropia({ ...tirada, disposicion: 'no' })).toBeNull();
  });

  it('no inventa una tirada con menos de dos referentes', () => {
    expect(() => tirarEntropia({
      semilla: 'sola',
      fuentes: [FUENTES[0]],
      herramientas: HERRAMIENTAS,
      tamano: { ancho: 620, alto: 360 },
    })).toThrow(/2 referentes/);
  });

  it('el proyecto guarda los gustos y los recorta al cargar', () => {
    const proyecto = createBoardProject('Luna');
    expect(proyecto.gustos).toEqual(gustosVacios());

    const cargado = normalizeBoardProject({
      ...proyecto,
      gustos: { referentes: { letterform: 99 }, reglas: {}, herramientas: {}, pares: {} },
    });
    expect(cargado?.gustos.referentes.letterform).toBe(PESO_MAXIMO);
    expect(normalizeBoardProject({ ...proyecto, gustos: 'roto' })?.gustos).toEqual(gustosVacios());
  });

  it('reconoce solo su marco y genera semillas reproducibles con azar inyectado', () => {
    const card = {
      id: 'c1', type: 'marco', title: 'Entropía', body: '', x: 0, y: 0, width: 620, color: 'paper' as const,
      datos: { ...tirar('reconocer'), alto: 460, hijos: [], vista: 'libre', modo: 'entropia' },
    } as BoardCard;
    expect(esMarcoEntropia(card)).toBe(true);
    expect(leerEntropia(card)?.semilla).toBe('reconocer');
    expect(esMarcoEntropia({ ...card, datos: { alto: 460, hijos: [], vista: 'libre' } })).toBe(false);

    const secuencia = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];
    let i = 0;
    expect(nuevaSemilla(() => secuencia[i++])).toBe('0134689bce');
  });
});
