import React from 'react';
import { AlertTriangle, CheckCircle2, Download, FolderOpen, ShieldCheck, XCircle } from 'lucide-react';
import type { SavedCopy, VerifyAndExportResponse } from '../types';
import type { TxPhase } from '../hooks/useTransaction';
import { EmptyState } from './ui';
import { verificationFailures } from '../verification/failures';

interface VerifierPanelProps {
  response: VerifyAndExportResponse | null;
  phase: TxPhase;
  saved: SavedCopy | null;
  saving: boolean;
  canReveal: boolean;
  uiMode: 'user' | 'technical';
  onSave: () => void;
  onReveal: () => void;
  saveLabel: string;
}

const REASON_COPY: Record<string, string> = {
  MIXED_TRANSACTION_UNSUPPORTED: 'El lote mezclaba cambios sobre texto nativo y sobre zonas escaneadas.',
  VERIFIER_UNAVAILABLE: 'El verificador necesario no estaba disponible; PROMETEO prefiere no aprobar sin verificar.',
  VERIFIER_ERROR: 'El verificador falló durante la comprobación; no se aprobó nada.',
  RASTER_PREFLIGHT_REJECTED: 'La zona escaneada no tiene un fondo que permita un parche verificable.',
  RASTER_COLOR_PAGE_UNSUPPORTED: 'La página tiene color y la edición la convertiría a escala de grises.',
  RASTER_TEXT_LAYER_PRESENT: 'La página tiene texto digital que la edición de imagen eliminaría.',
  CORE_REJECTED: 'El motor no pudo aplicar el cambio con la tipografía y el espacio disponibles.',
  VERIFICATION_FAILED: 'La copia generada no superó las comprobaciones de texto, posición o tipografía.',
  UNTOUCHED_PAGE_CHANGED: 'Una página que no se debía tocar cambió en la copia.',
  EXPORT_FAILED: 'No se pudo generar la copia.',
};

