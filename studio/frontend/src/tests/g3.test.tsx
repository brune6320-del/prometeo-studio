import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { anclaHacia, geometriaConector, rectDeTarjeta } from '../board/conectores';
import { duplicateCards, createCard, normalizeBoard, type BoardCard } from '../board/model';
import { readColumnData, setColumnFolded } from '../board/columnas';
import { escribirTareas, leerTareas, normalizarTareas } from '../board/tareas';
import { materializar, PLANTILLAS_BUILTIN } from '../board/plantillas';
import { MarkdownLite } from '../components/MarkdownLite';
import { BoardCardContent } from '../board/tools/CardView';

const NOOP = () => {};

describe('G3 · conectores con ancla y curva', () => {
  it('el ancla sale del lado que mira al objetivo', () => {
    const rect = { x: 0, y: 0, width: 200, height: 100 };
    expect(anclaHacia(rect, { x: 400, y: 50 }).lado).toBe('right');
    expect(anclaHacia(rect, { x: -400, y: 50 }).lado).toBe('left');
    expect(anclaHacia(rect, { x: 100, y: -400 }).lado).toBe('top');
    expect(anclaHacia(rect, { x: 100, y: 400 }).lado).toBe('bottom');
  });

  it('la curva se recalcula cuando se mueve una tarjeta', () => {
    const a = { x: 0, y: 0, width: 200, height: 100 };
    const b = { x: 400, y: 0, width: 200, height: 100 };
    const uno = geometriaConector(a, b);
    const dos = geometriaConector(a, { ...b, y: 300 });
    expect(uno.path).not.toBe(dos.path);
    expect(uno.path.startsWith('M ')).toBe(true);
    expect(uno.hasta.x).toBe(400);
    expect(dos.hasta.y).toBe(300);
  });

  it('lee el alto real de una imagen para anclar el conector', () => {
    const card = { ...createCard('media', 10, 20), media: { name: 'a.png', mimeType: 'image/png', dataUrl: 'data:image/png;base64,AA', kind: 'image' as const }, height: 300 };
    expect(rectDeTarjeta(card)).toEqual({ x: 10, y: 20, width: 290, height: 300 });
  });
});

describe('G3 · duplicar con Alt/Opción', () => {
  it('copia tarjetas, remapea hijos de marco y relaciones internas', () => {
    const marco = { ...createCard('marco', 0, 0), datos: { alto: 300, hijos: ['n1'], vista: 'libre' } };
    const nota = createCard('note', 40, 40);
    nota.id = 'n1';
    const fuera = createCard('note', 600, 40);
    const cards = [marco, nota, fuera];
    const relations = [
      { id: 'r1', from: marco.id, to: nota.id },
      { id: 'r2', from: nota.id, to: fuera.id },
    ];
    const dup = duplicateCards(cards, relations, [marco.id, nota.id], { x: 20, y: 20 });
    expect(dup.newIds).toHaveLength(2);
    expect(dup.cards.every((card) => card.id !== marco.id && card.id !== nota.id)).toBe(true);
    expect(dup.relations).toHaveLength(1);
    expect(dup.relations[0].from).toBe(dup.idMap.get(marco.id));
    const copiaMarco = dup.cards.find((card) => card.type === 'marco')!;
    expect(copiaMarco.datos?.hijos).toEqual([dup.idMap.get(nota.id)]);
  });
});

