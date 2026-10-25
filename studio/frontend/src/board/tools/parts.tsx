import React from 'react';
import type { BoardCard } from '../model';
import { TextoEnSitio } from '../../components/InlineEdit';

/** Cuerpo de texto común a las herramientas que ya existían (nota, enlace y medio). */
export const CuerpoTexto: React.FC<{
  datos: BoardCard;
  editar: (datos: BoardCard) => void;
  placeholder: string;
}> = ({ datos, editar, placeholder }) => (
  <TextoEnSitio
    value={datos.body}
    onCommit={(body) => editar({ ...datos, body })}
    placeholder={placeholder}
    ariaLabel="Contenido de tarjeta"
  />
);
