/**
 * T-4 · atenuado de la búsqueda sin re-renderizar 500 tarjetas.
 *
 * Con la búsqueda abierta, cada tecla cambiaba el prop `dimmed` de todas las
 * tarjetas: React volvía a renderizar las 500 y, con cuerpos completos en el
 * LOD, eso medía 100–165 ms. El estado vive aquí y se aplica con `classList`;
 * una tarjeta que se vuelva a pintar por otro motivo lee el valor vigente.
 */
const atenuadas = new Set<string>();

/** Guarda los ids que no coinciden con la búsqueda. */
export function fijarAtenuadas(ids: Iterable<string>): void {
  atenuadas.clear();
  for (const id of ids) atenuadas.add(id);
}

export function estaAtenuada(id: string): boolean {
  return atenuadas.has(id);
}

export function limpiarAtenuadas(): void {
  atenuadas.clear();
}
