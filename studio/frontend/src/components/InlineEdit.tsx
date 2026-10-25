import React, { useEffect, useRef, useState } from 'react';

interface TituloEnSitioProps {
  value: string;
  onCommit: (value: string) => void;
  ariaLabel: string;
  className?: string;
  placeholder?: string;
}

/** Doble clic edita en el sitio. Enter o clic fuera guarda; Escape cancela. */
export const TituloEnSitio: React.FC<TituloEnSitioProps> = ({ value, onCommit, ariaLabel, className = '', placeholder = 'Sin título' }) => {
  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const cerrado = useRef(false);

  useEffect(() => {
    if (!editando) setBorrador(value);
  }, [value, editando]);

  useEffect(() => {
    if (editando) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editando]);

  const guardar = () => {
    if (cerrado.current) return;
    cerrado.current = true;
    const limpio = borrador.trim();
    if (limpio && limpio !== value) onCommit(limpio);
    setEditando(false);
  };

  const cancelar = () => {
    cerrado.current = true;
    setBorrador(value);
    setEditando(false);
  };

  if (editando) {
    return (
      <input
        ref={inputRef}
        className={`board-inline-input ${className}`}
        value={borrador}
        maxLength={200}
        aria-label={ariaLabel}
        onChange={(event) => setBorrador(event.target.value)}
        onBlur={guardar}
        onClick={(event) => event.stopPropagation()}
        onDoubleClick={(event) => event.stopPropagation()}
        onPointerDown={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === 'Enter') {
            event.preventDefault();
            guardar();
          } else if (event.key === 'Escape') {
            event.preventDefault();
            cancelar();
          }
        }}
      />
    );
  }

  return (
    <span
      className={`board-inline-text ${className} ${value ? '' : 'is-empty'}`}
      title="Doble clic para editar"
      onDoubleClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        cerrado.current = false;
        setBorrador(value);
        setEditando(true);
      }}
    >
      {value || placeholder}
    </span>
  );
};

interface TextoEnSitioProps {
  value: string;
  onCommit: (value: string) => void;
  placeholder: string;
  ariaLabel: string;
  className?: string;
}

/** Cuerpo de tarjeta: texto en reposo, textarea solo al doble clic. */
export const TextoEnSitio: React.FC<TextoEnSitioProps> = ({ value, onCommit, placeholder, ariaLabel, className = '' }) => {
  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState(value);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const cerrado = useRef(false);

  useEffect(() => {
    if (!editando) setBorrador(value);
  }, [value, editando]);

  useEffect(() => {
    if (editando) {
      const area = areaRef.current;
      if (area) {
        area.focus();
        area.setSelectionRange(area.value.length, area.value.length);
      }
    }
  }, [editando]);

  const guardar = () => {
    if (cerrado.current) return;
    cerrado.current = true;
    if (borrador !== value) onCommit(borrador);
    setEditando(false);
  };

  const cancelar = () => {
    cerrado.current = true;
    setBorrador(value);
    setEditando(false);
  };

  if (editando) {
    return (
      <textarea
        ref={areaRef}
        className={`board-card-text-editor ${className}`}
        value={borrador}
        maxLength={12000}
        aria-label={ariaLabel}
        onChange={(event) => setBorrador(event.target.value)}
        onBlur={guardar}
        onClick={(event) => event.stopPropagation()}
        onDoubleClick={(event) => event.stopPropagation()}
        onPointerDown={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === 'Escape') {
            event.preventDefault();
            cancelar();
          } else if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            guardar();
          }
        }}
      />
    );
  }

  return (
    <div
      className={`board-card-text ${className} ${value ? '' : 'is-empty'}`}
      title="Doble clic para editar"
      onDoubleClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        cerrado.current = false;
        setBorrador(value);
        setEditando(true);
      }}
    >
      {value || placeholder}
    </div>
  );
};