export const VerifierPanel: React.FC<VerifierPanelProps> = ({ response, phase, saved, saving, canReveal, uiMode, onSave, onReveal, saveLabel }) => {
  if (phase === 'VERIFYING') {
    return (
      <div>
        <strong>Verificando la copia…</strong>
        <p className="hint">Se genera una copia nueva y se vuelve a leer para comprobar texto, posición y tipografía.</p>
        <div className="progress" role="progressbar" aria-label="Verificando la copia" />
      </div>
    );
  }
  if (!response && phase === 'VERIFIED') {
    // Sesión recuperada tras recargar la interfaz: la copia verificada sigue en el motor.
    return (
      <div className="result-card is-pass" aria-live="polite">
        <div className="result-head">
          <span className="result-icon" aria-hidden="true">
            <CheckCircle2 size={20} />
          </span>
          <div>
            <h3>Copia verificada recuperada</h3>
            <div className="hint">La interfaz se recargó; la copia que el verificador aprobó sigue disponible.</div>
          </div>
        </div>
        <div style={{ marginTop: 'var(--sp-4)' }}>
          {saved ? (
            <div className="saved-path" role="status">
              <CheckCircle2 size={14} color="var(--st-verified)" aria-hidden="true" />
              <span>
                Guardado en <strong>{saved.path}</strong>
              </span>
            </div>
          ) : (
            <button className="btn btn-primary" onClick={onSave} disabled={saving}>
              <Download size={15} aria-hidden="true" /> {saving ? 'Guardando…' : saveLabel}
            </button>
          )}
        </div>
      </div>
    );
  }
  if (!response) {
    return (
      <EmptyState icon={<ShieldCheck size={26} />} title="Todavía no se verificó nada">
        <p>Prepara uno o más cambios y pulsa «Verificar y crear copia». Solo una copia aprobada se puede guardar.</p>
      </EmptyState>
    );
  }

  const vr = response.verifier_result;
  // Defensa en profundidad: «Copia verificada» solo si el motor afirma que el verificador se ejecutó.
  const pass = response.ok && vr.verdict === 'PASS' && vr.verifier_executed === true;
  const reject = vr.verdict === 'HONEST_REJECT';
  const tone = pass ? 'is-pass' : reject ? 'is-reject' : 'is-failed';
  const reason = (vr.code && REASON_COPY[vr.code]) || vr.reason;
  const failures = verificationFailures(vr);

  return (
    <div className={`result-card ${tone}`} aria-live="polite">
      <div className="result-head">
        <span className="result-icon" aria-hidden="true">
          {pass ? <CheckCircle2 size={20} /> : reject ? <AlertTriangle size={20} /> : <XCircle size={20} />}
        </span>
        <div>
          <h3>{pass ? 'Copia verificada' : reject ? 'No se aplicó: no puede hacerse con seguridad' : 'La copia no superó la verificación'}</h3>
          <div className="hint">
            {pass
              ? `Se comprobaron ${vr.operations_verified ?? 0} ${vr.operations_verified === 1 ? 'cambio' : 'cambios'} sobre la copia generada.`
              : 'No se creó ninguna copia para guardar.'}
          </div>
        </div>
      </div>

      {!pass && reason && <p style={{ margin: '0 0 var(--sp-2)' }}>{reason}</p>}

      {!pass && failures.length > 0 && (
        <div className="failure-block" aria-label="Por qué falló la verificación">
          <h4 className="failure-title">Qué falló</h4>
          <table className="failure-table">
            <thead>
              <tr>
                <th scope="col">Comprobación</th>
                <th scope="col">Esperado</th>
                <th scope="col">Obtenido</th>
              </tr>
            </thead>
            <tbody>
              {failures.map((row) => (
                <tr key={`${row.id}-${row.label}-${row.expected}-${row.actual}`}>
                  <th scope="row">{row.label}</th>
                  <td>{row.expected}</td>
                  <td>{row.actual}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ul className="checks" aria-label="Qué se comprobó">
        <li>
          {vr.verifier_executed ? <CheckCircle2 size={14} color="var(--st-verified)" aria-hidden="true" /> : <XCircle size={14} color="var(--text-3)" aria-hidden="true" />}
          <span>{vr.verifier_executed ? 'El verificador se ejecutó sobre el archivo generado.' : 'El verificador no llegó a ejecutarse.'}</span>
        </li>
        {response.original_unchanged && (
          <li>
            <CheckCircle2 size={14} color="var(--st-verified)" aria-hidden="true" />
            <span>Tu original no cambió (huella SHA-256 comprobada después de la operación).</span>
          </li>
        )}
      </ul>

      {pass && (
        <div style={{ marginTop: 'var(--sp-4)' }}>
          {!saved ? (
            <button className="btn btn-primary" onClick={onSave} disabled={saving} id="save-verified-button">
              <Download size={15} aria-hidden="true" /> {saving ? 'Guardando…' : saveLabel}
            </button>
          ) : (
            <>
              <div className="saved-path" role="status">
                <CheckCircle2 size={14} color="var(--st-verified)" aria-hidden="true" />
                <span>
                  Guardado en <strong>{saved.path}</strong>
                </span>
              </div>
              <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: 'var(--sp-2)' }}>
                {canReveal && (
                  <button className="btn btn-outline btn-sm" onClick={onReveal}>
                    <FolderOpen size={14} aria-hidden="true" /> Mostrar en Finder
                  </button>
                )}
                <button className="btn btn-ghost btn-sm" onClick={onSave} disabled={saving}>
                  Guardar otra copia
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {uiMode === 'technical' && (
        <details style={{ marginTop: 'var(--sp-4)' }}>
          <summary className="muted" style={{ cursor: 'pointer' }}>
            Detalles técnicos
          </summary>
          <dl className="kv mono" style={{ fontSize: 'var(--fs-xs)', marginTop: 'var(--sp-2)' }}>
            <dt>Veredicto</dt>
            <dd>{vr.verdict}</dd>
            <dt>Código</dt>
            <dd>{vr.code ?? '—'}</dd>
            <dt>Perfil</dt>
            <dd>{vr.verifier_profile ?? '—'}</dd>
            <dt>Transacción</dt>
            <dd>{vr.transaction_id ?? '—'}</dd>
            <dt>SHA-256 copia</dt>
            <dd>{response.output_sha256 ?? '—'}</dd>
            <dt>SHA-256 original</dt>
            <dd>{response.original_sha256 ?? '—'}</dd>
          </dl>
          {vr.details && vr.details.length > 0 && (
            <pre className="notice-tech" style={{ maxHeight: 220, overflow: 'auto' }}>
              {JSON.stringify(vr.details, null, 2).slice(0, 6000)}
            </pre>
          )}
        </details>
      )}
    </div>
  );
};
