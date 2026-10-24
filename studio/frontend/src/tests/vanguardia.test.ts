import { describe, expect, it } from 'vitest';
import {
  combinar,
  PROBABILIDAD_AZAR_PURO,
  type Combinacion,
  type HerramientaFuente,
  type ReferenteFuente,
  type ReglaFuente,
  type RestriccionFuente,
} from '../board/vanguardia/combinador';
import {
  ARCHIVO_GUSTOS,
  conGustos,
  gustosAJson,
  gustosDeProyecto,
  gustosDesdeJson,
  gustosVacios,
  like,
  nope,
  PESO_MAXIMO,
  PESO_MINIMO,
  type Gustos,
} from '../board/vanguardia/gustos';

const REFERENTES: ReferenteFuente[] = [
  { id: 'letterform', nombre: 'Letterform Archive', etiquetas: ['tipografía'] },
  { id: 'nypl', nombre: 'NYPL Digital Collections', etiquetas: ['mapas'] },
  { id: 'cooper-hewitt', nombre: 'Cooper Hewitt', etiquetas: ['diseño'] },
  { id: 'dover', nombre: 'Dover', etiquetas: ['grabado'] },
];

const HERRAMIENTAS: HerramientaFuente[] = [
  { id: 'note', nombre: 'Nota' },
  { id: 'link', nombre: 'Enlace' },
  { id: 'referente', nombre: 'Referente' },
];

const REGLAS: ReglaFuente[] = [
  { id: 'dada', nombre: 'Dadá' },
  { id: 'bauhaus', nombre: 'Bauhaus' },
  { id: 'suizo', nombre: 'Suizo' },
];

const RESTRICCIONES: RestriccionFuente[] = [
  { id: 'dos-colores', texto: 'solo dos colores' },
  { id: 'quita-bonito', texto: 'quita lo más bonito' },
  { id: 'al-reves', texto: 'una pieza al revés' },
];

function tirar(semilla: string, gustos?: Gustos): Combinacion {
  return combinar(semilla, REFERENTES, HERRAMIENTAS, REGLAS, RESTRICCIONES, gustos);
}

describe('combinador con semilla', () => {
  it('la misma semilla devuelve siempre la misma combinación', () => {
    const primera = tirar('luna-2026');
    const segunda = tirar('luna-2026');
    expect(segunda).toEqual(primera);

    expect(primera.referentes.length).toBeGreaterThanOrEqual(2);
    expect(primera.referentes.length).toBeLessThanOrEqual(3);
    expect(new Set(primera.referentes).size).toBe(primera.referentes.length);
    expect(REFERENTES.map((referente) => referente.id)).toEqual(expect.arrayContaining(primera.referentes));
    expect(HERRAMIENTAS.map((tool) => tool.id)).toContain(primera.herramienta);
    expect(REGLAS.map((regla) => regla.id)).toContain(primera.regla);
    expect(RESTRICCIONES.map((restriccion) => restriccion.texto)).toContain(primera.restriccion);
  });

  it('otra semilla puede cambiar la tirada sin romper la forma', () => {
    const tiradas = Array.from({ length: 40 }, (_, index) => tirar(`semilla-${index}`));
    expect(new Set(tiradas.map((tirada) => tirada.referentes.join(','))).size).toBeGreaterThan(1);
    for (const tirada of tiradas) {
      expect(tirada.referentes.length).toBeGreaterThanOrEqual(2);
      expect(tirada.referentes.length).toBeLessThanOrEqual(3);
    }
  });

  it('los pesos se recortan a [0.2, 5] al dar ♥ y ✕', () => {
    const base = tirar('pesos');
    let gustos = gustosVacios();
    for (let i = 0; i < 20; i += 1) gustos = like(gustos, base);

    for (const id of base.referentes) expect(gustos.referentes[id]).toBe(PESO_MAXIMO);
    expect(gustos.reglas[base.regla]).toBe(PESO_MAXIMO);
    expect(gustos.herramientas[base.herramienta]).toBe(PESO_MAXIMO);
    expect(Object.keys(gustos.pares)).toHaveLength((base.referentes.length * (base.referentes.length - 1)) / 2);
    for (const peso of Object.values(gustos.pares)) expect(peso).toBe(PESO_MAXIMO);

    let abajo = gustos;
    for (let i = 0; i < 40; i += 1) abajo = nope(abajo, base);
    for (const id of base.referentes) expect(abajo.referentes[id]).toBe(PESO_MINIMO);
    expect(abajo.reglas[base.regla]).toBe(PESO_MINIMO);
    expect(abajo.herramientas[base.herramienta]).toBe(PESO_MINIMO);
    for (const peso of Object.values(abajo.pares)) expect(peso).toBe(PESO_MINIMO);

    // La memoria original no se muta.
    expect(gustosVacios()).toEqual({ version: 1, referentes: {}, reglas: {}, herramientas: {}, pares: {} });
    expect(nope(gustosVacios(), base).referentes[base.referentes[0]]).toBe(PESO_MINIMO);
  });

  it('el 20 % de azar puro se cumple en 10 000 tiradas (±2 %)', () => {
    const total = 10_000;
    let puras = 0;
    for (let i = 0; i < total; i += 1) {
      if (tirar(`tirada-${i}`).azarPuro) puras += 1;
    }
    const proporcion = puras / total;
    expect(Math.abs(proporcion - PROBABILIDAD_AZAR_PURO)).toBeLessThanOrEqual(0.02);
  });

  it('los gustos viven en el proyecto y salen como gustos.json', () => {
    const proyecto = { id: 'p-luna', nombre: 'Luna' };
    const gustos = like(gustosVacios(), tirar('memoria'));
    const conMemoria = conGustos(proyecto, gustos);

    expect(conMemoria.id).toBe('p-luna');
    expect(conMemoria.gustos).toEqual(gustos);
    expect(gustosDeProyecto(conMemoria)).toEqual(gustos);
    expect(gustosDeProyecto({ id: 'sin-gustos' })).toEqual(gustosVacios());
    expect(ARCHIVO_GUSTOS).toBe('gustos.json');

    const json = gustosAJson(gustos);
    expect(JSON.parse(json).version).toBe(1);
    expect(gustosDesdeJson(json)).toEqual(gustos);
    expect(gustosDesdeJson('no es json')).toBeNull();
  });
});
