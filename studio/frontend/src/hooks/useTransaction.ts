/**
 * Cambios preparados, verificación, copia guardada y página verificada para Comparar.
 * La fuente de verdad es el backend: tras cada operación se usa la lista que devuelve.
 */
import { useCallback, useEffect, useState } from 'react';
import { studioApi } from '../api/client';
import { ApiError, normalizeError } from '../api/errors';
import type { DocGraphDiffResult, PageRenderData, SavedCopy, StagedOperation, VerifierResult, VerifyAndExportResponse } from '../types';

export type TxPhase = 'READY' | 'STAGED' | 'VERIFYING' | 'VERIFIED' | 'FAILED' | 'HONEST_REJECT';

export interface TransactionState {
  ops: StagedOperation[];
  phase: TxPhase;
  result: VerifierResult | null;
  lastResponse: VerifyAndExportResponse | null;
  diff: DocGraphDiffResult | null;
  saved: SavedCopy | null;
  error: ApiError | null;
}

const EMPTY: TransactionState = { ops: [], phase: 'READY', result: null, lastResponse: null, diff: null, saved: null, error: null };

function phaseFor(state: string | undefined, ops: StagedOperation[]): TxPhase {
  if (state === 'VERIFIED' || state === 'FAILED' || state === 'HONEST_REJECT') return state;
  return ops.length ? 'STAGED' : 'READY';
}

export function useTransaction(sessionId: string | null) {
  const [tx, setTx] = useState<TransactionState>(EMPTY);
  const [busy, setBusy] = useState<'none' | 'staging' | 'verifying' | 'saving'>('none');

  useEffect(() => {
    setTx(EMPTY);
    setBusy('none');
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
    };
  }, [sessionId]);

  /** Lanza ApiError para que el formulario que lo invocó muestre el motivo. */
  const stageText = useCallback(
    async (nodeId: string, newText: string) => {
      if (!sessionId) return;
      setBusy('staging');
      try {
        await studioApi.stageEdit(sessionId, nodeId, newText);
        const tray = await studioApi.getTransaction(sessionId);
        setTx((t) => ({ ...t, ops: tray.staged_operations, phase: phaseFor(tray.transaction_state, tray.staged_operations), result: null, diff: null, saved: null, error: null }));
      } finally {
        setBusy('none');
      }
    },
    [sessionId],
  );

  const stageRaster = useCallback(
    async (page: number, observationId: string, newText: string) => {
      if (!sessionId) return;
      setBusy('staging');
      try {
        await studioApi.stageRasterEdit(sessionId, page, observationId, newText);
        const tray = await studioApi.getTransaction(sessionId);
        setTx((t) => ({ ...t, ops: tray.staged_operations, phase: phaseFor(tray.transaction_state, tray.staged_operations), result: null, diff: null, saved: null, error: null }));
      } finally {
        setBusy('none');
      }
    },
    [sessionId],
  );

  const remove = useCallback(
    async (opId: string) => {
      if (!sessionId) return;
      try {
        const tray = await studioApi.removeStagedOp(sessionId, opId);
        setTx((t) => ({ ...t, ops: tray.staged_operations, phase: phaseFor(tray.transaction_state, tray.staged_operations), result: null, diff: null, saved: null, error: null }));
      } catch (err) {
        setTx((t) => ({ ...t, error: normalizeError(err, 'STAGING') }));
      }
    },
    [sessionId],
  );

  const clear = useCallback(async () => {
    if (!sessionId) return;
    try {
      await studioApi.clearTransaction(sessionId);
      setTx({ ...EMPTY });
    } catch (err) {
      setTx((t) => ({ ...t, error: normalizeError(err, 'STAGING') }));
    }
  }, [sessionId]);

  const verify = useCallback(async () => {
    if (!sessionId || tx.ops.length === 0) return null;
    setBusy('verifying');
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

  return { tx, busy, stageText, stageRaster, remove, clear, verify, save, markDownloaded, reveal, refresh, dismissError };
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
