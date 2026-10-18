import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { studioApi } from '../api/client';
import { ApiError, describeError, normalizeError, technicalSummary } from '../api/errors';

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('normalizeError: el texto crudo del navegador nunca es la explicación', () => {
  it.each([
    ['Load failed'], // WebKit / Safari / WKWebView (el fallo que vio el propietario)
    ['Failed to fetch'], // Chromium
    ['NetworkError when attempting to fetch resource.'], // Firefox
  ])('TypeError "%s" → BACKEND_UNAVAILABLE', (msg) => {
    const e = normalizeError(new TypeError(msg), 'DOCUMENT_LOAD');
    expect(e.code).toBe('BACKEND_UNAVAILABLE');
    expect(e.retryable).toBe(true);
    expect(e.stage).toBe('DOCUMENT_LOAD');
    const copy = describeError(e);
    expect(copy.title).not.toContain(msg);
    expect(copy.message).not.toContain(msg);
    expect(technicalSummary(e)).toContain(msg); // conservado solo como detalle técnico
  });

  it('cualquier código desconocido usa un texto genérico, no el mensaje interno', () => {
    const copy = describeError(new ApiError({ code: 'SOMETHING_NEW', message: 'Traceback (most recent call last)' }));
    expect(copy.title).toBe('Algo no salió como se esperaba');
    expect(copy.message).not.toContain('Traceback');
  });
});

describe('studioApi.request', () => {
  let fetchMock: FetchMock;
  beforeEach(() => {
    (globalThis as unknown as { window: unknown }).window = globalThis;
    (globalThis as unknown as { __PROMETEO_BACKEND__: unknown }).__PROMETEO_BACKEND__ = { port: 51234, token: 'tok123', autoOpenSample: null };
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });
  afterEach(() => {
    vi.useRealTimers();
    delete (globalThis as unknown as { __PROMETEO_BACKEND__?: unknown }).__PROMETEO_BACKEND__;
  });

  it('envía el token y usa el puerto inyectado por el host', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true, samples: [] }));
    await studioApi.listSamples();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://127.0.0.1:51234/api/samples');
    expect(init.headers.Authorization).toBe('Bearer tok123');
  });

  it('un fallo de red de WebKit se convierte en BACKEND_UNAVAILABLE', async () => {
    fetchMock.mockRejectedValue(new TypeError('Load failed'));
    await expect(studioApi.openSample('case_a')).rejects.toMatchObject({ code: 'BACKEND_UNAVAILABLE', stage: 'DOCUMENT_LOAD' });
  });

  it('interpreta el sobre de error estructurado del backend', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(401, { ok: false, error: { code: 'AUTHENTICATION_FAILED', stage: 'AUTH', message: 'Token inválido', retryable: false, details: {} } }),
    );
    await expect(studioApi.listSamples()).rejects.toMatchObject({ code: 'AUTHENTICATION_FAILED', status: 401, stage: 'AUTH' });
  });

  it('un 5xx sin sobre del motor (proxy sin motor) se trata como motor no disponible', async () => {
    fetchMock.mockResolvedValue(new Response('proxy error', { status: 502 }));
    await expect(studioApi.listSamples()).rejects.toMatchObject({ code: 'BACKEND_UNAVAILABLE', status: 502, retryable: true });
  });

  it('un 500 con sobre del motor conserva su código', async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, { ok: false, error: { code: 'INTERNAL_ERROR', stage: 'API', message: 'x', retryable: true, details: {} } }));
    await expect(studioApi.listSamples()).rejects.toMatchObject({ code: 'INTERNAL_ERROR', status: 500 });
  });

  it('respeta el tiempo máximo y lo informa como REQUEST_TIMEOUT', async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation((_url: string, init: RequestInit) => new Promise((_res, rej) => {
      init.signal?.addEventListener('abort', () => rej(new DOMException('aborted', 'AbortError')));
    }));
    const p = studioApi.health();
    const assertion = expect(p).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' });
    await vi.advanceTimersByTimeAsync(3100);
    await assertion;
  });

  it('una cancelación externa se informa como CANCELLED (y la interfaz la ignora)', async () => {
    fetchMock.mockImplementation((_url: string, init: RequestInit) => new Promise((_res, rej) => {
      init.signal?.addEventListener('abort', () => rej(new DOMException('aborted', 'AbortError')));
    }));
    const ctrl = new AbortController();
    const p = studioApi.listSamples(ctrl.signal);
    ctrl.abort();
    await expect(p).rejects.toMatchObject({ code: 'CANCELLED' });
  });

  it('verify_and_export con ok=false es un resultado, no una excepción', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        ok: false,
        transaction_state: 'FAILED',
        published: false,
        verifier_result: { verdict: 'FAILED', status: 'FAILED', verified_globally: false, verifier_executed: true },
      }),
    );
    const res = await studioApi.verifyAndExport('s1');
    expect(res.ok).toBe(false);
    expect(res.verifier_result.verdict).toBe('FAILED');
  });
});
