import type { BoardCard } from '../model';
import {
  combinar,
  type HerramientaFuente,
  type ReferenteFuente,
} from './combinador';
import { gustosVacios, type Gustos } from './gustos';
import {
  aplicarRegla,
  REGLAS,
  type PiezaColocada,
  type TamanoLienzo,
} from './reglas';
import { RESTRICCIONES } from './restricciones';

/** Un referente listo para entrar en una tirada. `imagen` puede faltar: entonces se pinta su nombre. */
export interface FuenteEntropia {
  id: string;
  nombre: string;
  etiquetas: string[];
  imagen?: { src: string; nombre: string };
}

/** Todo lo necesario para volver a pintar el collage tal cual se tiró. */
export interface EntropiaDatos {
  modo: 'entropia';
  semilla: string;
  regla: string;
  reglaNombre: string;
  restriccion: string;
  herramienta: string;
  /** Ids de los referentes en el orden en que salieron. */
  fuentes: string[];
  disposicion: PiezaColocada[];
  ancho: number;
  alto: number;
  azarPuro: boolean;
  guardado: boolean;
  creado: string;
}

export interface TirarEntropiaOpciones {
  semilla: string;
  fuentes: readonly FuenteEntropia[];
  herramientas: readonly HerramientaFuente[];
  tamano: TamanoLienzo;
  gustos?: Gustos;
  creado?: string;
}

export const NOMBRE_ENTROPIA = 'Entropía';

/** Semilla corta y legible; se guarda con la tirada para poder repetirla. */
export function nuevaSemilla(azar: () => number = Math.random): string {
  const alfabeto = '0123456789abcdef';
  let semilla = '';
  for (let i = 0; i < 10; i += 1) {
    semilla += alfabeto[Math.min(15, Math.max(0, Math.floor(azar() * 16)))];
  }
  return semilla;
}

export function reglasDeEntropia(): Array<{ id: string; nombre: string }> {
  return REGLAS.map((regla) => ({ id: regla.id, nombre: regla.nombre }));
}

export function restriccionesDeEntropia() {
  return RESTRICCIONES;
}

/**
 * Pide una combinación con los referentes y aplica la regla elegida. Es pura:
 * la misma semilla, las mismas fuentes y el mismo lienzo dan la misma tirada.
 */
export function tirarEntropia(opciones: TirarEntropiaOpciones): EntropiaDatos {
  const vistas = new Set<string>();
  const fuentes = opciones.fuentes.filter((fuente) => {
    if (!fuente.id || vistas.has(fuente.id)) return false;
    vistas.add(fuente.id);
    return true;
  });
  if (fuentes.length < 2) {
    throw new Error('Entropía necesita al menos 2 referentes del proyecto.');
  }

  const referentes: ReferenteFuente[] = fuentes.map((fuente) => ({
    id: fuente.id,
    nombre: fuente.nombre,
    etiquetas: fuente.etiquetas,
  }));
  const combinacion = combinar(
    opciones.semilla,
    referentes,
    opciones.herramientas,
    reglasDeEntropia(),
    restriccionesDeEntropia(),
    opciones.gustos ?? gustosVacios(),
  );
  const piezas = combinacion.referentes.map((id) => ({ id, aspecto: 1 }));
  const regla = REGLAS.find((item) => item.id === combinacion.regla);
  const disposicion = aplicarRegla(combinacion.regla, piezas, combinacion.semilla, opciones.tamano);

  return {
    modo: 'entropia',
    semilla: combinacion.semilla,
    regla: combinacion.regla,
    reglaNombre: regla?.nombre ?? combinacion.regla,
    restriccion: combinacion.restriccion,
    herramienta: combinacion.herramienta,
    fuentes: [...combinacion.referentes],
    disposicion,
    ancho: opciones.tamano.ancho,
    alto: opciones.tamano.alto,
    azarPuro: combinacion.azarPuro,
    guardado: false,
    creado: opciones.creado ?? new Date().toISOString(),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function numero(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function pieza(value: unknown): PiezaColocada | null {
  if (!isRecord(value) || typeof value.id !== 'string' || !value.id) return null;
  const recorte = isRecord(value.recorte)
    && typeof value.recorte.x === 'number'
    && typeof value.recorte.y === 'number'
    && typeof value.recorte.w === 'number'
    && typeof value.recorte.h === 'number'
    ? { x: value.recorte.x, y: value.recorte.y, w: value.recorte.w, h: value.recorte.h }
    : undefined;
  return {
    id: value.id,
    x: numero(value.x, 0),
    y: numero(value.y, 0),
    w: numero(value.w, 1),
    h: numero(value.h, 1),
    rot: numero(value.rot, 0),
    z: numero(value.z, 0),
    ...(recorte ? { recorte } : {}),
  };
}

/** Acepta datos viejos o parciales sin inventar una tirada que no existió. */
export function normalizarEntropia(value: unknown): EntropiaDatos | null {
  if (!isRecord(value) || value.modo !== 'entropia') return null;
  if (typeof value.semilla !== 'string' || typeof value.regla !== 'string') return null;
  if (!Array.isArray(value.disposicion) || !Array.isArray(value.fuentes)) return null;
  return {
    modo: 'entropia',
    semilla: value.semilla.slice(0, 120),
    regla: value.regla.slice(0, 60),
    reglaNombre: typeof value.reglaNombre === 'string' ? value.reglaNombre.slice(0, 80) : value.regla,
    restriccion: typeof value.restriccion === 'string' ? value.restriccion.slice(0, 200) : '',
    herramienta: typeof value.herramienta === 'string' ? value.herramienta.slice(0, 60) : '',
    fuentes: value.fuentes.filter((id): id is string => typeof id === 'string' && id.length > 0).slice(0, 12),
    disposicion: value.disposicion.map(pieza).filter((item): item is PiezaColocada => Boolean(item)),
    ancho: Math.max(1, numero(value.ancho, 600)),
    alto: Math.max(1, numero(value.alto, 400)),
    azarPuro: value.azarPuro === true,
    guardado: value.guardado === true,
    creado: typeof value.creado === 'string' ? value.creado.slice(0, 40) : '',
  };
}

export function esMarcoEntropia(card: BoardCard): boolean {
  return card.type === 'marco' && isRecord(card.datos) && card.datos.modo === 'entropia';
}

export function leerEntropia(card: BoardCard): EntropiaDatos | null {
  return esMarcoEntropia(card) ? normalizarEntropia(card.datos) : null;
}
