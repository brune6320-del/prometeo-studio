import { describe, expect, it } from 'vitest';
import type { BoardCard, BoardDocument } from '../board/model';
import { idTarjetaReferente, importarBiblioteca } from '../board/referentes/biblioteca';
import {
  construirZipObsidian,
  filtrarLecturas,
  notasObsidian,
  opcionesDeFiltro,
  ordenarLecturas,
} from '../board/referentes/historial';
import { leerReferente, normalizarReferente, type Lectura } from '../board/referentes/model';
import { SEMILLA_REFERENTES } from '../board/referentes/semilla';

const LECTURAS: Lectura[] = [
  { fecha: '2026-09-15', proyecto: 'Luna', ojos: 'archivista', texto: 'Lectura vieja.', modelo: 'manual', aceptada: true },
  { fecha: '2026-10-02', proyecto: 'Collage', ojos: 'collagista dadá', texto: 'El corte es la idea.', modelo: 'deepseek', aceptada: true },
  { fecha: '2026-10-02', proyecto: 'Collage', ojos: 'archivista', texto: 'Misma fecha, añadida después.', modelo: 'manual', aceptada: false },
  { fecha: '', proyecto: 'Luna', ojos: 'archivista', texto: 'Sin fecha.', modelo: 'manual', aceptada: true },
];

function tarjetaConLecturas(board: BoardDocument, cardId: string, lecturas: Lectura[]): BoardDocument {
  return {
    ...board,
    cards: board.cards.map((card) => {
      if (card.id !== cardId) return card;
      return {
        ...card,
        datos: { ...normalizarReferente({ ...leerReferente(card), lecturas, etiquetas: ['archivo', 'tipografía'], vistoEn: ['2026-10-02'] }) },
      } as BoardCard;
    }),
  };
}

describe('historial de lecturas', () => {
  it('ordena de la más reciente a la más antigua sin mutar la entrada', () => {
    const original = LECTURAS.map((lectura) => lectura.texto);
    const ordenadas = ordenarLecturas(LECTURAS);

    expect(ordenadas.map((lectura) => lectura.texto)).toEqual([
      'Misma fecha, añadida después.',
      'El corte es la idea.',
      'Lectura vieja.',
      'Sin fecha.',
    ]);
    expect(LECTURAS.map((lectura) => lectura.texto)).toEqual(original);
  });

  it('filtra por proyecto y/o ojos, sin distinguir mayúsculas ni espacios', () => {
    expect(filtrarLecturas(LECTURAS, {})).toHaveLength(4);
    expect(filtrarLecturas(LECTURAS, { proyecto: 'collage' }).map((lectura) => lectura.texto)).toEqual([
      'El corte es la idea.',
      'Misma fecha, añadida después.',
    ]);
    expect(filtrarLecturas(LECTURAS, { ojos: ' Archivista ' }).map((lectura) => lectura.texto)).toEqual([
      'Lectura vieja.',
      'Misma fecha, añadida después.',
      'Sin fecha.',
    ]);
    expect(filtrarLecturas(LECTURAS, { proyecto: 'Luna', ojos: 'archivista' }).map((lectura) => lectura.texto)).toEqual([
      'Lectura vieja.',
      'Sin fecha.',
    ]);
    expect(filtrarLecturas(LECTURAS, { proyecto: 'No existe' })).toEqual([]);

    const opciones = opcionesDeFiltro(normalizarReferente({ lecturas: LECTURAS }));
    expect(opciones.proyectos).toEqual(['Collage', 'Luna']);
    expect(opciones.ojos).toEqual(['archivista', 'collagista dadá']);
  });

  it('exporta una nota por referente con frontmatter, solo lecturas aceptadas y enlaces del marco', () => {
    const { board } = importarBiblioteca([], SEMILLA_REFERENTES);
    const letterform = idTarjetaReferente('letterform');
    const conLecturas = tarjetaConLecturas(board, letterform, LECTURAS);
    const notas = notasObsidian([conLecturas]);

    expect(notas).toHaveLength(SEMILLA_REFERENTES.length);
    const nota = notas.find((item) => item.nombre === 'letterform-archive')!;
    expect(nota).toBeDefined();
    expect(nota.contenido.startsWith('---\n')).toBe(true);
    expect(nota.contenido).toContain('fuente: "https://letterformarchive.org"');
    expect(nota.contenido).toContain('etiquetas:\n  - "');
    expect(nota.contenido).toContain('vistoEn:\n  - "2026-10-02"');
    expect(nota.contenido).toContain('## Lecturas aceptadas');
    expect(nota.contenido).toContain('Lectura vieja.');
    expect(nota.contenido).toContain('El corte es la idea.');
    expect(nota.contenido).not.toContain('Misma fecha, añadida después.');
    expect(nota.contenido).toContain('Sin fecha.');
    expect(nota.contenido.indexOf('El corte es la idea.')).toBeLessThan(nota.contenido.indexOf('Lectura vieja.'));

    const medioMillon = notas.find((item) => item.nombre.startsWith('archivo-de-half-a-million'))!;
    expect(nota.contenido).toContain(`[[${medioMillon.nombre}]]`);
    expect(medioMillon.contenido).toContain('[[letterform-archive]]');

    const dover = notas.find((item) => item.nombre.startsWith('dover-treasury'))!;
    expect(dover.contenido).not.toContain('## Mismo marco');
    expect(notas.map((item) => item.nombre)).toEqual([...notas.map((item) => item.nombre)].sort((a, b) => a.localeCompare(b, 'es')));
  });

  it('el ZIP contiene una nota .md por referente', () => {
    const { board } = importarBiblioteca([], SEMILLA_REFERENTES);
    const notas = notasObsidian([board]);
    const zip = construirZipObsidian([board]);

    expect(zip[0]).toBe(0x50);
    expect(zip[1]).toBe(0x4b);
    const end = new DataView(zip.buffer, zip.byteOffset, zip.byteLength);
    const eocd = zip.length - 22;
    expect(end.getUint32(eocd, true)).toBe(0x06054b50);
    expect(end.getUint16(eocd + 10, true)).toBe(notas.length);

    const texto = new TextDecoder().decode(zip);
    for (const nota of notas) {
      expect(texto).toContain(`referentes/${nota.nombre}.md`);
      expect(texto).toContain(nota.contenido);
    }
  });
});
