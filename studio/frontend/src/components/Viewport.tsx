import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Columns2, FileText, Frame, MoveHorizontal, ScanText, ZoomIn, ZoomOut } from 'lucide-react';
import type { NodeSummary, OCRObservation, PageRenderData } from '../types';
import type { AsyncSlot } from '../hooks/useDocumentSession';
import type { OCRLayerData } from '../types';
import type { ApiError } from '../api/errors';
import { pdfBBoxToViewportRect } from '../utils/coordinates';
import { ErrorNotice, Notice, Spinner } from './ui';

interface ViewportProps {
  render: AsyncSlot<PageRenderData>;
  onRetryRender: () => void;
  nodesOnPage: NodeSummary[];
  selectedNodeId: string | null;
  stagedNodeIds: Set<string>;
  onSelectNode: (id: string) => void;
  currentPage: number;
  pageCount: number;
  onPageChange: (p: number) => void;
  onPageStep: (delta: 1 | -1) => void;
  ocr: AsyncSlot<OCRLayerData>;
  ocrVisible: boolean;
  isRaster: boolean;
  onToggleOcr: () => void;
  onRetryOcr: () => void;
  selectedOcrId: string | null;
  onSelectOcr: (obs: OCRObservation) => void;
  compare: { available: boolean; data: PageRenderData | null; error: ApiError | null };
  viewMode: 'original' | 'compare';
  onViewMode: (m: 'original' | 'compare') => void;
  uiMode: 'user' | 'technical';
  showStagedTags: boolean;
}

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5];

