import React, { useEffect, useMemo, useState } from 'react';
import { BadgeCheck, Download, FileText, Image as ImageIcon, Layers, RotateCw, Trash2, Type, X } from 'lucide-react';
import { studioApi } from '../api/client';
import { normalizeError } from '../api/errors';
import type { AdvancedOutput, DocumentSummary, NodeDetail } from '../types';
import { Notice, Spinner } from './ui';

type Herramienta = 'capacidades' | 'tipografia' | 'anotar' | 'paginas';

interface DocumentToolsProps {
  sessionId: string;
  summary: DocumentSummary;
  node: NodeDetail | null;
  currentPage: number;
  pageCount: number;
  onClose: () => void;
}

function readDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => (typeof reader.result === 'string' ? resolve(reader.result) : reject(new Error('No se pudo leer el archivo.')));
    reader.onerror = () => reject(new Error('No se pudo leer el archivo.'));
    reader.readAsDataURL(file);
  });
}

export const DocumentTools: React.FC<DocumentToolsProps> = ({ sessionId, summary, node, currentPage, pageCount, onClose }) => {
  const [tab, setTab] = useState<Herramienta>('capacidades');
  const [result, setResult] = useState<AdvancedOutput | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const dialogRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previo = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusables = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])'));
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      previo?.focus?.();
    };
  }, [onClose]);

  const ejecutar = async (fn: () => Promise<AdvancedOutput>) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const respuesta = await fn();
      if (respuesta.ok) setResult(respuesta);
      else {
        const sugerencia = respuesta.suggested_size_pt ? ` Tamaño sugerido: ${respuesta.suggested_size_pt} pt.` : '';
        setError(`${respuesta.reason || 'La operación no se pudo verificar.'}${sugerencia}`);
      }
    } catch (err) {
      setError(normalizeError(err, 'EXPORT').message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialogRef} className="board-dialog document-tools" role="dialog" aria-modal="true" aria-labelledby="document-tools-title" tabIndex={-1}>
        <div className="board-dialog-heading">
          <h2 id="document-tools-title"><FileText size={16} aria-hidden="true" /> Documento</h2>
          <button type="button" onClick={onClose} aria-label="Cerrar herramientas del documento"><X size={16} /></button>
        </div>
        <div className="document-tools-tabs" role="tablist" aria-label="Herramientas del documento">
          {([
            ['capacidades', 'Capacidades'],
            ['tipografia', 'Tipografía'],
            ['anotar', 'Anotar'],
            ['paginas', 'Páginas'],
          ] as Array<[Herramienta, string]>).map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? 'active' : ''} onClick={() => { setTab(id); setResult(null); setError(null); }}>{label}</button>
          ))}
        </div>
        <div className="document-tools-body">
          {tab === 'capacidades' && <Capacidades summary={summary} />}
          {tab === 'tipografia' && <Tipografia sessionId={sessionId} node={node} ejecutar={ejecutar} busy={busy} />}
          {tab === 'anotar' && <Anotar sessionId={sessionId} currentPage={currentPage} ejecutar={ejecutar} busy={busy} />}
          {tab === 'paginas' && <Paginas sessionId={sessionId} pageCount={pageCount} ejecutar={ejecutar} busy={busy} />}
          {error && <Notice tone="warn" title="No se creó ninguna copia"><p className="notice-text">{error}</p></Notice>}
          {result?.ok && (
            <Notice tone="ok" title="Copia nueva creada">
              <p className="notice-text">El original no cambió. SHA-256: <code>{result.sha256?.slice(0, 20)}…</code></p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => { if (result.token) void studioApi.downloadAdvancedPdf(sessionId, result.token); }}
              ><Download size={14} /> Descargar copia</button>
            </Notice>
          )}
        </div>
      </div>
    </div>
  );
};

const Capacidades: React.FC<{ summary: DocumentSummary }> = ({ summary }) => {
  const c = summary.capabilities;
  const nativo = Boolean(c.can_text_edit && c.is_born_digital && !c.is_raster);
  const escaneado = Boolean(c.is_raster || c.is_raster_dominant);
  const motivo = nativo
    ? 'El PDF tiene texto nativo: se puede sustituir un span y verificar que los demás no cambian.'
    : escaneado
      ? c.has_ocr_layer
        ? 'El PDF es una imagen. Hay capa OCR: se puede editar una región solo si el fondo y la confianza lo permiten.'
        : 'El PDF es una imagen sin texto nativo ni capa OCR: no hay texto que editar con verificación.'
      : 'No se detectó texto editable en este documento.';
  return (
    <div className="document-capabilities">
      <div className={`document-capability ${nativo ? 'is-ok' : 'is-limited'}`}>
        <BadgeCheck size={18} aria-hidden="true" />
        <div><strong>{nativo ? 'Texto nativo verificable' : escaneado ? 'Documento escaneado' : 'Sin texto editable'}</strong><p>{motivo}</p></div>
      </div>
      <dl className="kv">
        <dt>Texto</dt><dd>{summary.text_nodes_count}</dd>
        <dt>Imágenes</dt><dd>{summary.image_nodes_count}</dd>
        <dt>Vectores</dt><dd>{summary.vector_nodes_count}</dd>
        <dt>Páginas</dt><dd>{summary.pages_count}</dd>
        <dt>Contrato</dt><dd>{nativo ? 'sustituir y verificar' : escaneado && c.has_ocr_layer ? 'OCR con seguridad' : 'solo lectura'}</dd>
      </dl>
      <p className="hint">Esta pantalla no finge: si una edición no se puede verificar, la herramienta la rechaza con el motivo. No hay botón para abrir Acrobat.</p>
    </div>
  );
};

