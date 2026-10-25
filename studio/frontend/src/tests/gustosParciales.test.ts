import { describe, expect, it } from 'vitest';
import { gustosVacios, importarGustosParciales, pesoDe } from '../board/vanguardia/gustos';

function item(voto: string, referentes: string[], regla: string, herramienta: string) {
  return { semilla: 'abc', referentes, regla, herramienta, voto };
}

describe('importar gustos-parcial', () => {
  it('suma ♥ y ✕ sobre la memoria existente, sin reemplazarla', () => {
    const archivo = {
      format: 'prometeo-entropia-gustos',
      version: 1,
      items: [
        item('like', ['a', 'b'], 'dada', 'note'),
        item('nope', ['b', 'c'], 'suizo', 'marco'),
      ],
    };
    const resultado = importarGustosParciales(gustosVacios(), archivo);
    expect(resultado.likes).toBe(1);
    expect(resultado.nopes).toBe(1);
    expect(resultado.ignorados).toBe(0);
    expect(pesoDe(resultado.gustos.referentes, 'a')).toBe(2);
    expect(pesoDe(resultado.gustos.referentes, 'b')).toBe(1);
    expect(pesoDe(resultado.gustos.referentes, 'c')).toBe(0.2);
    expect(pesoDe(resultado.gustos.reglas, 'dada')).toBe(2);
    expect(pesoDe(resultado.gustos.reglas, 'suizo')).toBe(0.2);
    expect(pesoDe(resultado.gustos.herramientas, 'note')).toBe(2);
    expect(pesoDe(resultado.gustos.herramientas, 'marco')).toBe(0.2);
    expect(pesoDe(resultado.gustos.pares, 'a|b')).toBe(2);
    expect(pesoDe(resultado.gustos.pares, 'b|c')).toBe(0.2);
  });

  it('parte de los pesos que ya tenía el proyecto y respeta el recorte', () => {
    const previos = { ...gustosVacios(), referentes: { a: 4, b: 0.3 } };
    const resultado = importarGustosParciales(previos, { items: [item('like', ['a', 'b'], 'dada', 'note')] });
    expect(pesoDe(resultado.gustos.referentes, 'a')).toBe(5);
    expect(pesoDe(resultado.gustos.referentes, 'b')).toBe(1.3);
    expect(pesoDe(previos.referentes, 'a')).toBe(4);
  });

  it('ignora entradas incompletas y no falla con un archivo vacío', () => {
    const resultado = importarGustosParciales(gustosVacios(), {
      items: [
        item('like', [], 'dada', 'note'),
        item('like', ['a', 'b'], '', 'note'),
        { voto: 'like', referentes: ['a', 'b'] },
        item('quizá', ['a', 'b'], 'dada', 'note'),
      ],
    });
    expect(resultado.likes).toBe(0);
    expect(resultado.nopes).toBe(0);
    expect(resultado.ignorados).toBe(4);
    expect(resultado.gustos).toEqual(gustosVacios());

    const vacio = importarGustosParciales(gustosVacios(), { items: [] });
    expect(vacio.likes + vacio.nopes + vacio.ignorados).toBe(0);
    expect(vacio.gustos).toEqual(gustosVacios());
  });

  it('acepta votos con símbolos y referentes como objetos', () => {
    const resultado = importarGustosParciales(gustosVacios(), {
      items: [{ referentes: [{ id: 'a' }, 'b'], regla: { id: 'dada' }, herramienta: { id: 'note' }, voto: '♥' }],
    });
    expect(resultado.likes).toBe(1);
    expect(pesoDe(resultado.gustos.referentes, 'a')).toBe(2);
    expect(pesoDe(resultado.gustos.reglas, 'dada')).toBe(2);
  });
});
