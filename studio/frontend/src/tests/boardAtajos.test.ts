import { describe, expect, it } from 'vitest';
import {
  ATAJOS_LIENZO,
  atajoParaEvento,
  gruposDeAyuda,
  textoAtajo,
  type AtajoLienzo,
} from '../board/atajos';

function tecla(key: string, modificadores: Partial<KeyboardEvent> = {}): KeyboardEvent {
  return {
    key,
    metaKey: false,
    ctrlKey: false,
    shiftKey: false,
    altKey: false,
    ...modificadores,
  } as KeyboardEvent;
}

function accionDe(event: KeyboardEvent): AtajoLienzo['accion'] | null {
  return atajoParaEvento(event)?.accion ?? null;
}

describe('T-2 · tabla única de atajos del lienzo', () => {
  it('Supr y ⌫ borran, con Cmd o Ctrl', () => {
    expect(accionDe(tecla('Delete'))).toBe('borrar');
    expect(accionDe(tecla('Backspace'))).toBe('borrar');
    expect(accionDe(tecla('a', { metaKey: true }))).toBe('seleccionarTodo');
    expect(accionDe(tecla('a', { ctrlKey: true }))).toBe('seleccionarTodo');
  });

  it('las flechas distinguen 1 px y ⇧ 10 px', () => {
    expect(accionDe(tecla('ArrowLeft'))).toBe('moverIzquierda');
    expect(accionDe(tecla('ArrowRight'))).toBe('moverDerecha');
    expect(accionDe(tecla('ArrowUp'))).toBe('moverArriba');
    expect(accionDe(tecla('ArrowDown'))).toBe('moverAbajo');
    expect(accionDe(tecla('ArrowLeft', { shiftKey: true }))).toBe('moverIzquierda10');
    expect(accionDe(tecla('ArrowRight', { shiftKey: true }))).toBe('moverDerecha10');
  });

  it('el orden usa corchetes y Cmd/Ctrl para el extremo', () => {
    expect(accionDe(tecla(']'))).toBe('traerAdelante');
    expect(accionDe(tecla('['))).toBe('enviarAtras');
    expect(accionDe(tecla(']', { metaKey: true }))).toBe('alFrente');
    expect(accionDe(tecla('[', { metaKey: true }))).toBe('alFondo');
  });

  it('deshacer y rehacer no se pisan', () => {
    expect(accionDe(tecla('z', { metaKey: true }))).toBe('deshacer');
    expect(accionDe(tecla('z', { metaKey: true, shiftKey: true }))).toBe('rehacer');
  });

  it('Cmd+D duplica y Cmd+C/X/V usan el portapapeles interno', () => {
    expect(accionDe(tecla('d', { metaKey: true }))).toBe('duplicar');
    expect(accionDe(tecla('c', { metaKey: true }))).toBe('copiar');
    expect(accionDe(tecla('x', { metaKey: true }))).toBe('cortar');
    expect(accionDe(tecla('v', { metaKey: true }))).toBe('pegar');
  });

  it('Esc, ? y N forman parte de la misma tabla', () => {
    expect(accionDe(tecla('Escape'))).toBe('cerrar');
    expect(accionDe(tecla('?'))).toBe('ayuda');
    expect(accionDe(tecla('/', { shiftKey: true }))).toBe('ayuda');
    expect(accionDe(tecla('n'))).toBe('herramientas');
  });

  it('la ayuda se genera desde la tabla y no repite variantes ocultas', () => {
    const grupos = gruposDeAyuda();
    const items = grupos.flatMap((grupo) => grupo.items);
    expect(items).toContain(ATAJOS_LIENZO.find((atajo) => atajo.id === 'borrar'));
    expect(items).toContain(ATAJOS_LIENZO.find((atajo) => atajo.id === 'seleccionar-todo'));
    expect(items.some((atajo) => atajo.id === 'mover-derecha')).toBe(false);
    expect(items.every((atajo) => Boolean(atajo.descripcion))).toBe(true);
    expect(grupos.map((grupo) => grupo.grupo)).toEqual(['Selección', 'Edición', 'Mover', 'Orden', 'Lienzo', 'Vistas', 'Herramientas']);
  });

  it('cada fila visible de la ayuda se puede leer como tecla o gesto', () => {
    for (const atajo of gruposDeAyuda().flatMap((grupo) => grupo.items)) {
      expect(textoAtajo(atajo).length).toBeGreaterThan(0);
    }
    const borrar = ATAJOS_LIENZO.find((atajo) => atajo.id === 'borrar')!;
    expect(textoAtajo(borrar)).toContain('Supr');
  });
});
