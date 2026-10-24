import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { BoardCard } from '../board/model';
import { normalizeBoard } from '../board/model';
import { readFrameData, setFrameView } from '../board/frames';
import {
  buildMuro,
  distributeMuroColumns,
  muroColumnCount,
  stepIndex,
} from '../board/vistas/muro';
import { buildMesaPieces, layoutJustifiedRows, seededRotation } from '../board/vistas/mesa';
import { MuroView } from '../components/MuroView';
import { MesaView } from '../components/MesaView';

function card(id: string, type: BoardCard['type'], patch: Partial<BoardCard> = {}): BoardCard {
  return { id, type, title: id, body: '', x: 100, y: 100, width: 290, color: 'paper', ...patch };
}

function media(id: string, title: string): BoardCard {
  return card(id, 'media', {
    title,
    media: { name: `${id}.png`, mimeType: 'image/png', dataUrl: 'data:image/png;base64,AAAA', kind: 'image' },
  });
}

const CHILDREN: BoardCard[] = [
  card('etiqueta-1', 'etiqueta', { title: 'IN EXHIBITION', body: 'DE-P01.01' }),
  media('m1', 'Pareidolìa'),
  media('m2', 'Pareidolìa · detalle'),
  card('etiqueta-2', 'etiqueta', { title: 'RESEARCH', body: 'AR-P01.01' }),
  media('m3', 'Outdated Architecture'),
];

const IDS = CHILDREN.map((item) => item.id);

describe('muro: piezas, códigos y columnas', () => {
  it('toma los medios con el código de su bloque, sin tocar las tarjetas', () => {
    const items = buildMuro(CHILDREN, IDS);
    expect(items.map((item) => item.id)).toEqual(['m1', 'm2', 'm3']);
    expect(items.map((item) => item.code)).toEqual(['DE-P01.01', 'DE-P01.01', 'AR-P01.01']);
    expect(items[0].title).toBe('Pareidolìa');
    expect(CHILDREN[1].x).toBe(100);
    expect(CHILDREN[1].datos).toBeUndefined();
  });

  it('reparte en columnas de forma estable y sin perder piezas', () => {
    const items = buildMuro(CHILDREN, IDS);
    const first = distributeMuroColumns(items, 2);
    const second = distributeMuroColumns(items, 2);
    expect(first.map((column) => column.map((item) => item.id))).toEqual(second.map((column) => column.map((item) => item.id)));
    expect(first).toHaveLength(2);
    expect(first.flat().map((item) => item.id).sort()).toEqual(['m1', 'm2', 'm3']);
    expect(muroColumnCount(500)).toBe(4);
    expect(muroColumnCount(200)).toBe(2);
  });

  it('la caja de luz recorre en círculo y aguanta listas vacías', () => {
    expect(stepIndex(0, 3, -1)).toBe(2);
    expect(stepIndex(2, 3, 1)).toBe(0);
    expect(stepIndex(0, 1, 5)).toBe(0);
    expect(stepIndex(0, 0, 1)).toBe(-1);
  });
});

describe('mesa de luz: semilla y filas justificadas', () => {
  it('con la misma semilla la disposición es idéntica; con otra cambia', () => {
    const first = buildMesaPieces(CHILDREN, IDS, 42);
    const second = buildMesaPieces(CHILDREN, IDS, 42);
    const other = buildMesaPieces(CHILDREN, IDS, 43);
    expect(first).toEqual(second);
    expect(other.map((piece) => piece.rotation)).not.toEqual(first.map((piece) => piece.rotation));
    expect(first.map((piece) => piece.rotation)).toEqual(
      CHILDREN.filter((item) => item.type === 'media').map((item) => Number(seededRotation(item.id, 42).toFixed(2))),
    );
    for (const piece of first) {
      expect(Math.abs(piece.rotation)).toBeLessThanOrEqual(3.4);
      expect(Math.abs(piece.offsetX)).toBeLessThanOrEqual(4);
      expect(Math.abs(piece.offsetY)).toBeLessThanOrEqual(4);
    }
  });

  it('justifica cada fila al ancho disponible conservando el aspecto', () => {
    const pieces = [
      { id: 'a', aspect: 1.5 },
      { id: 'b', aspect: 1 },
      { id: 'c', aspect: 0.8 },
      { id: 'd', aspect: 1.2 },
      { id: 'e', aspect: 1.4 },
      { id: 'f', aspect: 1 },
    ];
    const layout = layoutJustifiedRows(pieces, 480, 100, 10);
    expect(layout.rows.length).toBeGreaterThan(1);
    expect(layout.width).toBe(480);
    for (const row of layout.rows) {
      expect(row.width).toBeCloseTo(480, 5);
      for (let index = 0; index < row.items.length; index += 1) {
        const item = row.items[index];
        expect(item.y).toBe(row.y);
        expect(item.width / item.height).toBeCloseTo(pieces.find((piece) => piece.id === item.id)!.aspect, 5);
        if (index > 0) expect(item.x).toBeCloseTo(row.items[index - 1].x + row.items[index - 1].width + 10, 5);
      }
    }
    expect(layout.height).toBeGreaterThan(0);

    const single = layoutJustifiedRows([{ id: 'solo', aspect: 0.5 }], 480, 100, 10);
    expect(single.rows[0]).toMatchObject({ width: 50, height: 100 });
    expect(single.rows[0].items[0]).toMatchObject({ x: 0, y: 0, width: 50, height: 100 });
  });

  it('sin piezas devuelve una disposición vacía', () => {
    expect(layoutJustifiedRows([], 480)).toEqual({ width: 480, height: 0, rows: [] });
    expect(buildMesaPieces(CHILDREN, [], 1)).toEqual([]);
  });
});

