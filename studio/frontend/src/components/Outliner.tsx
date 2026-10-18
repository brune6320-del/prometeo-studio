import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Folder, Image as ImageIcon, PenTool, Search, Type } from 'lucide-react';
import type { NodeSummary, NodeType } from '../types';
import { EmptyState, Spinner } from './ui';

interface OutlinerProps {
  pageCount: number;
  pageNodes: Record<number, NodeSummary[]>;
  pageLoading: boolean;
  selectedNodeId: string | null;
  stagedNodeIds: Set<string>;
  currentPage: number;
  loading: boolean;
  uiMode: 'user' | 'technical';
  onSelectNode: (nodeId: string, page: number) => void;
  onNavigatePage: (page: number) => void;
}

type Filter = 'ALL' | 'TEXT' | 'IMAGE' | 'VECTOR';
const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: 'ALL', label: 'Todo' },
  { id: 'TEXT', label: 'Texto' },
  { id: 'IMAGE', label: 'Imágenes' },
  { id: 'VECTOR', label: 'Vectores' },
];

function icon(type: NodeType) {
  if (type === 'TEXT') return <Type size={14} className="ic-text" aria-hidden="true" />;
  if (type === 'IMAGE') return <ImageIcon size={14} className="ic-image" aria-hidden="true" />;
  if (type === 'VECTOR') return <PenTool size={14} className="ic-vector" aria-hidden="true" />;
  return <Folder size={14} className="ic-group" aria-hidden="true" />;
}

const TYPE_LABEL: Record<string, string> = { TEXT: 'Texto', IMAGE: 'Imagen', VECTOR: 'Vector', GROUP: 'Grupo', PAGE: 'Página', DOCUMENT: 'Documento' };

/**
 * Contenido por página. Los nodos se cargan página a página (un documento largo puede tener
 * decenas de miles); la página actual está desplegada. Para buscar en todo el documento: ⌘F.
 */
export const Outliner: React.FC<OutlinerProps> = ({
  pageCount,
  pageNodes,
  pageLoading,
  selectedNodeId,
  stagedNodeIds,
  currentPage,
  loading,
  uiMode,
  onSelectNode,
  onNavigatePage,
}) => {
  const [filter, setFilter] = useState<Filter>('ALL');
  const [query, setQuery] = useState('');
  const [collapsedCurrent, setCollapsedCurrent] = useState(false);

  const visibleOnCurrent = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (pageNodes[currentPage] ?? []).filter((n) => {
      if (typeof n.page !== 'number') return false;
      if (uiMode === 'user' && (n.type === 'GROUP' || n.type === 'PAGE' || n.type === 'DOCUMENT')) return false;
      if (n.type === 'TEXT' && !(n.text || '').trim()) return false; // espacios: no hay nada que editar
      if (filter !== 'ALL' && n.type !== filter) return false;
      if (q && !(n.text || '').toLowerCase().includes(q) && !n.id.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [pageNodes, currentPage, filter, query, uiMode]);

  const pages = useMemo(() => Array.from({ length: pageCount }, (_, i) => i), [pageCount]);
  const listRef = useRef<HTMLUListElement>(null);

  // Al cambiar de página, mostrar su cabecera en la lista (documentos largos).
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-page-header="${currentPage}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [currentPage]);

  return (
    <section className="panel outliner-panel" aria-labelledby="outliner-title">
      <div className="panel-header">
        <h2 className="panel-title" id="outliner-title">
          Contenido
        </h2>
        <span className="tag" aria-label={`${pageCount} páginas`}>
          {pageCount} pág.
        </span>
      </div>
      <div className="panel-body">
        <div className="search-box">
          <Search size={14} aria-hidden="true" />
          <label htmlFor="outliner-filter" className="sr-only">
            Filtrar los elementos de la página actual
          </label>
          <input id="outliner-filter" className="input" placeholder="Filtrar esta página…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="chips" role="group" aria-label="Tipo de elemento">
          {FILTERS.map((f) => (
            <button key={f.id} className="chip" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
              {f.label}
            </button>
          ))}
        </div>
        <p className="hint" style={{ margin: '0 0 var(--sp-3)' }}>
          Para buscar en todo el documento usa <kbd>⌘</kbd> <kbd>F</kbd>.
        </p>

        {loading && pageCount === 0 ? (
          <div aria-busy="true" aria-label="Cargando contenido">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton" style={{ height: 22, margin: '8px 0', width: `${90 - i * 9}%` }} />
            ))}
          </div>
        ) : pageCount === 0 ? (
          <EmptyState title="Sin documento">
            <p>Cuando abras un PDF verás aquí sus textos e imágenes.</p>
          </EmptyState>
        ) : (
          <ul className="tree" aria-label="Páginas del documento" ref={listRef}>
            {pages.map((page) => {
              const isCurrent = page === currentPage;
              const expanded = isCurrent && !collapsedCurrent;
              return (
                <li key={page} className="tree-group">
                  <button
                    className="tree-page"
                    data-page-header={page}
                    aria-expanded={expanded}
                    aria-current={isCurrent ? 'page' : undefined}
                    onClick={() => {
                      if (isCurrent) setCollapsedCurrent((c) => !c);
                      else {
                        setCollapsedCurrent(false);
                        onNavigatePage(page);
                      }
                    }}
                  >
                    {expanded ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                    Página {page + 1}
                    {isCurrent && pageNodes[page] && <span className="subtle">· {visibleOnCurrent.length}</span>}
                    {isCurrent && pageLoading && !pageNodes[page] && <Spinner label="Cargando la página" />}
                  </button>
                  {expanded && pageNodes[page] && (
                    visibleOnCurrent.length === 0 ? (
                      <p className="hint" style={{ margin: '4px 0 0 var(--sp-5)' }}>
                        Nada coincide en esta página.
                      </p>
                    ) : (
                      <ul className="tree">
                        {visibleOnCurrent.map((n) => (
                          <li key={n.id}>
                            <button
                              className="tree-item"
                              data-node-id={n.id}
                              aria-pressed={selectedNodeId === n.id}
                              onClick={() => onSelectNode(n.id, page)}
                              title={n.text || n.id}
                            >
                              {icon(n.type)}
                              <span className="tree-item-text">
                                {n.text || (uiMode === 'technical' ? n.id : TYPE_LABEL[n.type] ?? n.type)}
                                <span className="sr-only">, {TYPE_LABEL[n.type] ?? n.type}</span>
                              </span>
                              {stagedNodeIds.has(n.id) ? (
                                <span className="staged-dot" title="Cambio preparado" aria-label="Cambio preparado" />
                              ) : uiMode === 'technical' && n.size ? (
                                <span className="tag">{Math.round(n.size)}pt</span>
                              ) : (
                                <span />
                              )}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
};
