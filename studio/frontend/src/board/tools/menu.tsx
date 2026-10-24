import React from 'react';
import { listBoardTools } from './registry';

/**
 * Lista de herramientas armada leyendo el registro. Añadir una herramienta nueva
 * no requiere tocar esta vista: basta con registrarla y traer su icono.
 */
export const BoardToolMenu: React.FC<{ onChoose: (id: string) => void }> = ({ onChoose }) => (
  <div className="board-tool-menu" role="menu" aria-label="Añadir tarjeta">
    {listBoardTools().map((tool) => {
      const Icono = tool.icono;
      return (
        <button
          key={tool.id}
          type="button"
          role="menuitem"
          className="board-tool-menu-item"
          onClick={() => onChoose(tool.id)}
        >
          {Icono ? <Icono size={15} /> : null}
          <span>{tool.nombre}</span>
        </button>
      );
    })}
  </div>
);
