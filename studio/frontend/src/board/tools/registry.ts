import type React from 'react';
import type { BoardCard } from '../model';
import { linkTool } from './link';
import { mediaTool } from './media';
import { noteTool } from './note';
import { etiquetaTool } from './etiqueta';
import { marcoTool } from './marco';
import { referenteTool } from './referente';

/**
 * Contrato de una herramienta de la pizarra (skill prometeo-herramientas).
 * Añadir una herramienta = un archivo nuevo + una línea de registro.
 */
export interface BoardTool<D = unknown> {
  id: string;
  nombre: string;
  tipo: 'tarjeta' | 'marco';
  /** Icono para el menú «+»; vive en el archivo de la herramienta. */
  icono?: React.ComponentType<{ size?: number }>;
  crear(x: number, y: number): D;
  validar(d: unknown): d is D;
  Vista: React.FC<{ datos: D; hijos?: BoardCard[]; editar: (d: D) => void }>;
  exportarMarkdown?(d: D): string;
}

// El registro guarda herramientas con datos heterogéneos; cada Vista valida su propio D.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyBoardTool = BoardTool<any>;

const registry = new Map<string, AnyBoardTool>();

export function registerBoardTool(tool: AnyBoardTool): void {
  if (registry.has(tool.id)) throw new Error(`La herramienta «${tool.id}» ya está registrada.`);
  registry.set(tool.id, tool);
}

export function getBoardTool(id: string): AnyBoardTool | undefined {
  return registry.get(id);
}

export function listBoardTools(): AnyBoardTool[] {
  return [...registry.values()];
}

registerBoardTool(noteTool);
registerBoardTool(linkTool);
registerBoardTool(mediaTool);
registerBoardTool(etiquetaTool);
registerBoardTool(referenteTool);
registerBoardTool(marcoTool);
