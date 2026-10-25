import type { VerifierResult } from '../types';

/**
 * Convierte el resultado del verificador en filas legibles: qué comprobación
 * falló, qué se esperaba y qué se obtuvo. No inventa valores: si el motor no
 * aporta el dato, lo dice.
 */
export interface FailureRow {
  id: string;
  label: string;
  expected: string;
  actual: string;
}

function show(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function quote(value: unknown): string {
  const text = show(value, '').trim();
  return text ? `«${text}»` : '(vacío)';
}

const RASTER_FALLBACK: Record<string, { label: string; expected: string; actual: (detail: Record<string, any>) => string }> = {
  OUTSIDE_PATCH_CONTAMINATION: {
    label: 'El parche no toca píxeles fuera de su zona',
    expected: '0 píxeles',
    actual: (d) => `${show(d.metrics?.outside_patch_changed_pixel_count, '—')} píxeles`,
  },
  NO_OP_DETECTED: {
    label: 'El parche cambia la imagen',
    expected: '> 0 píxeles',
    actual: (d) => `${show(d.metrics?.changed_pixel_count, '—')} píxeles`,
  },
  BORDER_RING_INSTABILITY: {
    label: 'El borde del parche queda estable',
    expected: 'sin saltos (MAE bajo)',
    actual: (d) => `MAE ${show(d.metrics?.border_ring_mae, '—')}`,
  },
  BACKGROUND_RECONSTRUCTION_FAILED: {
    label: 'El fondo reconstruido coincide con su anillo',
    expected: 'residual bajo',
    actual: (d) => `residual ${show(d.metrics?.background_residual, '—')}`,
  },
  NEW_TEXT_NOT_CONFIRMED: {
    label: 'El texto nuevo se lee en la copia',
    expected: 'el texto nuevo',
    actual: (d) => show(d.observed_text ?? d.evidence?.observed_readback_text, '(no se leyó)'),
  },
  OLD_TEXT_STILL_PRESENT: {
    label: 'El texto anterior ya no aparece',
    expected: 'sin el texto anterior',
    actual: (d) => show(d.observed_text ?? d.evidence?.observed_readback_text, '(sin lectura)'),
  },
  OCR_CONFIDENCE_TOO_LOW: {
    label: 'Confianza suficiente de la lectura OCR',
    expected: '≥ 50 %',
    actual: (d) => `${show(d.metrics?.readback_confidence, '—')} %`,
  },
};

/** Filas de fallo, deduplicadas por comprobación. Un resultado aprobado devuelve []. */
export function verificationFailures(result: VerifierResult | null | undefined): FailureRow[] {
  if (!result) return [];
  const rows: FailureRow[] = [];
  const seen = new Set<string>();

  const push = (row: FailureRow) => {
    const key = `${row.id}|${row.label}|${row.expected}|${row.actual}`;
    if (seen.has(key)) return;
    seen.add(key);
    rows.push(row);
  };

  for (const detail of result.details ?? []) {
    if (!detail || typeof detail !== 'object') continue;

    if (Array.isArray(detail.checks)) {
      for (const check of detail.checks) {
        if (!check || check.pass !== false) continue;
        push({
          id: show(check.id, 'check'),
          label: show(check.label, 'Comprobación'),
          expected: show(check.expected),
          actual: show(check.actual),
        });
      }
      continue;
    }

    if (detail.untouched_pages && detail.untouched_pages.pass === false) {
      push({
        id: 'untouched',
        label: 'Las páginas no editadas siguen idénticas',
        expected: 'sin cambios fuera de las páginas editadas',
        actual: show(detail.untouched_pages.changed_pages ?? detail.untouched_pages.reason, 'cambiaron'),
      });
      continue;
    }

    // Resultados vectoriales anteriores a G6 (sin `checks`).
    if ('text_ok' in detail) {
      if (detail.text_ok === false) {
        push({
          id: 'text',
          label: 'El texto nuevo aparece en la copia',
          expected: quote(detail.expected_text),
          actual: quote(detail.found_text),
        });
      }
      const tolerance = show(detail.tolerance_pt, '2.5');
      if (detail.dx_ok === false) {
        push({
          id: 'dx',
          label: 'Posición horizontal dentro de la tolerancia',
          expected: `±${tolerance} pt`,
          actual: detail.dx_pt == null ? 'sin texto' : `${show(detail.dx_pt)} pt`,
        });
      }
      if (detail.dy_ok === false) {
        push({
          id: 'dy',
          label: 'Posición vertical dentro de la tolerancia',
          expected: `±${tolerance} pt`,
          actual: detail.dy_pt == null ? 'sin texto' : `${show(detail.dy_pt)} pt`,
        });
      }
      if (detail.font_ok === false) {
        push({
          id: 'font',
          label: 'La tipografía de la copia coincide',
          expected: show(detail.expected_font ?? detail.font, 'la original'),
          actual: Array.isArray(detail.found_fonts) && detail.found_fonts.length
            ? detail.found_fonts.join(', ')
            : 'sin fuentes detectadas',
        });
      }
      continue;
    }

    // Resultados raster anteriores a G6: se reconstruye desde las razones.
    const reasons: unknown[] = Array.isArray(detail.reasons) ? detail.reasons : [];
    for (const reason of reasons) {
      const meta = RASTER_FALLBACK[String(reason)];
      if (!meta) continue;
      push({
        id: String(reason),
        label: meta.label,
        expected: meta.expected,
        actual: meta.actual(detail),
      });
    }
  }

  if (rows.length === 0 && result.verdict !== 'PASS' && result.reason) {
    push({
      id: 'reason',
      label: 'Comprobación del verificador',
      expected: 'que la copia pase todas las comprobaciones',
      actual: result.reason,
    });
  }

  return rows;
}
