/**
 * PROMETEO Studio · Coordinate Transform & Verification (ORDEN 133 / Section 16 & 46)
 * ────────────────────────────────────────────────────────────────────────────────
 * Conversión determinista bidireccional entre:
 * - Coordenadas del documento PDF (puntos tipográficos 1/72 pulgada, origen superior-izquierdo)
 * - Coordenadas del Viewport del navegador (CSS px)
 *
 * Requisito canónico: error medido <= 2.0 CSS px en 50%, 100%, 150%, 200% zoom.
 */

export interface ViewportTransformMetrics {
  scaleFactor: number; // css_px / pdf_pt
  offsetX: number;
  offsetY: number;
  viewportWidthPx: number;
  viewportHeightPx: number;
}

export interface BBoxPt {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface RectPx {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Transforma un Bounding Box de PDF (en puntos) a un rectángulo en píxeles del viewport.
 */
export function pdfBBoxToViewportRect(
  bbox: [number, number, number, number] | BBoxPt,
  metrics: ViewportTransformMetrics
): RectPx {
  const x0 = Array.isArray(bbox) ? bbox[0] : bbox.x0;
  const y0 = Array.isArray(bbox) ? bbox[1] : bbox.y0;
  const x1 = Array.isArray(bbox) ? bbox[2] : bbox.x1;
  const y1 = Array.isArray(bbox) ? bbox[3] : bbox.y1;

  const left = x0 * metrics.scaleFactor + metrics.offsetX;
  const top = y0 * metrics.scaleFactor + metrics.offsetY;
  const width = Math.max(1, (x1 - x0) * metrics.scaleFactor);
  const height = Math.max(1, (y1 - y0) * metrics.scaleFactor);

  return { left, top, width, height };
}

/**
 * Transforma una posición de click o cursor en píxeles del viewport a coordenadas PDF (puntos).
 */
export function viewportPointToPdfPt(
  clientX: number,
  clientY: number,
  metrics: ViewportTransformMetrics
): { x: number; y: number } {
  const x = (clientX - metrics.offsetX) / metrics.scaleFactor;
  const y = (clientY - metrics.offsetY) / metrics.scaleFactor;
  return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
}

/**
 * Test determinista de precisión de coordenadas según Gate S12 y Sección 46.
 * Comprueba el error de ida y vuelta para zooms estándar (50%, 100%, 150%, 200%).
 */
export function verifyCoordinateTransformAccuracy(
  testBboxes: [number, number, number, number][] = [
    [72.0, 108.0, 188.0, 123.0],
    [54.0, 200.5, 450.2, 230.8],
    [10.0, 10.0, 100.0, 50.0],
    [300.0, 500.0, 550.0, 750.0],
  ],
  zoomLevels: number[] = [0.5, 1.0, 1.5, 2.0]
): {
  passed: boolean;
  maxErrorPx: number;
  results: { zoom: number; bbox: [number, number, number, number]; errorPx: number; passed: boolean }[];
} {
  const results: { zoom: number; bbox: [number, number, number, number]; errorPx: number; passed: boolean }[] = [];
  let maxErrorPx = 0;

  for (const zoom of zoomLevels) {
    const metrics: ViewportTransformMetrics = {
      scaleFactor: zoom,
      offsetX: 0,
      offsetY: 0,
      viewportWidthPx: 612 * zoom,
      viewportHeightPx: 792 * zoom,
    };

    for (const bbox of testBboxes) {
      // 1. Proyectar a Viewport
      const rect = pdfBBoxToViewportRect(bbox, metrics);

      // 2. Proyección inversa de vértices
      const p0 = viewportPointToPdfPt(rect.left, rect.top, metrics);
      const p1 = viewportPointToPdfPt(rect.left + rect.width, rect.top + rect.height, metrics);

      // 3. Medir error en píxeles del viewport
      const errX0 = Math.abs((p0.x - bbox[0]) * metrics.scaleFactor);
      const errY0 = Math.abs((p0.y - bbox[1]) * metrics.scaleFactor);
      const errX1 = Math.abs((p1.x - bbox[2]) * metrics.scaleFactor);
      const errY1 = Math.abs((p1.y - bbox[3]) * metrics.scaleFactor);

      const maxErr = Math.max(errX0, errY0, errX1, errY1);
      if (maxErr > maxErrorPx) maxErrorPx = maxErr;

      results.push({
        zoom,
        bbox,
        errorPx: Math.round(maxErr * 1000) / 1000,
        passed: maxErr <= 2.0, // Requisito: <= 2.0 CSS px
      });
    }
  }

  return {
    passed: maxErrorPx <= 2.0,
    maxErrorPx: Math.round(maxErrorPx * 1000) / 1000,
    results,
  };
}
