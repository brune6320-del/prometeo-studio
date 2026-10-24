import type { Referente } from '../referentes/model';
import type { BoardTool } from '../tools/registry';
import { clavePar, gustosVacios, pesoDe, type Gustos } from './gustos';

/** Lo mínimo de un referente para combinarlo: id estable de la tarjeta y su ficha. */
export type ReferenteFuente = Pick<Referente, 'nombre' | 'etiquetas'> & { id: string };

/** Lo mínimo de una herramienta: no hace falta su Vista para combinar. */
export type HerramientaFuente = Pick<BoardTool, 'id' | 'nombre'>;

export interface ReglaFuente {
  id: string;
  nombre: string;
}

export interface RestriccionFuente {
  id: string;
  texto: string;
}

/**
 * Pieza nueva con procedencia: la semilla y los ids de las fuentes.
 * `azarPuro` dice si esta tirada salió del 20 % de entropía sin pesos.
 */
export interface Combinacion {
  semilla: string;
  referentes: string[];
  herramienta: string;
  regla: string;
  restriccion: string;
  azarPuro: boolean;
}

/** Proporción de tiradas que ignoran los gustos. */
export const PROBABILIDAD_AZAR_PURO = 0.2;

function hashSemilla(semilla: string): number {
  let hash = 2166136261;
  for (let i = 0; i < semilla.length; i += 1) {
    hash ^= semilla.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/** mulberry32: misma semilla, misma secuencia. */
function generador(semilla: string): () => number {
  let estado = hashSemilla(semilla);
  return () => {
    estado = (estado + 0x6d2b79f5) | 0;
    let t = Math.imul(estado ^ (estado >>> 15), 1 | estado);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function elegirUniforme<T>(items: readonly T[], azar: () => number): T {
  return items[Math.min(items.length - 1, Math.floor(azar() * items.length))];
}

function elegirPonderado<T>(
  items: readonly T[],
  peso: (item: T) => number,
  azar: () => number,
): T {
  let total = 0;
  for (const item of items) total += Math.max(0, peso(item));
  if (total <= 0) return elegirUniforme(items, azar);

  let objetivo = azar() * total;
  for (const item of items) {
    objetivo -= Math.max(0, peso(item));
    if (objetivo < 0) return item;
  }
  return items[items.length - 1];
}

function unicosPorId<T extends { id: string }>(items: readonly T[]): T[] {
  const vistos = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    if (!item.id || vistos.has(item.id)) continue;
    vistos.add(item.id);
    result.push(item);
  }
  return result;
}

/**
 * Combina 2-3 referentes distintos con una herramienta, una regla y una
 * restricción. Si `azarPuro` sale en el 20 %, todas las elecciones son
 * uniformes; si no, referentes (con sus pares), herramienta y regla se pesan
 * con la memoria de gusto. La restricción se elige siempre al azar.
 *
 * Precondición: al menos 2 referentes, 1 herramienta, 1 regla y 1 restricción.
 */
export function combinar(
  semilla: string,
  referentes: readonly ReferenteFuente[],
  herramientas: readonly HerramientaFuente[],
  reglas: readonly ReglaFuente[],
  restricciones: readonly RestriccionFuente[],
  gustos: Gustos = gustosVacios(),
): Combinacion {
  const refs = unicosPorId(referentes);
  const tools = unicosPorId(herramientas);
  const rules = unicosPorId(reglas);
  const limits = unicosPorId(restricciones.filter((item) => Boolean(item.texto)));

  if (refs.length < 2) throw new Error('La combinación necesita al menos 2 referentes distintos.');
  if (!tools.length) throw new Error('La combinación necesita al menos una herramienta.');
  if (!rules.length) throw new Error('La combinación necesita al menos una regla.');
  if (!limits.length) throw new Error('La combinación necesita al menos una restricción.');

  const memoria = gustos;
  const azar = generador(semilla);
  const azarPuro = azar() < PROBABILIDAD_AZAR_PURO;
  const cantidad = refs.length === 2 ? 2 : azar() < 0.5 ? 2 : 3;

  const elegidos: ReferenteFuente[] = [];
  const disponibles = [...refs];
  for (let i = 0; i < cantidad; i += 1) {
    const elegido = azarPuro
      ? elegirUniforme(disponibles, azar)
      : elegirPonderado(
        disponibles,
        (referente) => {
          let peso = pesoDe(memoria.referentes, referente.id);
          for (const previo of elegidos) {
            peso *= pesoDe(memoria.pares, clavePar(previo.id, referente.id));
          }
          return peso;
        },
        azar,
      );
    elegidos.push(elegido);
    disponibles.splice(disponibles.indexOf(elegido), 1);
  }

  const herramienta = azarPuro
    ? elegirUniforme(tools, azar)
    : elegirPonderado(tools, (tool) => pesoDe(memoria.herramientas, tool.id), azar);
  const regla = azarPuro
    ? elegirUniforme(rules, azar)
    : elegirPonderado(rules, (item) => pesoDe(memoria.reglas, item.id), azar);
  const restriccion = elegirUniforme(limits, azar);

  return {
    semilla,
    referentes: elegidos.map((referente) => referente.id),
    herramienta: herramienta.id,
    regla: regla.id,
    restriccion: restriccion.texto,
    azarPuro,
  };
}
