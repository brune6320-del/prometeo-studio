import type { BoardCard } from './model';
import { DEFAULT_CARD_LAYOUT_HEIGHT, type CardSize } from './geometry';
import { readFrameData } from './frames';

export type LadoAncla = 'left' | 'right' | 'top' | 'bottom';

export interface Punto {
  x: number;
  y: number;
}

export interface RectTarjeta {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function rectDeTarjeta(card: BoardCard, size?: CardSize): RectTarjeta {
  const height = size?.height
    ?? card.height
    ?? (card.type === 'marco' ? readFrameData(card).alto : DEFAULT_CARD_LAYOUT_HEIGHT);
  return { x: card.x, y: card.y, width: card.width, height };
}

export function centroDeRect(rect: RectTarjeta): Punto {
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
}

/**
 * Punto donde la recta centro→objetivo corta el borde de la tarjeta.
 * Es el «ancla» del conector: no sale del centro, sale del lado que mira al otro.
 */
export function anclaHacia(rect: RectTarjeta, hacia: Punto): { punto: Punto; lado: LadoAncla } {
  const centro = centroDeRect(rect);
  const dx = hacia.x - centro.x;
  const dy = hacia.y - centro.y;
  if (dx === 0 && dy === 0) return { punto: centro, lado: 'right' };
  const halfW = Math.max(1, rect.width / 2);
  const halfH = Math.max(1, rect.height / 2);
  const escalaX = dx === 0 ? Number.POSITIVE_INFINITY : halfW / Math.abs(dx);
  const escalaY = dy === 0 ? Number.POSITIVE_INFINITY : halfH / Math.abs(dy);
  const escala = Math.min(escalaX, escalaY);
  const punto = { x: centro.x + dx * escala, y: centro.y + dy * escala };
  if (escalaX < escalaY) return { punto, lado: dx >= 0 ? 'right' : 'left' };
  return { punto, lado: dy >= 0 ? 'bottom' : 'top' };
}

function normalDeLado(lado: LadoAncla): Punto {
  if (lado === 'left') return { x: -1, y: 0 };
  if (lado === 'right') return { x: 1, y: 0 };
  if (lado === 'top') return { x: 0, y: -1 };
  return { x: 0, y: 1 };
}

export interface GeometriaConector {
  path: string;
  desde: Punto;
  hasta: Punto;
  medio: Punto;
  control1: Punto;
  control2: Punto;
}

/**
 * Curva de Bézier que sale perpendicular al lado del ancla, como el conector de Milanote.
 * Se recalcula con las posiciones actuales, así que mover una tarjeta mueve la línea.
 */
export function geometriaConector(desde: RectTarjeta, hasta: RectTarjeta): GeometriaConector {
  const centroA = centroDeRect(desde);
  const centroB = centroDeRect(hasta);
  const a = anclaHacia(desde, centroB);
  const b = anclaHacia(hasta, centroA);
  const distancia = Math.hypot(b.punto.x - a.punto.x, b.punto.y - a.punto.y);
  const fuerza = Math.max(36, Math.min(180, distancia * 0.42));
  const normalA = normalDeLado(a.lado);
  const normalB = normalDeLado(b.lado);
  const control1 = { x: a.punto.x + normalA.x * fuerza, y: a.punto.y + normalA.y * fuerza };
  const control2 = { x: b.punto.x + normalB.x * fuerza, y: b.punto.y + normalB.y * fuerza };
  return {
    path: `M ${a.punto.x} ${a.punto.y} C ${control1.x} ${control1.y}, ${control2.x} ${control2.y}, ${b.punto.x} ${b.punto.y}`,
    desde: a.punto,
    hasta: b.punto,
    control1,
    control2,
    medio: {
      x: (a.punto.x + 3 * control1.x + 3 * control2.x + b.punto.x) / 8,
      y: (a.punto.y + 3 * control1.y + 3 * control2.y + b.punto.y) / 8,
    },
  };
}
