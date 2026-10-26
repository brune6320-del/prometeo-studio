import React, { useEffect, useState } from 'react';
import { ArrowRight, Image as ImageIcon, Layers, Lock, MousePointerClick, ScanText, ShieldCheck, Type } from 'lucide-react';
import type { NodeDetail, OCRObservation, RasterPatchPreviewData, RasterSafetyData } from '../types';
import { studioApi } from '../api/client';
import { ApiError, describeError, isCancellation, normalizeError } from '../api/errors';
import { EmptyState, Notice, Spinner, StatusBadge } from './ui';
import type { TxPhase } from '../hooks/useTransaction';

interface InspectorProps {
  sessionId: string | null;
  node: NodeDetail | null;
  /** Texto que el visor ya muestra (preparado o vista previa), para no enseñar el viejo. */
  editedText?: string;
  nodeLoading: boolean;
  ocrObservation: OCRObservation | null;
  isStaged: boolean;
  txPhase: TxPhase;
  busy: boolean;
  uiMode: 'user' | 'technical';
  onStageText: (nodeId: string, text: string) => Promise<void>;
  onStageRaster: (page: number, obsId: string, text: string) => Promise<void>;
}

const RASTER_REASON: Record<string, string> = {
  RASTER_TEXT_LAYER_PRESENT: 'la página ya tiene texto digital; edita ese texto en lugar de la imagen',
  RASTER_COLOR_PAGE_UNSUPPORTED: 'la página tiene color y la edición la convertiría a escala de grises',
  BACKGROUND_TOO_COMPLEX: 'el fondo alrededor del texto no es uniforme',
  EDGE_DENSITY_EXCEEDED: 'hay demasiados bordes o trazos cerca del texto (líneas, sellos o ruido)',
  RING_VARIANCE_EXCEEDED: 'el fondo que rodea al texto varía demasiado (textura o ruido del escaneo)',
  BACKGROUND_GRADIENT_DETECTED: 'el fondo tiene un degradado',
  PATCH_OVERLAPS_GRAPHIC: 'el texto toca una línea, tabla o dibujo',
  OCR_CONFIDENCE_TOO_LOW: 'la lectura OCR es poco fiable',
  OCR_CONFIDENCE_MARGINAL: 'la lectura OCR está en el límite de fiabilidad',
  TARGET_OUT_OF_BOUNDS: 'la región está fuera de la página',
  TARGET_SIZE_IMPLAUSIBLE: 'el tamaño de la región no es razonable para un texto',
  BACKGROUND_SURROUNDING_MISMATCH: 'el fondo de la región no coincide con su entorno',
  PAGE_SKEW_DETECTED: 'la página está inclinada',
  UNSUPPORTED_RASTER_STRUCTURE: 'la estructura de la imagen no está soportada',
};

function StageError({ error }: { error: ApiError }) {
  const copy = describeError(error);
  const detail = error.message && error.message !== copy.message ? error.message : null;
  return (
    <Notice tone="warn" title={copy.title}>
      <p className="notice-text">{detail ?? copy.message}</p>
      <p className="notice-action">{copy.action}</p>
    </Notice>
  );
}

export const Inspector: React.FC<InspectorProps> = (p) => {
  return (
    <section className="panel inspector-panel" aria-labelledby="inspector-title">
      <div className="panel-header">
        <h2 className="panel-title" id="inspector-title">
          {p.ocrObservation ? 'Lectura OCR' : p.node ? 'Elemento seleccionado' : 'Inspector'}
        </h2>
        {p.isStaged && (p.txPhase === 'VERIFIED' ? <StatusBadge kind="verified">En la copia verificada</StatusBadge> : <StatusBadge kind="staged">Preparado</StatusBadge>)}
      </div>
      <div className="panel-body">
        {p.ocrObservation ? (
          <OcrInspector {...p} obs={p.ocrObservation} />
        ) : p.nodeLoading && !p.node ? (
          <div aria-busy="true">
            <div className="skeleton" style={{ height: 18, width: '60%', marginBottom: 12 }} />
            <div className="skeleton" style={{ height: 64, marginBottom: 12 }} />
            <div className="skeleton" style={{ height: 32 }} />
          </div>
        ) : p.node ? (
          <NodeInspector {...p} node={p.node} />
        ) : (
          <EmptyState icon={<MousePointerClick size={26} />} title="Nada seleccionado">
            <p>Haz clic en un texto de la página o en la lista «Contenido» para ver sus datos y proponer un cambio.</p>
          </EmptyState>
        )}
      </div>
    </section>
  );
};

