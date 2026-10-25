import React, { useEffect, useLayoutEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';
import type { UnsavedCopy } from '../state/unsaved';
import { Spinner } from './ui';

interface UnsavedDialogProps {
  copy: UnsavedCopy;
  saving: boolean;
  error: string | null;
  onSave: () => void;
  onDiscard: () => void;
  onCancel: () => void;
  onExport?: () => void;
}

/**
 * Diálogo neutro de trabajo sin guardar: dice qué se perdería y ofrece guardar, descartar o cancelar.
 * Sin culpa ni urgencia (PROMETEO_ETHICAL_ENGAGEMENT.md, P8). El foco empieza en «Cancelar»
 * (la opción que no pierde nada) y queda atrapado dentro del diálogo; Esc cancela. Mientras está
 * abierto, ninguna tecla llega a los atajos de la app (⌘F, AvPág…). «Cancelar» sigue activo
 * durante un guardado: cierra el diálogo sin interrumpir el guardado ni ejecutar la acción.
 */
export const UnsavedDialog: React.FC<UnsavedDialogProps> = ({ copy, saving, error, onSave, onDiscard, onCancel, onExport }) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const cancelHandler = useRef(onCancel);
  useLayoutEffect(() => {
    cancelHandler.current = onCancel;
  }, [onCancel]);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      // Fase de captura en window: ninguna tecla llega a los atajos de la app.
      e.stopPropagation();
      if (e.key === 'Escape') {
        e.preventDefault();
        cancelHandler.current();
        return;
      }
      if (e.key !== 'Tab' || !dialogRef.current) return;
      const focusables = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled])'));
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => {
      window.removeEventListener('keydown', onKey, true);
      previouslyFocused?.focus?.();
    };
  }, []);

  return (
    <div className="modal-backdrop modal-center">
      <div
        className="modal modal-narrow"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="unsaved-title"
        aria-describedby="unsaved-body"
        ref={dialogRef}
        data-testid="unsaved-dialog"
      >
        <div className="unsaved-head">
          <AlertTriangle size={18} aria-hidden="true" className="ic-warn" />
          <h2 id="unsaved-title">{copy.title}</h2>
        </div>
        <p id="unsaved-body" className="unsaved-body">
          {copy.body}
        </p>
        {error && (
          <p className="unsaved-error" role="alert">
            {error}
          </p>
        )}
        <div className="unsaved-actions">
          <button className="btn btn-ghost" onClick={onCancel} ref={cancelRef}>
            Cancelar
          </button>
          {onExport && (
            <button className="btn btn-ghost" onClick={onExport} disabled={saving} data-testid="unsaved-export">
              Exportar copia de rescate
            </button>
          )}
          <button className="btn btn-danger-ghost" onClick={onDiscard} disabled={saving} data-testid="unsaved-discard">
            {copy.discardLabel}
          </button>
          {copy.canSave && (
            <button className="btn btn-primary" onClick={onSave} disabled={saving} data-testid="unsaved-save">
              {saving ? <Spinner label="Guardando" /> : null}
              {saving ? 'Guardando…' : copy.saveLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
