/**
 * Estado del motor local: STARTING → BACKEND_READY | DEGRADED | FAILED,
 * más DISCONNECTED si se pierde la conexión después de arrancar.
 *
 * Fuentes: el host nativo (get_backend_config: proceso lanzado, muerto, sin runtime…)
 * y GET /api/health. Nunca se declara listo antes de que /api/health diga ready.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { studioApi } from '../api/client';
import { ApiError, normalizeError } from '../api/errors';
import type { HealthInfo, HostStatus } from '../types';

export type BackendPhase = 'STARTING' | 'BACKEND_READY' | 'DEGRADED' | 'FAILED' | 'DISCONNECTED';

export interface BackendState {
  phase: BackendPhase;
  health: HealthInfo | null;
  host: HostStatus | null;
  error: ApiError | null;
  elapsedMs: number;
}

const BOOT_TIMEOUT_MS = 100_000;
const MONITOR_INTERVAL_MS = 5_000;

function hostError(host: HostStatus): ApiError {
  return new ApiError({
    code: host.code || 'BACKEND_UNAVAILABLE',
    message: host.message || 'El motor no está disponible.',
    stage: 'BOOT',
    retryable: host.code === 'HEALTH_TIMEOUT',
    details: { exit_code: host.exit_code, log_path: host.log_path },
  });
}

export function useBackend(): BackendState & { retry: () => void } {
  const [state, setState] = useState<BackendState>({ phase: 'STARTING', health: null, host: null, error: null, elapsedMs: 0 });
  const [attempt, setAttempt] = useState(0);
  const phaseRef = useRef<BackendPhase>('STARTING');

  useEffect(() => {
    let cancelled = false;
    const started = performance.now();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let misses = 0;
    phaseRef.current = 'STARTING';
    setState((s) => ({ ...s, phase: 'STARTING', error: null, elapsedMs: 0 }));

    const set = (patch: Partial<BackendState>) => {
      if (cancelled) return;
      if (patch.phase) phaseRef.current = patch.phase;
      setState((s) => ({ ...s, ...patch, elapsedMs: performance.now() - started }));
    };

    const tick = async () => {
      if (cancelled) return;
      const booting = phaseRef.current === 'STARTING';
      const host = await studioApi.getHostStatus();
      if (cancelled) return;
      if (host && host.state === 'FAILED' && host.code !== 'HEALTH_TIMEOUT') {
        set({ phase: 'FAILED', host, error: hostError(host) });
        return; // el proceso no se recupera solo
      }
      try {
        const health = await studioApi.health();
        misses = 0;
        if (health.ready) set({ phase: 'BACKEND_READY', health, host, error: null });
        else
          set({
            phase: 'DEGRADED',
            health,
            host,
            error: new ApiError({ code: health.workspace?.error_code || 'BACKEND_DEGRADED', message: 'Motor en modo degradado.', stage: 'BOOT' }),
          });
      } catch (err) {
        const e = normalizeError(err, 'BOOT');
        if (booting) {
          if (performance.now() - started > BOOT_TIMEOUT_MS) {
            set({ phase: 'FAILED', host, error: host?.state === 'FAILED' ? hostError(host) : new ApiError({ code: 'HEALTH_TIMEOUT', message: e.message, stage: 'BOOT', retryable: true }) });
            return;
          }
          set({ host });
        } else {
          misses += 1;
          if (misses >= 2) set({ phase: 'DISCONNECTED', host, error: e });
        }
      }
      const ready = phaseRef.current === 'BACKEND_READY' || phaseRef.current === 'DEGRADED';
      const elapsed = performance.now() - started;
      const delay = ready ? MONITOR_INTERVAL_MS : phaseRef.current === 'DISCONNECTED' ? 2000 : elapsed < 10_000 ? 300 : 1000;
      timer = setTimeout(tick, delay);
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}
