import type { BoardCard } from './model';

export interface TamanoMedio {
  width: number;
  height: number;
}

/** Una imagen o un vídeo se pinta como objeto libre, no como tarjeta de papel. */
export function esMediaLibre(card: BoardCard): boolean {
  return card.type === 'media' && (card.media?.kind === 'image' || card.media?.kind === 'video');
}

/**
 * Tamaño inicial de una pieza libre: cómodo de leer y sin desbordar el lienzo.
 * No reduce la fuente; solo elige el tamaño del objeto en el mundo.
 */
export function tamanoLibre(anchoNatural: number, altoNatural: number): TamanoMedio {
  const ancho = Number.isFinite(anchoNatural) && anchoNatural > 0 ? anchoNatural : 1600;
  const alto = Number.isFinite(altoNatural) && altoNatural > 0 ? altoNatural : 900;
  let width = Math.max(160, Math.min(460, ancho));
  let height = width * (alto / ancho);
  if (height > 620) {
    height = 620;
    width = height * (ancho / alto);
  }
  return { width: Math.round(width * 10) / 10, height: Math.round(height * 10) / 10 };
}

/** Lee las dimensiones reales del archivo antes de colocarlo. Si falla, asume 16:9. */
export function medirMedio(dataUrl: string, kind: 'image' | 'video'): Promise<TamanoMedio> {
  return new Promise((resolve) => {
    if (typeof document === 'undefined') {
      resolve({ width: 1600, height: 900 });
      return;
    }
    let terminado = false;
    const cerrar = (tamano: TamanoMedio) => {
      if (terminado) return;
      terminado = true;
      resolve(tamano);
    };
    const respaldo = window.setTimeout(() => cerrar({ width: 1600, height: 900 }), 4000);
    const listo = (ancho: number, alto: number) => {
      window.clearTimeout(respaldo);
      cerrar(tamanoLibre(ancho, alto));
    };
    if (kind === 'image') {
      const imagen = new Image();
      imagen.onload = () => listo(imagen.naturalWidth, imagen.naturalHeight);
      imagen.onerror = () => {
        window.clearTimeout(respaldo);
        cerrar({ width: 1600, height: 900 });
      };
      imagen.src = dataUrl;
      return;
    }
    const video = document.createElement('video');
    video.preload = 'metadata';
    video.muted = true;
    video.onloadedmetadata = () => listo(video.videoWidth, video.videoHeight);
    video.onerror = () => {
      window.clearTimeout(respaldo);
      cerrar({ width: 1600, height: 900 });
    };
    video.src = dataUrl;
  });
}
