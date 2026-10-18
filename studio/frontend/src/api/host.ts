/**
 * Puente con el host nativo (Tauri) para la guarda de cierre (CAMP-002 · F1).
 *
 * El host solo bloquea el cierre si la interfaz declaró trabajo sin guardar; si la interfaz
 * deja de responder, un segundo intento de cierre se permite (nunca deja la app atrapada).
 * En modo navegador (desarrollo) no hay host: estas funciones no hacen nada.
 */
import type { UnsavedWork } from '../state/unsaved';

type Invoke = (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;

function hostInvoke(): Invoke | null {
  const internals = (window as unknown as { __TAURI_INTERNALS__?: { invoke?: Invoke } }).__TAURI_INTERNALS__;
  return internals?.invoke ?? null;
}

export const hasNativeHost = () => hostInvoke() !== null;

/** Cada aviso lleva un número creciente: el host ignora los que lleguen fuera de orden. */
let reportSeq = 0;

export async function reportUnsavedWork(work: UnsavedWork | null): Promise<void> {
  const invoke = hostInvoke();
  if (!invoke) return;
  reportSeq += 1;
  try {
    await invoke('set_unsaved_work', { seq: reportSeq, dirty: work !== null, kind: work?.kind ?? '', count: work?.count ?? 0 });
  } catch {
    // Un host antiguo sin el comando no debe romper la interfaz.
  }
}

/** La interfaz confirma que mostró el diálogo (el host deja de considerar la ventana bloqueada). */
export async function acknowledgeCloseDialog(): Promise<void> {
  const invoke = hostInvoke();
  if (!invoke) return;
  try {
    await invoke('close_dialog_shown');
  } catch {
    /* sin host */
  }
}

/** Cierra la app aunque haya trabajo sin guardar (la persona lo decidió). */
export async function confirmClose(): Promise<void> {
  const invoke = hostInvoke();
  if (!invoke) return;
  await invoke('confirm_close');
}

/** Nombre global que el host invoca al interceptar un cierre. */
export const CLOSE_REQUEST_HANDLER = '__prometeoCloseRequested';