describe('G3 · modelo', () => {
  it('conserva bloqueo, etiqueta de conector y datos de vista previa', () => {
    const board = normalizeBoard({
      schemaVersion: 1,
      id: 'b-g3',
      title: 'G3',
      cards: [
        {
          id: 'a', type: 'note', title: 'A', body: '', x: 10, y: 20, width: 260, color: 'paper', locked: true,
        },
        {
          id: 'b', type: 'link', title: 'B', body: '', x: 400, y: 20, width: 280, color: 'paper', url: 'https://example.com',
          datos: { vistaPrevia: { titulo: 'Ejemplo', descripcion: 'Una descripción', imagen: 'https://example.com/a.png', sitio: 'example.com' } },
        },
      ],
      relations: [{ id: 'r', from: 'a', to: 'b', label: 'depende de', tone: 'sage' }],
    });
    expect(board?.cards[0].locked).toBe(true);
    expect(board?.relations[0].label).toBe('depende de');
    expect(board?.relations[0].tone).toBe('sage');
    expect(board?.cards[1].datos?.vistaPrevia).toBeTruthy();
  });
});

describe('G3 · columnas y tareas', () => {
  it('pliega la columna sin tocar sus hijos', () => {
    const columna = { ...createCard('columna', 10, 10), datos: { hijos: ['n1', 'n2'], plegada: false } };
    const cards = [columna, createCard('note', 40, 40)];
    const siguiente = setColumnFolded(cards, columna.id, true);
    expect(readColumnData(siguiente[0]).plegada).toBe(true);
    expect(readColumnData(siguiente[0]).hijos).toEqual(['n1', 'n2']);
  });

  it('normaliza tareas y produce Markdown con casillas', () => {
    const tareas = normalizarTareas([
      { id: 't1', texto: 'Primera', hecha: true },
      { id: 't1', texto: 'Duplicada', hecha: false, nivel: 9 },
      { texto: '   ' },
    ]);
    expect(tareas).toHaveLength(3);
    expect(tareas[0].id).not.toBe(tareas[1].id);
    expect(tareas[1].nivel).toBe(2);
    expect(tareas[2].texto.trim()).toBe('');
    const card = escribirTareas(createCard('tareas', 0, 0), tareas);
    expect(leerTareas(card)).toHaveLength(3);
  });
});

describe('G3 · formato mínimo de nota', () => {
  it('pinta título, negrita, lista, cita y código sin HTML crudo', () => {
    const html = renderToStaticMarkup(<MarkdownLite value={'# Título\n\n**Fuerte** y `código`\n\n- uno\n- dos\n\n> cita\n\n```\nx = 1\n```'} />);
    expect(html).toContain('<h3>Título</h3>');
    expect(html).toContain('<strong>Fuerte</strong>');
    expect(html).toContain('<code>código</code>');
    expect(html).toContain('<li>uno</li>');
    expect(html).toContain('<blockquote>cita</blockquote>');
    expect(html).toContain('<pre><code>x = 1</code></pre>');
  });

  it('pinta la vista previa de un enlace', () => {
    const card: BoardCard = {
      ...createCard('link', 0, 0),
      title: 'Enlace',
      url: 'https://example.com',
      datos: { vistaPrevia: { titulo: 'Ejemplo', descripcion: 'Descripción', imagen: 'https://example.com/a.png', sitio: 'example.com' } },
    };
    const html = renderToStaticMarkup(<BoardCardContent card={card} editar={NOOP} />);
    expect(html).toContain('board-link-preview');
    expect(html).toContain('Ejemplo');
    expect(html).toContain('example.com');
  });
});

describe('G3 · plantillas', () => {
  it('materializa una copia con ids nuevos', () => {
    const plantilla = PLANTILLAS_BUILTIN.find((item) => item.id === 'proyecto')!;
    const uno = materializar(plantilla.board);
    const dos = materializar(plantilla.board);
    expect(uno.cards.length).toBeGreaterThan(2);
    expect(uno.cards.map((card) => card.id)).not.toEqual(dos.cards.map((card) => card.id));
    expect(uno.cards.some((card) => card.type === 'columna' && readColumnData(card).hijos.length > 0)).toBe(true);
  });

  it('la plantilla vacía no trae tarjetas', () => {
    const vacia = PLANTILLAS_BUILTIN.find((item) => item.id === 'vacio')!;
    expect(materializar(vacia.board).cards).toEqual([]);
  });
});
