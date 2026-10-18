import React, { useEffect, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { studioApi } from '../api/client';
import { ApiError, isCancellation, normalizeError } from '../api/errors';
import type { OCRObservation, SearchCandidate } from '../types';
import { ErrorNotice, Spinner } from './ui';

interface SearchModalProps {
  sessionId: string;
  isRaster: boolean;
  onClose: () => void;
  onPickNode: (nodeId: string, page: number) => void;
  onPickOcr: (obs: OCRObservation) => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({ sessionId, isRaster, onClose, onPickNode, onPickOcr }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchCandidate[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const ctrl = useRef<AbortController | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      ctrl.current?.abort();
    };
  }, [onClose]);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setSearching(true);
    setError(null);
    try {
      const res = isRaster ? await studioApi.searchOcr(sessionId, query.trim(), c.signal) : await studioApi.searchText(sessionId, query.trim(), c.signal);
      setResults(res.candidates ?? []);
    } catch (err) {
      const ae = normalizeError(err);
      if (!isCancellation(ae)) setError(ae);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="search-title" onMouseDown={(e) => e.stopPropagation()}>
        <h2 id="search-title" className="sr-only">
          Buscar en el documento
        </h2>
        <form onSubmit={run} style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center' }}>
          <Search size={16} aria-hidden="true" className="subtle" />
          <label htmlFor="search-input" className="sr-only">
            Texto a buscar
          </label>
          <input
            id="search-input"
            ref={inputRef}
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={isRaster ? 'Buscar en la lectura OCR…' : 'Buscar texto…'}
          />
          <button className="btn btn-primary" type="submit" disabled={searching || !query.trim()}>
            {searching ? <Spinner label="Buscando" /> : 'Buscar'}
          </button>
          <button className="btn btn-ghost btn-icon" type="button" onClick={onClose} aria-label="Cerrar búsqueda">
            <X size={16} />
          </button>
        </form>
        {isRaster && <p className="hint" style={{ marginTop: 'var(--sp-2)' }}>Documento escaneado: se busca en las lecturas OCR, que pueden tener errores.</p>}
        {error && (
          <div style={{ marginTop: 'var(--sp-3)' }}>
            <ErrorNotice error={error} />
          </div>
        )}
        {results && (
          <>
            <p className="muted" style={{ margin: 'var(--sp-3) 0 0' }} role="status">
              {results.length === 0
                ? `No hay coincidencias para «${query}».`
                : results.length === 1
                  ? '1 coincidencia.'
                  : `${results.length} coincidencias: elige la que quieres editar.`}
            </p>
            <ul className="result-list">
              {results.map((c) => (
                <li key={c.candidate_id}>
                  <button
                    className="result-item"
                    onClick={() => {
                      if (isRaster) {
                        onPickOcr({
                          id: c.candidate_id || c.node_id,
                          observation_id: c.candidate_id || c.node_id,
                          page: c.page,
                          text: c.text,
                          bbox: c.bbox,
                          confidence: (c as unknown as { confidence?: number }).confidence ?? 0,
                          engine: 'tesseract',
                          config: 'tsv',
                          provenance: 'PROBABILISTIC_OBSERVATION',
                          is_native_entity: false,
                          capability_state: 'RASTER_INSPECTION_READY',
                          editing_state: 'RASTER_EDITING_NOT_VERIFIABLE',
                        });
                      } else onPickNode(c.node_id, c.page);
                      onClose();
                    }}
                  >
                    <span className="tag">pág. {c.page + 1}</span> <span>{c.text}</span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
};