const Tipografia: React.FC<{ sessionId: string; node: NodeDetail | null; ejecutar: (fn: () => Promise<AdvancedOutput>) => Promise<void>; busy: boolean }> = ({ sessionId, node, ejecutar, busy }) => {
  const [texto, setTexto] = useState('');
  const [tamano, setTamano] = useState('11');
  const [fuente, setFuente] = useState('helv');
  const [color, setColor] = useState('#000000');

  useEffect(() => {
    if (!node) return;
    setTexto(node.text ?? '');
    setTamano(String(node.size ?? 11));
    setColor('#000000');
  }, [node?.id, node?.text, node?.size]);

  if (!node || node.type !== 'TEXT') {
    return <Notice tone="warn" title="Selecciona un texto"><p className="notice-text">Haz clic en un span de texto de la página o en Contenido. Los dibujos e imágenes no se editan aquí.</p></Notice>;
  }

  return (
    <form
      className="document-form"
      onSubmit={(event) => {
        event.preventDefault();
        void ejecutar(() => studioApi.typography(sessionId, {
          node_id: node.id,
          new_text: texto,
          font_size_pt: Number(tamano) || undefined,
          color,
          font_family: fuente,
        }));
      }}
    >
      <p className="hint">Página {node.page !== undefined ? node.page + 1 : '—'} · bbox y fuente originales se conservan como referencia.</p>
      <label>Texto<textarea value={texto} onChange={(event) => setTexto(event.target.value)} rows={3} /></label>
      <div className="document-form-row">
        <label>Tamaño (pt)<input type="number" min="4" max="300" step="0.5" value={tamano} onChange={(event) => setTamano(event.target.value)} /></label>
        <label>Fuente
          <select value={fuente} onChange={(event) => setFuente(event.target.value)}>
            <option value="helv">Helvetica</option>
            <option value="hebo">Helvetica Bold</option>
            <option value="heit">Helvetica Italic</option>
            <option value="times">Times</option>
            <option value="tibo">Times Bold</option>
            <option value="cour">Courier</option>
          </select>
        </label>
        <label>Color<input type="color" value={color} onChange={(event) => setColor(event.target.value)} /></label>
      </div>
      <button type="submit" className="btn btn-primary" disabled={busy || !texto.trim()}>
        {busy ? <Spinner label="Verificando" /> : <Type size={14} />} {busy ? 'Midiendo y verificando…' : 'Cambiar tipografía y verificar'}
      </button>
      <p className="hint">La herramienta mide el ancho real con las métricas de la fuente. Si no cabe, no crea archivo y explica por qué.</p>
    </form>
  );
};

