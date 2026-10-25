import type { RestriccionFuente } from './combinador';

/**
 * Restricciones propias, al modo de las Oblique Strategies: una frase corta que
 * obliga a torcer la tirada. No son citas de nadie; son de este proyecto.
 */
export const RESTRICCIONES: readonly RestriccionFuente[] = [
  { id: 'dos-colores', texto: 'solo dos colores' },
  { id: 'quita-bonito', texto: 'quita lo más bonito' },
  { id: 'al-reves', texto: 'una pieza al revés' },
  { id: 'sin-centro', texto: 'nada puede tocar el centro' },
  { id: 'borde', texto: 'todo empuja hacia el borde' },
  { id: 'una-sola', texto: 'deja una sola pieza intacta' },
  { id: 'silencio', texto: 'deja el aire manda' },
  { id: 'repeticion', texto: 'repite un gesto tres veces' },
  { id: 'recorte-duro', texto: 'corta sin piedad el motivo principal' },
  { id: 'casi-fuera', texto: 'algo tiene que quedar casi fuera' },
  { id: 'monocromo', texto: 'todo del mismo tono' },
  { id: 'sin-fondo', texto: 'que no se vea el fondo' },
];
