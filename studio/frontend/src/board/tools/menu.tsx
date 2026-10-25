import React, { useMemo, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { getBoardTool } from './registry';
import {
  ALL_TOOLS,
  TOOL_CATEGORIES,
  filterToolLibrary,
  libraryEntryFor,
  type ToolCategoryFilter,
} from './library';

/**
 * Biblioteca de herramientas del «+ Más».
 *
 * Se navega con búsqueda y categorías, se ve una vista previa de la herramienta
 * elegida y se añade con el botón o con doble clic. La lista sale del registro;
 * este componente no conoce ninguna herramienta por su cuenta.
 */
export const BoardToolMenu: React.FC<{ onChoose: (id: string) => void }> = ({ onChoose }) => {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<ToolCategoryFilter>(ALL_TOOLS);
  const [selectedId, setSelectedId] = useState<string>('');
  const searchRef = useRef<HTMLInputElement | null>(null);

  const entries = useMemo(() => filterToolLibrary(query, category), [query, category]);
  const selected = entries.find((entry) => entry.id === selectedId) ?? entries[0] ?? null;

  const move = (delta: number) => {
    if (entries.length === 0) return;
    const index = selected ? entries.findIndex((entry) => entry.id === selected.id) : -1;
    const next = ((index + delta) % entries.length + entries.length) % entries.length;
    setSelectedId(entries[next].id);
  };

  const add = (id: string) => {
    if (!getBoardTool(id)) return;
    onChoose(id);
  };

  return (
    <div
      className="board-library"
      onKeyDown={(event) => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          move(event.key === 'ArrowDown' ? 1 : -1);
          return;
        }
        if (event.key === 'Enter' && event.target === searchRef.current && selected) {
          event.preventDefault();
          add(selected.id);
        }
      }}
    >
      <div className="board-library-search">
        <Search size={15} aria-hidden="true" />
        <input
          ref={searchRef}
          autoFocus
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar herramienta"
          aria-label="Buscar herramienta"
        />
        {query && (
          <button type="button" onClick={() => { setQuery(''); searchRef.current?.focus(); }} aria-label="Limpiar búsqueda">
            <X size={14} />
          </button>
        )}
      </div>

      <div className="board-library-categories" role="group" aria-label="Categorías de herramientas">
        <button
          type="button"
          className="board-library-chip"
          aria-pressed={category === ALL_TOOLS}
          onClick={() => setCategory(ALL_TOOLS)}
        >Todas</button>
        {TOOL_CATEGORIES.map((item) => (
          <button
            key={item}
            type="button"
            className="board-library-chip"
            aria-pressed={category === item}
            onClick={() => setCategory(item)}
          >{item}</button>
        ))}
      </div>

      <div className="board-library-body">
        <div className="board-library-list" role="listbox" aria-label="Herramientas del registro">
          {entries.length === 0 && (
            <p className="board-library-empty">Ninguna herramienta coincide. Prueba otro término o quita el filtro.</p>
          )}
          {entries.map((entry) => {
            const tool = getBoardTool(entry.id);
            const Icono = tool?.icono;
            const active = selected?.id === entry.id;
            return (
              <button
                key={entry.id}
                type="button"
                role="option"
                aria-selected={active}
                className={`board-library-item ${active ? 'is-selected' : ''}`}
                onClick={() => { setSelectedId(entry.id); }}
                onDoubleClick={() => add(entry.id)}
                onMouseEnter={() => setSelectedId(entry.id)}
                onFocus={() => setSelectedId(entry.id)}
              >
                <span className="board-library-item-icon">{Icono ? <Icono size={17} /> : null}</span>
                <span className="board-library-item-text">
                  <strong>{entry.nombre}</strong>
                  <small>{entry.categoria}</small>
                </span>
              </button>
            );
          })}
        </div>

        <aside className="board-library-preview" aria-live="polite" aria-label="Vista previa de la herramienta">
          {selected ? (() => {
            const tool = getBoardTool(selected.id);
            const Icono = tool?.icono;
            const entry = libraryEntryFor(selected.id, tool?.nombre ?? selected.nombre);
            return (
              <>
                <div className="board-library-preview-icon">{Icono ? <Icono size={26} /> : null}</div>
                <div className="board-library-preview-meta">
                  <span>{entry.categoria}</span>
                  <strong>{entry.nombre}</strong>
                </div>
                <p>{entry.descripcion}</p>
                <div className="board-library-preview-actions">
                  <button type="button" className="board-tool primary" onClick={() => add(entry.id)}>
                    Añadir al tablero
                  </button>
                  <small>Doble clic en la lista también añade.</small>
                </div>
              </>
            );
          })() : (
            <p className="board-library-empty">Elige una herramienta para ver qué hace.</p>
          )}
        </aside>
      </div>

      <div className="board-library-foot">
        <span>↑ ↓ elegir</span>
        <span>Enter añadir</span>
        <span>{entries.length} {entries.length === 1 ? 'herramienta' : 'herramientas'}</span>
      </div>
    </div>
  );
};
