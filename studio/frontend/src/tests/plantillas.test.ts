import { describe, expect, it } from 'vitest';
import { createBoard } from '../board/model';
import { crearPlantilla, listarPlantillas, normalizarPlantillas, PLANTILLAS_BUILTIN, MAX_PLANTILLAS } from '../board/plantillas';
import { createBoardProject, normalizeBoardProject } from '../board/projectModel';

describe('plantillas del proyecto', () => {
  it('crearPlantilla copia el tablero y no comparte referencias', () => {
    const board = createBoard('Estudio');
    board.cards = [{ id: 'n1', type: 'note', title: 'Idea', body: 'Texto', x: 1, y: 2, width: 260, color: 'paper' }];
    const plantilla = crearPlantilla(board);
    expect(plantilla.builtin).toBe(false);
    expect(plantilla.nombre).toBe('Estudio');
    expect(plantilla.board.cards[0].id).toBe('n1');
    plantilla.board.cards[0].title = 'Cambiada';
    expect(board.cards[0].title).toBe('Idea');
  });

  it('normaliza y descarta plantillas irrecuperables sin romper las demás', () => {
    const board = createBoard('Válida');
    const plantillas = normalizarPlantillas([
      { id: 'p1', nombre: 'Guardada', board, builtin: false },
      { id: 'p1', nombre: 'Duplicada', board },
      { id: 'p2', nombre: 'Sin tablero', board: null },
      { id: 3, nombre: 'Sin id', board },
      'texto',
    ]);
    expect(plantillas.map((item) => item.id)).toEqual(['p1']);
    expect(plantillas[0].nombre).toBe('Guardada');
  });

  it('respeta el tope local y lista primero las guardadas', () => {
    const board = createBoard('Una');
    const many = Array.from({ length: MAX_PLANTILLAS + 5 }, (_, index) => ({
      id: `p${index}`,
      nombre: `Plantilla ${index}`,
      board,
      builtin: false,
    }));
    const normalizadas = normalizarPlantillas(many);
    expect(normalizadas).toHaveLength(MAX_PLANTILLAS);
    const lista = listarPlantillas(normalizadas);
    expect(lista[0].id).toBe('p0');
    expect(lista.length).toBe(MAX_PLANTILLAS + PLANTILLAS_BUILTIN.length);
  });

  it('el proyecto acepta plantillas y las sanea al cargar', () => {
    const project = createBoardProject('Proyecto');
    expect(project.plantillas).toEqual([]);
    const board = createBoard('Dentro');
    const conPlantilla = normalizeBoardProject({
      ...project,
      plantillas: [{ id: 'p1', nombre: 'Dentro', board, builtin: false }],
    });
    expect(conPlantilla?.plantillas).toHaveLength(1);
    const rota = normalizeBoardProject({ ...project, plantillas: 'no es una lista' });
    expect(rota?.plantillas).toEqual([]);
  });
});
