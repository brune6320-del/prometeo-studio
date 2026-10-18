import { describe, expect, it } from 'vitest';
import { FIT_MIN_ZOOM, fitBoardCamera } from '../board/camera';
import type { BoardCard } from '../board/model';

function card(id: string, x: number, y: number, width = 260): BoardCard {
  return { id, type: 'note', title: id, body: '', x, y, width, color: 'paper' };
}

describe('encuadre del tablero (Visual V1 · L1)', () => {
  it('Ajustar incluye una tarjeta alta medida en el DOM', () => {
    const cards = [card('alta', 0, 0)];
    const viewport = { width: 1000, height: 700 };
    const camera = fitBoardCamera(cards, viewport, new Map([['alta', { width: 260, height: 1400 }]]));
    const bottom = camera.pan.y + 1400 * camera.zoom;
    expect(camera.pan.y).toBeGreaterThanOrEqual(0);
    expect(bottom).toBeLessThanOrEqual(viewport.height);
  });

  it('sin medidas usa la altura de maquetación por defecto', () => {
    const cards = [card('a', 0, 0)];
    const viewport = { width: 1000, height: 700 };
    const withDefault = fitBoardCamera(cards, viewport);
    const withSize = fitBoardCamera(cards, viewport, new Map([['a', { width: 260, height: 210 }]]));
    expect(withDefault).toEqual(withSize);
  });

  it('un canvas amplio se encuadra entero aunque el zoom quede bajo el mínimo de navegación', () => {
    const cards = [card('izq', 0, 0), card('der', 6000, 0)];
    const viewport = { width: 1000, height: 700 };
    const camera = fitBoardCamera(cards, viewport);
    expect(camera.zoom).toBeLessThan(0.35);
    expect(camera.zoom).toBeGreaterThanOrEqual(FIT_MIN_ZOOM);
    const left = camera.pan.x;
    const right = camera.pan.x + (6000 + 260) * camera.zoom;
    expect(left).toBeGreaterThanOrEqual(0);
    expect(right).toBeLessThanOrEqual(viewport.width);
  });
});
