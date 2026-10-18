/**
 * Documento abierto: muestras, sesión, nodos, página actual, render y capa OCR.
 *
 * Reglas:
 * - Cada apertura cancela la anterior; una respuesta antigua nunca pisa a la nueva.
 * - Cargando, error y vacío son estados distintos (el visor nunca se queda "cargando" tras un fallo).
 * - El OCR solo se pide en documentos escaneados o si la persona activa la capa OCR.
 * - Las páginas renderizadas se guardan en una caché pequeña por sesión.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { studioApi } from '../api/client';
import { ApiError, isCancellation, normalizeError } from '../api/errors';
import type { DocumentSummary, NodeSummary, OCRLayerData, PageRenderData, SampleItem } from '../types';

export type LoadPhase = 'EMPTY' | 'DOCUMENT_LOADING' | 'READY' | 'LOAD_ERROR';

export interface OpenDocument {
  sessionId: string;
  filename: string;
  summary: DocumentSummary;
  source: { kind: 'sample'; key: string } | { kind: 'file'; name: string };
  isRaster: boolean;
}

export interface AsyncSlot<T> {
  status: 'idle' | 'loading' | 'ready' | 'error';
  data: T | null;
  error: ApiError | null;
}

const idle = <T,>(): AsyncSlot<T> => ({ status: 'idle', data: null, error: null });
const RENDER_CACHE_MAX = 16;

/**
 * Sesión abierta recordada en sessionStorage (solo el identificador y el nombre; nunca el token).
 * Si la interfaz se recarga (error, menú, reconexión) y el motor conserva la sesión, se recupera
 * con sus cambios en lugar de perderlos de vista (CAMP-002 · F1, revisión crítica).
 */
const STORAGE_KEY = 'prometeo.openSession';
interface RememberedSession {
  sessionId: string;
  filename: string;
  source: OpenDocument['source'];
}
function remember(s: RememberedSession | null) {
  try {
    if (s) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* almacenamiento no disponible: sin recuperación tras recargar */
  }
}
function recall(): RememberedSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const v = raw ? (JSON.parse(raw) as RememberedSession) : null;
    return v && typeof v.sessionId === 'string' && /^studio_sess_[0-9a-f]+$/.test(v.sessionId) ? v : null;
  } catch {
    return null;
  }
}

export function isRasterSummary(summary: DocumentSummary | null): boolean {
  const c = summary?.capabilities;
  return Boolean(c && (c.is_raster || c.is_raster_dominant || !c.is_born_digital));
}

