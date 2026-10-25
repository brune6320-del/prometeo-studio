import type { FC } from 'react';
import type { EntropiaDatos, FuenteEntropia } from '../vanguardia/entropia';

export interface EntropiaVistaProps {
  datos: EntropiaDatos | null;
  fuentes: readonly FuenteEntropia[];
  onTirar?: () => void;
  onOtra?: () => void;
  onLike?: () => void;
  onNope?: () => void;
}

function nombresFuentes(datos: EntropiaDatos, fuentes: readonly FuenteEntropia[]): string {
  const porId = new Map(fuentes.map((fuente) => [fuente.id, fuente.nombre]));
  return datos.fuentes.map((id) => porId.get(id) || id).join(', ');
}

export const EntropiaVista: FC<EntropiaVistaProps> = ({
  datos,
  fuentes,
  onTirar,
  onOtra,
  onLike,
  onNope,
}) => {
  const porId = new Map(fuentes.map((fuente) => [fuente.id, fuente]));
  const ancho = datos?.ancho ?? 1;
  const alto = datos?.alto ?? 1;

  return (
    <section
      className={`board-entropia ${datos ? (datos.guardado ? 'guardado' : 'vivo') : 'vacio'}`}
      data-entropia={datos ? (datos.guardado ? 'guardado' : 'vivo') : 'vacio'}
      data-semilla={datos?.semilla ?? ''}
    >
      {datos ? (
        <header className="board-entropia-meta" data-testid="entropia-meta">
          <span className="board-entropia-semilla">{datos.semilla}</span>
          <span aria-hidden="true"> · </span>
          <span>{datos.reglaNombre || datos.regla}</span>
          <span aria-hidden="true"> · </span>
          <span>{datos.restriccion || 'sin restricción'}</span>
          <span aria-hidden="true"> · </span>
          <span>{nombresFuentes(datos, fuentes)}</span>
        </header>
      ) : (
        <p className="board-entropia-vacio">Sin tirada todavía. Pulsa «Tirar» para pedir una combinación.</p>
      )}

      {datos && (
        <div className="board-entropia-lienzo" aria-label="Collage de entropía">
          {datos.disposicion.map((pieza) => {
            const fuente = porId.get(pieza.id);
            const recorte = pieza.recorte ?? { x: 0, y: 0, w: 1, h: 1 };
            return (
              <div
                key={pieza.id}
                className={`board-entropia-pieza ${fuente?.imagen ? '' : 'sin-imagen'}`}
                data-pieza-id={pieza.id}
                style={{
                  left: `${(pieza.x / ancho) * 100}%`,
                  top: `${(pieza.y / alto) * 100}%`,
                  width: `${(pieza.w / ancho) * 100}%`,
                  height: `${(pieza.h / alto) * 100}%`,
                  zIndex: pieza.z,
                  transform: pieza.rot ? `rotate(${pieza.rot}deg)` : undefined,
                }}
              >
                {fuente?.imagen ? (
                  <img
                    src={fuente.imagen.src}
                    alt={fuente.nombre || fuente.imagen.nombre}
                    draggable={false}
                    style={{
                      position: 'absolute',
                      left: `${(-recorte.x / recorte.w) * 100}%`,
                      top: `${(-recorte.y / recorte.h) * 100}%`,
                      width: `${(1 / recorte.w) * 100}%`,
                      height: `${(1 / recorte.h) * 100}%`,
                      maxWidth: 'none',
                    }}
                  />
                ) : (
                  <span>{fuente?.nombre || pieza.id}</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {datos && !datos.guardado && (
        <div className="board-entropia-acciones">
          <button type="button" className="board-entropia-otra" onClick={onOtra} title="Tirar con una semilla nueva">Otra</button>
          <button type="button" className="board-entropia-like" aria-label="♥ Me gusta y guardar" title="♥ Guardar en el tablero y recordar el gusto" onClick={onLike}>♥</button>
          <button type="button" className="board-entropia-nope" aria-label="✕ No me gusta" title="✕ Solo recordar que no me gusta" onClick={onNope}>✕</button>
        </div>
      )}

      {!datos && onTirar && (
        <div className="board-entropia-acciones">
          <button type="button" className="board-entropia-tirar" onClick={onTirar}>Tirar</button>
        </div>
      )}
    </section>
  );
};
