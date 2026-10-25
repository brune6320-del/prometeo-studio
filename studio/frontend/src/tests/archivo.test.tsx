import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { BoardCard } from '../board/model';
import { normalizeBoard } from '../board/model';
import { blockYear, buildArchive, formatClock, groupBlocksByYear, paragraphs, slideCounter, slideIndex } from '../board/archivo';
import { readFrameData, setFrameView } from '../board/frames';
import { ArchivoView } from '../components/ArchivoView';

function card(id: string, type: BoardCard['type'], patch: Partial<BoardCard> = {}): BoardCard {
  return { id, type, title: id, body: '', x: 100, y: 100, width: 260, color: 'paper', ...patch };
}

function media(id: string, title: string, body = ''): BoardCard {
  return card(id, 'media', {
    title,
    body,
    media: { name: `${id}.png`, mimeType: 'image/png', dataUrl: 'data:image/png;base64,AAAA', kind: 'image' },
  });
}

function frame(hijos: string[]): BoardCard {
  return card('marco', 'marco', { title: 'Archivo', datos: { alto: 420, hijos, vista: 'libre' } });
}

const CHILDREN: BoardCard[] = [
  card('nota', 'note', { title: 'IRENE GUERRA®', body: 'Bio del proyecto.\n\nSegundo párrafo.' }),
  card('etiqueta', 'etiqueta', { title: 'IN EXHIBITION', body: 'DE-P01.01' }),
  media('m1', 'Pareidolìa'),
  media('m2', 'Pareidolìa · detalle'),
  card('texto', 'note', { title: 'Texto', body: 'Un dispositivo especulativo.' }),
  card('enlace', 'link', { title: 'Fuente', body: '', url: 'https://example.com/pareidolia' }),
  card('etiqueta-2', 'etiqueta', { title: 'RESEARCH', body: 'AR-P01.01' }),
  media('m3', 'Outdated Architecture'),
];

describe('archivo: lectura de los hijos del marco', () => {
  it('separa nota fija, bloques de medios consecutivos, etiqueta y texto', () => {
    const { note, blocks } = buildArchive(CHILDREN, CHILDREN.map((item) => item.id));

    expect(note?.id).toBe('nota');
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toMatchObject({
      code: 'DE-P01.01',
      title: 'Pareidolìa',
      status: 'IN EXHIBITION',
      text: 'Un dispositivo especulativo.',
      url: 'https://example.com/pareidolia',
    });
    expect(blocks[0].items.map((item) => item.id)).toEqual(['m1', 'm2']);
    expect(blocks[1]).toMatchObject({ code: 'AR-P01.01', title: 'Outdated Architecture', status: 'RESEARCH' });
    expect(blocks[1].items.map((item) => item.id)).toEqual(['m3']);
  });

  it('si un bloque no tiene nota de texto usa el cuerpo de sus medios', () => {
    const cards = [media('m1', 'A', 'Pie de foto')];
    const { blocks } = buildArchive(cards, ['m1']);
    expect(blocks[0].text).toBe('Pie de foto');
  });

  it('las notas y herramientas sueltas se pintan como bloques de texto, sin perder datos', () => {
    const cards = [card('n1', 'note', { title: 'Fija', body: 'Bio' }), card('n2', 'note', { title: 'Suelta', body: 'Aparte' }), card('x1', 'muro', { title: 'Muro', body: 'Datos' })];
    const { blocks } = buildArchive(cards, ['n1', 'n2', 'x1']);
    expect(blocks.map((block) => block.title)).toEqual(['Suelta', 'Muro']);
    expect(blocks.map((block) => block.text)).toEqual(['Aparte', 'Datos']);
  });
});

describe('archivo: carrusel circular', () => {
  it('envuelve por ambos extremos y aguanta listas vacías', () => {
    expect(slideIndex(0, 3, -1)).toBe(2);
    expect(slideIndex(2, 3, 1)).toBe(0);
    expect(slideIndex(1, 3, 5)).toBe(0);
    expect(slideIndex(0, 3, -7)).toBe(2);
    expect(slideIndex(4, 0, 1)).toBe(0);
    expect(slideIndex(Number.NaN, 4, 1)).toBe(1);
  });

  it('con una sola diapositiva siempre devuelve 0', () => {
    expect(slideIndex(0, 1, 1)).toBe(0);
    expect(slideIndex(0, 1, -1)).toBe(0);
  });

  it('el contador es 1-based y no se sale de la lista', () => {
    expect(slideCounter(0, 3)).toBe('1 / 3');
    expect(slideCounter(2, 3)).toBe('3 / 3');
    expect(slideCounter(9, 3)).toBe('3 / 3');
    expect(slideCounter(-2, 3)).toBe('1 / 3');
    expect(slideCounter(0, 0)).toBe('0 / 0');
  });
});

