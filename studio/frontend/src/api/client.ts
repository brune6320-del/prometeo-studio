/**
 * PROMETEO Studio · cliente HTTP del motor local.
 *
 * - Una sola función `request` para todas las llamadas: tiempo máximo, cancelación
 *   (AbortSignal), cabeceras de sesión y errores estructurados del backend.
 * - En la app de escritorio, el host inyecta `window.__PROMETEO_BACKEND__`
 *   ({ port, token, autoOpenSample }) antes de que cargue la página.
 * - `getHostStatus` consulta al host Tauri el estado real del arranque del motor.
 */

import { ApiError, normalizeError, type ErrorStage } from './errors';
import type {
  DocumentSummary,
  HealthInfo,
  HostStatus,
  MirarReferentesRequest,
  MirarReferentesResponse,
  NodeDetail,
  NodeSummary,
  OCRLayerData,
  PageRenderData,
  RasterPatchPreviewData,
  RasterSafetyData,
  SampleItem,
  SavedCopy,
  SearchResult,
  StagedOperation,
  TransactionTrayData,
  VerifyAndExportResponse,
} from '../types';

interface InjectedBackend {
  port: number;
  token: string;
  autoOpenSample?: string | null;
  /** Solo pruebas nativas (variable de entorno al lanzar; valores fijos validados por el host). */
  autoTest?: string | null;
}

export interface BackendEndpoint {
  baseUrl: string;
  token: string;
  isDesktop: boolean;
  autoOpenSample: string | null;
  autoTest: string | null;
}

export function getBackendEndpoint(): BackendEndpoint {
  const injected = (typeof window !== 'undefined'
    ? (window as unknown as { __PROMETEO_BACKEND__?: InjectedBackend }).__PROMETEO_BACKEND__
    : undefined);
  if (injected && injected.port) {
    return {
      baseUrl: `http://127.0.0.1:${injected.port}`,
      token: injected.token || '',
      isDesktop: true,
      autoOpenSample: injected.autoOpenSample ?? null,
      autoTest: injected.autoTest ?? null,
    };
  }
  // Modo web de desarrollo: Vite reenvía /api al backend local.
  const env = (import.meta as unknown as { env?: Record<string, string> }).env ?? {};
  return { baseUrl: env.VITE_API_URL || '', token: '', isDesktop: false, autoOpenSample: null, autoTest: null };
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE';
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  timeoutMs?: number;
  stage?: ErrorStage;
  raw?: boolean;
}

const DEFAULT_TIMEOUT_MS = 20_000;

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { baseUrl, token } = getBackendEndpoint();
  const stage = opts.stage ?? 'API';
  const controller = new AbortController();
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onExternalAbort = () => controller.abort();
  if (opts.signal) {
    if (opts.signal.aborted) controller.abort();
    else opts.signal.addEventListener('abort', onExternalAbort, { once: true });
  }

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
    headers['X-Prometeo-Token'] = token;
  }
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }

  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, { method: opts.method ?? 'GET', headers, body, signal: controller.signal });
  } catch (err) {
    if (timedOut) {
      throw new ApiError({ code: 'REQUEST_TIMEOUT', message: 'La operación tardó demasiado.', stage, retryable: true });
    }
    if (controller.signal.aborted) {
      throw new ApiError({ code: 'CANCELLED', message: 'Operación cancelada.', stage });
    }
    throw normalizeError(err, stage);
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener('abort', onExternalAbort);
  }

  if (!res.ok) {
    let payload: { error?: { code?: string; stage?: string; message?: string; retryable?: boolean; details?: Record<string, unknown> }; detail?: unknown } = {};
    try {
      payload = await res.json();
    } catch {
      /* cuerpo no JSON: se describe por el estado HTTP */
    }
    const e = payload.error;
    // El motor siempre responde errores con su sobre JSON. Un 5xx sin sobre viene de algo
    // intermedio (p. ej. el proxy de desarrollo) cuando el motor no responde.
    const noEnvelope5xx = !e && [500, 502, 503, 504].includes(res.status);
    throw new ApiError({
      code: e?.code ?? (noEnvelope5xx ? 'BACKEND_UNAVAILABLE' : res.status === 401 ? 'AUTHENTICATION_FAILED' : res.status >= 500 ? 'INTERNAL_ERROR' : 'REQUEST_FAILED'),
      message: e?.message ?? (typeof payload.detail === 'string' ? payload.detail : `HTTP ${res.status}`),
      stage: e?.stage ?? stage,
      status: res.status,
      retryable: e?.retryable ?? res.status >= 500,
      details: e?.details ?? {},
    });
  }
  if (opts.raw) return res as unknown as T;
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError({ code: 'INVALID_RESPONSE', message: 'Respuesta ilegible del motor.', stage, status: res.status });
  }
}

