import React from 'react';
import { ArrowRight, GitCompare } from 'lucide-react';
import type { DocGraphDiffResult } from '../types';
import { EmptyState } from './ui';

interface DiffPanelProps {
  diff: DocGraphDiffResult | null;
  uiMode: 'user' | 'technical';
  onSelectNode: (nodeId: string, page: number) => void;
}

export function textChanges(diff: DocGraphDiffResult) {
  return diff.changed_nodes.filter((c) => ((c as any).node_type ?? 'TEXT') === 'TEXT' && ((c as any).text_changed || c.text_before !== c.text_after));
}

/** Diferencias estructurales entre el original y la copia verificada. */
export const DiffPanel: React.FC<DiffPanelProps> = ({ diff, uiMode, onSelectNode }) => {
  if (!diff) {
    return (
      <EmptyState icon={<GitCompare size={26} />} title="Sin comparación todavía">
        <p>Después de una verificación aprobada verás aquí qué cambió entre el original y la copia, elemento por elemento.</p>
      </EmptyState>
    );
  }
  const { summary } = diff;
  // En modo usuario solo importan los textos; los grupos cambian de índice al reescribirse la página.
  const changed_nodes = uiMode === 'technical' ? diff.changed_nodes : textChanges(diff);
  return (
    <div>
      <div className="diff-stats">
        <div className="diff-stat">
          <span className="value">{changed_nodes.length}</span>
          <span className="label">{uiMode === 'technical' ? 'nodos modificados' : 'textos modificados'}</span>
        </div>
        {uiMode === 'technical' && (
          <>
            <div className="diff-stat">
              <span className="value">{summary.added_count}</span>
              <span className="label">añadidos</span>
            </div>
            <div className="diff-stat">
              <span className="value">{summary.removed_count}</span>
              <span className="label">eliminados</span>
            </div>
            <div className="diff-stat">
              <span className="value">{summary.total_nodes_before}</span>
              <span className="label">nodos en el original</span>
            </div>
          </>
        )}
      </div>
      {changed_nodes.length === 0 ? (
        <p className="muted">La copia es estructuralmente idéntica al original.</p>
      ) : (
        <ul className="diff-list">
          {changed_nodes.map((ch) => {
            const before = ch.text_before ?? (ch as any).old_text;
            const after = ch.text_after ?? (ch as any).new_text;
            return (
              <li key={ch.node_id}>
                <button className="diff-card" onClick={() => onSelectNode(ch.node_id, ch.page ?? 0)}>
                  <div className="hint">
                    Página {(ch.page ?? 0) + 1}
                    {uiMode === 'technical' ? ` · ${ch.node_id}` : ''}
                  </div>
                  <div className="before-after">
                    <span className="text-old">{before}</span>
                    <ArrowRight size={14} aria-hidden="true" />
                    <span className="text-new">{after}</span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
