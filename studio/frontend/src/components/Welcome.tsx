import React from 'react';
import { FileUp, MousePointerClick, PenLine, ShieldCheck } from 'lucide-react';
import type { SampleItem } from '../types';
import type { ApiError } from '../api/errors';
import { BrandMark, ErrorNotice, Spinner } from './ui';

interface WelcomeProps {
  samples: SampleItem[];
  samplesError: ApiError | null;
  onRetrySamples: () => void;
  loading: boolean;
  loadingLabel: string;
  error: ApiError | null;
  workspaceError: ApiError | null;
  onOpenFile: () => void;
  onOpenSample: (key: string) => void;
  onRetry: () => void;
  onDismiss: () => void;
}

/** Punto de entrada: dos caminos obvios (tu PDF o un ejemplo) y qué va a pasar en tres pasos. */
export const Welcome: React.FC<WelcomeProps> = ({ samples, samplesError, loading, loadingLabel, error, workspaceError, onOpenFile, onOpenSample, onRetry, onRetrySamples, onDismiss }) => {
  if (loading) {
    return (
      <div className="empty" aria-busy="true">
        <Spinner large label="Abriendo documento" />
        <h2>Abriendo {loadingLabel}…</h2>
        <p>PROMETEO crea una copia de trabajo y analiza la estructura del documento. Tu archivo no se modifica.</p>
      </div>
    );
  }
  return (
    <div className="empty">
      <div className="welcome">
        <BrandMark size={40} />
        <h2 style={{ marginTop: 'var(--sp-3)' }}>Edita PDFs sin poner en riesgo el original</h2>
        <p style={{ margin: 'var(--sp-2) auto 0' }}>
          Preparas el cambio, PROMETEO crea una copia nueva y solo te la entrega si una verificación independiente confirma que el cambio
          quedó exactamente donde debía.
        </p>

        {workspaceError && (
          <div style={{ marginTop: 'var(--sp-4)', textAlign: 'left' }}>
            <ErrorNotice error={workspaceError} />
          </div>
        )}
        {error && (
          <div style={{ marginTop: 'var(--sp-4)', textAlign: 'left' }}>
            <ErrorNotice error={error} onRetry={onRetry} onDismiss={onDismiss} />
          </div>
        )}
        {samplesError && !workspaceError && (
          <div style={{ marginTop: 'var(--sp-4)', textAlign: 'left' }} data-testid="samples-error">
            <ErrorNotice error={samplesError} onRetry={onRetrySamples} />
          </div>
        )}

        <div className="welcome-actions">
          <button className="btn btn-primary btn-lg" onClick={onOpenFile} disabled={!!workspaceError} id="welcome-open-pdf">
            <FileUp size={17} aria-hidden="true" /> Abrir un PDF…
          </button>
        </div>

        {samples.length > 0 && (
          <>
            <p className="hint" style={{ marginTop: 'var(--sp-5)' }}>
              ¿Sin un PDF a mano? Prueba con un ejemplo incluido:
            </p>
            <ul className="sample-list" style={{ margin: 'var(--sp-2) auto 0' }}>
              {samples.map((s) => (
                <li key={s.key}>
                  <button className="sample-btn" onClick={() => onOpenSample(s.key)} disabled={!!workspaceError} data-sample={s.key}>
                    <span>{s.description}</span>
                    <span className="subtle">Abrir</span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}

        <ol
          aria-label="Cómo funciona"
          style={{ listStyle: 'none', padding: 0, margin: 'var(--sp-6) auto 0', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--sp-3)', maxWidth: 560 }}
        >
          {[
            { icon: <MousePointerClick size={18} />, t: '1 · Selecciona', d: 'Haz clic en un texto de la página.' },
            { icon: <PenLine size={18} />, t: '2 · Prepara', d: 'Escribe el texto nuevo.' },
            { icon: <ShieldCheck size={18} />, t: '3 · Verifica y guarda', d: 'Solo una copia aprobada se guarda.' },
          ].map((s) => (
            <li key={s.t} style={{ background: 'var(--bg-1)', border: '1px solid var(--line)', borderRadius: 'var(--radius-md)', padding: 'var(--sp-3)' }}>
              <div style={{ color: 'var(--ember-text)' }} aria-hidden="true">
                {s.icon}
              </div>
              <strong style={{ display: 'block', marginTop: 4 }}>{s.t}</strong>
              <span className="hint">{s.d}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
};
