import { describe, expect, it } from 'vitest';
import { verificationFailures } from '../verification/failures';
import type { VerifierResult } from '../types';

function result(patch: Partial<VerifierResult> = {}): VerifierResult {
  return {
    verdict: 'FAILED',
    status: 'FAILED',
    verified_globally: false,
    verifier_executed: true,
    ...patch,
  };
}

describe('por qué falla la verificación', () => {
  it('lee las comprobaciones nuevas con esperado y obtenido', () => {
    const rows = verificationFailures(result({
      details: [{
        page: 0,
        checks: [
          { id: 'text', label: 'El texto nuevo aparece', expected: 'Contratado: Ana Ruiz', actual: 'Contratado: Juan Pérez', pass: false },
          { id: 'dx', label: 'Posición horizontal', expected: '±2.5 pt', actual: '3.4 pt', pass: false },
          { id: 'font', label: 'Tipografía', expected: 'Helvetica', actual: 'Helvetica', pass: true },
        ],
      }],
    }));
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ label: 'El texto nuevo aparece', expected: 'Contratado: Ana Ruiz', actual: 'Contratado: Juan Pérez' });
    expect(rows[1]).toMatchObject({ label: 'Posición horizontal', expected: '±2.5 pt', actual: '3.4 pt' });
  });

  it('entiende resultados vectoriales anteriores sin `checks`', () => {
    const rows = verificationFailures(result({
      details: [{
        expected_text: 'Ana',
        found_text: 'Juan',
        text_ok: false,
        dx_ok: false,
        dy_ok: true,
        font_ok: false,
        dx_pt: 4.2,
        tolerance_pt: 2.5,
        expected_font: 'Helvetica',
        found_fonts: ['Courier'],
      }],
    }));
    expect(rows.map((row) => row.id)).toEqual(['text', 'dx', 'font']);
    expect(rows[0].expected).toBe('«Ana»');
    expect(rows[0].actual).toBe('«Juan»');
    expect(rows[1].actual).toBe('4.2 pt');
    expect(rows[2].actual).toBe('Courier');
  });

  it('entiende resultados raster anteriores por sus razones', () => {
    const rows = verificationFailures(result({
      details: [{
        reasons: ['NEW_TEXT_NOT_CONFIRMED', 'OCR_CONFIDENCE_TOO_LOW'],
        observed_text: 'Juan Pérez',
        metrics: { readback_confidence: 31 },
      }],
    }));
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ label: 'El texto nuevo se lee en la copia', actual: 'Juan Pérez' });
    expect(rows[1]).toMatchObject({ label: 'Confianza suficiente de la lectura OCR', expected: '≥ 50 %', actual: '31 %' });
  });

  it('sin detalles usa el motivo del verificador y no inventa', () => {
    const rows = verificationFailures(result({ reason: 'La copia no superó las comprobaciones.' }));
    expect(rows).toHaveLength(1);
    expect(rows[0].actual).toBe('La copia no superó las comprobaciones.');
    expect(verificationFailures(result({ verdict: 'PASS', status: 'VERIFIED', verified_globally: true }))).toEqual([]);
  });
});
