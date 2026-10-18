import { describe, expect, it } from 'vitest';
import { describeUnsaved, unsavedCopy } from '../state/unsaved';

describe('trabajo sin guardar (CAMP-002 · F1)', () => {
  it('sin cambios no hay nada que perder', () => {
    expect(describeUnsaved({ phase: 'READY', opsCount: 0, saved: false })).toBeNull();
  });

  it('cambios preparados se perderían', () => {
    expect(describeUnsaved({ phase: 'STAGED', opsCount: 2, saved: false })).toEqual({ kind: 'staged', count: 2 });
  });

  it('verificando también cuenta como trabajo pendiente', () => {
    expect(describeUnsaved({ phase: 'VERIFYING', opsCount: 1, saved: false })).toEqual({ kind: 'staged', count: 1 });
  });

  it('una copia verificada sin guardar se perdería', () => {
    expect(describeUnsaved({ phase: 'VERIFIED', opsCount: 1, saved: false })).toEqual({ kind: 'verified_unsaved', count: 1 });
  });

  it('con la copia verificada guardada no hay nada que perder', () => {
    expect(describeUnsaved({ phase: 'VERIFIED', opsCount: 1, saved: true })).toBeNull();
  });

  it('un rechazo conserva los cambios preparados, que se perderían', () => {
    expect(describeUnsaved({ phase: 'HONEST_REJECT', opsCount: 1, saved: false })).toEqual({ kind: 'staged', count: 1 });
    expect(describeUnsaved({ phase: 'FAILED', opsCount: 3, saved: false })).toEqual({ kind: 'staged', count: 3 });
  });

  it('el texto para una copia verificada ofrece guardar y dice que el original no cambia', () => {
    const c = unsavedCopy({ kind: 'verified_unsaved', count: 1 }, 'close', 'Descargas');
    expect(c.canSave).toBe(true);
    expect(c.saveLabel).toBe('Guardar en Descargas y cerrar');
    expect(c.discardLabel).toBe('Cerrar sin guardar');
    expect(c.body).toContain('Tu original no cambia');
  });

  it('el texto para cambios sin verificar no ofrece guardar (no hay copia aprobada)', () => {
    const c = unsavedCopy({ kind: 'staged', count: 2 }, 'open', 'Descargas');
    expect(c.canSave).toBe(false);
    expect(c.body).toContain('2 cambios preparados');
    expect(c.discardLabel).toBe('Descartar y abrir');
  });

  it('singular correcto con un solo cambio', () => {
    expect(unsavedCopy({ kind: 'staged', count: 1 }, 'close', 'Descargas').body).toContain('1 cambio preparado.');
  });

  it('sin culpa ni urgencia (P8): no usa signos de exclamación ni «¿seguro?»', () => {
    for (const kind of ['staged', 'verified_unsaved'] as const) {
      for (const action of ['close', 'open'] as const) {
        const c = unsavedCopy({ kind, count: 1 }, action, 'Descargas');
        const text = `${c.title} ${c.body} ${c.saveLabel} ${c.discardLabel}`;
        expect(text).not.toMatch(/[!¡]|seguro/i);
      }
    }
  });
});
