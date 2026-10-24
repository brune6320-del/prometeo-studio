import type { BoardCard, BoardDocument } from '../model';
import { leerReferente, normalizarReferente, type Lectura, type Referente } from './model';
import { OJOS, ojosPorId, type Ojos } from './ojos';

/** De dónde salió cada referente elegido. Se muestra en el ritual, no se guarda. */
export type MotivoSeleccion = 'sin-mirar' | 'semilla' | 'tablero-abierto' | 'relleno';

export interface ReferenteElegido {
  boardId: string;
  cardId: string;
  nombre: string;
  motivo: MotivoSeleccion;
  referente: Referente;
}

export interface SeleccionMirada {
  semilla: string;
  ojos: Ojos;
  elegidos: ReferenteElegido[];
}

export function motivoSeleccion(motivo: MotivoSeleccion): string {
  switch (motivo) {
    case 'sin-mirar':
      return 'el que lleva más sin mirarse';
    case 'semilla':
      return 'al azar con semilla';
    case 'tablero-abierto':
      return 'del tablero abierto';
    default:
      return 'relleno de la biblioteca';
  }
}

/** Semilla corta, legible y nueva en cada ritual; el usuario puede repetirla. */
export function nuevaSemilla(): string {
  const bytes = new Uint8Array(4);
  if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

function hashSemilla(semilla: string): number {
  let hash = 2166136261;
  for (let i = 0; i < semilla.length; i += 1) {
    hash ^= semilla.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/** mulberry32: mismo texto de semilla, misma tirada. */
function generador(semilla: string): () => number {
  let estado = hashSemilla(semilla);
  return () => {
    estado = (estado + 0x6d2b79f5) | 0;
    let t = Math.imul(estado ^ (estado >>> 15), 1 | estado);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function elegirConSemilla<T>(items: readonly T[], azar: () => number): T | undefined {
  if (items.length === 0) return undefined;
  return items[Math.min(items.length - 1, Math.floor(azar() * items.length))];
}

/** La última fecha conocida de `vistoEn`; 0 significa que nunca se miró. */
export function ultimaVezVisto(referente: Referente): number {
  let ultima = 0;
  for (const fecha of referente.vistoEn) {
    const valor = Date.parse(fecha);
    if (Number.isFinite(valor) && valor > ultima) ultima = valor;
  }
  return ultima;
}

interface Candidato extends ReferenteElegido {
  clave: string;
}

/** Todos los referentes de todos los tableros, en un orden estable. */
export function referentesDe(boards: readonly BoardDocument[]): Candidato[] {
  const candidatos: Candidato[] = [];
  for (const board of boards) {
    for (const card of board.cards) {
      if (card.type !== 'referente') continue;
      const referente = leerReferente(card);
      candidatos.push({
        boardId: board.id,
        cardId: card.id,
        nombre: referente.nombre || card.title || 'Referente sin nombre',
        motivo: 'relleno',
        referente,
        clave: `${board.id}:${card.id}`,
      });
    }
  }
  return candidatos.sort((a, b) => a.clave.localeCompare(b.clave));
}

function masAntiguo(candidatos: readonly Candidato[]): Candidato | undefined {
  return [...candidatos].sort((a, b) => {
    const porFecha = ultimaVezVisto(a.referente) - ultimaVezVisto(b.referente);
    if (porFecha !== 0) return porFecha;
    const porNombre = a.nombre.localeCompare(b.nombre, 'es');
    return porNombre !== 0 ? porNombre : a.clave.localeCompare(b.clave);
  })[0];
}

/**
 * El ritual elige tres: el que lleva más sin mirarse, uno al azar con semilla y
 * uno del tablero abierto (si no queda, otro de la biblioteca). Nunca repite.
 */
export function seleccionarReferentes(
  boards: readonly BoardDocument[],
  tableroAbiertoId: string,
  semilla: string,
  ojosId?: string,
): SeleccionMirada {
  const azar = generador(semilla);
  const ojos = (ojosId ? ojosPorId(ojosId) : undefined) ?? elegirConSemilla(OJOS, azar) ?? OJOS[0];
  const candidatos = referentesDe(boards);
  const elegidos: ReferenteElegido[] = [];
  const usados = new Set<string>();

  const primero = masAntiguo(candidatos);
  if (!primero) return { semilla, ojos, elegidos };
  elegidos.push({ ...primero, motivo: 'sin-mirar' });
  usados.add(primero.clave);

  const restantes = () => candidatos.filter((candidato) => !usados.has(candidato.clave));

  const segundo = elegirConSemilla(restantes(), azar);
  if (segundo) {
    elegidos.push({ ...segundo, motivo: 'semilla' });
    usados.add(segundo.clave);
  }

  const delAbierto = restantes().filter((candidato) => candidato.boardId === tableroAbiertoId);
  const tercero = elegirConSemilla(delAbierto, azar) ?? elegirConSemilla(restantes(), azar);
  if (tercero) {
    elegidos.push({ ...tercero, motivo: delAbierto.length ? 'tablero-abierto' : 'relleno' });
  }

  return {
    semilla,
    ojos,
    elegidos: elegidos.map((elegido) => ({
      boardId: elegido.boardId,
      cardId: elegido.cardId,
      nombre: elegido.nombre,
      motivo: elegido.motivo,
      referente: elegido.referente,
    })),
  };
}

/** Aceptar una propuesta es el único gesto que cambia el referente. */
export function aceptarLectura(card: BoardCard, lectura: Lectura): BoardCard {
  const actual = leerReferente(card);
  const fecha = (lectura.fecha || new Date().toISOString()).slice(0, 10);
  const vistoEn = actual.vistoEn.includes(fecha) ? actual.vistoEn : [...actual.vistoEn, fecha];
  const siguiente = normalizarReferente({
    ...actual,
    vistoEn,
    lecturas: [...actual.lecturas, { ...lectura, fecha, aceptada: true }],
  });
  return {
    ...card,
    title: siguiente.nombre || card.title,
    datos: { ...siguiente },
  };
}

/** La lectura propuesta no se guarda hasta que Bruno pulsa Aceptar. */
export function lecturaPropuesta(input: {
  proyecto: string;
  ojos: string;
  texto: string;
  modelo: string;
  fecha?: string;
}): Lectura {
  return {
    fecha: (input.fecha ?? new Date().toISOString()).slice(0, 10),
    proyecto: input.proyecto,
    ojos: input.ojos,
    texto: input.texto,
    modelo: input.modelo,
    aceptada: true,
  };
}
