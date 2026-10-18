/**
 * Escenarios de prueba nativa (CAMP-002 · F1). Solo se activan si el host se lanzó con
 * `PROMETEO_AUTOTEST` (valores fijos, validados en Rust); en un arranque normal `scenario` es null
 * y este gancho no hace nada.
 *
 * El arnés no puede hacer clic: este gancho prepara el estado (cambio preparado y verificado,
 * sin guardar) y, según el escenario, pide el cierre de la ventana por el mismo camino que el
 * botón rojo. El arnés comprueba después si la app siguió abierta y fotografía el diálogo.
 */
import { useEffect, useRef } from 'react';
import type { NodeSummary } from '../types';

type Invoke = (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;

interface Inputs {
  scenario: string | null;
  /** Solo actúa sobre la muestra abierta automáticamente (nunca sobre documentos de la persona). */
  autoOpenSample: string | null;
  openedSample: string | null;
  docReady: boolean;
  nodesOnPage: NodeSummary[];
  restored: boolean;
  txPhase: string;
  stageText: (nodeId: string, text: string) => Promise<void>;
  verify: () => Promise<unknown>;
}

const TARGET = 'Juan Perez';
const RELOADED_MARK = 'prometeo.autotest.reloaded';

function requestCloseForTest() {
  const invoke = (window as unknown as { __TAURI_INTERNALS__?: { invoke?: Invoke } }).__TAURI_INTERNALS__?.invoke;
  return invoke ? invoke('request_close_for_test') : Promise.resolve();
}

export function useNativeAutoTest({ scenario, autoOpenSample, openedSample, docReady, nodesOnPage, restored, txPhase, stageText, verify }: Inputs) {
  const started = useRef(false);
  const staged = useRef(false);
  const verified = useRef(false);

  // Paso 2: verificar cuando la cesta ya refleja el cambio (verify() de un render anterior vería la
  // cesta vacía y no haría nada).
  useEffect(() => {
    if (!scenario || scenario === 'clean_close_window' || !staged.current || verified.current || txPhase !== 'STAGED') return;
    verified.current = true;
    (async () => {
      await verify();
      if (scenario === 'unsaved_verified_reload_close') {
        sessionStorage.setItem(RELOADED_MARK, '1');
        await new Promise((r) => setTimeout(r, 800));
        window.location.reload();
        return;
      }
      if (scenario === 'unsaved_verified_close_window') {
        await new Promise((r) => setTimeout(r, 1000));
        await requestCloseForTest();
      }
    })().catch((err) => console.error('[autotest]', err));
  }, [scenario, txPhase, verify]);
  // Escenario de recarga, segunda mitad: tras recargar, la sesión recuperada debe conservar la copia
  // verificada sin guardar; entonces se pide el cierre (el diálogo debe aparecer).
  useEffect(() => {
    if (scenario !== 'unsaved_verified_reload_close' || started.current) return;
    let reloaded = false;
    try {
      reloaded = sessionStorage.getItem(RELOADED_MARK) === '1';
    } catch {
      /* sin almacenamiento */
    }
    if (!reloaded || !restored || txPhase !== 'VERIFIED') return;
    started.current = true;
    setTimeout(() => void requestCloseForTest(), 1500);
  }, [scenario, restored, txPhase]);

  useEffect(() => {
    if (scenario === 'unsaved_verified_reload_close') {
      try {
        if (sessionStorage.getItem(RELOADED_MARK) === '1') return; // segunda mitad: arriba
      } catch {
        /* sin almacenamiento */
      }
    }
    // Defensa en profundidad: aunque la variable quedara puesta en la sesión de macOS, el gancho
    // solo toca la muestra incluida que el propio host abrió, nunca un documento real.
    if (!scenario || !autoOpenSample || openedSample !== autoOpenSample || started.current || !docReady) return;
    const node = nodesOnPage.find((n) => n.type === 'TEXT' && (n.text || '').includes(TARGET));
    if (!node) return;
    started.current = true;
    const run = async () => {
      if (scenario === 'clean_close_window') {
        await new Promise((r) => setTimeout(r, 1500));
        await requestCloseForTest();
        return;
      }
      staged.current = true;
      await stageText(node.id, (node.text || '').replace(TARGET, 'Ana Ruiz'));
      // El paso 2 (verificar y, según el escenario, recargar o cerrar) lo dispara el efecto de arriba.
    };
    run().catch((err) => console.error('[autotest]', err));
  }, [scenario, autoOpenSample, openedSample, docReady, nodesOnPage, stageText, verify]);
}
