/**
 * Guarda de trabajo sin guardar (CAMP-002 · F1).
 *
 * - Informa al host nativo de si hay trabajo que se perdería; el host bloquea el cierre solo entonces.
 * - Registra el manejador global que el host invoca al interceptar un cierre (botón rojo, ⌘Q).
 * - Protege también la apertura de otro documento (la sesión anterior se cierra y se borra).
 * - En modo navegador usa `beforeunload` (el navegador muestra su propio aviso).
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { CLOSE_REQUEST_HANDLER, acknowledgeCloseDialog, confirmClose, hasNativeHost, reportUnsavedWork } from '../api/host';
import type { TransactionState } from './useTransaction';
import { describeUnsaved, unsavedCopy, type GuardedAction, type UnsavedCopy, type UnsavedWork } from '../state/unsaved';

interface Pending {
  action: GuardedAction;
  proceed: () => void;
}

export interface UnsavedDialogState {
  copy: UnsavedCopy;
  saving: boolean;
  error: string | null;
  onSave: () => void;
  onDiscard: () => void;
  onCancel: () => void;
  /** Copia de rescate cuando el volcado falla: no se cierra y se ofrece exportar. */
  onExport?: () => void;
}

export interface UnsavedGuardOptions {
  /** Cerrar fuerza el volcado real antes de permitir cerrar (regla 19). */
  flush?: () => Promise<boolean>;
  /** Exportación de rescate si el volcado falla. */
  onExport?: () => void;
}

export function useUnsavedGuard(
  tx: TransactionState,
  saveTarget: string,
  saveCopy: () => Promise<boolean>,
  boardWork: UnsavedWork | null = null,
  options: UnsavedGuardOptions = {},
) {
  // El tablero tiene prioridad: es el trabajo que la persona puede guardar en ese momento.
  const work = useMemo(
    () => boardWork ?? describeUnsaved({ phase: tx.phase, opsCount: tx.ops.length, saved: Boolean(tx.saved) }),
    [boardWork, tx.phase, tx.ops.length, tx.saved],
  );
  const workRef = useRef(work);
  useLayoutEffect(() => {
    workRef.current = work;
  }, [work]);
  const flushRef = useRef(options.flush);
  useLayoutEffect(() => {
    flushRef.current = options.flush;
  }, [options.flush]);
  const exportRef = useRef(options.onExport);
  useLayoutEffect(() => {
    exportRef.current = options.onExport;
  }, [options.onExport]);

  const [pending, setPendingState] = useState<Pending | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  const setPending = useCallback((p: Pending | null) => {
    pendingRef.current = p;
    setPendingState(p);
  }, []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // El host conoce siempre el estado vigente.
  useEffect(() => {
    void reportUnsavedWork(work);
  }, [work]);
  // Al desmontarse NO se informa «limpio»: si la interfaz falló, el trabajo sigue en el motor y la
  // pantalla de error se encarga de avisar antes de cerrar (ErrorBoundary).

  // Modo navegador: aviso estándar del navegador al cerrar o recargar la pestaña.
  useEffect(() => {
    if (hasNativeHost() || !work) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [work]);

  // El host llama a este manejador cuando intercepta un cierre.
  useEffect(() => {
    const w = window as unknown as Record<string, unknown>;
    w[CLOSE_REQUEST_HANDLER] = () => {
      void (async () => {
        await acknowledgeCloseDialog();
        if (!workRef.current) {
          await confirmClose();
          return;
        }
        // Cerrar con trabajo del tablero: se fuerza el volcado antes de decidir.
        if (pendingRef.current) return;
        if (workRef.current.kind === 'board_unsaved' && flushRef.current) {
          const ok = await flushRef.current();
          if (ok) {
            await confirmClose();
            return;
          }
          setError('El volcado a IndexedDB falló. No se cerró nada: reintenta el guardado o exporta una copia de rescate.');
        }
        setError((current) => current ?? null);
        setPending({ action: 'close', proceed: () => void confirmClose() });
      })();
    };
    return () => {
      delete w[CLOSE_REQUEST_HANDLER];
    };
  }, [setPending]);

  /** Ejecuta `proceed` directamente si no hay nada que perder; si lo hay, pregunta antes. */
  const guard = useCallback((action: GuardedAction, proceed: () => void) => {
    if (!workRef.current) {
      proceed();
      return;
    }
    setError(null);
    setPending({ action, proceed });
  }, [setPending]);

  const onCancel = useCallback(() => setPending(null), [setPending]);
  const onDiscard = useCallback(() => {
    const p = pendingRef.current;
    setPending(null);
    p?.proceed();
  }, [setPending]);
  const onSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    const ok = await saveCopy();
    setSaving(false);
    if (!ok) {
      setError('No se pudo guardar la copia. No se cerró nada: revisa el aviso y vuelve a intentarlo.');
      return;
    }
    const p = pendingRef.current;
    setPending(null);
    p?.proceed();
  }, [saveCopy, setPending]);

  // Si mientras el diálogo está abierto deja de haber trabajo que perder (p. ej. se guardó desde
  // el panel), la persona ya obtuvo lo que pedía: se ejecuta la acción y se cierra el diálogo.
  useEffect(() => {
    if (!work && pendingRef.current && !saving) {
      const p = pendingRef.current;
      setPending(null);
      p.proceed();
    }
  }, [work, saving, setPending]);

  const dialog: UnsavedDialogState | null =
    pending && work
      ? {
        copy: unsavedCopy(work, pending.action, saveTarget),
        saving,
        error,
        onSave,
        onDiscard,
        onCancel,
        ...(exportRef.current ? { onExport: exportRef.current } : {}),
      }
      : null;

  return { work, guard, dialog };
}
