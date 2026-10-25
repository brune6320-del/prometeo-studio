/**
 * Física del movimiento de Prometeo · sin dependencias.
 * Ley exponencial y constantes portadas de Sala Oscura (FKU2 v3.2 §9):
 * pos += (objetivo − pos) · (1 − e^(−dt/τ)). Ver .agents/skills/prometeo-fisica.
 */

export interface Punto {
  x: number;
  y: number;
}

export interface EstadoMuelle {
  posicion: number;
  velocidad: number;
}

export interface ParametrosMuelle {
  rigidez: number;
  amortiguacion: number;
  masa: number;
}

export interface MuestraInercia {
  t: number;
  x: number;
  y: number;
}

export interface EstadoInercia {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export const MUELLES = {
  firme: { rigidez: 520, amortiguacion: 48, masa: 1 },
  suave: { rigidez: 170, amortiguacion: 27, masa: 1 },
  seco: { rigidez: 900, amortiguacion: 62, masa: 1 },
} as const satisfies Record<string, ParametrosMuelle>;

export const DURACIONES = {
  instant: 0,
  fast: 120,
  base: 180,
  slow: 280,
} as const;

export const TAU = {
  seco: 0.035,
  suave: 0.16,
  anim: 0.085,
  rubber: 0.12,
} as const;

export const IMAN = 0.0018;
export const ATAQUE = 0.04;
export const RELEASE = 0.22;
export const GIVE = 0.55;
export const FRICCION_INERCIA = 3.2;
export const PARADA_INERCIA = 0.02;

const DT_MAXIMO = 1 / 30;
const SUBPASO = 0.004;

const limitar = (valor: number, minimo: number, maximo: number) => Math.min(maximo, Math.max(minimo, valor));

export function crearEstado(posicion = 0, velocidad = 0): EstadoMuelle {
  return { posicion, velocidad };
}

/** Un paso de muelle sobreamortiguado; subdivide para no explotar con dt grandes. */
export function pasoMuelle(
  estado: EstadoMuelle,
  objetivo: number,
  dt: number,
  parametros: ParametrosMuelle = MUELLES.firme,
): EstadoMuelle {
  if (!Number.isFinite(objetivo)) return { ...estado };
  if (dt <= 0) return { ...estado };
  const total = Math.min(dt, DT_MAXIMO);
  const pasos = Math.max(1, Math.min(8, Math.ceil(total / SUBPASO)));
  const h = total / pasos;
  const { rigidez, amortiguacion } = parametros;
  const masa = Math.max(0.05, parametros.masa);
  let posicion = estado.posicion;
  let velocidad = estado.velocidad;

  for (let i = 0; i < pasos; i += 1) {
    const aceleracion = (-rigidez * (posicion - objetivo) - amortiguacion * velocidad) / masa;
    velocidad += aceleracion * h;
    posicion += velocidad * h;
  }
  if (Math.abs(objetivo - posicion) < 0.002 && Math.abs(velocidad) < 0.02) {
    return { posicion: objetivo, velocidad: 0 };
  }
  return { posicion, velocidad };
}

export class Muelle {
  private estado: EstadoMuelle;
  private objetivo: number;
  private readonly parametros: ParametrosMuelle;

  constructor(posicion = 0, parametros: ParametrosMuelle = MUELLES.firme) {
    this.estado = crearEstado(posicion);
    this.objetivo = posicion;
    this.parametros = parametros;
  }

  get posicion(): number {
    return this.estado.posicion;
  }

  get velocidad(): number {
    return this.estado.velocidad;
  }

  get destino(): number {
    return this.objetivo;
  }

  get enReposo(): boolean {
    return this.estado.posicion === this.objetivo && this.estado.velocidad === 0;
  }

  irA(objetivo: number): void {
    if (Number.isFinite(objetivo)) this.objetivo = objetivo;
  }

  /** Un gesto nuevo toma el relevo: no se espera a que termine la animación. */
  saltarA(posicion: number): void {
    this.estado = crearEstado(posicion);
    this.objetivo = posicion;
  }

  empujar(velocidad: number): void {
    this.estado = { ...this.estado, velocidad };
  }

  paso(dt: number): number {
    this.estado = pasoMuelle(this.estado, this.objetivo, dt, this.parametros);
    return this.estado.posicion;
  }
}

/** La ley de Sala Oscura: una exponencial, con imán para llegar de verdad. */
export function seguir(posicion: number, objetivo: number, dt: number, tau: number, iman = 0): number {
  if (!Number.isFinite(objetivo)) return posicion;
  if (dt <= 0) return posicion;
  if (tau <= 0) return objetivo;
  const siguiente = posicion + (objetivo - posicion) * (1 - Math.exp(-dt / tau));
  return Math.abs(objetivo - siguiente) < iman ? objetivo : siguiente;
}

/** τ según masa declarada: 0.2 → 35 ms (seco), 1.2 → 160 ms (filtra temblor). */
export function tauPorMasa(masa: number): number {
  const t = (limitar(masa, 0.2, 1.2) - 0.2) / 1;
  return TAU.seco + t * (TAU.suave - TAU.seco);
}

/** Envolvente ADSR de Sala Oscura: ataque 40 ms, release 220 ms. */
export function envolvente(actual: number, activo: boolean, dt: number): number {
  const tau = activo ? ATAQUE : RELEASE;
  return actual + ((activo ? 1 : 0) - actual) * (1 - Math.exp(-Math.max(0, dt) / tau));
}

export function velocidadDeMuestras(muestras: readonly MuestraInercia[], ventana = 100): Punto {
  if (muestras.length < 2) return { x: 0, y: 0 };
  const ultima = muestras[muestras.length - 1];
  let primera = muestras[0];
  for (let i = muestras.length - 1; i >= 0; i -= 1) {
    primera = muestras[i];
    if (ultima.t - muestras[i].t >= ventana) break;
  }
  const dt = ultima.t - primera.t;
  if (dt <= 0) return { x: 0, y: 0 };
  return { x: ((ultima.x - primera.x) / dt) * 1000, y: ((ultima.y - primera.y) / dt) * 1000 };
}

export function pasoInercia(estado: EstadoInercia, dt: number, friccion = FRICCION_INERCIA): EstadoInercia {
  if (dt <= 0) return { ...estado };
  const segundos = Math.min(dt, 0.1);
  const decaimiento = Math.exp(-friccion * segundos);
  const vx = estado.vx * decaimiento;
  const vy = estado.vy * decaimiento;
  const x = estado.x + ((estado.vx + vx) / 2) * segundos;
  const y = estado.y + ((estado.vy + vy) / 2) * segundos;
  if (Math.hypot(vx, vy) < PARADA_INERCIA * 1000) return { x, y, vx: 0, vy: 0 };
  return { x, y, vx, vy };
}

/** Banda elástica de iOS: el límite no corta, cede y devuelve (give = 0.55). */
export function rubberBand(desborde: number, dimension: number, constante = GIVE): number {
  if (desborde === 0 || dimension <= 0) return 0;
  const signo = Math.sign(desborde);
  const magnitud = Math.abs(desborde);
  return signo * (1 - 1 / ((magnitud * constante) / dimension + 1)) * dimension;
}

export function resortar(valor: number, minimo: number, maximo: number, constante = GIVE): number {
  if (valor < minimo) return minimo + rubberBand(valor - minimo, Math.max(1, maximo - minimo), constante);
  if (valor > maximo) return maximo + rubberBand(valor - maximo, Math.max(1, maximo - minimo), constante);
  return valor;
}

export function movimientoReducido(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
