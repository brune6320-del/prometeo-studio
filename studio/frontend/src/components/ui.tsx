/**
 * Componentes base del sistema de diseño "Forja".
 * Los estados nunca se comunican solo por color: siempre icono + texto.
 */
import React, { useCallback, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, CircleDashed, Clock3, Layers, ScanText, XCircle, Info, FlaskConical } from 'lucide-react';
import { ApiError, describeError, technicalSummary } from '../api/errors';

/** Marca original: una llama formada por dos trazos sobre una línea base (transformación sobre el documento). */
export const BrandMark: React.FC<{ size?: number }> = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
    <defs>
      <linearGradient id="pm-ember" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0" stopColor="#ff6a2b" />
        <stop offset="1" stopColor="#ffb07a" />
      </linearGradient>
    </defs>
    <path d="M12 2.5c1.6 3 4.8 4.9 4.8 9.1A4.8 4.8 0 0 1 12 16.4a4.8 4.8 0 0 1-4.8-4.8c0-2.1 1-3.6 2.2-4.9.2 1.5.9 2.6 2 3.2-.3-2.6.3-5 .6-7.4Z" fill="url(#pm-ember)" />
    <rect x="4" y="19" width="16" height="2" rx="1" fill="#ededf2" opacity="0.85" />
  </svg>
);

export type StatusKind = 'ready' | 'staged' | 'verifying' | 'verified' | 'reject' | 'failed' | 'ocr' | 'experimental';

const STATUS_ICON: Record<StatusKind, React.ReactNode> = {
  ready: <CircleDashed size={13} aria-hidden="true" />,
  staged: <Layers size={13} aria-hidden="true" />,
  verifying: <Clock3 size={13} aria-hidden="true" />,
  verified: <CheckCircle2 size={13} aria-hidden="true" />,
  reject: <AlertTriangle size={13} aria-hidden="true" />,
  failed: <XCircle size={13} aria-hidden="true" />,
  ocr: <ScanText size={13} aria-hidden="true" />,
  experimental: <FlaskConical size={13} aria-hidden="true" />,
};

export const StatusBadge: React.FC<{ kind: StatusKind; children: React.ReactNode; title?: string }> = ({ kind, children, title }) => (
  <span className={`status status-${kind}`} title={title}>
    {STATUS_ICON[kind]}
    <span>{children}</span>
  </span>
);

export const Spinner: React.FC<{ large?: boolean; label?: string }> = ({ large, label }) => (
  <span className={`spinner ${large ? 'spinner-lg' : ''}`} role="status" aria-label={label ?? 'Cargando'} />
);

export const EmptyState: React.FC<{ icon?: React.ReactNode; title: string; children?: React.ReactNode; level?: 2 | 3 }> = ({
  icon,
  title,
  children,
  level = 3,
}) => {
  const Heading = level === 2 ? 'h2' : 'h3';
  return (
    <div className="empty">
      {icon && <div className="empty-icon">{icon}</div>}
      <Heading>{title}</Heading>
      {children}
    </div>
  );
};

interface NoticeProps {
  tone: 'error' | 'warn' | 'ok' | 'info';
  title: string;
  children?: React.ReactNode;
  onDismiss?: () => void;
  actions?: React.ReactNode;
}

export const Notice: React.FC<NoticeProps> = ({ tone, title, children, onDismiss, actions }) => {
  const icon =
    tone === 'error' ? <XCircle size={18} /> : tone === 'warn' ? <AlertTriangle size={18} /> : tone === 'ok' ? <CheckCircle2 size={18} /> : <Info size={18} />;
  return (
    <div className={`notice notice-${tone}`} role={tone === 'error' || tone === 'warn' ? 'alert' : 'status'}>
      <span className="notice-icon" aria-hidden="true">
        {icon}
      </span>
      <div>
        <p className="notice-title">{title}</p>
        {children}
        {actions && <div className="notice-buttons">{actions}</div>}
      </div>
      {onDismiss ? (
        <button className="btn btn-ghost btn-icon btn-sm" onClick={onDismiss} aria-label="Cerrar aviso">
          ×
        </button>
      ) : (
        <span />
      )}
    </div>
  );
};

/**
 * Aviso de error estructurado. `reassurance` solo se pasa cuando el contexto lo ha
 * comprobado (p. ej. original_unchanged devuelto por el motor tras verificar).
 */
export const ErrorNotice: React.FC<{
  error: ApiError;
  onRetry?: () => void;
  onDismiss?: () => void;
  reassurance?: string;
  extra?: React.ReactNode;
}> = ({ error, onRetry, onDismiss, reassurance, extra }) => {
  const [showTech, setShowTech] = useState(false);
  const copy = describeError(error);
  return (
    <Notice
      tone="error"
      title={copy.title}
      onDismiss={onDismiss}
      actions={
        <>
          {onRetry && error.retryable !== false && (
            <button className="btn btn-sm btn-outline" onClick={onRetry}>
              Reintentar
            </button>
          )}
          <button className="btn btn-sm btn-ghost" onClick={() => setShowTech((v) => !v)} aria-expanded={showTech}>
            {showTech ? 'Ocultar detalles técnicos' : 'Detalles técnicos'}
          </button>
        </>
      }
    >
      <p className="notice-text">{copy.message}</p>
      <p className="notice-action">{copy.action}</p>
      {reassurance && <p className="notice-action">{reassurance}</p>}
      {extra}
      {showTech && <div className="notice-tech">{technicalSummary(error)}</div>}
    </Notice>
  );
};

/** Divisor de paneles redimensionable con ratón y teclado (flechas, Inicio/Fin). */
export function useResizable(initial: number, min: number, max: number, invert = false) {
  const [size, setSize] = useState(initial);
  const [dragging, setDragging] = useState(false);
  const start = useRef({ x: 0, size: initial });

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      start.current = { x: e.clientX, size };
      setDragging(true);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [size],
  );
  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      const delta = (e.clientX - start.current.x) * (invert ? -1 : 1);
      setSize(Math.max(min, Math.min(max, start.current.size + delta)));
    },
    [dragging, invert, min, max],
  );
  const onPointerUp = useCallback(() => setDragging(false), []);
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const step = e.shiftKey ? 48 : 16;
      const dir = invert ? -1 : 1;
      if (e.key === 'ArrowLeft') setSize((s) => Math.max(min, Math.min(max, s - step * dir)));
      else if (e.key === 'ArrowRight') setSize((s) => Math.max(min, Math.min(max, s + step * dir)));
      else if (e.key === 'Home') setSize(min);
      else if (e.key === 'End') setSize(max);
      else return;
      e.preventDefault();
    },
    [invert, min, max],
  );

  const handleProps = {
    role: 'separator',
    'aria-orientation': 'vertical' as const,
    'aria-valuemin': min,
    'aria-valuemax': max,
    'aria-valuenow': Math.round(size),
    tabIndex: 0,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onKeyDown,
    className: `resizer ${dragging ? 'dragging' : ''}`,
  };
  return { size, handleProps };
}
