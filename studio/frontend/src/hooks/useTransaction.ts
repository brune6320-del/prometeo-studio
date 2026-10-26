/**
 * Cambios preparados, verificación, copia guardada y página verificada para Comparar.
 * La fuente de verdad es el backend: tras cada operación se usa la lista que devuelve.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { studioApi } from '../api/client';
import { ApiError, normalizeError } from '../api/errors';
import type { DocGraphDiffResult, PageRenderData, PreflightResponse, SavedCopy, StagedOperation, VerifierResult, VerifyAndExportResponse } from '../types';

export type TxPhase = 'READY' | 'STAGED' | 'VERIFYING' | 'VERIFIED' | 'FAILED' | 'HONEST_REJECT';

export interface TransactionState {
  ops: StagedOperation[];
  phase: TxPhase;
  result: VerifierResult | null;
  lastResponse: VerifyAndExportResponse | null;
  diff: DocGraphDiffResult | null;
  saved: SavedCopy | null;
  error: ApiError | null;
  /** Verificación en segundo plano del último cambio; no publica archivo. */
  preflight: PreflightResponse | null;
  preflightBusy: boolean;
}

const EMPTY: TransactionState = { ops: [], phase: 'READY', result: null, lastResponse: null, diff: null, saved: null, error: null, preflight: null, preflightBusy: false };

function phaseFor(state: string | undefined, ops: StagedOperation[]): TxPhase {
  if (state === 'VERIFIED' || state === 'FAILED' || state === 'HONEST_REJECT') return state;
  return ops.length ? 'STAGED' : 'READY';
}

/** Receta para poder volver a preparar una operación después de deshacerla. */
type RecetaPdf =
  | { kind: 'text'; nodeId?: string; targetId?: string; newText: string }
  | { kind: 'raster'; page: number; observationId: string; newText: string };

interface PdfSnapshot {
  ops: StagedOperation[];
  recipes: Record<string, RecetaPdf | undefined>;
}

const MAX_PDF_HISTORY = 100;

function copiaOps(ops: StagedOperation[]): StagedOperation[] {
  return ops.map((op) => ({ ...op }));
}

