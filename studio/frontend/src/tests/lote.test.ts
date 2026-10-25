import { describe, expect, it } from 'vitest';
import { gustosVacios } from '../board/vanguardia/gustos';
import { crearLote, semillaDeLote, tituloCorto, tituloDeRespaldo } from '../board/vanguardia/lote';
import type { FuenteEntropia } from '../board/vanguardia/entropia';

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

const BASE = {
  semillaBase: '2026',
  n: 12,
  fuentes: FUENTES,
  herramientas: HERRAMIENTAS,
  tamano: { ancho: 900, alto: 640 },
  gustos: gustosVacios(),
  creado: '2026-10-24T00:00:00.000Z',
};

describe('lote de entropía', () => {
  it('la misma semilla produce el mismo lote, bit a bit', () => {
    const primero = crearLote(BASE);
    const segundo = crearLote(BASE);
    expect(segundo).toEqual(primero);
    expect(primero).toHaveLength(12);
    expect(new Set(primero.map((item) => item.datos.semilla)).size).toBe(12);
  });

  it('deriva semillas estables y con forma de semilla', () => {
    expect(semillaDeLote('2026', 7)).toBe(semillaDeLote('2026', 7));
    expect(semillaDeLote('2026', 7)).not.toBe(semillaDeLote('2027', 7));
    for (let i = 0; i < 50; i += 1) expect(semillaDeLote('2026', i)).toMatch(/^[0-9a-f]{10}$/);
  });

  it('rechaza lotes imposibles', () => {
    expect(() => crearLote({ ...BASE, n: 0 })).toThrow();
    expect(() => crearLote({ ...BASE, n: 201 })).toThrow();
    expect(() => crearLote({ ...BASE, semillaBase: '   ' })).toThrow();
  });

  it('recorta títulos a seis palabras y quita comillas', () => {
    expect(tituloCorto('«Un título de exactamente siete palabras aquí»')).toBe('Un título de exactamente siete palabras');
    expect(tituloCorto('  uno\n dos\t tres  ')).toBe('uno dos tres');
    expect(tituloCorto('   ')).toBe('Collage sin título');
    const respaldo = tituloDeRespaldo(crearLote({ ...BASE, n: 1 })[0].datos);
    expect(respaldo.split(' ').length).toBeLessThanOrEqual(6);
  });
});
