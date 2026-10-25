import { describe, expect, it } from 'vitest';
import { FIT_MIN_ZOOM, fitBoardCamera, factorDePellizco, screenToWorld, zoomAtPoint, ZOOM_PINCH_K } from '../board/camera';
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

describe('T-1 · pellizco 1:1', () => {
  it('la constante vive en un solo sitio y un pellizco normal duplica el zoom', () => {
    expect(ZOOM_PINCH_K).toBeGreaterThanOrEqual(0.01);
    expect(ZOOM_PINCH_K).toBeLessThanOrEqual(0.02);
    // Un gesto normal de trackpad Mac acumula alrededor de −58 px de deltaY.
    expect(factorDePellizco(-58)).toBeGreaterThan(1.9);
    expect(factorDePellizco(-58)).toBeLessThan(2.1);
  });

  it('el mundo bajo el cursor no se mueve al aplicar el factor', () => {
    const camera = { pan: { x: 120, y: 80 }, zoom: 0.9 };
    const cursor = { x: 733, y: 412 };
    const antes = screenToWorld(cursor, camera);
    const siguiente = zoomAtPoint(camera, camera.zoom * factorDePellizco(-24), cursor);
    const despues = screenToWorld(cursor, siguiente);
    expect(despues.x).toBeCloseTo(antes.x, 6);
    expect(despues.y).toBeCloseTo(antes.y, 6);
  });

  it('H7 · el zoom de inspección llega a 800 % y no pasa', () => {
    const camera = zoomAtPoint({ pan: { x: 0, y: 0 }, zoom: 1 }, 20, { x: 400, y: 300 });
    expect(camera.zoom).toBe(8);
    expect(zoomAtPoint(camera, 0.01, { x: 400, y: 300 }).zoom).toBe(0.25);
  });

  it('el delta se aplica sin muelle: dos eventos seguidos multiplican de inmediato', () => {
    const camera = { pan: { x: 10, y: 20 }, zoom: 1 };
    const cursor = { x: 400, y: 300 };
    const uno = zoomAtPoint(camera, camera.zoom * factorDePellizco(-10), cursor);
    const dos = zoomAtPoint(uno, uno.zoom * factorDePellizco(-10), cursor);
    expect(dos.zoom).toBeCloseTo(factorDePellizco(-20), 6);
  });
});