const enc = encodeURIComponent;

export const studioApi = {
  health(signal?: AbortSignal) {
    return request<HealthInfo>('/api/health', { signal, timeoutMs: 3000, stage: 'BOOT' });
  },

  /**
   * «Volver a mirar»: pide hasta tres lecturas al motor local, que es quien
   * habla con DeepSeek. La clave vive en el entorno del backend, nunca aquí.
   */
  mirarReferentes(input: MirarReferentesRequest) {
    return request<MirarReferentesResponse>('/api/referentes/mirar', {
      method: 'POST',
      json: input,
      timeoutMs: 120_000,
      stage: 'API',
    });
  },

  async getHostStatus(): Promise<HostStatus | null> {
    const internals = (window as unknown as { __TAURI_INTERNALS__?: { invoke?: (cmd: string, args?: unknown) => Promise<unknown> } }).__TAURI_INTERNALS__;
    if (!internals?.invoke) return null;
    try {
      return (await internals.invoke('get_backend_config')) as HostStatus;
    } catch {
      return null;
    }
  },

  listSamples(signal?: AbortSignal) {
    return request<{ ok: boolean; samples: SampleItem[] }>('/api/samples', { signal, timeoutMs: 15_000, stage: 'DOCUMENT_LOAD' });
  },

  openSample(sampleKey: string, signal?: AbortSignal) {
    return request<{ ok: boolean; session_id: string; filename: string; summary: DocumentSummary }>(
      '/api/sessions/open_sample',
      { method: 'POST', json: { sample_key: sampleKey }, signal, timeoutMs: 180_000, stage: 'DOCUMENT_LOAD' },
    );
  },

  uploadPdf(file: File, signal?: AbortSignal) {
    const form = new FormData();
    form.append('file', file);
    return request<{ ok: boolean; session_id: string; filename: string; summary: DocumentSummary }>(
      '/api/sessions/upload',
      { method: 'POST', form, signal, timeoutMs: 180_000, stage: 'DOCUMENT_LOAD' },
    );
  },

  /** Nodos de una página (sin recorte). La interfaz carga páginas bajo demanda. */
  async queryNodes(sessionId: string, page: number, signal?: AbortSignal): Promise<NodeSummary[]> {
    const data = await request<{ nodes: Array<Record<string, unknown>> }>(`/api/sessions/${enc(sessionId)}/nodes?page=${page}`, {
      signal,
      timeoutMs: 60_000,
      stage: 'DOCUMENT_LOAD',
    });
    return (data.nodes || []).map((n) => {
      const p = typeof n.page === 'number' ? n.page : undefined;
      return {
        ...(n as object),
        id: (n.id as string) || (n.node_id as string),
        type: ((n.type as string) || (n.node_type as string)) as NodeSummary['type'],
        page: p,
      } as NodeSummary;
    });
  },

  async getNode(sessionId: string, nodeId: string, signal?: AbortSignal): Promise<NodeDetail> {
    const data = await request<{ node: Record<string, any> }>(`/api/sessions/${enc(sessionId)}/nodes/${enc(nodeId)}`, { signal });
    const raw = data.node?.target_node || data.node || {};
    return {
      ...raw,
      id: raw.id || raw.node_id || nodeId,
      type: raw.type || raw.node_type || 'TEXT',
      relations: data.node?.relations || [],
    } as NodeDetail;
  },

  async renderPage(sessionId: string, page: number, opts: { dpi?: number; verified?: boolean; signal?: AbortSignal } = {}) {
    const base = opts.verified ? `/api/sessions/${enc(sessionId)}/verified/page/${page}/render` : `/api/sessions/${enc(sessionId)}/page/${page}/render`;
    const data = await request<{ page: PageRenderData }>(`${base}?dpi=${opts.dpi ?? 150}`, {
      signal: opts.signal,
      timeoutMs: 45_000,
      stage: 'RENDER',
    });
    return data.page;
  },

  getOcrLayer(sessionId: string, page: number, signal?: AbortSignal) {
    return request<OCRLayerData>(`/api/sessions/${enc(sessionId)}/ocr/${page}`, { signal, timeoutMs: 90_000, stage: 'OCR' });
  },

  searchText(sessionId: string, query: string, signal?: AbortSignal) {
    return request<SearchResult>(`/api/sessions/${enc(sessionId)}/search`, { method: 'POST', json: { query }, signal });
  },

  searchOcr(sessionId: string, query: string, signal?: AbortSignal) {
    return request<SearchResult>(`/api/sessions/${enc(sessionId)}/ocr_search`, {
      method: 'POST',
      json: { query },
      signal,
      timeoutMs: 120_000,
      stage: 'OCR',
    });
  },

  async stageEdit(sessionId: string, nodeId: string, newText: string): Promise<StagedOperation> {
    const data = await request<{ staged: StagedOperation }>(`/api/sessions/${enc(sessionId)}/stage_edit`, {
      method: 'POST',
      json: { node_id: nodeId, new_text: newText },
      stage: 'STAGING',
      timeoutMs: 60_000,
    });
    return data.staged;
  },

  async stageRasterEdit(sessionId: string, page: number, observationId: string, newText: string): Promise<StagedOperation> {
    const data = await request<{ staged: StagedOperation }>(`/api/sessions/${enc(sessionId)}/stage_raster_edit`, {
      method: 'POST',
      json: { page, observation_id: observationId, new_text: newText },
      stage: 'STAGING',
      timeoutMs: 90_000,
    });
    return data.staged;
  },

  getRasterSafety(sessionId: string, page: number, observationId: string, signal?: AbortSignal) {
    return request<RasterSafetyData>(`/api/sessions/${enc(sessionId)}/raster_safety/${page}/${enc(observationId)}`, {
      signal,
      timeoutMs: 90_000,
      stage: 'STAGING',
    });
  },

  getRasterPatchPreview(sessionId: string, page: number, observationId: string, newText?: string, signal?: AbortSignal) {
    const q = newText !== undefined ? `?new_text=${enc(newText)}` : '';
    return request<RasterPatchPreviewData>(
      `/api/sessions/${enc(sessionId)}/raster_patch_preview/${page}/${enc(observationId)}${q}`,
      { signal, timeoutMs: 90_000, stage: 'STAGING' },
    );
  },

  getSummary(sessionId: string, signal?: AbortSignal) {
    return request<{ ok: boolean; summary: DocumentSummary }>(`/api/sessions/${enc(sessionId)}/summary`, { signal, timeoutMs: 30_000, stage: 'DOCUMENT_LOAD' });
  },

  getTransaction(sessionId: string) {
    return request<TransactionTrayData>(`/api/sessions/${enc(sessionId)}/transaction`, { stage: 'STAGING' });
  },

  removeStagedOp(sessionId: string, opId: string) {
    return request<TransactionTrayData>(`/api/sessions/${enc(sessionId)}/staged/${enc(opId)}`, { method: 'DELETE', stage: 'STAGING' });
  },

  clearTransaction(sessionId: string) {
    return request<TransactionTrayData>(`/api/sessions/${enc(sessionId)}/transaction`, { method: 'DELETE', stage: 'STAGING' });
  },

  verifyAndExport(sessionId: string) {
    return request<VerifyAndExportResponse>(`/api/sessions/${enc(sessionId)}/verify_and_export`, {
      method: 'POST',
      json: {},
      timeoutMs: 300_000,
      stage: 'VERIFICATION',
    });
  },

  saveVerified(sessionId: string) {
    return request<SavedCopy>(`/api/sessions/${enc(sessionId)}/save_verified`, { method: 'POST', stage: 'EXPORT', timeoutMs: 60_000 });
  },

  revealSaved(sessionId: string) {
    return request<{ ok: boolean; path: string }>(`/api/sessions/${enc(sessionId)}/reveal_saved`, { method: 'POST', stage: 'EXPORT' });
  },

  /** Descarga por el navegador (solo modo web; en escritorio se usa saveVerified). */
  async downloadVerifiedPdf(sessionId: string): Promise<string> {
    const res = await request<Response>(`/api/sessions/${enc(sessionId)}/download`, { raw: true, stage: 'EXPORT', timeoutMs: 60_000 });
    const blob = await res.blob();
    const match = (res.headers.get('content-disposition') || '').match(/filename="?([^";]+)"?/);
    const filename = match?.[1] ?? 'documento_verificado.pdf';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return filename;
  },

  sendAgentMessage(sessionId: string, message: string) {
    return request<{ ok: boolean; reply: Record<string, any> }>(`/api/sessions/${enc(sessionId)}/agent/chat`, {
      method: 'POST',
      json: { message },
      timeoutMs: 60_000,
    });
  },

  closeSession(sessionId: string) {
    return request<{ ok: boolean }>(`/api/sessions/${enc(sessionId)}/close`, { method: 'POST', stage: 'SESSION' });
  },
};

export type StudioApi = typeof studioApi;