const NodeInspector: React.FC<InspectorProps & { node: NodeDetail }> = ({ node, editedText, isStaged, txPhase, busy, uiMode, onStageText }) => {
  const [text, setText] = useState(editedText ?? node.text ?? '');
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [justStaged, setJustStaged] = useState(false);
  const [preparedText, setPreparedText] = useState<string | null>(null);

  useEffect(() => {
    setText(editedText ?? node.text ?? '');
    setError(null);
    setJustStaged(false);
    setPreparedText(null);
  }, [node.id, node.text]);

  // El visor puede cambiar el texto (edición en el sitio); no se pierde el estado preparado.
  useEffect(() => {
    if (editedText === undefined) return;
    setText((actual) => (actual === editedText ? actual : editedText));
  }, [editedText]);

  if (node.type !== 'TEXT') {
    return (
      <>
        <div className="section">
          <h3 className="section-title">
            <ImageIcon size={14} aria-hidden="true" /> {node.type === 'IMAGE' ? 'Imagen' : node.type === 'VECTOR' ? 'Dibujo vectorial' : 'Grupo'}
          </h3>
          <p className="muted" style={{ margin: 0 }}>
            Este elemento se puede inspeccionar, pero no editar en esta versión.
          </p>
        </div>
        {uiMode === 'technical' && <TechnicalNode node={node} />}
      </>
    );
  }

  const original = node.text ?? '';
  const changed = text.trim() !== '' && text !== original;
  const upToDate = preparedText !== null && text.trim() === preparedText;
  const tooLong = original.length > 0 && text.length > original.length * 1.5;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!changed) return;
    setSubmitting(true);
    setError(null);
    try {
      await onStageText(node.id, text);
      setPreparedText(text.trim());
      setJustStaged(true);
    } catch (err) {
      setError(normalizeError(err, 'STAGING'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="section">
        <h3 className="section-title">
          <Type size={14} aria-hidden="true" /> Texto
        </h3>
        <dl className="kv">
          <dt>Página</dt>
          <dd>{node.page !== undefined ? node.page + 1 : '—'}</dd>
          <dt>Fuente</dt>
          <dd>{node.font || '—'}</dd>
          <dt>Tamaño</dt>
          <dd>{node.size ? `${node.size.toFixed(1)} pt` : '—'}</dd>
        </dl>
      </div>

      <form className="section" onSubmit={submit}>
        <h3 className="section-title">
          <Layers size={14} aria-hidden="true" /> Proponer cambio
        </h3>
        <div className="field">
          <span className="field-label">Texto actual</span>
          <div className="readonly-text">{original}</div>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="edit-text">
            Texto nuevo
          </label>
          <textarea
            id="edit-text"
            className="textarea"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setJustStaged(false);
            }}
            disabled={submitting || busy}
            aria-describedby="edit-help"
          />
        </div>
        {changed && (
          <div className="before-after" style={{ marginBottom: 'var(--sp-3)' }} aria-label="Vista previa del cambio">
            <span className="text-old">{original}</span>
            <ArrowRight size={14} aria-hidden="true" />
            <span className="text-new">{text}</span>
          </div>
        )}
        {tooLong && (
          <div style={{ marginBottom: 'var(--sp-3)' }}>
            <Notice tone="warn" title="El texto nuevo es bastante más largo">
              <p className="notice-text">Puede no caber en el espacio original. Si no cabe, la verificación lo rechazará sin tocar nada.</p>
            </Notice>
          </div>
        )}
        {error && (
          <div style={{ marginBottom: 'var(--sp-3)' }}>
            <StageError error={error} />
          </div>
        )}
        {justStaged && !error && txPhase !== 'VERIFIED' && (
          <div style={{ marginBottom: 'var(--sp-3)' }}>
            <Notice tone="ok" title="Cambio preparado">
              <p className="notice-text">Revísalo abajo, en «Cambios», y pulsa «Verificar y crear copia» cuando estés listo.</p>
            </Notice>
          </div>
        )}
        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%' }}
          disabled={!changed || submitting || busy || (isStaged && upToDate)}
        >
          {submitting ? <Spinner label="Preparando" /> : <Layers size={15} aria-hidden="true" />}
          {submitting ? 'Preparando…' : isStaged
            ? (upToDate
              ? (txPhase === 'VERIFIED' ? 'Incluido en la copia verificada' : 'Cambio preparado')
              : 'Actualizar cambio preparado')
            : 'Preparar cambio'}
        </button>
        <p className="hint" id="edit-help" style={{ marginTop: 'var(--sp-2)' }}>
          <ShieldCheck size={12} aria-hidden="true" /> Preparar no modifica nada. El cambio solo se aplica en una copia nueva, y solo si la verificación lo aprueba.
        </p>
      </form>
      {uiMode === 'technical' && <TechnicalNode node={node} />}
    </>
  );
};

