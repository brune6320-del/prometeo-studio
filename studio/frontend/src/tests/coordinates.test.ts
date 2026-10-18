import { describe, it, expect } from 'vitest';
import {
  pdfBBoxToViewportRect,
  viewportPointToPdfPt,
  verifyCoordinateTransformAccuracy,
  type ViewportTransformMetrics,
} from '../utils/coordinates';

describe('PROMETEO Studio · Coordinate Transform Tests (ORDEN 133 / Section 16 & 46 / Gate S12)', () => {
  it('should transform standard PDF bbox to viewport rect deterministically at 100% zoom', () => {
    const metrics: ViewportTransformMetrics = {
      scaleFactor: 1.0,
      offsetX: 0,
      offsetY: 0,
      viewportWidthPx: 612,
      viewportHeightPx: 792,
    };

    const bbox: [number, number, number, number] = [72.0, 108.0, 188.0, 123.0];
    const rect = pdfBBoxToViewportRect(bbox, metrics);

    expect(rect.left).toBe(72.0);
    expect(rect.top).toBe(108.0);
    expect(rect.width).toBe(116.0);
    expect(rect.height).toBe(15.0);
  });

  it('should transform bbox correctly under 150% zoom', () => {
    const metrics: ViewportTransformMetrics = {
      scaleFactor: 1.5,
      offsetX: 10,
      offsetY: 20,
      viewportWidthPx: 612 * 1.5,
      viewportHeightPx: 792 * 1.5,
    };

    const bbox: [number, number, number, number] = [100.0, 200.0, 300.0, 250.0];
    const rect = pdfBBoxToViewportRect(bbox, metrics);

    expect(rect.left).toBe(100.0 * 1.5 + 10);
    expect(rect.top).toBe(200.0 * 1.5 + 20);
    expect(rect.width).toBe(200.0 * 1.5);
    expect(rect.height).toBe(50.0 * 1.5);
  });

  it('should project viewport click coordinates inversely back to exact PDF points', () => {
    const metrics: ViewportTransformMetrics = {
      scaleFactor: 2.0,
      offsetX: 50,
      offsetY: 50,
      viewportWidthPx: 1224,
      viewportHeightPx: 1584,
    };

    const clientX = 250; // (250 - 50) / 2 = 100 pt
    const clientY = 450; // (450 - 50) / 2 = 200 pt

    const pt = viewportPointToPdfPt(clientX, clientY, metrics);
    expect(pt.x).toBe(100.0);
    expect(pt.y).toBe(200.0);
  });

  it('CRITICAL GATE S12 & Section 46: coordinate transform max error <= 2.0 CSS px across 50%, 100%, 150%, 200% zoom', () => {
    const benchmark = verifyCoordinateTransformAccuracy(
      [
        [72.0, 108.0, 188.0, 123.0],
        [54.0, 200.5, 450.2, 230.8],
        [10.0, 10.0, 100.0, 50.0],
        [300.0, 500.0, 550.0, 750.0],
        [0.0, 0.0, 612.0, 792.0],
      ],
      [0.5, 1.0, 1.5, 2.0]
    );

    expect(benchmark.passed).toBe(true);
    expect(benchmark.maxErrorPx).toBeLessThanOrEqual(2.0);
    // En nuestro caso analítico exacto, el error de redondeo de punto flotante es casi cero (< 0.01 px)
    expect(benchmark.maxErrorPx).toBeLessThan(0.1);
  });
});