const Anotar: React.FC<{ sessionId: string; currentPage: number; ejecutar: (fn: () => Promise<AdvancedOutput>) => Promise<void>; busy: boolean }> = ({ sessionId, currentPage, ejecutar, busy }) => {
  const [kind, setKind] = useState<'text' | 'image'>('text');
  const [texto, setTexto] = useState('');
  const [x, setX] = useState('72');
  const [y, setY] = useState('72');
  const [width, setWidth] = useState('240');
  const [height, setHeight] = useState('60');
  const [fontSize, setFontSize] = useState('12');
  const [color, setColor] = useState('#111111');
  const [imagen, setImagen] = useState<string | null>(null);

  return (
    <form
      className="document-form"
      onSubmit={(event) => {
        event.preventDefault();
        void ejecutar(() => studioApi.annotate(sessionId, {
          page: currentPage + 1,
          kind,
          text: kind === 'text' ? texto : undefined,
          image_data_url: kind === 'image' ? imagen ?? undefined : undefined,
          x: Number(x) || 72,
          y: Number(y) || 72,
          width: Number(width) || 240,
          height: Number(height) || 60,
          font_size_pt: Number(fontSize) || 12,
          color,
        }));
      }}
    >
      <p className="hint">Página {currentPage + 1}. Se añade en la capa «Prometeo · anotaciones» de una copia nueva; el original no se toca.</p>
      <div className="document-form-row">
        <button type="button" className={`btn ${kind === 'text' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setKind('text')}><Type size={14} /> Texto</button>
        <button type="button" className={`btn ${kind === 'image' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setKind('image')}><ImageIcon size={14} /> Imagen</button>
      </div>
      {kind === 'text' ? (
        <>
          <label>Texto<textarea value={texto} onChange={(event) => setTexto(event.target.value)} rows={3} /></label>
          <div className="document-form-row">
            <label>Tamaño (pt)<input type="number" min="4" max="120" value={fontSize} onChange={(event) => setFontSize(event.target.value)} /></label>
            <label>Color<input type="color" value={color} onChange={(event) => setColor(event.target.value)} /></label>
          </div>
        </>
      ) : (
        <label>Imagen<input type="file" accept="image/*" onChange={(event) => { const file = event.target.files?.[0]; if (file) void readDataUrl(file).then(setImagen).catch(() => setImagen(null)); }} /></label>
      )}
      <div className="document-form-row">
        <label>X (pt)<input type="number" value={x} onChange={(event) => setX(event.target.value)} /></label>
        <label>Y (pt)<input type="number" value={y} onChange={(event) => setY(event.target.value)} /></label>
        <label>Ancho<input type="number" value={width} onChange={(event) => setWidth(event.target.value)} /></label>
        <label>Alto<input type="number" value={height} onChange={(event) => setHeight(event.target.value)} /></label>
      </div>
      <button type="submit" className="btn btn-primary" disabled={busy || (kind === 'text' ? !texto.trim() : !imagen)}>
        {busy ? <Spinner label="Añadiendo" /> : <Layers size={14} />} {busy ? 'Creando copia…' : 'Añadir en capa y crear copia'}
      </button>
    </form>
  );
};

const Paginas: React.FC<{ sessionId: string; pageCount: number; ejecutar: (fn: () => Promise<AdvancedOutput>) => Promise<void>; busy: boolean }> = ({ sessionId, pageCount, ejecutar, busy }) => {
  const inicial = useMemo(() => Array.from({ length: pageCount }, (_, indice) => indice + 1), [pageCount]);
  const [orden, setOrden] = useState<number[]>(inicial);
  const [rotaciones, setRotaciones] = useState<Record<number, number>>({});
  const [borradas, setBorradas] = useState<number[]>([]);
  const [unir, setUnir] = useState<string[]>([]);
  const [unirNombres, setUnirNombres] = useState<string[]>([]);

  useEffect(() => setOrden(inicial), [inicial]);

  const mover = (indice: number, delta: -1 | 1) => {
    const destino = indice + delta;
    if (destino < 0 || destino >= orden.length) return;
    const siguiente = [...orden];
    [siguiente[indice], siguiente[destino]] = [siguiente[destino], siguiente[indice]];
    setOrden(siguiente);
  };

  const restantes = orden.filter((page) => !borradas.includes(page));

  return (
    <form
      className="document-form"
      onSubmit={(event) => {
        event.preventDefault();
        void ejecutar(() => studioApi.organizePages(sessionId, {
          order: restantes,
          rotate: Object.entries(rotaciones).map(([page, degrees]) => ({ page: Number(page), degrees })).filter((item) => item.degrees % 360 !== 0),
          merge: unir,
          filename: undefined,
        }));
      }}
    >
      <p className="hint">Reordenar, rotar, quitar y unir siempre produce un PDF nuevo con su SHA-256. La copia de trabajo no se sobrescribe.</p>
      <ol className="document-pages">
        {orden.map((page, indice) => {
          const borrada = borradas.includes(page);
          const giro = rotaciones[page] ?? 0;
          return (
            <li key={page} className={borrada ? 'is-deleted' : ''}>
              <span className="document-page-number">Página {page}</span>
              <span className="document-page-rotation">{giro ? `${giro}°` : '0°'}</span>
              <div className="document-page-actions">
                <button type="button" onClick={() => mover(indice, -1)} disabled={indice === 0} aria-label={`Subir página ${page}`}>↑</button>
                <button type="button" onClick={() => mover(indice, 1)} disabled={indice === orden.length - 1} aria-label={`Bajar página ${page}`}>↓</button>
                <button type="button" onClick={() => setRotaciones((actual) => ({ ...actual, [page]: ((actual[page] ?? 0) + 90) % 360 }))} aria-label={`Rotar página ${page}`}><RotateCw size={13} /></button>
                <button type="button" onClick={() => setBorradas((actual) => actual.includes(page) ? actual.filter((item) => item !== page) : [...actual, page])} aria-label={`${borrada ? 'Recuperar' : 'Quitar'} página ${page}`}><Trash2 size={13} /></button>
              </div>
            </li>
          );
        })}
      </ol>
      <label>Unir PDFs
        <input
          type="file"
          accept="application/pdf"
          multiple
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            setUnirNombres(files.map((file) => file.name));
            void Promise.all(files.map((file) => readDataUrl(file))).then(setUnir).catch(() => setUnir([]));
          }}
        />
      </label>
      {unirNombres.length > 0 && <p className="hint">Se unirán al final: {unirNombres.join(', ')}</p>}
      <button type="submit" className="btn btn-primary" disabled={busy || restantes.length === 0}>
        {busy ? <Spinner label="Organizando" /> : <FileText size={14} />} {busy ? 'Creando copia…' : `Organizar ${restantes.length} ${restantes.length === 1 ? 'página' : 'páginas'}`}
      </button>
    </form>
  );
};
