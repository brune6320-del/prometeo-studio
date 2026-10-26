/**
 * T-3 · marcas de rendimiento para cazar congelones.
 *
 * No hace nada si la página no abrió el registro (`window.__prometeoT3`). El
 * soak de Playwright lo abre antes de medir. Cada marca es un punto con
 * nombre, tiempo y detalle; las operaciones con duración se miden con
 * `marcaInicio`/`marcaFin`. El registro vive en memoria y se vuelca al final.
 */
export interface MarcaRendimiento {
  nombre: string;
  t: number;
  detalle?: string;
  /** Duración en ms cuando la marca cierra un intervalo. */
  dur?: number;
}

export interface RegistroT3 {
  activo: boolean;
  marcas: MarcaRendimiento[];
  acciones: Array<{ nombre: string; t: number }>;
}

const MAX_MARCAS = 20_000;

function registro(): RegistroT3 | null {
  if (typeof window === 'undefined') return null;
  return (window as unknown as { __prometeoT3?: RegistroT3 }).__prometeoT3 ?? null;
}

export function t3Activo(): boolean {
  return registro()?.activo === true;
}

function anotar(marca: MarcaRendimiento): void {
  const actual = registro();
  if (!actual?.activo) return;
  if (actual.marcas.length >= MAX_MARCAS) actual.marcas.splice(0, MAX_MARCAS / 2);
  actual.marcas.push(marca);
}

/** Punto instantáneo. Devuelve el tiempo para poder cerrar un intervalo después. */
export function marca(nombre: string, detalle?: string): number {
  if (!t3Activo()) return 0;
  const t = performance.now();
  anotar({ nombre, t, detalle });
  return t;
}

export function marcaFin(nombre: string, inicio: number, detalle?: string): void {
  if (!inicio) return;
  const t = performance.now();
  anotar({ nombre, t, detalle, dur: t - inicio });
}

/** Envuelve una operación síncrona y deja su duración en el registro. */
export function medir<T>(nombre: string, operacion: () => T, detalle?: () => string): T {
  const inicio = marca(`${nombre}:inicio`);
  const resultado = operacion();
  marcaFin(nombre, inicio, detalle?.());
  return resultado;
}

/** Anota una acción del guion del soak para correlacionar con los picos. */
export function accionT3(nombre: string): void {
  const actual = registro();
  if (!actual?.activo) return;
  actual.acciones.push({ nombre, t: performance.now() });
}