describe('vistas del marco: cambiar de vista no mueve ni borra', () => {
  const frame: BoardCard = card('marco', 'marco', {
    title: 'Marco',
    datos: { alto: 420, hijos: IDS, vista: 'libre' },
  });
  const cards = [frame, ...CHILDREN];

  function snapshot(list: BoardCard[]) {
    return list.map((item) => ({ id: item.id, type: item.type, x: item.x, y: item.y, width: item.width, title: item.title, body: item.body }));
  }

  it('Libre → Muro → Mesa → Libre deja las posiciones iguales', () => {
    const before = snapshot(cards);
    const inMuro = setFrameView(cards, 'marco', 'muro');
    expect(readFrameData(inMuro[0]).vista).toBe('muro');
    expect(readFrameData(inMuro[0]).hijos).toEqual(IDS);
    const inMesa = setFrameView(inMuro, 'marco', 'mesa');
    expect(readFrameData(inMesa[0]).vista).toBe('mesa');
    const back = setFrameView(inMesa, 'marco', 'libre');
    expect(readFrameData(back[0]).vista).toBe('libre');
    expect(snapshot(back)).toEqual(before);
    expect(readFrameData(back[0]).hijos).toEqual(IDS);
  });

  it('al cargar se conservan Muro y Mesa; una vista desconocida vuelve a Libre', () => {
    const loaded = normalizeBoard({
      schemaVersion: 1,
      id: 'b',
      title: 'Vistas',
      cards: [
        { ...frame, datos: { alto: 420, hijos: IDS, vista: 'mesa' } },
        ...CHILDREN,
      ],
      relations: [],
    });
    expect(readFrameData(loaded!.cards[0]).vista).toBe('mesa');

    const unknown = normalizeBoard({
      schemaVersion: 1,
      id: 'b2',
      title: 'Vistas',
      cards: [{ ...frame, datos: { alto: 420, hijos: [], vista: 'inventada' } }],
      relations: [],
    });
    expect(readFrameData(unknown!.cards[0]).vista).toBe('libre');
  });
});

describe('componentes de las vistas', () => {
  it('el muro pinta miniaturas con su código', () => {
    const html = renderToStaticMarkup(<MuroView frameTitle="BARATTOLO" cards={CHILDREN} childIds={IDS} width={500} />);
    expect(html).toContain('Muro');
    expect(html).toContain('3 piezas');
    expect(html).toContain('DE-P01.01');
    expect(html).toContain('AR-P01.01');
    expect(html).toContain('Pareidolìa');
    expect((html.match(/class="muro-thumb"/g) ?? []).length).toBe(3);
    expect(html).not.toContain('board-muro-lightbox');
  });

  it('la mesa pinta piezas giradas y el botón de ordenar', () => {
    const html = renderToStaticMarkup(<MesaView frameTitle="BARATTOLO" cards={CHILDREN} childIds={IDS} width={500} seed={42} />);
    expect(html).toContain('Mesa de luz');
    expect(html).toContain('Ordenar en muro');
    expect(html).toContain('DE-P01.01');
    expect(html).toContain('--mesa-rotation');
    expect((html.match(/class="mesa-piece"/g) ?? []).length).toBe(3);
  });
});
