import { useEffect, useRef, useState } from 'react';
import { Bold, Code2, Heading2, Italic, List, Quote, StickyNote } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';
import { MarkdownLite } from '../../components/MarkdownLite';

type Formato = 'titulo' | 'negrita' | 'cursiva' | 'lista' | 'codigo' | 'cita';

/** Envuelve la selección o la prefija según el formato pedido. El texto sigue siendo Markdown. */
function aplicarFormato(texto: string, inicio: number, fin: number, formato: Formato): { texto: string; cursor: number } {
  const seleccion = texto.slice(inicio, fin);
  const antes = texto.slice(0, inicio);
  const despues = texto.slice(fin);
  if (formato === 'negrita') {
    const cuerpo = seleccion || 'texto';
    return { texto: `${antes}**${cuerpo}**${despues}`, cursor: inicio + cuerpo.length + 4 };
  }
  if (formato === 'cursiva') {
    const cuerpo = seleccion || 'texto';
    return { texto: `${antes}_${cuerpo}_${despues}`, cursor: inicio + cuerpo.length + 2 };
  }
  if (formato === 'codigo') {
    const cuerpo = seleccion || 'código';
    return { texto: `${antes}\`${cuerpo}\`${despues}`, cursor: inicio + cuerpo.length + 2 };
  }
  const prefijo = formato === 'titulo' ? '# ' : formato === 'lista' ? '- ' : '> ';
  const lineaInicio = antes.lastIndexOf('\n') + 1;
  const prefijado = `${texto.slice(0, lineaInicio)}${prefijo}${texto.slice(lineaInicio)}`;
  return { texto: prefijado, cursor: inicio + prefijo.length + (fin - inicio) };
}

const BOTONES: Array<{ id: Formato; label: string; icono: React.ComponentType<{ size?: number }> }> = [
  { id: 'titulo', label: 'Título', icono: Heading2 },
  { id: 'negrita', label: 'Negrita', icono: Bold },
  { id: 'cursiva', label: 'Cursiva', icono: Italic },
  { id: 'lista', label: 'Lista', icono: List },
  { id: 'cita', label: 'Cita', icono: Quote },
  { id: 'codigo', label: 'Código', icono: Code2 },
];

const NotaRica = ({ datos, editar }: { datos: BoardCard; editar: (datos: BoardCard) => void }) => {
  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState(datos.body);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const cerrado = useRef(false);

  useEffect(() => {
    if (!editando) setBorrador(datos.body);
  }, [datos.body, editando]);

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
    if (borrador !== datos.body) editar({ ...datos, body: borrador });
    setEditando(false);
  };
  const cancelar = () => {
    cerrado.current = true;
    setBorrador(datos.body);
    setEditando(false);
  };
  const formatear = (formato: Formato) => {
    const area = areaRef.current;
    if (!area) return;
    const resultado = aplicarFormato(borrador, area.selectionStart, area.selectionEnd, formato);
    setBorrador(resultado.texto);
    window.requestAnimationFrame(() => {
      area.focus();
      area.setSelectionRange(resultado.cursor, resultado.cursor);
    });
  };

  if (editando) {
    return (
      <div className="board-note-editor">
        <div className="board-note-toolbar" role="toolbar" aria-label="Formato de la nota">
          {BOTONES.map(({ id, label, icono: Icono }) => (
            <button key={id} type="button" onPointerDown={(event) => event.stopPropagation()} onClick={() => formatear(id)} title={label} aria-label={label}>
              <Icono size={13} />
            </button>
          ))}
          <span className="board-note-toolbar-hint">⌘/Ctrl + Enter guarda</span>
        </div>
        <textarea
          ref={areaRef}
          className="board-card-text-editor"
          value={borrador}
          maxLength={12000}
          aria-label="Contenido de la nota con formato"
          onChange={(event) => setBorrador(event.target.value)}
          onBlur={guardar}
          onClick={(event) => event.stopPropagation()}
          onPointerDown={(event) => event.stopPropagation()}
          onKeyDown={(event) => {
            event.stopPropagation();
            if (event.key === 'Escape') {
              event.preventDefault();
              cancelar();
            } else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              guardar();
            }
          }}
        />
      </div>
    );
  }

  return (
    <div
      className="board-note-read"
      title="Doble clic para editar con formato"
      onDoubleClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        cerrado.current = false;
        setBorrador(datos.body);
        setEditando(true);
      }}
    >
      <MarkdownLite value={datos.body} placeholder="Escribe una idea…" />
    </div>
  );
};

export const noteTool: BoardTool<BoardCard> = {
  id: 'note',
  nombre: 'Nota',
  tipo: 'tarjeta',
  icono: StickyNote,
  crear: (x, y) => createCard('note', x, y),
  validar: esTarjetaDe('note'),
  Vista: ({ datos, editar }) => <NotaRica datos={datos} editar={editar} />,
};
