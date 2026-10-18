/**
 * Trabajo sin guardar (CAMP-002 · F1, hallazgo P8 de CLAUDE-ATTENTION-001).
 *
 * Fuente de verdad: el estado de la transacción que devuelve el motor.
 * - Una copia verificada sin guardar se pierde al cerrar la sesión (el motor borra la carpeta).
 * - Unos cambios preparados (o verificándose, o rechazados) también se pierden.
 * - Con la copia verificada ya guardada no hay nada que perder.
 * El original nunca está en riesgo: PROMETEO no lo escribe.
 */
import type { TxPhase } from '../hooks/useTransaction';

export type UnsavedKind = 'verified_unsaved' | 'staged' | 'board_unsaved';

export interface UnsavedWork {
  kind: UnsavedKind;
  /** Número de cambios que se perderían. */
  count: number;
}

export interface UnsavedInput {
  phase: TxPhase;
  opsCount: number;
  saved: boolean;
}

/** Revisiones del tablero que el almacenamiento aún no confirmó (o cuya última escritura falló). */
export function describeBoardUnsaved(pendingBoards: number): UnsavedWork | null {
  return pendingBoards > 0 ? { kind: 'board_unsaved', count: pendingBoards } : null;
}

export function describeUnsaved({ phase, opsCount, saved }: UnsavedInput): UnsavedWork | null {
  if (phase === 'VERIFIED') return saved ? null : { kind: 'verified_unsaved', count: opsCount };
  if (opsCount > 0) return { kind: 'staged', count: opsCount };
  return null;
}

export type GuardedAction = 'close' | 'open';

export interface UnsavedCopy {
  title: string;
  body: string;
  /** Solo hay copia que guardar si está verificada. */
  canSave: boolean;
  discardLabel: string;
  saveLabel: string;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function unsavedCopy(work: UnsavedWork, action: GuardedAction, saveTarget: string): UnsavedCopy {
  const leaving = action === 'close' ? 'Si cierras ahora' : 'Si abres otro documento';
  if (work.kind === 'board_unsaved') {
    return {
      title: 'El tablero aún no está guardado',
      body: `${leaving}, ${plural(work.count, 'tablero tiene cambios', 'tableros tienen cambios')} que el almacenamiento local no ha confirmado. Guárdalos ahora o cancela y espera.`,
      canSave: true,
      saveLabel: action === 'close' ? 'Guardar tablero y cerrar' : 'Guardar tablero y continuar',
      discardLabel: action === 'close' ? 'Cerrar sin guardar' : 'Descartar y abrir',
    };
  }
  if (work.kind === 'verified_unsaved') {
    return {
      title: 'La copia verificada no está guardada',
      body: `${leaving}, la copia verificada se pierde. Tu original no cambia.`,
      canSave: true,
      saveLabel: action === 'close' ? `Guardar en ${saveTarget} y cerrar` : `Guardar en ${saveTarget} y continuar`,
      discardLabel: action === 'close' ? 'Cerrar sin guardar' : 'Descartar y abrir',
    };
  }
  return {
    title: 'Tienes cambios sin verificar',
    body: `${leaving}, se pierden ${plural(work.count, 'cambio preparado', 'cambios preparados')}. Tu original no cambia. Para conservarlos, cancela, verifica y guarda la copia.`,
    canSave: false,
    saveLabel: '',
    discardLabel: action === 'close' ? 'Cerrar sin guardar' : 'Descartar y abrir',
  };
}
