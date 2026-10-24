import type { Referente } from '../referentes/model';
import type { BoardTool } from '../tools/registry';
import { clavePar, gustosVacios, pesoDe, type Gustos } from './gustos';
import {
  aplicarRegla,
  type PiezaColocada,
  type PiezaCollage,
  type TamanoLienzo,
} from './reglas';
import { generador } from './semilla';

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

/** Piezas y lienzo con los que aplicar la regla elegida. */
export interface Colocacion {
  piezas: readonly PiezaCollage[];
  tamano: TamanoLienzo;
}

/** Combinación que ya trae la disposición de la regla elegida. */
export interface CombinacionColocada extends Combinacion {
  disposicion: PiezaColocada[];
}

/** Proporción de tiradas que ignoran los gustos. */
export const PROBABILIDAD_AZAR_PURO = 0.2;

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

function esColocacion(value: Gustos | Colocacion | undefined): value is Colocacion {
  return typeof value === 'object' && value !== null && 'piezas' in value && 'tamano' in value;
}

/**
 * Combina 2-3 referentes distintos con una herramienta, una regla y una
 * restricción. Si `azarPuro` sale en el 20 %, todas las elecciones son
 * uniformes; si no, referentes (con sus pares), herramienta y regla se pesan
 * con la memoria de gusto. La restricción se elige siempre al azar.
 *
 * Si se pasa `colocacion`, el resultado incluye `disposicion`: la regla
 * elegida ya aplicada con `reglas.ts`.
 *
 * Precondición: al menos 2 referentes, 1 herramienta, 1 regla y 1 restricción.
 */
export function combinar(
  semilla: string,
  referentes: readonly ReferenteFuente[],
  herramientas: readonly HerramientaFuente[],
  reglas: readonly ReglaFuente[],
  restricciones: readonly RestriccionFuente[],
  gustos?: Gustos,
): Combinacion;
export function combinar(
  semilla: string,
  referentes: readonly ReferenteFuente[],
  herramientas: readonly HerramientaFuente[],
  reglas: readonly ReglaFuente[],
  restricciones: readonly RestriccionFuente[],
  colocacion: Colocacion,
  gustos?: Gustos,
): CombinacionColocada;
export function combinar(
  semilla: string,
  referentes: readonly ReferenteFuente[],
  herramientas: readonly HerramientaFuente[],
  reglas: readonly ReglaFuente[],
  restricciones: readonly RestriccionFuente[],
  opciones?: Gustos | Colocacion,
  gustosExtra?: Gustos,
): Combinacion | CombinacionColocada {
  let colocacion: Colocacion | undefined;
  let gustos: Gustos;
  if (esColocacion(opciones)) {
    colocacion = opciones;
    gustos = gustosExtra ?? gustosVacios();
  } else {
    gustos = opciones ?? gustosVacios();
  }
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

  const combinacion: Combinacion = {
    semilla,
    referentes: elegidos.map((referente) => referente.id),
    herramienta: herramienta.id,
    regla: regla.id,
    restriccion: restriccion.texto,
    azarPuro,
  };
  if (!colocacion) return combinacion;

  return {
    ...combinacion,
    disposicion: aplicarRegla(regla.id, colocacion.piezas, semilla, colocacion.tamano),
  };
}
