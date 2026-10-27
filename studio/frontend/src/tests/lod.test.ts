import { afterEach, describe, expect, it, vi } from 'vitest';
import { fijarLodCompletas, limpiarLod, lodCompleta, lodCompletas, suscribirLod } from '../board/lod';

afterEach(() => {
  limpiarLod();
});

describe('LOD por tarjeta (T-4)', () => {
  it('solo despierta a las tarjetas que entran o salen', () => {
    const a = vi.fn();
    const b = vi.fn();
    const c = vi.fn();
    suscribirLod('a', a);
    suscribirLod('b', b);
    suscribirLod('c', c);

    fijarLodCompletas(new Set(['a', 'b']));

    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    expect(c).not.toHaveBeenCalled();
    expect(lodCompleta('a')).toBe(true);
    expect(lodCompleta('c')).toBe(false);
  });

  it('no avisa si el conjunto no cambia y devuelve cuántas cambiaron', () => {
    const oyente = vi.fn();
    suscribirLod('a', oyente);
    expect(fijarLodCompletas(new Set(['a']))).toBe(1);
    expect(oyente).toHaveBeenCalledTimes(1);
    expect(fijarLodCompletas(new Set(['a']))).toBe(0);
    expect(oyente).toHaveBeenCalledTimes(1);
  });

  it('apaga las que ya no están en encuadre y olvida sus oyentes', () => {
    const oyente = vi.fn();
    const dejar = suscribirLod('a', oyente);
    fijarLodCompletas(new Set(['a', 'b']));
    fijarLodCompletas(new Set(['b']));
    expect(lodCompletas().has('a')).toBe(false);
    expect(lodCompletas().has('b')).toBe(true);
    expect(oyente).toHaveBeenCalledTimes(2);

    dejar();
    fijarLodCompletas(new Set());
    expect(oyente).toHaveBeenCalledTimes(2);
    expect(lodCompletas().size).toBe(0);
  });

  it('limpiarLod apaga todo, como al desmontar el tablero', () => {
    const oyente = vi.fn();
    suscribirLod('a', oyente);
    fijarLodCompletas(new Set(['a']));
    limpiarLod();
    expect(lodCompleta('a')).toBe(false);
    expect(oyente).toHaveBeenCalledTimes(2);
  });
});
