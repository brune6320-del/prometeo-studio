import type { BoardCard } from './model';
import { rectDeTarjeta } from './conectores';

export type Direccion = 'izquierda' | 'derecha' | 'arriba' | 'abajo';

/**
 * Vecino geométrico para Alt+flecha (A-1 · D6). Se mide desde el centro de la
 * tarjeta; primero importa el eje de la flecha y solo después la desviación
 * perpendicular, para que una fila de tarjetas se recorra en línea recta.
 */
export function vecinoGeometrico(cards: readonly BoardCard[], actualId: string, direccion: Direccion): string | null {
  const actual = cards.find((card) => card.id === actualId);
  if (!actual) return null;
  const caja = rectDeTarjeta(actual);
  const centro = { x: caja.x + caja.width / 2, y: caja.y + caja.height / 2 };

  let mejor: { id: string; puntuacion: number } | null = null;
  let mejorFueraDeCono: { id: string; puntuacion: number } | null = null;
  for (const card of cards) {
    if (card.id === actualId) continue;
    const otra = rectDeTarjeta(card);
    const centroOtro = { x: otra.x + otra.width / 2, y: otra.y + otra.height / 2 };
    const dx = centroOtro.x - centro.x;
    const dy = centroOtro.y - centro.y;
    const enDireccion = direccion === 'izquierda' ? dx < -1
      : direccion === 'derecha' ? dx > 1
        : direccion === 'arriba' ? dy < -1
          : dy > 1;
    if (!enDireccion) continue;
    const avance = direccion === 'izquierda' || direccion === 'derecha' ? Math.abs(dx) : Math.abs(dy);
    const desvio = direccion === 'izquierda' || direccion === 'derecha' ? Math.abs(dy) : Math.abs(dx);
    // Cono de 42°: una tarjeta lejana pero alineada gana a una cercana muy desviada.
    const dentroDelCono = desvio <= avance * 0.9;
    const puntuacion = avance + desvio * 0.65;
    if (dentroDelCono && (!mejor || puntuacion < mejor.puntuacion)) mejor = { id: card.id, puntuacion };
    if (!mejorFueraDeCono || puntuacion < mejorFueraDeCono.puntuacion) mejorFueraDeCono = { id: card.id, puntuacion };
  }
  return (mejor ?? mejorFueraDeCono)?.id ?? null;
}
