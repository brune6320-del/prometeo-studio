import React from 'react';
import { ArrowRight, ShieldCheck, Trash2 } from 'lucide-react';
import type { StagedOperation } from '../types';
import type { TxPhase } from '../hooks/useTransaction';

interface TrayProps {
  ops: StagedOperation[];
  phase: TxPhase;
  verifying: boolean;
  uiMode: 'user' | 'technical';
  onRemove: (opId: string) => void;
  onClear: () => void;
  onVerify: () => void;
}

export const TransactionTray: React.FC<TrayProps> = ({ ops, phase, verifying, uiMode, onRemove, onClear, onVerify }) => {
  const count = ops.length;
  return (
    <div>
      <div className="tray-head">
        <div>
          <strong>
            {count === 0
              ? 'No hay cambios preparados'
              : phase === 'VERIFIED'
                ? `${count} ${count === 1 ? 'cambio incluido' : 'cambios incluidos'} en la copia verificada`
                : `${count} ${count === 1 ? 'cambio preparado' : 'cambios preparados'}`}
          </strong>
          <div className="hint">
            {count === 0
              ? 'Selecciona un texto y usa «Preparar cambio» en el Inspector.'
              : phase === 'VERIFIED'
                ? 'Guarda la copia en «Verificación». Si añades o quitas cambios, habrá que verificar de nuevo.'
                : 'Se verificarán juntos: si uno no se puede aplicar con fidelidad, no se aplica ninguno.'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
          {count > 0 && (
            <button className="btn btn-danger-ghost btn-sm" onClick={onClear} disabled={verifying}>
              Descartar todo
            </button>
          )}
          <button className="btn btn-primary" onClick={onVerify} disabled={count === 0 || verifying || phase === 'VERIFIED'} id="verify-button">
            <ShieldCheck size={15} aria-hidden="true" />
            {verifying ? 'Verificando…' : phase === 'VERIFIED' ? 'Verificado' : 'Verificar y crear copia'}
          </button>
        </div>
      </div>

      {verifying && <div className="progress" style={{ marginBottom: 'var(--sp-3)' }} role="progressbar" aria-label="Verificando la copia" />}

      {count === 0 ? null : (
        <ol className="tray-list" aria-label="Cambios preparados">
          {ops.map((op, i) => (
            <li key={op.op_id} className="tray-item">
              <span className="tray-index">{i + 1}</span>
              <div className="before-after">
                <span className="text-old">{op.original_text}</span>
                <ArrowRight size={14} aria-hidden="true" />
                <span className="text-new">{op.new_text}</span>
              </div>
              <span className="tag">
                {op.type === 'RASTER_REPLACE_TEXT' ? 'escaneado' : 'texto'}
                {uiMode === 'technical' ? ` · ${op.op_id}` : ''}
              </span>
              <button
                className="btn btn-ghost btn-icon btn-sm"
                onClick={() => onRemove(op.op_id)}
                disabled={verifying}
                aria-label={`Descartar el cambio ${i + 1}: ${op.original_text} por ${op.new_text}`}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ol>
      )}
      <p className="hint" style={{ marginTop: 'var(--sp-3)' }}>
        PROMETEO trabaja sobre una copia: no escribe en tu archivo original.
      </p>
    </div>
  );
};
