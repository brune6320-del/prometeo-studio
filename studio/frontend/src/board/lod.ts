/**
 * T-4 · LOD por tarjeta sin repintar el tablero.
 *
 * T-3 montaba el contenido completo por tandas de 4, pero cada tanda cambiaba
 * un `Set` en el estado de `BoardWorkspace`: React volvía a renderizar las 500
 * tarjetas y el navegador tenía que reconciliar el lienzo entero para añadir
 * cuatro cuerpos. En el zoom eso se sumaba al transform del escenario y
 * producía picos de 100–300 ms.
 *
 * Aquí el conjunto de tarjetas completas vive fuera de React. Cada
 * `BoardCardItem` se suscribe solo a su id; encender o apagar una tarjeta
 * despierta únicamente a esa tarjeta. El tablero no se renderiza.
 */

const completas = new Set<string>();
const oyentes = new Map<string, Set<() => void>>();

function avisar(id: string): void {
  const propios = oyentes.get(id);
  if (!propios) return;
  for (const oyente of propios) oyente();
}

/** ¿Esta tarjeta tiene ya su contenido completo? */
export function lodCompleta(id: string): boolean {
  return completas.has(id);
}

/** Foto de solo lectura para las marcas de rendimiento y las pruebas. */
export function lodCompletas(): ReadonlySet<string> {
  return completas;
}

/** Suscripción por tarjeta; `useSyncExternalStore` la usa con su id. */
export function suscribirLod(id: string, oyente: () => void): () => void {
  const propios = oyentes.get(id) ?? new Set<() => void>();
  propios.add(oyente);
  oyentes.set(id, propios);
  return () => {
    propios.delete(oyente);
    if (!propios.size) oyentes.delete(id);
  };
}

/**
 * Cambia el conjunto y despierta solo a las tarjetas que entran o salen.
 * Devuelve cuántas cambiaron (lo usan las marcas del soak).
 */
export function fijarLodCompletas(siguiente: Set<string>): number {
  let cambios = 0;
  for (const id of [...completas]) {
    if (siguiente.has(id)) continue;
    completas.delete(id);
    cambios += 1;
    avisar(id);
  }
  for (const id of siguiente) {
    if (completas.has(id)) continue;
    completas.add(id);
    cambios += 1;
    avisar(id);
  }
  return cambios;
}

/** Solo pruebas: deja el registro limpio entre escenarios. */
export function limpiarLod(): void {
  const ids = [...completas];
  completas.clear();
  for (const id of ids) avisar(id);
}
