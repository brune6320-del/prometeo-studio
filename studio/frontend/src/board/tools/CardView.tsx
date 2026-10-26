import React from 'react';
import type { BoardCard } from '../model';
import { getBoardTool, type BoardToolActions } from './registry';

/**
 * Pinta el contenido de una tarjeta preguntando al registro. Un tipo que esta versión
 * no conoce se muestra como «herramienta no instalada» y sus datos quedan intactos.
 */
export const BoardCardContent: React.FC<{
  card: BoardCard;
  editar: (card: BoardCard) => void;
  acciones?: BoardToolActions;
}> = React.memo(function BoardCardContent({ card, editar, acciones }) {
  const tool = getBoardTool(card.type);
  if (!tool) {
    return (
      <div className="board-card-unknown" role="status">
        <strong>Herramienta no instalada</strong>
        <span>Tipo «{card.type}». Los datos se conservan sin cambios.</span>
        {card.body ? <p className="board-card-unknown-body">{card.body}</p> : null}
      </div>
    );
  }
  const Vista = tool.Vista;
  return <Vista datos={card} editar={editar} acciones={acciones} />;
});
