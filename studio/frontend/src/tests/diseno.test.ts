import { describe, expect, it } from 'vitest';
import { DESIGN_SYSTEMS, designSystemEntry, normalizeDesignSystem } from '../board/diseno';

describe('sistemas de diseño por tablero', () => {
  it('conoce Forja 2 y el sistema inspirado en Irene', () => {
    expect(DESIGN_SYSTEMS.map((entry) => entry.id)).toEqual(['forja', 'irene']);
    expect(designSystemEntry('irene').nombre).toBe('Archivo Irene');
    expect(designSystemEntry(undefined).id).toBe('forja');
  });

  it('un valor desconocido vuelve a Forja 2 sin romper el tablero', () => {
    expect(normalizeDesignSystem('inventado')).toBe('forja');
    expect(normalizeDesignSystem(null)).toBe('forja');
    expect(normalizeDesignSystem('irene')).toBe('irene');
  });
});
