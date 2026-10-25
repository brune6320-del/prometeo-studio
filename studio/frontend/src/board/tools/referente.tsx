import { useMemo, useState } from 'react';
import { BookOpen, ImagePlus, Plus, Trash2, X } from 'lucide-react';
import { createCard, isSafeExternalUrl, MAX_MEDIA_BYTES, type BoardCard, type BoardMedia } from '../model';
import {
  esTarjetaReferente,
  leerReferente,
  normalizarReferente,
  referenteMarkdown,
  referenteVacio,
  ultimaLectura,
  type Lectura,
  type Referente,
} from '../referentes/model';
import { filtrarLecturas, opcionesDeFiltro, ordenarLecturas } from '../referentes/historial';
import type { BoardTool } from './registry';
import { TituloEnSitio } from '../../components/InlineEdit';

function comoDatos(referente: Referente): Record<string, unknown> {
  return { ...referente };
}

function listaDesdeTexto(value: string): string[] {
  return value.split(/[,;\n]+/).map((item) => item.trim()).filter(Boolean);
}

function lecturaVacia(): Lectura {
  return { fecha: new Date().toISOString().slice(0, 10), proyecto: '', ojos: '', texto: '', modelo: '', aceptada: false };
}

export const referenteTool: BoardTool<BoardCard> = {
  id: 'referente',
  nombre: 'Referente',
  tipo: 'tarjeta',
  icono: BookOpen,
  crear: (x, y) => createReferenteCard(x, y),
  validar: esTarjetaReferente,
  Vista: ({ datos, editar }) => {
    const [editando, setEditando] = useState(false);
    const [borrador, setBorrador] = useState<Referente>(() => leerReferente(datos));
    const [etiquetas, setEtiquetas] = useState(() => leerReferente(datos).etiquetas.join(', '));
    const [vistoEn, setVistoEn] = useState(() => leerReferente(datos).vistoEn.join(', '));
    const [panel, setPanel] = useState<'ficha' | 'historial'>('ficha');
    const [filtroProyecto, setFiltroProyecto] = useState('');
    const [filtroOjos, setFiltroOjos] = useState('');
    const referente = editando ? borrador : leerReferente(datos);
    const lectura = ultimaLectura(referente);
    const principal = referente.imagenes[0];
    const historial = useMemo(() => {
      const opciones = opcionesDeFiltro(referente);
      const lecturas = ordenarLecturas(referente.lecturas);
      return {
        opciones,
        lecturas,
        filtradas: filtrarLecturas(lecturas, { proyecto: filtroProyecto, ojos: filtroOjos }),
      };
    }, [referente, filtroProyecto, filtroOjos]);

    const empezarEdicion = () => {
      const actual = leerReferente(datos);
      setBorrador(actual);
      setEtiquetas(actual.etiquetas.join(', '));
      setVistoEn(actual.vistoEn.join(', '));
      setEditando(true);
    };

    const cambiar = (patch: Partial<Referente>) => setBorrador((previo) => ({ ...previo, ...patch }));

    const cambiarLectura = (index: number, patch: Partial<Lectura>) => {
      setBorrador((previo) => ({
        ...previo,
        lecturas: previo.lecturas.map((item, i) => (i === index ? { ...item, ...patch } : item)),
      }));
    };

    const anadirImagenes = (files: FileList | null) => {
      if (!files) return;
      for (const file of Array.from(files)) {
        if (!file.type.startsWith('image/') || file.size > MAX_MEDIA_BYTES) continue;
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = typeof reader.result === 'string' ? reader.result : '';
          if (!dataUrl.startsWith(`data:${file.type};base64,`)) return;
          const imagen: BoardMedia = { name: file.name, mimeType: file.type, dataUrl, kind: 'image' };
          setBorrador((previo) => ({ ...previo, imagenes: [...previo.imagenes, imagen] }));
        };
        reader.readAsDataURL(file);
      }
    };

    const guardar = () => {
      const siguiente = normalizarReferente({
        ...borrador,
        etiquetas: listaDesdeTexto(etiquetas),
        vistoEn: listaDesdeTexto(vistoEn),
      });
      editar({ ...datos, title: siguiente.nombre.trim() || datos.title, datos: comoDatos(siguiente) });
      setEditando(false);
    };

    if (editando) {
      return (
        <div className="board-referente-editor" onDoubleClick={(event) => event.stopPropagation()}>
          <div className="board-referente-form">
            <label>Nombre<input value={borrador.nombre} maxLength={200} onChange={(event) => cambiar({ nombre: event.target.value })} autoFocus /></label>
            <label>URL de la fuente<input value={borrador.url} maxLength={2048} onChange={(event) => cambiar({ url: event.target.value })} placeholder="https://…" /></label>
            <div className="board-referente-row">
              <label>Archivo de origen<input value={borrador.archivoOrigen} maxLength={500} onChange={(event) => cambiar({ archivoOrigen: event.target.value })} /></label>
              <label>Año<input value={borrador.anio} maxLength={20} onChange={(event) => cambiar({ anio: event.target.value })} /></label>
            </div>
            <div className="board-referente-row">
              <label>Autor<input value={borrador.autor} maxLength={200} onChange={(event) => cambiar({ autor: event.target.value })} /></label>
              <label>Licencia<input value={borrador.licencia} maxLength={200} onChange={(event) => cambiar({ licencia: event.target.value })} /></label>
            </div>
            <label>Por qué lo guardé<textarea value={borrador.porQue} maxLength={6000} onChange={(event) => cambiar({ porQue: event.target.value })} /></label>
            <label>Etiquetas<input value={etiquetas} onChange={(event) => setEtiquetas(event.target.value)} placeholder="collage, tipografía, archivo" /></label>
            <label>Visto en<input value={vistoEn} onChange={(event) => setVistoEn(event.target.value)} placeholder="2026-10-24, 2026-09-02" /></label>
          </div>

          <div className="board-referente-seccion">
            <span className="board-referente-label">Imágenes</span>
            <div className="board-referente-thumbs">
              {borrador.imagenes.map((imagen, index) => (
                <figure key={`${imagen.name}-${index}`} title={imagen.fuente ? `${imagen.fuente}${imagen.fecha ? ` · ${imagen.fecha}` : ''}` : imagen.name}>
                  <img src={imagen.dataUrl} alt={imagen.name} />
                  <button type="button" onClick={() => cambiar({ imagenes: borrador.imagenes.filter((_, i) => i !== index) })} aria-label={`Quitar ${imagen.name}`}><X size={11} /></button>
                  {imagen.fuente && (
                    <figcaption>
                      {imagen.fecha && <span>{imagen.fecha}</span>}
                      <a href={imagen.fuente} target="_blank" rel="noreferrer">fuente</a>
                    </figcaption>
                  )}
                </figure>
              ))}
            </div>
            <label className="board-referente-file">
              <ImagePlus size={13} /> Añadir imagen
              <input type="file" accept="image/*" multiple onChange={(event) => { anadirImagenes(event.target.files); event.target.value = ''; }} />
            </label>
          </div>

          <div className="board-referente-seccion">
            <div className="board-referente-seccion-head">
              <span className="board-referente-label">Lecturas</span>
              <button type="button" onClick={() => cambiar({ lecturas: [...borrador.lecturas, lecturaVacia()] })}><Plus size={12} /> Añadir</button>
            </div>
            {borrador.lecturas.length === 0 && <p className="board-referente-vacio">Sin lecturas todavía.</p>}
            {borrador.lecturas.map((item, index) => (
              <div className="board-referente-lectura-edit" key={index}>
                <div className="board-referente-row">
                  <label>Fecha<input value={item.fecha} maxLength={40} onChange={(event) => cambiarLectura(index, { fecha: event.target.value })} /></label>
                  <label>Proyecto<input value={item.proyecto} maxLength={200} onChange={(event) => cambiarLectura(index, { proyecto: event.target.value })} /></label>
                </div>
                <div className="board-referente-row">
                  <label>Ojos<input value={item.ojos} maxLength={200} onChange={(event) => cambiarLectura(index, { ojos: event.target.value })} /></label>
                  <label>Modelo<input value={item.modelo} maxLength={200} onChange={(event) => cambiarLectura(index, { modelo: event.target.value })} /></label>
                </div>
                <label>Texto<textarea value={item.texto} maxLength={6000} onChange={(event) => cambiarLectura(index, { texto: event.target.value })} /></label>
                <div className="board-referente-lectura-foot">
                  <label className="board-referente-check"><input type="checkbox" checked={item.aceptada} onChange={(event) => cambiarLectura(index, { aceptada: event.target.checked })} /> Aceptada</label>
                  <button type="button" onClick={() => cambiar({ lecturas: borrador.lecturas.filter((_, i) => i !== index) })} aria-label="Quitar lectura"><Trash2 size={12} /></button>
                </div>
              </div>
            ))}
          </div>

          <div className="board-referente-actions">
            <button type="button" onClick={() => setEditando(false)}>Cancelar</button>
            <button type="button" className="board-referente-save" onClick={guardar}>Guardar</button>
          </div>
        </div>
      );
    }

    return (
      <div
        className="board-referente"
        onDoubleClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          empezarEdicion();
        }}
        title="Doble clic para editar"
      >
        <TituloEnSitio
          value={referente.nombre}
          onCommit={(nombre) => {
            const actual = leerReferente(datos);
            editar({ ...datos, title: nombre, datos: comoDatos({ ...actual, nombre }) });
          }}
          ariaLabel="Título del referente"
          className="board-referente-nombre"
          placeholder="Referente sin nombre"
        />
        <div className="board-referente-tabs" role="tablist" aria-label="Vista del referente" onDoubleClick={(event) => event.stopPropagation()}>
          <button type="button" role="tab" aria-selected={panel === 'ficha'} className={panel === 'ficha' ? 'active' : ''} onClick={(event) => { event.stopPropagation(); setPanel('ficha'); }}>Ficha</button>
          <button type="button" role="tab" aria-selected={panel === 'historial'} className={panel === 'historial' ? 'active' : ''} onClick={(event) => { event.stopPropagation(); setPanel('historial'); }}>Historial{referente.lecturas.length ? ` (${referente.lecturas.length})` : ''}</button>
        </div>
        {panel === 'historial' ? (
          <div className="board-referente-historial" onDoubleClick={(event) => event.stopPropagation()}>
            <div className="board-referente-filtros">
              <label>Proyecto
                <select value={filtroProyecto} onChange={(event) => setFiltroProyecto(event.target.value)} onClick={(event) => event.stopPropagation()}>
                  <option value="">Todos</option>
                  {historial.opciones.proyectos.map((proyecto) => <option key={proyecto} value={proyecto}>{proyecto}</option>)}
                </select>
              </label>
              <label>Ojos
                <select value={filtroOjos} onChange={(event) => setFiltroOjos(event.target.value)} onClick={(event) => event.stopPropagation()}>
                  <option value="">Todos</option>
                  {historial.opciones.ojos.map((ojos) => <option key={ojos} value={ojos}>{ojos}</option>)}
                </select>
              </label>
            </div>
            {(filtroProyecto || filtroOjos) && historial.filtradas.length > 0 && (
              <p className="board-referente-historial-count">
                {historial.filtradas.length} de {historial.lecturas.length} lecturas
              </p>
            )}
            {historial.filtradas.length === 0 ? (
              <p className="board-referente-vacio">
                {historial.lecturas.length ? 'Ninguna lectura coincide con este filtro.' : 'Sin lecturas todavía.'}
              </p>
            ) : (
              <ol className="board-referente-timeline">
                {historial.filtradas.map((item, index) => (
                  <li key={`${item.fecha}-${index}`} className={item.aceptada ? '' : 'propuesta'}>
                    <div className="board-referente-timeline-meta">
                      <time>{item.fecha || 'Sin fecha'}</time>
                      {item.ojos && <span>{item.ojos}</span>}
                      {item.proyecto && <span>{item.proyecto}</span>}
                    </div>
                    {item.texto && <p>{item.texto}</p>}
                    {!item.aceptada && <span className="board-referente-propuesta">Propuesta sin aceptar</span>}
                  </li>
                ))}
              </ol>
            )}
          </div>
        ) : (
          <>
            {principal ? (
              <img className="board-referente-imagen" src={principal.dataUrl} alt={referente.nombre || principal.name} draggable={false} />
            ) : (
              <button type="button" className="board-referente-noimg" onClick={(event) => { event.stopPropagation(); empezarEdicion(); }} title="Añadir una imagen al referente">Añadir imagen</button>
            )}
            <div className="board-referente-meta">
              <span>{referente.archivoOrigen || 'archivo sin nombre'} · {referente.anio || 's.f.'}</span>
              {referente.url && isSafeExternalUrl(referente.url) && (
                <a href={referente.url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>Fuente</a>
              )}
            </div>
            {referente.etiquetas.length > 0 && (
              <div className="board-referente-etiquetas">
                {referente.etiquetas.map((etiqueta) => <span key={etiqueta}>{etiqueta}</span>)}
              </div>
            )}
            <div className="board-referente-porque">
              <span className="board-referente-label">Por qué lo guardé</span>
              <p>{referente.porQue.trim() || 'Sin nota todavía.'}</p>
            </div>
            {lectura && (
              <blockquote className="board-referente-lectura">
                <span>{[lectura.fecha, lectura.ojos, lectura.proyecto].filter(Boolean).join(' · ') || 'Lectura sin fecha'}</span>
                {lectura.texto && <p>{lectura.texto}</p>}
              </blockquote>
            )}
            <span className="board-referente-hint">Doble clic para editar · pega una URL de imagen</span>
          </>
        )}
      </div>
    );
  },
  exportarMarkdown: (datos) => referenteMarkdown(leerReferente(datos)),
};

function createReferenteCard(x: number, y: number) {
  return {
    ...createCard('referente', x, y),
    title: 'Nuevo referente',
    width: 320,
    datos: comoDatos(referenteVacio()),
  };
}
