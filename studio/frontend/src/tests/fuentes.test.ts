import { describe, expect, it } from 'vitest';
import { fuentesDeProyecto, type TableroEntropia } from '../board/vanguardia/fuentes';

const PNG_A = 'data:image/png;base64,AAAA';
const PNG_B = 'data:image/png;base64,BBBB';
const PNG_C = 'data:image/png;base64,CCCC';

function referente(id: string, nombre: string, imagenes: string[] = []) {
  return {
    id,
    type: 'referente',
    title: nombre,
    body: '',
    datos: {
      nombre,
      imagenes: imagenes.map((dataUrl, index) => ({
        name: `imagen-${index}.png`,
        mimeType: 'image/png',
        dataUrl,
        kind: 'image',
      })),
    },
  };
}

function media(id: string, src: string) {
  return { id, type: 'media', title: id, body: '', media: { name: `${id}.png`, mimeType: 'image/png', dataUrl: src, kind: 'image' } };
}

function marco(id: string, hijos: string[]) {
  return { id, type: 'marco', title: id, body: '', datos: { hijos, vista: 'libre', alto: 400 } };
}

describe('fuentes de entropía desde un export', () => {
  it('prefiere la imagen del referente, luego el marco, luego el tablero y cae al texto', () => {
    const tableros: TableroEntropia[] = [
      {
        id: 'b1',
        title: 'Biblioteca',
        cards: [
          marco('f1', ['ref-propia', 'ref-marco', 'img-marco']),
          referente('ref-propia', 'Propia', [PNG_A]),
          referente('ref-marco', 'Del marco'),
          referente('ref-tablero', 'Del tablero'),
          media('img-marco', PNG_B),
          media('img-tablero', PNG_C),
        ],
      },
      {
        id: 'b2',
        title: 'Vacío',
        cards: [referente('ref-texto', 'Sin imagen'), referente('ref-propia', 'Duplicada', [PNG_C])],
      },
    ];

    const { fuentes, procedencia } = fuentesDeProyecto(tableros);
    expect(fuentes.map((fuente) => fuente.id)).toEqual(['ref-propia', 'ref-marco', 'ref-tablero', 'ref-texto']);
    expect(procedencia['ref-propia']).toBe('referente');
    expect(procedencia['ref-marco']).toBe('marco');
    expect(procedencia['ref-tablero']).toBe('tablero');
    expect(procedencia['ref-texto']).toBe('tipografico');
    expect(fuentes[0].imagen?.src).toBe(PNG_A);
    expect(fuentes[1].imagen?.src).toBe(PNG_B);
    expect(fuentes[2].imagen?.src).toBe(PNG_B);
    expect(fuentes[3].imagen).toBeUndefined();
  });

  it('no usa imágenes externas: no descarga nada de internet', () => {
    const tableros: TableroEntropia[] = [{
      id: 'b1',
      title: 'Remoto',
      cards: [
        referente('ref-remota', 'Remota', ['https://example.com/a.png']),
        { id: 'img-remota', type: 'media', title: 'remota', body: '', media: { name: 'a.png', mimeType: 'image/png', dataUrl: 'https://example.com/b.png', kind: 'image' } },
      ],
    }];
    const { fuentes, procedencia } = fuentesDeProyecto(tableros);
    expect(fuentes[0].imagen).toBeUndefined();
    expect(procedencia['ref-remota']).toBe('tipografico');
  });
});
