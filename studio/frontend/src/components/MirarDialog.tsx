import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Eye, RefreshCw, X } from 'lucide-react';
import type { BoardDocument } from '../board/model';
import { pedirLecturas, type LecturaPedida } from '../board/referentes/deepseek';
import {
  motivoSeleccion,
  nuevaSemilla,
  seleccionarReferentes,
  type ReferenteElegido,
  type SeleccionMirada,
} from '../board/referentes/mirar';
import type { Lectura } from '../board/referentes/model';
import { useFocusTrap } from './useFocusTrap';
import { OJOS } from '../board/referentes/ojos';

interface MirarDialogProps {
  boards: readonly BoardDocument[];
  activeBoardId: string;
  tableroNombre: string;
  proyecto: string;
  onClose: () => void;
  onAceptar: (boardId: string, cardId: string, lectura: Lectura) => void;
}

interface Propuesta extends LecturaPedida {
  boardId: string;
  cardId: string;
  nombre: string;
  motivo: ReferenteElegido['motivo'];
  ojos: string;
  fecha: string;
}

function hoy(): string {
  return new Date().toISOString().slice(0, 10);
}

export const MirarDialog: React.FC<MirarDialogProps> = ({
  boards,
  activeBoardId,
  tableroNombre,
  proyecto,
  onClose,
  onAceptar,
}) => {
  const [semilla, setSemilla] = useState(() => nuevaSemilla());
  const [ojosId, setOjosId] = useState(() => OJOS[0].id);
  const [propuestas, setPropuestas] = useState<Propuesta[] | null>(null);
  const [fijada, setFijada] = useState<SeleccionMirada | null>(null);
  const [cargando, setCargando] = useState(false);
  const [aviso, setAviso] = useState('');

  const seleccion = useMemo(
    () => seleccionarReferentes(boards, activeBoardId, semilla, ojosId),
    [activeBoardId, boards, ojosId, semilla],
  );

  const dialogRef = useRef<HTMLElement>(null);
  useFocusTrap(true, dialogRef);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !cargando) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [cargando, onClose]);

  const cambiarSemilla = (value: string) => {
    setSemilla(value);
    setPropuestas(null);
    setFijada(null);
    setAviso('');
  };

  const cambiarOjos = (value: string) => {
    setOjosId(value);
    setPropuestas(null);
    setFijada(null);
    setAviso('');
  };

  const mirar = async () => {
    if (!seleccion.elegidos.length || cargando) return;
    setCargando(true);
    setAviso('');
    setPropuestas(null);
    setFijada(seleccion);
    const resultado = await pedirLecturas(proyecto, seleccion.ojos, seleccion.elegidos);
    const fecha = hoy();
    setPropuestas(
      seleccion.elegidos.map((elegido, index) => ({
        boardId: elegido.boardId,
        cardId: elegido.cardId,
        nombre: elegido.nombre,
        motivo: elegido.motivo,
        ojos: seleccion.ojos.nombre,
        fecha,
        texto: resultado.lecturas[index]?.texto ?? '',
        modelo: resultado.lecturas[index]?.modelo || (resultado.disponible ? 'deepseek-chat' : 'manual'),
      })),
    );
    if (!resultado.disponible) {
      setAviso(resultado.motivo || 'El ritual sigue en blanco: escribe cada lectura a mano.');
    }
    setCargando(false);
  };

  const editarTexto = (index: number, texto: string) => {
    setPropuestas((actual) => actual?.map((propuesta, i) => (i === index ? { ...propuesta, texto } : propuesta)) ?? actual);
  };

  const aceptar = (index: number) => {
    const propuesta = propuestas?.[index];
    if (!propuesta) return;
    const texto = propuesta.texto.trim();
    if (!texto) return;
    onAceptar(propuesta.boardId, propuesta.cardId, {
      fecha: propuesta.fecha,
      proyecto,
      ojos: propuesta.ojos,
      texto,
      modelo: propuesta.modelo || 'manual',
      aceptada: true,
    });
    setPropuestas((actual) => actual?.filter((_, i) => i !== index) ?? actual);
  };

  const descartar = (index: number) => {
    setPropuestas((actual) => actual?.filter((_, i) => i !== index) ?? actual);
  };

  const hayReferentes = seleccion.elegidos.length > 0;
  const completado = propuestas !== null && propuestas.length === 0;
  const visibles = fijada ?? seleccion;

  return (
    <div
      className="board-dialog-backdrop"
      onMouseDown={(event) => { if (event.target === event.currentTarget && !cargando) onClose(); }}
    >
      <section
        ref={(element) => { dialogRef.current = element; }}
        className="board-dialog board-mirar-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="board-mirar-title"
      >
        <div className="board-dialog-heading">
          <h2 id="board-mirar-title"><Eye size={17} aria-hidden="true" /> Volver a mirar con otros ojos</h2>
          <button type="button" onClick={onClose} aria-label="Cerrar" disabled={cargando}><X size={16} /></button>
        </div>

        <p className="board-dialog-hint">
          {proyecto} · tablero «{tableroNombre}». Las lecturas son propuestas: nada cambia hasta que aceptes.
        </p>

        <div className="board-mirar-ojos">
          <label>
            Ojos
            <select value={seleccion.ojos.id} onChange={(event) => cambiarOjos(event.target.value)}>
              {OJOS.map((ojos) => <option key={ojos.id} value={ojos.id}>{ojos.nombre}</option>)}
            </select>
          </label>
          <p><strong>{seleccion.ojos.nombre}.</strong> {seleccion.ojos.comoMira}</p>
          <p className="board-mirar-fuente">Fuente: {seleccion.ojos.fuente}</p>
        </div>

        <div className="board-mirar-semilla">
          <label>
            Semilla
            <input value={semilla} maxLength={40} onChange={(event) => cambiarSemilla(event.target.value)} />
          </label>
          <button type="button" className="board-tool" onClick={() => cambiarSemilla(nuevaSemilla())} title="Otra tirada con una semilla nueva">
            <RefreshCw size={13} /> Otra tirada
          </button>
        </div>

        <div className="board-mirar-seleccion">
          <span className="board-referente-label">Tres referentes</span>
          {!hayReferentes && (
            <p className="board-dialog-hint">Todavía no hay referentes. Importa la Biblioteca primero.</p>
          )}
          <ol>
            {visibles.elegidos.map((elegido) => (
              <li key={`${elegido.boardId}:${elegido.cardId}`}>
                <span>{elegido.nombre}</span>
                <small>{motivoSeleccion(elegido.motivo)}</small>
              </li>
            ))}
          </ol>
        </div>

        <div className="board-mirar-acciones">
          <button type="button" className="board-tool primary" onClick={() => void mirar()} disabled={!hayReferentes || cargando}>
            <Eye size={14} /> {cargando ? 'Mirando…' : propuestas === null ? 'Mirar' : 'Volver a mirar'}
          </button>
          {cargando && <span className="board-mirar-estado" role="status">Preguntando a DeepSeek a través del motor local…</span>}
        </div>

        {aviso && <p className="board-mirar-aviso" role="status">{aviso}</p>}

        {propuestas?.map((propuesta, index) => (
          <article className="board-mirar-propuesta" key={`${propuesta.boardId}:${propuesta.cardId}`}>
            <header>
              <strong>{propuesta.nombre}</strong>
              <small>{motivoSeleccion(propuesta.motivo)} · {propuesta.ojos}</small>
            </header>
            <label>
              Lectura
              <textarea
                rows={5}
                maxLength={1200}
                value={propuesta.texto}
                onChange={(event) => editarTexto(index, event.target.value)}
                placeholder="Escribe aquí lo que ves con estos ojos. Máximo 120 palabras."
              />
            </label>
            <footer>
              <span className="board-mirar-modelo">{propuesta.modelo || 'manual'}</span>
              <button type="button" className="board-tool" onClick={() => descartar(index)}>Descartar</button>
              <button type="button" className="board-tool primary" onClick={() => aceptar(index)} disabled={!propuesta.texto.trim()}>Aceptar</button>
            </footer>
          </article>
        ))}

        {completado && (
          <p className="board-mirar-completado" role="status">
            Ritual completado. Lo aceptado quedó en su referente; lo descartado no dejó rastro.
          </p>
        )}
      </section>
    </div>
  );
};