describe('archivo: filas por año', () => {
  const cards = [
    card('e1', 'etiqueta', { title: 'IN EXHIBITION', body: 'DE-P01.01' }),
    card('m1', 'media', { title: 'Pareidolìa', datos: { año: 2024 }, media: { name: 'a.png', mimeType: 'image/png', dataUrl: 'data:image/png;base64,AAAA', kind: 'image' } }),
    card('e2', 'etiqueta', { title: 'RESEARCH', body: 'AR-P01.01' }),
    media('m2', 'The Century of the Bed 1999'),
    card('e3', 'etiqueta', { title: 'RADIO', body: 'FI-P01.01' }),
    media('m3', 'Sin fecha'),
  ];
  const blocks = buildArchive(cards, cards.map((item) => item.id)).blocks;

  it('lee datos.año, luego el primer año del código, título o texto', () => {
    expect(blockYear(blocks[0])).toBe(2024);
    expect(blockYear(blocks[1])).toBe(1999);
    expect(blockYear(blocks[2])).toBeNull();
  });

  it('ordena de más reciente a más antiguo y deja «Sin año» al final', () => {
    const rows = groupBlocksByYear(blocks);
    expect(rows.map((row) => row.label)).toEqual(['2024', '1999', 'Sin año']);
    expect(rows[0].blocks).toHaveLength(1);
    expect(rows[2].blocks[0].title).toBe('Sin fecha');
  });

  it('los bloques de solo texto no crean fila', () => {
    const onlyText = buildArchive([card('n', 'note', { title: '2020', body: 'Sin medios' })], ['n']).blocks;
    expect(groupBlocksByYear(onlyText)).toEqual([]);
  });
});

describe('archivo: cambiar de vista no toca posiciones ni datos', () => {
  const cards = [frame(['nota', 'm1']), card('nota', 'note', { x: 40, y: 80, body: 'Bio' }), media('m1', 'Pieza')];

  function snapshot(list: BoardCard[]) {
    return list.map((item) => ({ id: item.id, type: item.type, x: item.x, y: item.y, width: item.width, title: item.title, body: item.body }));
  }

  it('Libre → Archivo → Libre deja las posiciones iguales', () => {
    const before = snapshot(cards);
    const inArchive = setFrameView(cards, 'marco', 'archivo');
    expect(readFrameData(inArchive[0]).vista).toBe('archivo');
    const back = setFrameView(inArchive, 'marco', 'libre');
    expect(readFrameData(back[0]).vista).toBe('libre');
    expect(snapshot(back)).toEqual(before);
  });

  it('cambiar a la vista que ya está activa devuelve el mismo array', () => {
    expect(setFrameView(cards, 'marco', 'libre')).toBe(cards);
  });

  it('al cargar se conserva la vista Archivo y una vista desconocida vuelve a Libre', () => {
    const loaded = normalizeBoard({
      schemaVersion: 1,
      id: 'b',
      title: 'Archivo',
      cards: [
        { ...frame(['nota']), datos: { alto: 420, hijos: ['nota'], vista: 'archivo' } },
        card('nota', 'note'),
      ],
      relations: [],
    });
    expect(readFrameData(loaded!.cards[0]).vista).toBe('archivo');

    const unknown = normalizeBoard({
      schemaVersion: 1,
      id: 'b2',
      title: 'Archivo',
      cards: [{ ...frame([]), datos: { alto: 420, hijos: [], vista: 'inventada' } }],
      relations: [],
    });
    expect(readFrameData(unknown!.cards[0]).vista).toBe('libre');
  });
});

describe('archivo: utilidades de presentación', () => {
  it('formatea el reloj vivo y los párrafos', () => {
    expect(formatClock(new Date(2026, 9, 24, 9, 5, 3))).toBe('09:05:03');
    expect(paragraphs('Uno\n\nDos\n\n\nTres')).toEqual(['Uno', 'Dos', 'Tres']);
  });

  it('pinta las tres columnas con etiqueta, código, estado, texto y reloj', () => {
    const html = renderToStaticMarkup(
      <ArchivoView frameTitle="BARATTOLO" cards={CHILDREN} childIds={CHILDREN.map((item) => item.id)} />,
    );
    expect(html).toContain('IRENE GUERRA®');
    expect(html).toContain('BARATTOLO');
    expect(html).toContain('Índice');
    expect(html).toContain('DE-P01.01');
    expect(html).toContain('IN EXHIBITION');
    expect(html).toContain('Un dispositivo especulativo.');
    expect(html).toMatch(/\d{2}:\d{2}:\d{2}/);
    expect((html.match(/class="archivo-col /g) ?? []).length).toBe(3);
    expect(html).toContain('1 / 2');
    expect(html).toContain('archivo-counter');
  });
});
