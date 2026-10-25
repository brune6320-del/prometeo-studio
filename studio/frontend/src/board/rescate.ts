/** Descargas locales de rescate: nunca pasan por la red. */
import { boardFilename, makeBoardExport } from './model';
import { loadBoardWorkspace } from './storage';

export function descargarTexto(filename: string, content: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

/**
 * Cuando IndexedDB no confirma el volcado, la copia de rescate se baja desde la
 * última revisión confirmada (y, si no hay ninguna, desde lo que quedó guardado).
 * Devuelve false si no hay tableros que exportar o el navegador bloquea la descarga.
 */
export async function exportarRescateTableros(): Promise<boolean> {
  try {
    const snapshot = await loadBoardWorkspace();
    if (!snapshot.boards.length) return false;
    for (const board of snapshot.boards) {
      descargarTexto(boardFilename(board.title || 'tablero', 'json'), JSON.stringify(makeBoardExport(board), null, 2), 'application/json');
    }
    return true;
  } catch {
    return false;
  }
}