export function useDocumentSession(backendReady: boolean) {
  const [samples, setSamples] = useState<SampleItem[]>([]);
  const [samplesError, setSamplesError] = useState<ApiError | null>(null);
  const [samplesAttempt, setSamplesAttempt] = useState(0);
  const [phase, setPhase] = useState<LoadPhase>('EMPTY');
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loadingLabel, setLoadingLabel] = useState<string>('');
  const [doc, setDoc] = useState<OpenDocument | null>(null);
  // Nodos por página, cargados bajo demanda (un documento de 73 págs tiene ~36 000 nodos).
  const [pageNodes, setPageNodes] = useState<Record<number, NodeSummary[]>>({});
  const [pageNodesLoading, setPageNodesLoading] = useState(false);
  const [currentPage, setCurrentPageRaw] = useState(0);
  const [render, setRender] = useState<AsyncSlot<PageRenderData>>(idle);
  const [ocr, setOcr] = useState<AsyncSlot<OCRLayerData>>(idle);
  const [ocrVisible, setOcrVisible] = useState(false);
  const [renderAttempt, setRenderAttempt] = useState(0);
  const [ocrAttempt, setOcrAttempt] = useState(0);
  /** La sesión actual se recuperó tras recargar la interfaz. */
  const [restored, setRestored] = useState(false);
  /** Hay un intento de recuperación en curso (la apertura automática de pruebas espera). */
  const [restoring, setRestoring] = useState(() => recall() !== null);

  const openCtrl = useRef<AbortController | null>(null);
  const renderCache = useRef(new Map<string, PageRenderData>());
  const lastRequest = useRef<(() => void) | null>(null);

  // Muestras disponibles en esta instalación.
  useEffect(() => {
    if (!backendReady) return;
    const ctrl = new AbortController();
    studioApi
      .listSamples(ctrl.signal)
      .then((r) => {
        setSamples(r.samples);
        setSamplesError(null);
      })
      .catch((err) => {
        if (!isCancellation(normalizeError(err))) setSamplesError(normalizeError(err, 'DOCUMENT_LOAD'));
      });
    return () => ctrl.abort();
  }, [backendReady, samplesAttempt]);

  const pageCount = doc?.summary.pages_count || (doc?.summary as any)?.page_count || 0;

  const setCurrentPage = useCallback(
    (p: number) => setCurrentPageRaw((prev) => (pageCount ? Math.max(0, Math.min(pageCount - 1, p)) : prev)),
    [pageCount],
  );

  const load = useCallback(
    async (label: string, source: OpenDocument['source'], fetcher: (signal: AbortSignal) => Promise<{ session_id: string; filename: string; summary: DocumentSummary }>) => {
      openCtrl.current?.abort();
      const ctrl = new AbortController();
      openCtrl.current = ctrl;
      const previous = doc?.sessionId;
      setPhase('DOCUMENT_LOADING');
      setLoadingLabel(label);
      setLoadError(null);
      try {
        const res = await fetcher(ctrl.signal);
        const firstPage = await studioApi.queryNodes(res.session_id, 0, ctrl.signal);
        if (ctrl.signal.aborted) return;
        renderCache.current.clear();
        const isRaster = isRasterSummary(res.summary);
        const filename = res.filename || res.summary.filename || label;
        setDoc({ sessionId: res.session_id, filename, summary: res.summary, source, isRaster });
        remember({ sessionId: res.session_id, filename, source });
        setRestored(false);
        setPageNodes({ 0: firstPage });
        setCurrentPageRaw(0);
        setOcrVisible(isRaster);
        setRender(idle());
        setOcr(idle());
        setPhase('READY');
        if (previous) studioApi.closeSession(previous).catch(() => undefined);
      } catch (err) {
        const e = normalizeError(err, 'DOCUMENT_LOAD');
        if (isCancellation(e)) return;
        setLoadError(e);
        setPhase(doc ? 'READY' : 'LOAD_ERROR');
      }
    },
    [doc],
  );

  const openSample = useCallback(
    (key: string) => {
      const sample = samples.find((s) => s.key === key);
      const run = () => load(sample?.description ?? key, { kind: 'sample', key }, (signal) => studioApi.openSample(key, signal));
      lastRequest.current = run;
      return run();
    },
    [load, samples],
  );

  const openFile = useCallback(
    (file: File) => {
      const run = () => load(file.name, { kind: 'file', name: file.name }, (signal) => studioApi.uploadPdf(file, signal));
      lastRequest.current = run;
      return run();
    },
    [load],
  );

  /** Avanza o retrocede usando siempre el valor más reciente (clics rápidos no se pierden). */
  const stepPage = useCallback(
    (delta: 1 | -1) => setCurrentPageRaw((prev) => (pageCount ? Math.max(0, Math.min(pageCount - 1, prev + delta)) : prev)),
    [pageCount],
  );

  const retryLoad = useCallback(() => lastRequest.current?.(), []);
  const dismissLoadError = useCallback(() => setLoadError(null), []);

  // Render de la página actual (cancelable, con caché).
  const sessionId = doc?.sessionId ?? null;
  useEffect(() => {
    if (!sessionId) return;
    const key = `${sessionId}:${currentPage}`;
    const cached = renderCache.current.get(key);
    if (cached) {
      setRender({ status: 'ready', data: cached, error: null });
      return;
    }
    const ctrl = new AbortController();
    setRender((r) => ({ status: 'loading', data: r.data && r.data.page_number === currentPage ? r.data : null, error: null }));
    studioApi
      .renderPage(sessionId, currentPage, { signal: ctrl.signal })
      .then((data) => {
        const cache = renderCache.current;
        cache.set(key, data);
        if (cache.size > RENDER_CACHE_MAX) cache.delete(cache.keys().next().value as string);
        setRender({ status: 'ready', data, error: null });
      })
      .catch((err) => {
        const e = normalizeError(err, 'RENDER');
        if (!isCancellation(e)) setRender({ status: 'error', data: null, error: e });
      });
    return () => ctrl.abort();
  }, [sessionId, currentPage, renderAttempt]);

  // Capa OCR: solo si el documento es escaneado o la persona la activó.
  useEffect(() => {
    if (!sessionId || !ocrVisible) {
      setOcr(idle());
      return;
    }
    const ctrl = new AbortController();
    setOcr({ status: 'loading', data: null, error: null });
    studioApi
      .getOcrLayer(sessionId, currentPage, ctrl.signal)
      .then((data) => setOcr({ status: 'ready', data, error: null }))
      .catch((err) => {
        const e = normalizeError(err, 'OCR');
        if (!isCancellation(e)) setOcr({ status: 'error', data: null, error: e });
      });
    return () => ctrl.abort();
  }, [sessionId, currentPage, ocrVisible, ocrAttempt]);

  // Nodos de la página actual (si no están cargados, se piden; cancelable).
  useEffect(() => {
    if (!sessionId || pageNodes[currentPage]) return;
    const ctrl = new AbortController();
    setPageNodesLoading(true);
    studioApi
      .queryNodes(sessionId, currentPage, ctrl.signal)
      .then((list) => setPageNodes((prev) => ({ ...prev, [currentPage]: list })))
      .catch(() => undefined)
      .finally(() => setPageNodesLoading(false));
    return () => ctrl.abort();
  }, [sessionId, currentPage, pageNodes]);

  const nodesOnPage = useMemo(() => pageNodes[currentPage] ?? [], [pageNodes, currentPage]);

  // Recuperar la sesión recordada si el motor todavía la tiene. Una cancelación (p. ej. el doble
  // efecto del modo estricto de React) no cuenta como «la sesión ya no existe»: no borra nada.
  const restoreDone = useRef(false);
  useEffect(() => {
    if (!backendReady || doc || restoreDone.current) return;
    const saved = recall();
    if (!saved) {
      restoreDone.current = true;
      setRestoring(false);
      return;
    }
    const ctrl = new AbortController();
    (async () => {
      try {
        const res = await studioApi.getSummary(saved.sessionId, ctrl.signal);
        const firstPage = await studioApi.queryNodes(saved.sessionId, 0, ctrl.signal);
        if (ctrl.signal.aborted) return;
        restoreDone.current = true;
        const isRaster = isRasterSummary(res.summary);
        setDoc({ sessionId: saved.sessionId, filename: saved.filename, summary: res.summary, source: saved.source, isRaster });
        setPageNodes({ 0: firstPage });
        setCurrentPageRaw(0);
        setOcrVisible(isRaster);
        setRestored(true);
        setPhase('READY');
        setRestoring(false);
      } catch (err) {
        if (ctrl.signal.aborted || isCancellation(normalizeError(err))) return;
        restoreDone.current = true;
        remember(null); // la sesión ya no existe en el motor
        setRestoring(false);
      }
    })();
    return () => ctrl.abort();
  }, [backendReady, doc]);

  /** Tras un reinicio del motor, la sesión anterior ya no existe. */
  const resetDocument = useCallback(() => {
    openCtrl.current?.abort();
    remember(null);
    setRestored(false);
    setDoc(null);
    setPageNodes({});
    setRender(idle());
    setOcr(idle());
    setPhase('EMPTY');
  }, []);

  return {
    samples,
    samplesError,
    retrySamples: () => setSamplesAttempt((n) => n + 1),
    phase,
    loadError,
    loadingLabel,
    doc,
    pageNodes,
    pageNodesLoading,
    nodesOnPage,
    pageCount,
    currentPage,
    setCurrentPage,
    stepPage,
    render,
    retryRender: () => setRenderAttempt((n) => n + 1),
    ocr,
    ocrVisible,
    setOcrVisible,
    retryOcr: () => setOcrAttempt((n) => n + 1),
    openSample,
    openFile,
    retryLoad,
    dismissLoadError,
    resetDocument,
    restored,
    restoring,
    dismissRestored: () => setRestored(false),
  };
}

export type DocumentSessionApi = ReturnType<typeof useDocumentSession>;