const TechnicalNode: React.FC<{ node: NodeDetail }> = ({ node }) => (
  <div className="section">
    <h3 className="section-title">Detalles técnicos</h3>
    <dl className="kv mono" style={{ fontSize: 'var(--fs-xs)' }}>
      <dt>ID</dt>
      <dd>{node.id}</dd>
      <dt>Tipo</dt>
      <dd>{node.type}</dd>
      {node.bbox && (
        <>
          <dt>BBox (pt)</dt>
          <dd>{node.bbox.map((v) => v.toFixed(1)).join(', ')}</dd>
        </>
      )}
      {node.clearance_pt !== undefined && (
        <>
          <dt>Holgura</dt>
          <dd>{node.clearance_pt.toFixed(1)} pt</dd>
        </>
      )}
      <dt>Relaciones</dt>
      <dd>{node.relations?.length ?? 0}</dd>
    </dl>
  </div>
);

const OcrInspector: React.FC<InspectorProps & { obs: OCRObservation }> = ({ obs, sessionId, busy, uiMode, onStageRaster }) => {
  const [safety, setSafety] = useState<RasterSafetyData | null>(null);
  const [preview, setPreview] = useState<RasterPatchPreviewData | null>(null);
  const [checkError, setCheckError] = useState<ApiError | null>(null);
  const [checking, setChecking] = useState(false);
  const [text, setText] = useState(obs.text);
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [staged, setStaged] = useState(false);
  const [preparedText, setPreparedText] = useState<string | null>(null);

  useEffect(() => {
    setText(obs.text);
    setSafety(null);
    setPreview(null);
    setError(null);
    setCheckError(null);
    setStaged(false);
    setPreparedText(null);
    if (!sessionId) return;
    const ctrl = new AbortController();
    setChecking(true);
    studioApi
      .getRasterSafety(sessionId, obs.page, obs.id, ctrl.signal)
      .then(async (s) => {
        setSafety(s);
        if (s.edit_eligible) {
          const pv = await studioApi.getRasterPatchPreview(sessionId, obs.page, obs.id, undefined, ctrl.signal).catch(() => null);
          if (pv) setPreview(pv);
        }
      })
      .catch((err) => {
        const e = normalizeError(err, 'STAGING');
        if (!isCancellation(e)) setCheckError(e);
      })
      .finally(() => setChecking(false));
    return () => ctrl.abort();
  }, [obs.id, obs.page, obs.text, sessionId]);

  const changed = text.trim() !== '' && text !== obs.text;
  const upToDate = preparedText !== null && text.trim() === preparedText;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!changed) return;
    setSubmitting(true);
    setError(null);
    try {
      await onStageRaster(obs.page, obs.id, text.trim());
      setPreparedText(text.trim());
      setStaged(true);
    } catch (err) {
      setError(normalizeError(err, 'STAGING'));
    } finally {
      setSubmitting(false);
    }
  };

  const reasons = (safety?.reasons ?? []).map((r) => RASTER_REASON[r] ?? r);

  return (
    <>
      <div className="section">
        <h3 className="section-title">
          <ScanText size={14} aria-hidden="true" /> Lectura de la imagen
        </h3>
        <Notice tone="info" title="Es una hipótesis, no texto del PDF">
          <p className="notice-text">El OCR leyó estas letras en la imagen escaneada; pueden contener errores.</p>
        </Notice>
        <dl className="kv" style={{ marginTop: 'var(--sp-3)' }}>
          <dt>Leído</dt>
          <dd className="mono">«{obs.text}»</dd>
          <dt>Confianza</dt>
          <dd>{Math.round(obs.confidence)}%</dd>
          <dt>Página</dt>
          <dd>{obs.page + 1}</dd>
        </dl>
      </div>

      <div className="section">
        <h3 className="section-title">¿Se puede editar?</h3>
        {checking ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Spinner label="Analizando la región" /> <span className="muted">Analizando el fondo de la región…</span>
          </div>
        ) : checkError ? (
          <StageError error={checkError} />
        ) : safety?.edit_eligible ? (
          <StatusBadge kind="verified">Sí: fondo uniforme, edición verificable</StatusBadge>
        ) : safety ? (
          <>
            <StatusBadge kind="reject">No se puede editar con seguridad</StatusBadge>
            <p className="muted" style={{ marginTop: 'var(--sp-2)' }}>
              <Lock size={12} aria-hidden="true" /> Motivo: {reasons.join('; ') || 'el fondo o la estructura no permiten un parche verificable'}.
            </p>
          </>
        ) : null}

        {preview?.ok && preview.edit_eligible && (
          <div className="patch-preview" style={{ marginTop: 'var(--sp-3)' }}>
            <figure style={{ margin: 0 }}>
              <img src={preview.before_data_url} alt="Región original" />
              <figcaption className="hint">Original</figcaption>
            </figure>
            <figure style={{ margin: 0 }}>
              <img src={preview.preview_data_url} alt="Vista previa del fondo reconstruido" />
              <figcaption className="hint">Fondo reconstruido</figcaption>
            </figure>
          </div>
        )}
      </div>

      {safety?.edit_eligible && (
        <form className="section" onSubmit={submit}>
          <div className="field">
            <label className="field-label" htmlFor="raster-edit-input">
              Texto nuevo
            </label>
            <input id="raster-edit-input" className="input" value={text} onChange={(e) => setText(e.target.value)} disabled={submitting || busy} />
          </div>
          {error && (
            <div style={{ marginBottom: 'var(--sp-3)' }}>
              <StageError error={error} />
            </div>
          )}
          {staged && upToDate && !error && (
            <div style={{ marginBottom: 'var(--sp-3)' }}>
              <Notice tone="ok" title="Parche preparado">
                <p className="notice-text">Se verificará píxel a píxel antes de crear la copia. Si cambias el texto, vuelve a prepararlo para actualizarlo.</p>
              </Notice>
            </div>
          )}
          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%' }}
            disabled={!changed || submitting || busy || upToDate}
          >
            {submitting ? 'Preparando…' : upToDate ? 'Parche preparado' : staged ? 'Actualizar parche preparado' : 'Preparar parche'}
          </button>
        </form>
      )}

      {uiMode === 'technical' && safety && (
        <div className="section">
          <h3 className="section-title">Detalles técnicos</h3>
          <dl className="kv mono" style={{ fontSize: 'var(--fs-xs)' }}>
            <dt>Clase</dt>
            <dd>{safety.raster_class}</dd>
            <dt>Seguridad</dt>
            <dd>{safety.safety_classification}</dd>
            <dt>Perfil</dt>
            <dd>{safety.profile_name}</dd>
            <dt>Razones</dt>
            <dd>{safety.reasons.join(', ') || '—'}</dd>
          </dl>
        </div>
      )}
    </>
  );
};
