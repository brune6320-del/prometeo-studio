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
}

export function useUnsavedGuard(tx: TransactionState, saveTarget: string, saveCopy: () => Promise<boolean>, boardWork: UnsavedWork | null = null) {
  // El tablero tiene prioridad: es el trabajo que la persona puede guardar en ese momento.
  const work = useMemo(
    () => boardWork ?? describeUnsaved({ phase: tx.phase, opsCount: tx.ops.length, saved: Boolean(tx.saved) }),
    [boardWork, tx.phase, tx.ops.length, tx.saved],
  );
  const workRef = useRef(work);
  useLayoutEffect(() => {
    workRef.current = work;
  }, [work]);

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
      void acknowledgeCloseDialog();
      if (!workRef.current) {
        void confirmClose();
        return;
      }
      // Si ya hay un diálogo abierto (p. ej. «abrir otro documento» o un guardado en curso),
      // no se sustituye su acción: la persona está decidiendo ahí.
      if (pendingRef.current) return;
      setError(null);
      setPending({ action: 'close', proceed: () => void confirmClose() });
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
    pending && work ? { copy: unsavedCopy(work, pending.action, saveTarget), saving, error, onSave, onDiscard, onCancel } : null;

  return { work, guard, dialog };
}
