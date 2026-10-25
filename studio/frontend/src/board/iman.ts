/**
 * Imán del tablero: alineación suave con otras tarjetas y con la retícula.
 * Devuelve el desplazamiento que falta para alinear y la guía rosada que se pinta.
 * No toca el DOM ni el estado: se prueba en `src/tests/iman.test.ts`.
 */

export interface CajaIman {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface GuiasIman {
  x?: number;
  y?: number;
}

export interface ResultadoIman {
  dx: number;
  dy: number;
  guias: GuiasIman;
}

export interface OpcionesIman {
  /** Umbral en unidades del mundo. El llamador lo divide por el zoom para que sea constante en pantalla. */
  umbral?: number;
  /** Retícula del tablero. 0 desactiva el imán a la retícula. */
  rejilla?: number;
}

export const UMBRAL_IMAN = 7;
export const REJILLA_IMAN = 24;

function distanciaMenor(actual: number, candidatos: readonly number[]): { objetivo: number; distancia: number } {
  let objetivo = actual;
  let distancia = Number.POSITIVE_INFINITY;
  for (const candidato of candidatos) {
    const delta = candidato - actual;
    if (Math.abs(delta) < Math.abs(distancia)) {
      distancia = delta;
      objetivo = candidato;
    }
  }
  return { objetivo, distancia };
}

function candidatosDeEje(inicio: number, tamano: number): number[] {
  return [inicio, inicio + tamano / 2, inicio + tamano];
}

function candidatosRejilla(valores: readonly number[], rejilla: number): number[] {
  if (rejilla <= 0) return [];
  return valores.flatMap((valor) => {
    const base = Math.round(valor / rejilla) * rejilla;
    return [base - rejilla, base, base + rejilla];
  });
}

/**
 * Imán de una caja que se arrastra. `otras` debe excluir las cajas que se mueven
 * en el mismo gesto. Las guías se devuelven en coordenadas del mundo.
 */
export function imanDeCaja(
  caja: CajaIman,
  otras: readonly CajaIman[],
  opciones: OpcionesIman = {},
): ResultadoIman {
  const umbral = Math.max(0, opciones.umbral ?? UMBRAL_IMAN);
  const rejilla = Math.max(0, opciones.rejilla ?? 0);
  const propiasX = candidatosDeEje(caja.x, caja.width);
  const propiasY = candidatosDeEje(caja.y, caja.height);
  const ajenasX = otras.flatMap((otra) => candidatosDeEje(otra.x, otra.width));
  const ajenasY = otras.flatMap((otra) => candidatosDeEje(otra.y, otra.height));

  const objetivosX = [...ajenasX, ...candidatosRejilla(propiasX, rejilla)];
  const objetivosY = [...ajenasY, ...candidatosRejilla(propiasY, rejilla)];

  let mejorX = { dx: 0, distancia: Number.POSITIVE_INFINITY, guia: undefined as number | undefined };
  for (const propia of propiasX) {
    const { objetivo, distancia } = distanciaMenor(propia, objetivosX);
    if (Math.abs(distancia) < Math.abs(mejorX.distancia)) {
      mejorX = { dx: objetivo - propia, distancia, guia: objetivo };
    }
  }
  let mejorY = { dy: 0, distancia: Number.POSITIVE_INFINITY, guia: undefined as number | undefined };
  for (const propia of propiasY) {
    const { objetivo, distancia } = distanciaMenor(propia, objetivosY);
    if (Math.abs(distancia) < Math.abs(mejorY.distancia)) {
      mejorY = { dy: objetivo - propia, distancia, guia: objetivo };
    }
  }

  const guias: GuiasIman = {};
  const dx = Math.abs(mejorX.distancia) <= umbral ? mejorX.dx : 0;
  const dy = Math.abs(mejorY.distancia) <= umbral ? mejorY.dy : 0;
  if (dx !== 0) guias.x = mejorX.guia;
  if (dy !== 0) guias.y = mejorY.guia;
  return { dx, dy, guias };
}

/** Inclinación muy leve al coger una tarjeta: la velocidad horizontal manda. */
export function inclinacionPorVelocidad(vx: number, maximo = 1.2): number {
  if (!Number.isFinite(vx)) return 0;
  const inclinacion = Math.tanh(vx / 900) * maximo;
  return Math.round(inclinacion * 1000) / 1000;
}
