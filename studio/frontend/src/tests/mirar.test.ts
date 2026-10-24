import { describe, expect, it, vi } from 'vitest';
import { studioApi } from '../api/client';
import { boardToMarkdown, type BoardCard, type BoardDocument } from '../board/model';
import { idTarjetaReferente, importarBiblioteca } from '../board/referentes/biblioteca';
import { pedirLecturas } from '../board/referentes/deepseek';
import { aceptarLectura, seleccionarReferentes } from '../board/referentes/mirar';
import { leerReferente, normalizarReferente, type Lectura } from '../board/referentes/model';
import { OJOS } from '../board/referentes/ojos';
import { SEMILLA_REFERENTES } from '../board/referentes/semilla';
import { getBoardTool } from '../board/tools/registry';

const LETTERFORM = idTarjetaReferente('letterform');

const LECTURA: Lectura = {
  fecha: '2026-10-24',
  proyecto: 'Luna',
  ojos: 'Irene Guerra',
  texto: 'La mancha de tinta repite el gesto del corte: mirar dos veces antes de decidir.',
  modelo: 'deepseek-chat',
  aceptada: true,
};

function conVistoEn(board: BoardDocument, fechas: Record<string, string[]>): BoardDocument {
  return {
    ...board,
    cards: board.cards.map((card) => {
      if (card.type !== 'referente') return card;
      return {
        ...card,
        datos: { ...normalizarReferente({ ...leerReferente(card), vistoEn: fechas[card.id] ?? ['2026-10-20'] }) },
      };
    }) as BoardCard[],
  };
}

describe('ritual Volver a mirar', () => {
  it('elige tres referentes distintos y la misma semilla da la misma tirada', () => {
    const { board } = importarBiblioteca([], SEMILLA_REFERENTES);
    const conFechas = conVistoEn(board, { [LETTERFORM]: ['2020-01-01'] });

    const primera = seleccionarReferentes([conFechas], conFechas.id, 'semilla-fija', 'hannah-hoch');
    const segunda = seleccionarReferentes(
      [{ ...conFechas, cards: [...conFechas.cards].reverse() }],
      conFechas.id,
      'semilla-fija',
      'hannah-hoch',
    );

    expect(primera.elegidos).toHaveLength(3);
    expect(new Set(primera.elegidos.map((elegido) => elegido.cardId)).size).toBe(3);
    expect(primera.elegidos.map((elegido) => elegido.cardId)).toEqual(segunda.elegidos.map((elegido) => elegido.cardId));
    expect(primera.elegidos[0]).toMatchObject({ cardId: LETTERFORM, motivo: 'sin-mirar' });
    expect(primera.elegidos[1].motivo).toBe('semilla');
    expect(primera.elegidos[2].motivo).toBe('tablero-abierto');
    expect(primera.ojos.id).toBe('hannah-hoch');
  });

  it('aceptar la lectura actualiza lecturas y vistoEn; descartar no toca el referente', () => {
    const { board } = importarBiblioteca([], SEMILLA_REFERENTES);
    const original = board.cards.find((card) => card.id === LETTERFORM)!;
    const antes = leerReferente(original);
    expect(antes.lecturas).toHaveLength(0);
    expect(antes.vistoEn).toEqual([]);

    const aceptado = aceptarLectura(original, LECTURA);
    const despues = leerReferente(aceptado);
    expect(despues.lecturas).toHaveLength(1);
    expect(despues.lecturas[0]).toMatchObject({
      fecha: '2026-10-24',
      proyecto: 'Luna',
      ojos: 'Irene Guerra',
      modelo: 'deepseek-chat',
      aceptada: true,
    });
    expect(despues.vistoEn).toEqual(['2026-10-24']);
    // La tarjeta original no se muta: descartar es no llamar a esta función.
    expect(leerReferente(original).lecturas).toHaveLength(0);

    const segunda = aceptarLectura(aceptado, { ...LECTURA, texto: 'Otra lectura del mismo día.' });
    expect(leerReferente(segunda).vistoEn.filter((fecha) => fecha === '2026-10-24')).toHaveLength(1);
    expect(leerReferente(segunda).lecturas).toHaveLength(2);
  });

  it('sin red el ritual sale en blanco, listo para escribir a mano', async () => {
    const { board } = importarBiblioteca([], SEMILLA_REFERENTES);
    const card = board.cards.find((item) => item.id === LETTERFORM)!;
    const espia = vi.spyOn(studioApi, 'mirarReferentes').mockRejectedValue(new Error('sin motor'));
    try {
      const resultado = await pedirLecturas('Luna', OJOS[0], [{
        boardId: board.id,
        cardId: card.id,
        nombre: leerReferente(card).nombre,
        motivo: 'sin-mirar',
        referente: leerReferente(card),
      }]);
      expect(resultado.disponible).toBe(false);
      expect(resultado.lecturas).toEqual([{ texto: '', modelo: '' }]);
      expect(resultado.motivo).toContain('Sin conexión');
    } finally {
      espia.mockRestore();
    }
  });

  it('la clave de DeepSeek no aparece en el Markdown exportado', () => {
    const secreto = 'sk-prueba-no-debe-salir-2026';
    vi.stubEnv('DEEPSEEK_API_KEY', secreto);
    vi.stubEnv('VITE_DEEPSEEK_API_KEY', secreto);

    const { board } = importarBiblioteca([], SEMILLA_REFERENTES);
    const card = board.cards.find((item) => item.id === LETTERFORM)!;
    const conLectura = {
      ...board,
      cards: board.cards.map((item) => item.id === card.id ? aceptarLectura(item, LECTURA) : item),
    };

    const markdown = boardToMarkdown(conLectura, {
      cardMarkdown: (item) => {
        const tool = getBoardTool(item.type);
        return tool?.exportarMarkdown ? tool.exportarMarkdown(item) : null;
      },
    });

    expect(markdown).toContain('La mancha de tinta repite el gesto del corte');
    expect(markdown).not.toContain(secreto);
    expect(JSON.stringify(conLectura)).not.toContain(secreto);
    vi.unstubAllEnvs();
  });
});
