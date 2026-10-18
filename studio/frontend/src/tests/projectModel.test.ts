import { describe, expect, it } from 'vitest';
import { createBoard } from '../board/model';
import {
  createBoardProject,
  createPdfReference,
  hasFutureProjectSchema,
  normalizeBoardProject,
  normalizePdfReference,
  PROJECT_WORKSPACE_SCHEMA_VERSION,
  projectToMarkdown,
} from '../board/projectModel';

describe('proyectos y referencias PDF (L2)', () => {
  it('valida la huella, la página y limita los campos de una referencia', () => {
    const project = createBoardProject('Proyecto');
    const board = createBoard('Investigación');
    const source = { filename: 'articulo.pdf', sha256: 'A'.repeat(64), page: 7 };
    const reference = createPdfReference({ projectId: project.id, boardId: board.id, source, quote: 'cita', note: 'nota' });

    expect(project.schemaVersion).toBe(PROJECT_WORKSPACE_SCHEMA_VERSION);
    expect(reference?.schemaVersion).toBe(PROJECT_WORKSPACE_SCHEMA_VERSION);
    expect(reference?.sourceSha256).toBe('a'.repeat(64));
    expect(createPdfReference({
      projectId: project.id,
      boardId: board.id,
      source: { ...source, filename: '/Users/person/Private/articulo.pdf' },
      quote: '',
      note: '',
    })?.sourceName).toBe('articulo.pdf');
    expect(normalizePdfReference({ ...reference, page: 0 })).toBeNull();
    expect(normalizePdfReference({ ...reference, sourceSha256: 'not-a-hash' })).toBeNull();
    expect(normalizePdfReference({ ...reference, note: 'n'.repeat(4000) })?.note).toHaveLength(3000);
  });

  it('rechaza datos de una versión futura sin reinterpretarlos', () => {
    const futureProject = {
      schemaVersion: PROJECT_WORKSPACE_SCHEMA_VERSION + 1,
      id: 'project-12345678',
      name: 'No abrir',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    expect(hasFutureProjectSchema(futureProject)).toBe(true);
    expect(normalizeBoardProject(futureProject)).toBeNull();
  });

  it('exporta proyecto y referencias como Markdown compatible con Obsidian sin HTML activo', () => {
    const project = createBoardProject('# Investigación');
    const board = createBoard('Marco teórico');
    const reference = createPdfReference({
      projectId: project.id,
      boardId: board.id,
      source: { filename: 'articulo <b>.pdf', sha256: 'b'.repeat(64), page: 3 },
      quote: '<script>alert(1)</script> [abrir](javascript:alert(1))',
      note: 'Revisar después ![[archivo privado]]',
    });
    const markdown = projectToMarkdown(project, [board], reference ? [reference] : []);

    expect(markdown).toContain('[[Marco-teorico]]');
    expect(markdown).toContain('&lt;script&gt;alert\\(1\\)&lt;/script&gt;');
    expect(markdown).toContain('SHA-256: ' + 'b'.repeat(64));
    expect(markdown).not.toContain('<script>');
    expect(markdown).not.toContain('[abrir](javascript:');
    expect(markdown).not.toContain('![[archivo privado]]');
    expect(markdown).not.toContain('/Users/');
  });
});