export function useTransaction(sessionId: string | null) {
  const [tx, setTx] = useState<TransactionState>(EMPTY);
  const [busy, setBusy] = useState<'none' | 'staging' | 'verifying' | 'saving'>('none');
  const [, setHistoryVersion] = useState(0);
  const recipes = useRef(new Map<string, RecetaPdf>());
  const past = useRef<PdfSnapshot[]>([]);
  const future = useRef<PdfSnapshot[]>([]);
  const txRef = useRef<TransactionState>(EMPTY);

  useEffect(() => {
    txRef.current = tx;
  }, [tx]);

  const snapshot = useCallback((ops: StagedOperation[]): PdfSnapshot => ({
    ops: copiaOps(ops),
    recipes: Object.fromEntries(ops.map((op) => [op.op_id, recipes.current.get(op.op_id)])),
  }), []);

  const apuntar = useCallback((antes: PdfSnapshot) => {
    past.current = [...past.current, antes].slice(-MAX_PDF_HISTORY);
    future.current = [];
    setHistoryVersion((value) => value + 1);
  }, []);

  const adoptarCesta = useCallback((ops: StagedOperation[], phase: TxPhase = phaseFor(undefined, ops), extra: Partial<TransactionState> = {}) => {
    setTx((current) => ({ ...current, ops, phase, result: null, diff: null, saved: null, error: null, ...extra }));
  }, []);

  const preflightTimer = useRef<number | null>(null);
  const preflightCtrl = useRef<AbortController | null>(null);

  /** Tras cada cambio, la misma verificación física corre en segundo plano (sin publicar). */
  const programarPreflight = useCallback(() => {
    if (!sessionId) return;
    if (preflightTimer.current) window.clearTimeout(preflightTimer.current);
    preflightTimer.current = window.setTimeout(() => {
      preflightTimer.current = null;
      preflightCtrl.current?.abort();
      const ctrl = new AbortController();
      preflightCtrl.current = ctrl;
      setTx((t) => ({ ...t, preflightBusy: true }));
      studioApi
        .preflight(sessionId, ctrl.signal)
        .then((res) => {
          if (ctrl.signal.aborted) return;
          setTx((t) => ({ ...t, preflight: res, preflightBusy: false }));
        })
        .catch((err) => {
          const e = normalizeError(err, 'VERIFICATION');
          if (e.code === 'CANCELLED') return;
          setTx((t) => ({ ...t, preflightBusy: false }));
        });
    }, 420);
  }, [sessionId]);

  useEffect(() => {
    setTx(EMPTY);
    setBusy('none');
    past.current = [];
    future.current = [];
    recipes.current.clear();
    setHistoryVersion((value) => value + 1);
    if (preflightTimer.current) window.clearTimeout(preflightTimer.current);
    preflightCtrl.current?.abort();
    if (!sessionId) return;
    // La cesta vive en el motor: al cambiar de sesión (o recuperarla tras recargar) se lee de ahí.
    let cancelled = false;
    studioApi
      .getTransaction(sessionId)
      .then((tray) => {
        if (cancelled || !tray.staged_operations?.length) return;
        setTx((t) => ({ ...t, ops: tray.staged_operations, phase: phaseFor(tray.transaction_state, tray.staged_operations) }));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (preflightTimer.current) window.clearTimeout(preflightTimer.current);
      preflightCtrl.current?.abort();
    };
  }, [sessionId]);

  /** Lanza ApiError para que el formulario que lo invocó muestre el motivo. */
  const stageText = useCallback(
    async (nodeId: string, newText: string) => {
      if (!sessionId) return;
      setBusy('staging');
      if (preflightTimer.current) window.clearTimeout(preflightTimer.current);
      preflightCtrl.current?.abort();
      setTx((t) => ({ ...t, preflight: null, preflightBusy: true }));
      try {
        const antes = snapshot(txRef.current.ops);
        const op = await studioApi.stageEdit(sessionId, nodeId, newText);
        recipes.current.set(op.op_id, { kind: 'text', nodeId, newText });
        const tray = await studioApi.getTransaction(sessionId);
        apuntar(antes);
        adoptarCesta(tray.staged_operations, phaseFor(tray.transaction_state, tray.staged_operations));
        programarPreflight();
      } finally {
        setBusy('none');
      }
    },
    [adoptarCesta, apuntar, programarPreflight, sessionId, snapshot],
  );

  const stageRaster = useCallback(
    async (page: number, observationId: string, newText: string) => {
      if (!sessionId) return;
      setBusy('staging');
      if (preflightTimer.current) window.clearTimeout(preflightTimer.current);
      preflightCtrl.current?.abort();
      setTx((t) => ({ ...t, preflight: null, preflightBusy: true }));
      try {
        const antes = snapshot(txRef.current.ops);
        const op = await studioApi.stageRasterEdit(sessionId, page, observationId, newText);
        recipes.current.set(op.op_id, { kind: 'raster', page, observationId, newText });
        const tray = await studioApi.getTransaction(sessionId);
        apuntar(antes);
        adoptarCesta(tray.staged_operations, phaseFor(tray.transaction_state, tray.staged_operations));
        programarPreflight();
      } finally {
        setBusy('none');
      }
    },
    [adoptarCesta, apuntar, programarPreflight, sessionId, snapshot],
  );

  const remove = useCallback(
    async (opId: string) => {
      if (!sessionId) return;
      try {
        const antes = snapshot(txRef.current.ops);
        const tray = await studioApi.removeStagedOp(sessionId, opId);
        apuntar(antes);
        adoptarCesta(tray.staged_operations, phaseFor(tray.transaction_state, tray.staged_operations));
        if (tray.staged_operations.length) programarPreflight();
        else setTx((t) => ({ ...t, preflight: null, preflightBusy: false }));
      } catch (err) {
        setTx((t) => ({ ...t, error: normalizeError(err, 'STAGING') }));
      }
    },
    [adoptarCesta, apuntar, programarPreflight, sessionId, snapshot],
  );

  const clear = useCallback(async () => {
    if (!sessionId) return;
    try {
      const antes = snapshot(txRef.current.ops);
      await studioApi.clearTransaction(sessionId);
      apuntar(antes);
      adoptarCesta([], 'READY');
      setTx((t) => ({ ...t, preflight: null, preflightBusy: false }));
    } catch (err) {
      setTx((t) => ({ ...t, error: normalizeError(err, 'STAGING') }));
    }
  }, [adoptarCesta, apuntar, sessionId, snapshot]);

  /** Lleva la cesta del motor al estado de una instantánea: quita, re-prepara o corrige. */
  const aplicarSnapshot = useCallback(async (target: PdfSnapshot) => {
    if (!sessionId) throw new Error('No hay sesión PDF abierta.');
    const actuales = txRef.current.ops;
    for (const op of actuales) {
      if (!target.ops.some((item) => item.op_id === op.op_id)) {
        await studioApi.removeStagedOp(sessionId, op.op_id);
      }
    }
    for (const op of target.ops) {
      const actual = actuales.find((item) => item.op_id === op.op_id);
      if (actual && actual.new_text === op.new_text) continue;
      const receta = target.recipes[op.op_id] ?? recipes.current.get(op.op_id);
      if (!receta) {
        throw new Error('Ese cambio se preparó en otra sesión del motor y no se puede volver a preparar. Vuelve a seleccionar el texto.');
      }
      const nueva = receta.kind === 'text'
        ? await studioApi.stageEdit(sessionId, receta.nodeId ?? op.node_id, receta.newText)
        : await studioApi.stageRasterEdit(sessionId, receta.page, receta.observationId, receta.newText);
      recipes.current.set(nueva.op_id, receta);
      target.recipes[nueva.op_id] = receta;
    }
    return studioApi.getTransaction(sessionId);
  }, [sessionId]);

  const undo = useCallback(async () => {
    const target = past.current[past.current.length - 1];
    if (!target) return false;
    setBusy('staging');
    try {
      const actual = snapshot(txRef.current.ops);
      await aplicarSnapshot(target);
      past.current = past.current.slice(0, -1);
      future.current = [...future.current, actual].slice(-MAX_PDF_HISTORY);
      const tray = await studioApi.getTransaction(sessionId!);
      adoptarCesta(tray.staged_operations, phaseFor(tray.transaction_state, tray.staged_operations));
      if (tray.staged_operations.length) programarPreflight();
      else setTx((t) => ({ ...t, preflight: null, preflightBusy: false }));
      setHistoryVersion((value) => value + 1);
      return true;
    } catch (err) {
      setTx((t) => ({ ...t, error: normalizeError(err, 'STAGING') }));
      return false;
    } finally {
      setBusy('none');
    }
  }, [adoptarCesta, aplicarSnapshot, programarPreflight, sessionId, snapshot]);

  const redo = useCallback(async () => {
    const target = future.current[future.current.length - 1];
    if (!target) return false;
    setBusy('staging');
    try {
      const actual = snapshot(txRef.current.ops);
      await aplicarSnapshot(target);
      future.current = future.current.slice(0, -1);
      past.current = [...past.current, actual].slice(-MAX_PDF_HISTORY);
      const tray = await studioApi.getTransaction(sessionId!);
      adoptarCesta(tray.staged_operations, phaseFor(tray.transaction_state, tray.staged_operations));
      if (tray.staged_operations.length) programarPreflight();
      else setTx((t) => ({ ...t, preflight: null, preflightBusy: false }));
      setHistoryVersion((value) => value + 1);
      return true;
    } catch (err) {
      setTx((t) => ({ ...t, error: normalizeError(err, 'STAGING') }));
      return false;
    } finally {
      setBusy('none');
    }
  }, [adoptarCesta, aplicarSnapshot, programarPreflight, sessionId, snapshot]);

  const verify = useCallback(async () => {
    if (!sessionId || tx.ops.length === 0) return null;
    setBusy('verifying');
    if (preflightTimer.current) window.clearTimeout(preflightTimer.current);
    preflightCtrl.current?.abort();
    setTx((t) => ({ ...t, phase: 'VERIFYING', error: null, saved: null }));
    try {
      const res = await studioApi.verifyAndExport(sessionId);
      setTx((t) => ({
        ...t,
        phase: phaseFor(res.transaction_state, t.ops),
        result: res.verifier_result,
        lastResponse: res,
        diff: res.ok ? res.diff ?? null : null,
        error: null,
      }));
      return res;
    } catch (err) {
      const e = normalizeError(err, 'VERIFICATION');
      setTx((t) => ({ ...t, phase: phaseFor(undefined, t.ops), error: e }));
      return null;
    } finally {
      setBusy('none');
    }
  }, [sessionId, tx.ops.length]);

  const save = useCallback(async () => {
    if (!sessionId) return null;
    setBusy('saving');
    try {
      const saved = await studioApi.saveVerified(sessionId);
      setTx((t) => ({ ...t, saved, error: null }));
      return saved;
    } catch (err) {
      setTx((t) => ({ ...t, error: normalizeError(err, 'EXPORT') }));
      return null;
    } finally {
      setBusy('none');
    }
  }, [sessionId]);

  /** Modo navegador: la descarga del PDF verificado cuenta como copia guardada. */
  const markDownloaded = useCallback((filename: string) => {
    setTx((t) => ({ ...t, saved: { ok: true, path: filename, filename, folder: 'Descargas del navegador', sha256: '', original_unchanged: Boolean(t.lastResponse?.original_unchanged) } }));
  }, []);

  const reveal = useCallback(async () => {
    if (!sessionId) return;
    try {
      await studioApi.revealSaved(sessionId);
    } catch (err) {
      setTx((t) => ({ ...t, error: normalizeError(err, 'EXPORT') }));
    }
  }, [sessionId]);

  /** Vuelve a leer la cesta del backend (p. ej. tras una propuesta del asistente). */
  const refresh = useCallback(async () => {
    if (!sessionId) return;
    try {
      const tray = await studioApi.getTransaction(sessionId);
      setTx((t) => ({ ...t, ops: tray.staged_operations, phase: phaseFor(tray.transaction_state, tray.staged_operations), result: null, diff: null, saved: null }));
    } catch (err) {
      setTx((t) => ({ ...t, error: normalizeError(err, 'STAGING') }));
    }
  }, [sessionId]);

  const dismissError = useCallback(() => setTx((t) => ({ ...t, error: null })), []);

  return {
    tx,
    busy,
    stageText,
    stageRaster,
    remove,
    clear,
    verify,
    save,
    markDownloaded,
    reveal,
    refresh,
    dismissError,
    undo,
    redo,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
  };
}

/** Página de la copia verificada (Comparar). Solo existe tras un PASS vigente; se cachea por huella de la copia. */
const verifiedCache = new Map<string, PageRenderData>();

export function useVerifiedPage(sessionId: string | null, page: number, enabled: boolean, outputSha: string | null) {
  const [data, setData] = useState<PageRenderData | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    setError(null);
    if (!sessionId || !enabled || !outputSha) {
      setData(null);
      return;
    }
    const key = `${sessionId}:${outputSha}:${page}`;
    const hit = verifiedCache.get(key);
    if (hit) {
      setData(hit);
      return;
    }
    setData(null);
    const ctrl = new AbortController();
    studioApi
      .renderPage(sessionId, page, { verified: true, signal: ctrl.signal })
      .then((d) => {
        verifiedCache.set(key, d);
        if (verifiedCache.size > 24) verifiedCache.delete(verifiedCache.keys().next().value as string);
        setData(d);
      })
      .catch((err) => {
        const e = normalizeError(err, 'RENDER');
        if (e.code !== 'CANCELLED') setError(e);
      });
    return () => ctrl.abort();
  }, [sessionId, page, enabled, outputSha]);
  return { data, error };
}
