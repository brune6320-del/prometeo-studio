import React, { useRef } from 'react';
import { FileUp, LayoutDashboard, Search, Wrench } from 'lucide-react';
import { BrandMark, StatusBadge, type StatusKind } from './ui';
import type { OpenDocument } from '../hooks/useDocumentSession';
import type { TxPhase } from '../hooks/useTransaction';
import type { SampleItem } from '../types';

export const TX_STATUS: Record<TxPhase, { kind: StatusKind; user: string; technical: string }> = {
  READY: { kind: 'ready', user: 'Sin cambios', technical: 'READY' },
  STAGED: { kind: 'staged', user: 'Cambios preparados', technical: 'STAGED' },
  VERIFYING: { kind: 'verifying', user: 'Verificando…', technical: 'VERIFYING' },
  VERIFIED: { kind: 'verified', user: 'Copia verificada', technical: 'VERIFIED' },
  FAILED: { kind: 'failed', user: 'Verificación no superada', technical: 'FAILED' },
  HONEST_REJECT: { kind: 'reject', user: 'No aplicable con seguridad', technical: 'HONEST_REJECT' },
};

interface ToolbarProps {
  doc: OpenDocument | null;
  pageCount: number;
  txPhase: TxPhase;
  stagedCount: number;
  samples: SampleItem[];
  busy: boolean;
  uiMode: 'user' | 'technical';
  onOpenSample: (key: string) => void;
  onOpenFile: (file: File) => void;
  onToggleMode: () => void;
  onSearch: () => void;
  onOpenBoard: () => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  doc,
  pageCount,
  txPhase,
  stagedCount,
  samples,
  busy,
  uiMode,
  onOpenSample,
  onOpenFile,
  onToggleMode,
  onSearch,
  onOpenBoard,
}) => {
  const fileInput = useRef<HTMLInputElement>(null);
  const status = TX_STATUS[txPhase];
  const sampleKey = doc?.source.kind === 'sample' ? doc.source.key : '';

  return (
    <header className="header">
      <h1 className="sr-only">PROMETEO Studio</h1>
      <div className="brand">
        <BrandMark />
        <span className="brand-name">PROMETEO</span>
        <span className="brand-sub">Studio</span>
      </div>

      <div className="file-identity" aria-label="Documento abierto">
        {doc ? (
          <>
            <span className="file-name" title={doc.filename} id="open-file-name">
              {doc.filename}
            </span>
            <span className="file-meta">
              {pageCount} {pageCount === 1 ? 'página' : 'páginas'} · {doc.isRaster ? 'escaneado (OCR)' : 'texto nativo'}
            </span>
            <StatusBadge kind={status.kind}>
              {uiMode === 'technical' ? status.technical : status.user}
              {txPhase === 'STAGED' && ` (${stagedCount})`}
            </StatusBadge>
          </>
        ) : (
          <span className="muted">Ningún documento abierto</span>
        )}
      </div>

      <div className="header-actions">
        <label htmlFor="sample-select" className="sr-only">
          Abrir un ejemplo
        </label>
        <select
          id="sample-select"
          className="select"
          value={sampleKey}
          disabled={busy || samples.length === 0}
          onChange={(e) => e.target.value && onOpenSample(e.target.value)}
          style={{ width: 230 }}
        >
          <option value="">{samples.length ? 'Abrir un ejemplo…' : 'Sin ejemplos disponibles'}</option>
          {samples.map((s) => (
            <option key={s.key} value={s.key}>
              {s.description}
            </option>
          ))}
        </select>

        <button className="btn btn-primary" onClick={() => fileInput.current?.click()} disabled={busy}>
          <FileUp size={15} aria-hidden="true" /> Abrir PDF
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onOpenFile(f);
            e.target.value = '';
          }}
        />

        <button className="btn btn-ghost btn-sm" onClick={onOpenBoard} title="Abrir el tablero visual">
          <LayoutDashboard size={15} aria-hidden="true" /> Tablero
        </button>

        <button className="btn btn-ghost btn-icon" onClick={onSearch} disabled={!doc} aria-label="Buscar en el documento (Cmd+F)" title="Buscar (⌘F)">
          <Search size={16} />
        </button>

        <button
          className="btn btn-ghost btn-sm"
          onClick={onToggleMode}
          aria-pressed={uiMode === 'technical'}
          title="Muestra identificadores, hashes y detalles del verificador"
        >
          <Wrench size={14} aria-hidden="true" /> Detalles técnicos
        </button>
      </div>
    </header>
  );
};
