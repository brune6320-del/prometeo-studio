import React from 'react';
import { BrandMark, ErrorNotice, Spinner } from './ui';
import type { BackendState } from '../hooks/useBackend';

type StepState = 'pending' | 'active' | 'done' | 'failed';

interface BootScreenProps {
  backend: BackendState;
  onRetry: () => void;
  onOpenBoard: () => void;
  version?: string;
}

/** Pantalla visible desde el primer instante mientras arranca el motor local. */
export const BootScreen: React.FC<BootScreenProps> = ({ backend, onRetry, onOpenBoard }) => {
  const failed = backend.phase === 'FAILED';
  const hostState = backend.host?.state;
  const spawned = hostState && hostState !== 'STARTING' ? true : backend.elapsedMs > 1500;
  const steps: Array<{ label: string; state: StepState }> = [
    { label: 'Abriendo la interfaz', state: 'done' },
    {
      label: 'Iniciando el motor de documentos',
      state: failed && !spawned ? 'failed' : spawned ? 'done' : 'active',
    },
    {
      label: 'Comprobando que el motor responde',
      state: failed ? 'failed' : spawned ? 'active' : 'pending',
    },
  ];
  const seconds = Math.floor(backend.elapsedMs / 1000);

  return (
    <main className="boot" aria-live="polite">
      <section className="boot-card" aria-labelledby="boot-title">
        <div className="boot-brand">
          <BrandMark size={34} />
          <div>
            <h1 id="boot-title" style={{ margin: 0, fontSize: 'var(--fs-xl)', letterSpacing: '0.12em' }}>
              PROMETEO
            </h1>
            <div className="muted">Studio · edición documental verificada</div>
          </div>
        </div>

        {!failed ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
              <Spinner label="Iniciando PROMETEO" />
              <strong>Preparando el espacio de trabajo…</strong>
            </div>
            <div className="progress" style={{ marginTop: 'var(--sp-4)' }} aria-hidden="true" />
          </>
        ) : null}

        <ol className="boot-steps">
          {steps.map((s) => (
            <li key={s.label} className="boot-step" data-state={s.state}>
              <span className="boot-dot" aria-hidden="true" />
              <span>
                {s.label}
                <span className="sr-only">
                  {' '}
                  — {s.state === 'done' ? 'completado' : s.state === 'active' ? 'en curso' : s.state === 'failed' ? 'falló' : 'pendiente'}
                </span>
              </span>
            </li>
          ))}
        </ol>

        {!failed && seconds >= 8 && (
          <p className="hint" style={{ marginTop: 'var(--sp-4)' }}>
            El primer arranque tras instalar puede tardar más mientras macOS comprueba la aplicación ({seconds} s).
          </p>
        )}

        {failed && backend.error && (
          <div style={{ marginTop: 'var(--sp-5)' }}>
            <ErrorNotice
              error={backend.error}
              onRetry={onRetry}
              extra={
                backend.host?.log_path ? (
                  <p className="hint" style={{ marginTop: 'var(--sp-2)' }}>
                    Registro técnico: <span className="mono">{backend.host.log_path}</span>
                  </p>
                ) : null
              }
            />
          </div>
        )}

        <div style={{ marginTop: 'var(--sp-5)', display: 'grid', gap: 'var(--sp-2)', justifyItems: 'start' }}>
          <button type="button" className="btn btn-primary" onClick={onOpenBoard}>
            Abrir tablero visual
          </button>
          <p className="hint" style={{ margin: 0 }}>
            El tablero puede usarse y guardarse mientras el motor de documentos termina de iniciar.
          </p>
        </div>
      </section>
    </main>
  );
};
