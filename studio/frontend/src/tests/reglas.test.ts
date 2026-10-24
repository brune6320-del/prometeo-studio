import { describe, expect, it } from 'vitest';
import { combinar, type HerramientaFuente, type ReferenteFuente, type RestriccionFuente } from '../board/vanguardia/combinador';
import {
  aplicarCombinacion,
  aplicarRegla,
  REGLAS,
  type PiezaColocada,
  type PiezaCollage,
  type TamanoLienzo,
} from '../board/vanguardia/reglas';

const PIEZAS: PiezaCollage[] = [
  { id: 'letterform', aspecto: 1.5 },
  { id: 'nypl', aspecto: 0.75 },
  { id: 'cooper-hewitt', aspecto: 1 },
  { id: 'dover', aspecto: 1.2 },
  { id: 'monoskop', aspecto: 0.6 },
  { id: 'archive-org', aspecto: 1.8 },
];

const TAMANO: TamanoLienzo = { ancho: 1200, alto: 900 };

function aabb(pieza: PiezaColocada): { left: number; top: number; right: number; bottom: number } {
  const rad = Math.abs((pieza.rot * Math.PI) / 180);
  const ancho = Math.abs(pieza.w * Math.cos(rad)) + Math.abs(pieza.h * Math.sin(rad));
  const alto = Math.abs(pieza.w * Math.sin(rad)) + Math.abs(pieza.h * Math.cos(rad));
  const centroX = pieza.x + pieza.w / 2;
  const centroY = pieza.y + pieza.h / 2;
  return {
    left: centroX - ancho / 2,
    top: centroY - alto / 2,
    right: centroX + ancho / 2,
    bottom: centroY + alto / 2,
  };
}

describe('reglas de collage', () => {
  it('la misma semilla devuelve exactamente la misma disposición en las 7 reglas', () => {
    const ids = PIEZAS.map((pieza) => pieza.id).sort();

    for (const regla of REGLAS) {
      const primera = aplicarRegla(regla.id, PIEZAS, 'luna-v2', TAMANO);
      const segunda = aplicarRegla(regla.id, PIEZAS, 'luna-v2', TAMANO);

      expect(segunda).toEqual(primera);
      expect(primera.map((pieza) => pieza.id).sort()).toEqual(ids);
      expect(new Set(primera.map((pieza) => pieza.z)).size).toBe(PIEZAS.length);
      for (const pieza of primera) {
        expect(Number.isFinite(pieza.x)).toBe(true);
        expect(Number.isFinite(pieza.y)).toBe(true);
        expect(pieza.w).toBeGreaterThan(0);
        expect(pieza.h).toBeGreaterThan(0);
        if (pieza.recorte) {
          expect(pieza.recorte.x).toBeGreaterThanOrEqual(0);
          expect(pieza.recorte.y).toBeGreaterThanOrEqual(0);
          expect(pieza.recorte.x + pieza.recorte.w).toBeLessThanOrEqual(1 + 1e-9);
          expect(pieza.recorte.y + pieza.recorte.h).toBeLessThanOrEqual(1 + 1e-9);
        }
      }
    }
  });

  it('nada se sale del lienzo, salvo dadá, que puede hacerlo hasta un 10 %', () => {
    const semillas = ['a', 'collage', 'luna-2026', 'otra-mas'];
    const permitidoX = TAMANO.ancho * 0.1;
    const permitidoY = TAMANO.alto * 0.1;

    for (const regla of REGLAS) {
      for (const semilla of semillas) {
        const colocadas = aplicarRegla(regla.id, PIEZAS, semilla, TAMANO);
        for (const pieza of colocadas) {
          const caja = aabb(pieza);
          if (regla.id === 'dada') {
            expect(caja.left).toBeGreaterThanOrEqual(-permitidoX - 1e-6);
            expect(caja.top).toBeGreaterThanOrEqual(-permitidoY - 1e-6);
            expect(caja.right).toBeLessThanOrEqual(TAMANO.ancho + permitidoX + 1e-6);
            expect(caja.bottom).toBeLessThanOrEqual(TAMANO.alto + permitidoY + 1e-6);
          } else {
            expect(caja.left).toBeGreaterThanOrEqual(-1e-6);
            expect(caja.top).toBeGreaterThanOrEqual(-1e-6);
            expect(caja.right).toBeLessThanOrEqual(TAMANO.ancho + 1e-6);
            expect(caja.bottom).toBeLessThanOrEqual(TAMANO.alto + 1e-6);
          }
        }
      }
    }
  });

  it('bauhaus queda alineado a la retícula de 12 en los dos ejes', () => {
    const unidad = TAMANO.ancho / 12;
    const colocadas = aplicarRegla('bauhaus', PIEZAS, 'reticula', TAMANO);

    expect(colocadas).toHaveLength(PIEZAS.length);
    for (const pieza of colocadas) {
      for (const valor of [pieza.x, pieza.y, pieza.w, pieza.h]) {
        const celdas = valor / unidad;
        expect(Math.abs(celdas - Math.round(celdas))).toBeLessThan(1e-6);
      }
      expect(pieza.rot).toBe(0);
    }

    for (let i = 0; i < colocadas.length; i += 1) {
      for (let j = i + 1; j < colocadas.length; j += 1) {
        const a = colocadas[i];
        const b = colocadas[j];
        const solapan = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
        expect(solapan).toBe(false);
      }
    }
  });

  it('combinar() devuelve la regla elegida ya aplicada y coincide con reglas.ts', () => {
    const referentes: ReferenteFuente[] = [
      { id: 'letterform', nombre: 'Letterform Archive', etiquetas: ['tipografía'] },
      { id: 'nypl', nombre: 'NYPL', etiquetas: ['mapas'] },
      { id: 'dover', nombre: 'Dover', etiquetas: ['grabado'] },
    ];
    const herramientas: HerramientaFuente[] = [
      { id: 'referente', nombre: 'Referente' },
      { id: 'media', nombre: 'Medio' },
    ];
    const restricciones: RestriccionFuente[] = [
      { id: 'dos-colores', texto: 'solo dos colores' },
      { id: 'quitar', texto: 'quita lo más bonito' },
    ];

    const colocacion = { piezas: PIEZAS, tamano: TAMANO };
    const combinacion = combinar('luna-v2', referentes, herramientas, REGLAS, restricciones, colocacion);

    expect(combinacion.disposicion).toHaveLength(PIEZAS.length);
    expect(combinacion.disposicion).toEqual(
      aplicarRegla(combinacion.regla, PIEZAS, combinacion.semilla, TAMANO),
    );
    expect(combinacion.disposicion).toEqual(aplicarCombinacion(combinacion, PIEZAS, TAMANO));

    const sinColocacion = combinar('luna-v2', referentes, herramientas, REGLAS, restricciones);
    expect('disposicion' in sinColocacion).toBe(false);
    expect(combinacion).toMatchObject(sinColocacion);
    expect(REGLAS.map((regla) => regla.id)).toEqual([
      'dada',
      'bauhaus',
      'constructivista',
      'fluxus',
      'situacionista',
      'suizo',
      'irene',
    ]);
  });
});