export const Viewport: React.FC<ViewportProps> = (p) => {
  const [zoom, setZoom] = useState(1);
  const [showFrames, setShowFrames] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const data = p.render.data;

  const metrics = useMemo(
    () => ({ scaleFactor: zoom, offsetX: 0, offsetY: 0, viewportWidthPx: (data?.width_pt ?? 612) * zoom, viewportHeightPx: (data?.height_pt ?? 792) * zoom }),
    [zoom, data],
  );
  // Una imagen que cubre casi toda la página es el propio escaneo: no se marca (taparía la página).
  const pageArea = (data?.width_pt ?? 0) * (data?.height_pt ?? 0);
  const selectableNodes = p.nodesOnPage.filter((n) => {
    if (!n.bbox || !(n.type === 'TEXT' || n.type === 'IMAGE' || n.type === 'VECTOR')) return false;
    if (n.type === 'IMAGE' && pageArea > 0) {
      const area = (n.bbox[2] - n.bbox[0]) * (n.bbox[3] - n.bbox[1]);
      if (area / pageArea > 0.6) return false;
    }
    return true;
  });

  const step = (dir: 1 | -1) => {
    const idx = ZOOMS.findIndex((z) => z >= zoom - 1e-6);
    const next = ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, (idx === -1 ? ZOOMS.length - 1 : idx) + dir))];
    setZoom(next);
  };
  const fitWidth = () => {
    const el = scrollRef.current;
    if (!el || !data) return;
    const columns = p.viewMode === 'compare' ? 2 : 1;
    const available = (el.clientWidth - 64 - (columns - 1) * 32) / columns;
    setZoom(Math.max(0.25, Math.min(3, available / data.width_pt)));
  };

  // Al entrar en Comparar, ajustar para que quepan las dos páginas.
  const prevMode = useRef(p.viewMode);
  useEffect(() => {
    if (p.viewMode === 'compare' && prevMode.current !== 'compare' && data) {
      const el = scrollRef.current;
      if (el) {
        const available = (el.clientWidth - 64 - 32) / 2;
        setZoom(Math.max(0.25, Math.min(1.5, available / data.width_pt)));
      }
    }
    prevMode.current = p.viewMode;
  }, [p.viewMode, data]);

  const page = (img: PageRenderData, opts: { label?: string; tone?: 'original' | 'verified'; interactive: boolean }) => {
    const w = img.width_pt * zoom;
    const h = img.height_pt * zoom;
    return (
      <figure className="page-frame" style={{ margin: 0 }}>
        {opts.label && (
          <figcaption className="page-label" style={{ color: opts.tone === 'verified' ? 'var(--st-verified)' : 'var(--text-2)' }}>
            {opts.label}
          </figcaption>
        )}
        <div className={`page-paper ${p.render.status === 'loading' && opts.interactive ? 'is-loading' : ''}`} style={{ width: w, height: h }}>
          <img src={img.image_data_url} alt={`${opts.label ?? 'Página'} ${p.currentPage + 1}`} width={w} height={h} draggable={false} />
          {opts.interactive && showFrames && (
            <div aria-hidden="true">
              {selectableNodes.map((n) => {
                const r = pdfBBoxToViewportRect(n.bbox!, metrics);
                const cls = [
                  'overlay',
                  n.type === 'TEXT' ? 'overlay-text' : n.type === 'IMAGE' ? 'overlay-image' : 'overlay-vector',
                  p.selectedNodeId === n.id ? 'is-selected' : '',
                  p.stagedNodeIds.has(n.id) ? 'is-staged' : '',
                ].join(' ');
                return (
                  <div
                    key={n.id}
                    data-node-id={n.id}
                    className={cls}
                    style={{ left: r.left, top: r.top, width: r.width, height: r.height }}
                    onClick={() => p.onSelectNode(n.id)}
                    title={n.text || n.id}
                  >
                    {p.showStagedTags && p.stagedNodeIds.has(n.id) && <span className="overlay-tag">Preparado</span>}
                  </div>
                );
              })}
            </div>
          )}
          {opts.interactive && p.ocrVisible && p.ocr.data?.observations && (
            <div aria-hidden="true">
              {p.ocr.data.observations.map((o) => {
                const r = pdfBBoxToViewportRect(o.bbox, metrics);
                return (
                  <div
                    key={o.id}
                    data-ocr-id={o.id}
                    className={`overlay overlay-ocr ${p.selectedOcrId === o.id ? 'is-selected' : ''}`}
                    style={{ left: r.left, top: r.top, width: r.width, height: r.height }}
                    onClick={() => p.onSelectOcr(o)}
                    title={`Lectura OCR (${Math.round(o.confidence)}%): ${o.text}`}
                  />
                );
              })}
            </div>
          )}
        </div>
      </figure>
    );
  };

  const ocrCount = p.ocr.data?.observations?.length ?? 0;

  return (
    <section className="panel viewport" aria-label="Vista del documento">
      <div className="viewport-toolbar" role="toolbar" aria-label="Controles de la vista">
        <div className="toolbar-group">
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => p.onPageStep(-1)} disabled={p.currentPage <= 0} aria-label="Página anterior">
            <ChevronLeft size={16} />
          </button>
          <label className="page-indicator" htmlFor="page-jump">
            Página{' '}
            <input
              id="page-jump"
              key={p.currentPage}
              className="input"
              type="number"
              min={1}
              max={p.pageCount || 1}
              defaultValue={p.currentPage + 1}
              aria-label={`Página actual, de ${p.pageCount || 1}. Escribe un número y pulsa Intro para ir`}
              style={{ width: 64, height: 28, padding: '0 6px', display: 'inline-block', textAlign: 'center' }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const n = parseInt((e.target as HTMLInputElement).value, 10);
                  if (Number.isFinite(n)) p.onPageChange(n - 1);
                }
              }}
              onBlur={(e) => {
                const n = parseInt(e.target.value, 10);
                if (Number.isFinite(n) && n - 1 !== p.currentPage) p.onPageChange(n - 1);
              }}
            />{' '}
            de {p.pageCount || 1}
          </label>
          <button
            className="btn btn-ghost btn-icon btn-sm"
            onClick={() => p.onPageStep(1)}
            disabled={p.currentPage >= p.pageCount - 1}
            aria-label="Página siguiente"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        <div className="toolbar-group">
          <div className="segmented" role="group" aria-label="Modo de vista">
            <button aria-pressed={p.viewMode === 'original'} onClick={() => p.onViewMode('original')}>
              <FileText size={13} aria-hidden="true" /> Original
            </button>
            <button
              aria-pressed={p.viewMode === 'compare'}
              onClick={() => p.onViewMode('compare')}
              disabled={!p.compare.available}
              title={p.compare.available ? 'Original y copia verificada lado a lado' : 'Disponible cuando haya una copia verificada'}
            >
              <Columns2 size={13} aria-hidden="true" /> Comparar
            </button>
          </div>
        </div>

        <div className="toolbar-group">
          <button className="btn btn-ghost btn-sm" aria-pressed={showFrames} onClick={() => setShowFrames((v) => !v)} title="Muestra los contornos de los elementos detectados">
            <Frame size={14} aria-hidden="true" /> Marcos
          </button>
          <button
            className="btn btn-ghost btn-sm"
            aria-pressed={p.ocrVisible}
            onClick={p.onToggleOcr}
            title="Lecturas OCR: hipótesis de texto sobre la imagen, no texto del PDF"
          >
            <ScanText size={14} aria-hidden="true" /> Capa OCR{p.ocrVisible && p.ocr.status === 'ready' ? ` (${ocrCount})` : ''}
            {p.ocrVisible && p.ocr.status === 'loading' && <Spinner label="Leyendo texto de la imagen" />}
          </button>
          <span style={{ width: 8 }} />
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => step(-1)} disabled={zoom <= ZOOMS[0]} aria-label="Alejar">
            <ZoomOut size={15} />
          </button>
          <button className="btn btn-ghost btn-sm zoom-value" onClick={() => setZoom(1)} aria-label={`Zoom ${Math.round(zoom * 100)} por ciento; restablecer al 100`}>
            {Math.round(zoom * 100)}%
          </button>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => step(1)} disabled={zoom >= ZOOMS[ZOOMS.length - 1]} aria-label="Acercar">
            <ZoomIn size={15} />
          </button>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={fitWidth} disabled={!data} aria-label="Ajustar al ancho">
            <MoveHorizontal size={15} />
          </button>
        </div>
      </div>

      <div className="canvas-scroll" ref={scrollRef}>
        {p.ocrVisible && p.ocr.status === 'error' && p.ocr.error && (
          <div className="viewport-banner">
            <ErrorNotice error={p.ocr.error} onRetry={p.onRetryOcr} />
          </div>
        )}
        {p.ocrVisible && p.ocr.status === 'ready' && !p.isRaster && (
          <div className="viewport-banner">
            <Notice tone="info" title="Capa OCR sobre un PDF con texto nativo">
              <p className="notice-text">
                Las lecturas OCR son hipótesis sobre la imagen. Para editar texto nativo, selecciona el texto (contorno azul), no la lectura OCR.
              </p>
            </Notice>
          </div>
        )}

        {p.render.status === 'error' && p.render.error ? (
          <div style={{ maxWidth: 560, margin: '0 auto' }}>
            <ErrorNotice error={p.render.error} onRetry={p.onRetryRender} />
          </div>
        ) : !data ? (
          <div className="pages-row" aria-busy="true">
            <div className="page-frame">
              <div className="page-paper skeleton" style={{ width: 612 * zoom * 0.8, height: 792 * zoom * 0.8, display: 'grid', placeItems: 'center' }}>
                <Spinner large label="Dibujando la página" />
              </div>
            </div>
          </div>
        ) : p.viewMode === 'compare' && p.compare.available ? (
          <div className="pages-row">
            {page(data, { label: 'Original (sin cambios)', tone: 'original', interactive: true })}
            {p.compare.data ? (
              page(p.compare.data, { label: 'Copia verificada', tone: 'verified', interactive: false })
            ) : p.compare.error ? (
              <div style={{ maxWidth: 420 }}>
                <ErrorNotice error={p.compare.error} />
              </div>
            ) : (
              <div className="page-frame">
                <span className="page-label">Copia verificada</span>
                <div className="page-paper skeleton" style={{ width: data.width_pt * zoom, height: data.height_pt * zoom, display: 'grid', placeItems: 'center' }}>
                  <Spinner large label="Dibujando la copia verificada" />
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="pages-row">{page(data, { interactive: true })}</div>
        )}
      </div>
    </section>
  );
};
