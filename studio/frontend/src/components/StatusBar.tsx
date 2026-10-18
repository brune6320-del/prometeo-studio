import React from 'react';
import type { BackendPhase } from '../hooks/useBackend';

interface StatusBarProps {
  phase: BackendPhase;
  version?: string;
  ocrAvailable?: boolean;
  isDesktop: boolean;
}

const CONN: Record<BackendPhase, { cls: string; label: string }> = {
  STARTING: { cls: 'is-wait', label: 'Motor iniciando' },
  BACKEND_READY: { cls: '', label: 'Motor conectado' },
  DEGRADED: { cls: 'is-wait', label: 'Motor en modo degradado' },
  FAILED: { cls: 'is-down', label: 'Motor no disponible' },
  DISCONNECTED: { cls: 'is-down', label: 'Reconectando con el motor…' },
};

export const StatusBar: React.FC<StatusBarProps> = ({ phase, version, ocrAvailable, isDesktop }) => {
  const c = CONN[phase];
  return (
    <footer className="statusbar" aria-label="Estado">
      <span className="conn" role="status" aria-live="polite">
        <span className={`conn-dot ${c.cls}`} aria-hidden="true" />
        {c.label}
      </span>
      <span>OCR {ocrAvailable ? 'disponible' : 'no disponible'}</span>
      <span>{isDesktop ? 'Copias verificadas: Descargas › PROMETEO' : 'Copias verificadas: descargas del navegador'}</span>
      <span className="sep" />
      <span>
        <kbd>⌘</kbd> <kbd>F</kbd> buscar
      </span>
      <span>PROMETEO Studio {version ?? ''}</span>
    </footer>
  );
};
