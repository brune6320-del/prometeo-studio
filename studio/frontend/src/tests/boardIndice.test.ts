import { describe, expect, it } from 'vitest';
import { createCard } from '../board/model';
import { coincideBusqueda, ordenDePintado, ventanaVirtual } from '../board/indice';

describe('H5 · índice virtualizado y orden de pintado', () => {
  it('con 500 tarjetas solo monta la ventana visible y mantiene el alto total', () => {
    const ventana = ventanaVirtual(500, 0, 400);
    expect(ventana.inicio).toBe(0);
    expect(ventana.fin - ventana.inicio).toBeLessThan(30);
    expect(ventana.altoTotal).toBe(500 * 38);
    expect(ventana.offsetSuperior).toBe(0);
    expect(ventana.offsetInferior).toBeGreaterThan(0);
  });

  it('al bajar al final la ventana termina en la última fila', () => {
    const ventana = ventanaVirtual(500, 500 * 38, 400);
    expect(ventana.fin).toBe(500);
    expect(ventana.inicio).toBeGreaterThan(460);
    expect(ventana.offsetInferior).toBe(0);
  });

  it('el índice invierte el array: arriba está el último pintado', () => {
    const a = { ...createCard('note', 0, 0), id: 'a' };
    const b = { ...createCard('note', 0, 0), id: 'b' };
    expect(ordenDePintado([a, b]).map((card) => card.id)).toEqual(['b', 'a']);
  });

  it('la búsqueda ignora mayúsculas y busca en título, cuerpo y tipo', () => {
    const card = { ...createCard('note', 0, 0), title: 'Alfa', body: 'beta' };
    expect(coincideBusqueda(card, 'ALFA')).toBe(true);
    expect(coincideBusqueda(card, 'beta')).toBe(true);
    expect(coincideBusqueda(card, 'note')).toBe(true);
    expect(coincideBusqueda(card, 'gamma')).toBe(false);
  });
});
