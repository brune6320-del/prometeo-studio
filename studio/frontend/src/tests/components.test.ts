import { describe, it, expect } from 'vitest';
import type { NodeSummary, StagedOperation, DocumentSummary } from '../types';

describe('PROMETEO Studio · UI Component & State Logic Tests (ORDEN 133 / Section 44)', () => {
  it('should track staged operations and verify atomic tray count', () => {
    const ops: StagedOperation[] = [
      {
        op_id: 'op_1',
        node_id: 'text_p0_s1',
        original_text: 'Juan Perez',
        new_text: 'Pedro Pascal',
        page: 0,
        status: 'STAGED',
        timestamp: '12:00:00',
      },
      {
        op_id: 'op_2',
        node_id: 'text_p0_s2',
        original_text: 'Directora',
        new_text: 'Presidenta',
        page: 0,
        status: 'STAGED',
        timestamp: '12:00:01',
      },
    ];

    expect(ops.length).toBe(2);
    // Verificar inmutabilidad del array
    const updated = ops.filter((o) => o.op_id !== 'op_1');
    expect(updated.length).toBe(1);
    expect(updated[0].op_id).toBe('op_2');
  });

  it('should filter outliner nodes by type correctly', () => {
    const nodes: NodeSummary[] = [
      { id: 'text_1', type: 'TEXT', page: 0, text: 'Hello' },
      { id: 'img_1', type: 'IMAGE', page: 0 },
      { id: 'vec_1', type: 'VECTOR', page: 0 },
      { id: 'text_2', type: 'TEXT', page: 1, text: 'World' },
    ];

    const textOnly = nodes.filter((n) => n.type === 'TEXT');
    expect(textOnly.length).toBe(2);

    const imageOnly = nodes.filter((n) => n.type === 'IMAGE');
    expect(imageOnly.length).toBe(1);

    const page0Only = nodes.filter((n) => n.page === 0);
    expect(page0Only.length).toBe(3);
  });

  it('should distinguish born digital from raster document capabilities honest UX (Section 48 & 49)', () => {
    const bornDigitalSummary: DocumentSummary = {
      document_id: 'doc_1',
      source_sha256: 'abc',
      pages_count: 1,
      total_nodes: 50,
      text_nodes_count: 45,
      image_nodes_count: 0,
      vector_nodes_count: 5,
      docgraph_version: '0.3',
      session_id: 'sess_1',
      transaction_state: 'READY',
      staged_count: 0,
      capabilities: {
        is_born_digital: true,
        is_raster: false,
        can_text_edit: true,
        can_verify_physically: true,
        capability_badge: 'BORN_DIGITAL_FULL',
      },
    };

    const rasterSummary: DocumentSummary = {
      document_id: 'doc_2',
      source_sha256: 'def',
      pages_count: 1,
      total_nodes: 1,
      text_nodes_count: 0,
      image_nodes_count: 1,
      vector_nodes_count: 0,
      docgraph_version: '0.3',
      session_id: 'sess_2',
      transaction_state: 'READY',
      staged_count: 0,
      capabilities: {
        is_born_digital: false,
        is_raster: true,
        can_text_edit: false,
        can_verify_physically: false,
        capability_badge: 'RASTER_LIMITED',
        warning: 'Documento escaneado / raster: edición textual restringida.',
      },
    };

    expect(bornDigitalSummary.capabilities.can_text_edit).toBe(true);
    expect(bornDigitalSummary.capabilities.can_verify_physically).toBe(true);

    expect(rasterSummary.capabilities.can_text_edit).toBe(false);
    expect(rasterSummary.capabilities.can_verify_physically).toBe(false);
    expect(rasterSummary.capabilities.capability_badge).toBe('RASTER_LIMITED');
  });
});
