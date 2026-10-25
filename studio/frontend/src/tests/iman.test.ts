import { describe, expect, it } from 'vitest';
import { imanDeCaja, inclinacionPorVelocidad } from '../board/iman';

const caja = (x: number, y: number, width = 260, height = 200) => ({ x, y, width, height });

describe('imán de tarjetas', () => {
  it('alinea el borde izquierdo con otra tarjeta y devuelve la guía', () => {
    const resultado = imanDeCaja(caja(103, 40), [caja(100, 300)]);
    expect(resultado.dx).toBe(-3);
    expect(resultado.guias.x).toBe(100);
  });

  it('alinea centros aunque los anchos no coincidan', () => {
    const resultado = imanDeCaja(caja(5, 10, 300), [caja(100, 400, 120)]);
    expect(resultado.dx).toBe(5);
    expect(resultado.guias.x).toBe(160);
  });

  it('no toca nada fuera del umbral', () => {
    const resultado = imanDeCaja(caja(140, 40), [caja(100, 300)]);
    expect(resultado.dx).toBe(0);
    expect(resultado.guias.x).toBeUndefined();
  });

  it('usa la retícula cuando no hay otras tarjetas', () => {
    const resultado = imanDeCaja(caja(51, 77), [], { rejilla: 24 });
    expect(resultado.dx).toBe(1);
    expect(resultado.dy).toBe(-5);
    expect(resultado.guias).toEqual({ x: 312, y: 72 });
  });

  it('respeta el umbral en unidades del mundo', () => {
    const resultado = imanDeCaja(caja(107, 40), [caja(100, 300)], { umbral: 4 });
    expect(resultado.dx).toBe(0);
  });
});

describe('inclinación al arrastrar', () => {
  it('crece con la velocidad y se queda por debajo de 1,2°', () => {
    expect(inclinacionPorVelocidad(0)).toBe(0);
    expect(inclinacionPorVelocidad(60)).toBeGreaterThan(0);
    expect(inclinacionPorVelocidad(60)).toBeLessThan(0.1);
    expect(Math.abs(inclinacionPorVelocidad(10000))).toBeLessThanOrEqual(1.2);
    expect(Math.abs(inclinacionPorVelocidad(-10000))).toBeLessThanOrEqual(1.2);
  });

  it('ignora velocidades no finitas', () => {
    expect(inclinacionPorVelocidad(Number.NaN)).toBe(0);
  });
});
