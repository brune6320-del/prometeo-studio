import type { BoardCard } from './model';
import { DEFAULT_CARD_LAYOUT_HEIGHT } from './geometry';

export interface Point {
  x: number;
  y: number;
}

export interface BoardCamera {
  pan: Point;
  zoom: number;
}

export interface ViewportSize {
  width: number;
  height: number;
}

export const MIN_BOARD_ZOOM = 0.25;
export const MAX_BOARD_ZOOM = 2.4;
/** «Ajustar» debe poder alejar más que el zoom de navegación para incluir todo el contenido. */
export const FIT_MIN_ZOOM = 0.02;

export function screenToWorld(point: Point, camera: BoardCamera): Point {
  return {
    x: (point.x - camera.pan.x) / camera.zoom,
    y: (point.y - camera.pan.y) / camera.zoom,
  };
}

export function worldToScreen(point: Point, camera: BoardCamera): Point {
  return {
    x: camera.pan.x + point.x * camera.zoom,
    y: camera.pan.y + point.y * camera.zoom,
  };
}

export function zoomAtPoint(camera: BoardCamera, nextZoom: number, focalPoint: Point): BoardCamera {
  const boundedZoom = Math.max(MIN_BOARD_ZOOM, Math.min(MAX_BOARD_ZOOM, nextZoom));
  const worldPoint = screenToWorld(focalPoint, camera);
  return {
    zoom: boundedZoom,
    pan: {
      x: focalPoint.x - worldPoint.x * boundedZoom,
      y: focalPoint.y - worldPoint.y * boundedZoom,
    },
  };
}

export interface CardBox {
  width: number;
  height: number;
}

/**
 * Encuadra todas las tarjetas. `sizes` aporta la altura real medida en el mundo;
 * sin ella se usa la altura de maquetación por defecto.
 */
export function fitBoardCamera(cards: BoardCard[], viewport: ViewportSize, sizes?: ReadonlyMap<string, CardBox>): BoardCamera {
  if (!viewport.width || !viewport.height) return { pan: { x: 0, y: 0 }, zoom: 1 };
  if (!cards.length) {
    return { pan: { x: viewport.width / 2, y: viewport.height / 2 }, zoom: 1 };
  }

  const boxes = cards.map((card) => {
    const measured = sizes?.get(card.id);
    return {
      x: card.x,
      y: card.y,
      width: measured?.width ?? card.width,
      height: measured?.height ?? DEFAULT_CARD_LAYOUT_HEIGHT,
    };
  });
  const minX = Math.min(...boxes.map((box) => box.x));
  const minY = Math.min(...boxes.map((box) => box.y));
  const maxX = Math.max(...boxes.map((box) => box.x + box.width));
  const maxY = Math.max(...boxes.map((box) => box.y + box.height));
  const contentWidth = Math.max(1, maxX - minX);
  const contentHeight = Math.max(1, maxY - minY);
  const zoom = Math.max(
    FIT_MIN_ZOOM,
    Math.min(1.35, (viewport.width - 100) / contentWidth, (viewport.height - 120) / contentHeight),
  );

  return {
    zoom,
    pan: {
      x: viewport.width / 2 - ((minX + maxX) / 2) * zoom,
      y: viewport.height / 2 - ((minY + maxY) / 2) * zoom,
    },
  };
}
