import type { Combinacion } from './combinador';
import { generador } from './semilla';

/**
 * Reglas de collage de la vanguardia. Son funciones puras: no tocan el DOM,
 * no leen reloj ni azar del sistema y no mutan las piezas de entrada.
 */

export type IdRegla =
  | 'dada'
  | 'bauhaus'
  | 'constructivista'
  | 'fluxus'
  | 'situacionista'
  | 'suizo'
  | 'irene';

export interface PiezaCollage {
  id: string;
  /** Relación ancho/alto de la imagen; por defecto 1. */
  aspecto?: number;
}

export interface TamanoLienzo {
  ancho: number;
  alto: number;
}

/** Ventana de recorte normalizada (0-1) dentro de la imagen original. */
export interface Recorte {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PiezaColocada {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  rot: number;
  z: number;
  recorte?: Recorte;
}

export interface ReglaCollage {
  id: IdRegla;
  nombre: string;
  disponer(
    piezas: readonly PiezaCollage[],
    semilla: string,
    tamano: TamanoLienzo,
  ): PiezaColocada[];
}

const SEPARACION_MINIMA = 0.01;
const ASPECTO_MINIMO = 0.2;
const ASPECTO_MAXIMO = 5;

function validarLienzo(tamano: TamanoLienzo): void {
  if (
    !Number.isFinite(tamano.ancho)
    || !Number.isFinite(tamano.alto)
    || tamano.ancho <= 0
    || tamano.alto <= 0
  ) {
    throw new Error('El lienzo necesita un ancho y un alto finitos y mayores que cero.');
  }
}

function unicas(piezas: readonly PiezaCollage[]): PiezaCollage[] {
  const vistos = new Set<string>();
  const result: PiezaCollage[] = [];
  for (const pieza of piezas) {
    if (!pieza.id || vistos.has(pieza.id)) continue;
    vistos.add(pieza.id);
    result.push(pieza);
  }
  return result;
}

function aspectoDe(pieza: PiezaCollage): number {
  if (typeof pieza.aspecto !== 'number' || !Number.isFinite(pieza.aspecto)) return 1;
  return Math.min(ASPECTO_MAXIMO, Math.max(ASPECTO_MINIMO, pieza.aspecto));
}

function limitar(valor: number, minimo: number, maximo: number): number {
  if (minimo > maximo) return (minimo + maximo) / 2;
  return Math.min(maximo, Math.max(minimo, valor));
}

/** Ajusta el ancho pedido al aspecto y a un alto máximo, sin deformar. */
function medidas(
  aspecto: number,
  anchoDeseado: number,
  anchoMaximo: number,
  altoMaximo: number,
): { w: number; h: number } {
  let w = Math.min(anchoMaximo, Math.max(SEPARACION_MINIMA, anchoDeseado));
  let h = w / aspecto;
  if (h > altoMaximo) {
    h = Math.max(SEPARACION_MINIMA, altoMaximo);
    w = Math.min(anchoMaximo, h * aspecto);
  }
  return { w, h };
}

function acotar(pieza: PiezaColocada, tamano: TamanoLienzo): PiezaColocada {
  const maxX = Math.max(0, tamano.ancho - pieza.w);
  const maxY = Math.max(0, tamano.alto - pieza.h);
  return {
    ...pieza,
    x: limitar(pieza.x, 0, maxX),
    y: limitar(pieza.y, 0, maxY),
  };
}

/** Recorte centrado que lleva el aspecto de la fuente al del hueco. */
function recorteParaAspecto(fuente: number, objetivo: number): Recorte | undefined {
  if (!Number.isFinite(objetivo) || objetivo <= 0) return undefined;
  if (Math.abs(fuente - objetivo) / objetivo < 0.02) return undefined;
  if (fuente > objetivo) {
    const w = objetivo / fuente;
    return { x: (1 - w) / 2, y: 0, w, h: 1 };
  }
  const h = fuente / objetivo;
  return { x: 0, y: (1 - h) / 2, w: 1, h };
}

function barajarZ(piezas: PiezaColocada[], azar: () => number): PiezaColocada[] {
  const orden = piezas.map((_, index) => index);
  for (let i = orden.length - 1; i > 0; i -= 1) {
    const j = Math.floor(azar() * (i + 1));
    [orden[i], orden[j]] = [orden[j], orden[i]];
  }
  return piezas.map((pieza, index) => ({ ...pieza, z: orden[index] }));
}

/** Dadá: recortes rotados, superpuestos y sin retícula. Puede salirse un 10 %. */
export function dada(
  piezas: readonly PiezaCollage[],
  semilla: string,
  tamano: TamanoLienzo,
): PiezaColocada[] {
  validarLienzo(tamano);
  const lista = unicas(piezas);
  const azar = generador(`dada:${semilla}`);
  const base = Math.min(tamano.ancho, tamano.alto);

  const colocadas = lista.map((pieza) => {
    const aspecto = aspectoDe(pieza);
    const { w: anchoInicial, h: altoInicial } = medidas(
      aspecto,
      base * (0.3 + azar() * 0.28),
      tamano.ancho * 0.68,
      tamano.alto * 0.74,
    );
    const rot = -22 + azar() * 44;
    const rad = Math.abs((rot * Math.PI) / 180);
    let w = anchoInicial;
    let h = altoInicial;
    let anchoRotado = Math.abs(w * Math.cos(rad)) + Math.abs(h * Math.sin(rad));
    let altoRotado = Math.abs(w * Math.sin(rad)) + Math.abs(h * Math.cos(rad));

    const escala = Math.min(
      1,
      (tamano.ancho * 1.15) / anchoRotado,
      (tamano.alto * 1.15) / altoRotado,
    );
    if (escala < 1) {
      w *= escala;
      h *= escala;
      anchoRotado *= escala;
      altoRotado *= escala;
    }

    const centroX = limitar(
      tamano.ancho * (0.25 + azar() * 0.5),
      -tamano.ancho * 0.1 + anchoRotado / 2,
      tamano.ancho * 1.1 - anchoRotado / 2,
    );
    const centroY = limitar(
      tamano.alto * (0.25 + azar() * 0.5),
      -tamano.alto * 0.1 + altoRotado / 2,
      tamano.alto * 1.1 - altoRotado / 2,
    );

    const anchoRecorte = 0.6 + azar() * 0.35;
    const altoRecorte = 0.6 + azar() * 0.35;
    const recorte: Recorte = {
      x: azar() * (1 - anchoRecorte),
      y: azar() * (1 - altoRecorte),
      w: anchoRecorte,
      h: altoRecorte,
    };

    return {
      id: pieza.id,
      x: centroX - w / 2,
      y: centroY - h / 2,
      w,
      h,
      rot,
      z: 0,
      recorte,
    };
  });

  return barajarZ(colocadas, azar);
}

function repartirFilas(cantidad: number): number[] {
  const filas = Math.max(1, Math.ceil(cantidad / 3));
  const base = Math.floor(cantidad / filas);
  const extra = cantidad % filas;
  return Array.from({ length: filas }, (_, index) => base + (index < extra ? 1 : 0));
}

function columnasDe(cantidad: number, azar: () => number): number[] {
  if (cantidad <= 1) return [12];
  if (cantidad === 2) {
    const opciones = [[6, 6], [7, 5], [5, 7]];
    return opciones[Math.floor(azar() * opciones.length)];
  }
  const opciones = [[4, 4, 4], [6, 3, 3], [3, 6, 3], [3, 3, 6]];
  return opciones[Math.floor(azar() * opciones.length)];
}

/** Bauhaus: retícula de 12 columnas, bloques limpios y sin rotación. */
export function bauhaus(
  piezas: readonly PiezaCollage[],
  semilla: string,
  tamano: TamanoLienzo,
): PiezaColocada[] {
  validarLienzo(tamano);
  const lista = unicas(piezas);
  if (!lista.length) return [];

  const azar = generador(`bauhaus:${semilla}`);
  const unidad = tamano.ancho / 12;
  const filas = repartirFilas(lista.length);
  const filasDisponibles = Math.max(1, Math.floor(tamano.alto / unidad));
  const altoFila = Math.max(1, Math.floor(filasDisponibles / filas.length));
  const altoTotal = filas.length * altoFila * unidad;
  const escalaVertical = altoTotal > tamano.alto ? tamano.alto / altoTotal : 1;

  const colocadas: PiezaColocada[] = [];
  let indice = 0;
  let y = 0;

  for (const cantidad of filas) {
    const columnas = columnasDe(cantidad, azar);
    let x = 0;
    for (const columnasPieza of columnas) {
      const pieza = lista[indice];
      const w = Math.min(columnasPieza * unidad, tamano.ancho - x);
      let h = altoFila * unidad * escalaVertical;
      if (y + h > tamano.alto) h = Math.max(SEPARACION_MINIMA, tamano.alto - y);
      const recorte = recorteParaAspecto(aspectoDe(pieza), w / h);
      colocadas.push({
        id: pieza.id,
        x,
        y,
        w,
        h,
        rot: 0,
        z: indice,
        ...(recorte ? { recorte } : {}),
      });
      x += columnasPieza * unidad;
      indice += 1;
    }
    y += altoFila * unidad * escalaVertical;
  }

  return colocadas;
}

/** Constructivista: bloques en tensión sobre una diagonal de 30°. */
export function constructivista(
  piezas: readonly PiezaCollage[],
  semilla: string,
  tamano: TamanoLienzo,
): PiezaColocada[] {
  validarLienzo(tamano);
  const lista = unicas(piezas);
  const azar = generador(`constructivista:${semilla}`);
  const pendiente = Math.tan(Math.PI / 6);
  const paso = lista.length > 1 ? (tamano.ancho * 0.56) / (lista.length - 1) : 0;
  const inicio = lista.length > 1 ? tamano.ancho * 0.18 : tamano.ancho * 0.34;

  return lista.map((pieza, indice) => {
    const { w, h } = medidas(
      aspectoDe(pieza),
      Math.min(tamano.ancho, tamano.alto) * (0.26 + azar() * 0.12),
      tamano.ancho * 0.42,
      tamano.alto * 0.46,
    );
    const centroX = inicio + indice * paso + (azar() - 0.5) * tamano.ancho * 0.04;
    const centroY = tamano.alto * 0.5 - (centroX - tamano.ancho / 2) * pendiente
      + (azar() - 0.5) * tamano.alto * 0.04;
    return acotar({
      id: pieza.id,
      x: centroX - w / 2,
      y: centroY - h / 2,
      w,
      h,
      rot: 0,
      z: indice,
    }, tamano);
  });
}

/** Fluxus: partitura en el tiempo; cada pieza ocupa un pulso de izquierda a derecha. */
export function fluxus(
  piezas: readonly PiezaCollage[],
  semilla: string,
  tamano: TamanoLienzo,
): PiezaColocada[] {
  validarLienzo(tamano);
  const lista = unicas(piezas);
  if (!lista.length) return [];

  const azar = generador(`fluxus:${semilla}`);
  const margen = Math.min(tamano.ancho, tamano.alto) * 0.08;
  const pulso = (tamano.ancho - margen * 2) / lista.length;

  return lista.map((pieza, indice) => {
    const { w, h } = medidas(
      aspectoDe(pieza),
      pulso * 0.72,
      tamano.ancho * 0.22,
      tamano.alto * 0.28,
    );
    const centroX = margen + pulso * (indice + 0.5);
    const centroY = tamano.alto * 0.5
      + (indice % 2 === 0 ? -1 : 1) * tamano.alto * 0.07
      + (azar() - 0.5) * tamano.alto * 0.03;
    return acotar({
      id: pieza.id,
      x: centroX - w / 2,
      y: centroY - h / 2,
      w,
      h,
      rot: 0,
      z: indice,
    }, tamano);
  });
}

/** Situacionista: deriva; cada pieza cae en un punto de un recorrido aleatorio. */
export function situacionista(
  piezas: readonly PiezaCollage[],
  semilla: string,
  tamano: TamanoLienzo,
): PiezaColocada[] {
  validarLienzo(tamano);
  const lista = unicas(piezas);
  const azar = generador(`situacionista:${semilla}`);
  let centroX = tamano.ancho * 0.22;
  let centroY = tamano.alto * 0.32;

  return lista.map((pieza, indice) => {
    const { w, h } = medidas(
      aspectoDe(pieza),
      Math.min(tamano.ancho, tamano.alto) * (0.18 + azar() * 0.08),
      tamano.ancho * 0.3,
      tamano.alto * 0.3,
    );
    if (indice > 0) {
      const angulo = azar() * Math.PI * 2;
      const paso = Math.min(tamano.ancho, tamano.alto) * (0.14 + azar() * 0.16);
      centroX += Math.cos(angulo) * paso;
      centroY += Math.sin(angulo) * paso;
    }
    centroX = limitar(centroX, w / 2, tamano.ancho - w / 2);
    centroY = limitar(centroY, h / 2, tamano.alto - h / 2);
    return {
      id: pieza.id,
      x: centroX - w / 2,
      y: centroY - h / 2,
      w,
      h,
      rot: 0,
      z: indice,
    };
  });
}

/** Suizo: rejilla estricta, una sola alineación y mucho aire. */
export function suizo(
  piezas: readonly PiezaCollage[],
  semilla: string,
  tamano: TamanoLienzo,
): PiezaColocada[] {
  validarLienzo(tamano);
  const lista = unicas(piezas);
  if (!lista.length) return [];

  const azar = generador(`suizo:${semilla}`);
  const margen = Math.min(tamano.ancho, tamano.alto) * 0.12;
  const unidad = (tamano.ancho - margen * 2) / 12;
  const hueco = tamano.alto * 0.05;
  const altoDisponible = Math.max(1, tamano.alto - margen * 2 - hueco * (lista.length - 1));
  const anchos = [4, 5, 6, 7];

  const deseadas = lista.map((pieza) => {
    const w = unidad * anchos[Math.floor(azar() * anchos.length)];
    return { w, h: w / aspectoDe(pieza) };
  });
  const suma = deseadas.reduce((total, medida) => total + medida.h, 0);
  const escala = suma > altoDisponible ? altoDisponible / suma : 1;

  let y = margen;
  return lista.map((pieza, indice) => {
    const { w } = deseadas[indice];
    const h = Math.max(SEPARACION_MINIMA, deseadas[indice].h * escala);
    const recorte = recorteParaAspecto(aspectoDe(pieza), w / h);
    const colocada: PiezaColocada = {
      id: pieza.id,
      x: margen,
      y,
      w,
      h,
      rot: 0,
      z: indice,
      ...(recorte ? { recorte } : {}),
    };
    y += h + hueco;
    return acotar(colocada, tamano);
  });
}

/** Irene: archivador grande y una pieza pequeña al borde, como en la mesa de archivo. */
export function irene(
  piezas: readonly PiezaCollage[],
  semilla: string,
  tamano: TamanoLienzo,
): PiezaColocada[] {
  validarLienzo(tamano);
  const lista = unicas(piezas);
  if (!lista.length) return [];

  const azar = generador(`irene:${semilla}`);
  const primera = lista[0];
  const principal = medidas(
    aspectoDe(primera),
    Math.min(tamano.ancho, tamano.alto) * 0.62,
    tamano.ancho * 0.62,
    tamano.alto * 0.72,
  );
  const colocadas: PiezaColocada[] = [acotar({
    id: primera.id,
    x: tamano.ancho * 0.08,
    y: tamano.alto * 0.12,
    w: principal.w,
    h: principal.h,
    rot: 0,
    z: 0,
  }, tamano)];

  const resto = lista.slice(1);
  resto.forEach((pieza, indice) => {
    const mono = indice === resto.length - 1;
    const base = Math.min(tamano.ancho, tamano.alto) * (mono ? 0.09 : 0.14);
    const { w, h } = medidas(
      aspectoDe(pieza),
      base,
      tamano.ancho * 0.18,
      tamano.alto * 0.2,
    );
    const columna = indice % 2;
    const fila = Math.floor(indice / 2);
    const x = tamano.ancho * 0.7 + columna * tamano.ancho * 0.14
      + (azar() - 0.5) * tamano.ancho * 0.02;
    const y = tamano.alto * 0.16 + fila * tamano.alto * 0.17
      + (azar() - 0.5) * tamano.alto * 0.02;
    colocadas.push(acotar({
      id: pieza.id,
      x,
      y,
      w,
      h,
      rot: 0,
      z: indice + 1,
    }, tamano));
  });

  return colocadas;
}

export const REGLAS: readonly ReglaCollage[] = [
  { id: 'dada', nombre: 'Dadá', disponer: dada },
  { id: 'bauhaus', nombre: 'Bauhaus', disponer: bauhaus },
  { id: 'constructivista', nombre: 'Constructivista', disponer: constructivista },
  { id: 'fluxus', nombre: 'Fluxus', disponer: fluxus },
  { id: 'situacionista', nombre: 'Situacionista', disponer: situacionista },
  { id: 'suizo', nombre: 'Suizo', disponer: suizo },
  { id: 'irene', nombre: 'Irene', disponer: irene },
];

const POR_ID = new Map<string, ReglaCollage>(REGLAS.map((regla) => [regla.id, regla]));

export function reglaDe(id: string): ReglaCollage | undefined {
  return POR_ID.get(id);
}

/** Aplica una de las 7 reglas por su id. Lanza si el id no existe. */
export function aplicarRegla(
  id: string,
  piezas: readonly PiezaCollage[],
  semilla: string,
  tamano: TamanoLienzo,
): PiezaColocada[] {
  const regla = reglaDe(id);
  if (!regla) throw new Error(`Regla de collage desconocida: «${id}».`);
  return regla.disponer(piezas, semilla, tamano);
}

/** Atajo para aplicar la regla que devolvió `combinar()`. */
export function aplicarCombinacion(
  combinacion: Pick<Combinacion, 'regla' | 'semilla'>,
  piezas: readonly PiezaCollage[],
  tamano: TamanoLienzo,
): PiezaColocada[] {
  return aplicarRegla(combinacion.regla, piezas, combinacion.semilla, tamano);
}
