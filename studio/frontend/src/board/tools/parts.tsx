import React from 'react';
import type { BoardCard } from '../model';

/** Cuerpo de texto común a las herramientas que ya existían (nota, enlace y medio). */
export const CuerpoTexto: React.FC<{
  datos: BoardCard;
  editar: (datos: BoardCard) => void;
  placeholder: string;
}> = ({ datos, editar, placeholder }) => (
  <textarea
    className="board-card-body"
    value={datos.body}
    maxLength={12000}
    onChange={(event) => editar({ ...datos, body: event.target.value })}
    placeholder={placeholder}
    aria-label="Contenido de tarjeta"
  />
);
