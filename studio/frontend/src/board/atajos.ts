/**
 * Atajos del lienzo: una sola tabla es la fuente de verdad para el teclado y
 * para el panel de ayuda. Ningún atajo se dispara mientras se escribe.
 */

export type AccionLienzo =
  | 'borrar'
  | 'seleccionarTodo'
  | 'duplicar'
  | 'copiar'
  | 'cortar'
  | 'pegar'
  | 'moverIzquierda'
  | 'moverDerecha'
  | 'moverArriba'
  | 'moverAbajo'
  | 'moverIzquierda10'
  | 'moverDerecha10'
  | 'moverArriba10'
  | 'moverAbajo10'
  | 'traerAdelante'
  | 'enviarAtras'
  | 'alFrente'
  | 'alFondo'
  | 'deshacer'
  | 'rehacer'
  | 'cerrar'
  | 'ayuda'
  | 'herramientas'
  | 'pan'
  | 'agrupar'
  | 'desagrupar';

export type GrupoAyuda = 'Selección' | 'Edición' | 'Mover' | 'Orden' | 'Lienzo' | 'Vistas' | 'Herramientas';

export interface ModificadoresAtajo {
  /** Cmd en Mac, Ctrl en el resto. */
  primario?: boolean;
  shift?: boolean;
  alt?: boolean;
}

export interface AtajoLienzo {
  id: string;
  tipo: 'tecla' | 'gesto';
  /** `KeyboardEvent.key` en minúsculas; en los gestos, el texto que se muestra. */
  tecla: string;
  modificadores: ModificadoresAtajo;
  accion: AccionLienzo;
  descripcion: string;
  grupo: GrupoAyuda;
  /** Las flechas y el espacio se pueden mantener pulsados. */
  repetible?: boolean;
  /** Variantes de la misma acción que no necesitan una fila propia en la ayuda. */
  oculto?: boolean;
}

/** Solo estos elementos consumen el teclado: escribir nunca borra una tarjeta. */
export const SELECTOR_OBJETIVO_TEXTO = 'input, textarea, select, [contenteditable="true"]';

export function esObjetivoDeTexto(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest(SELECTOR_OBJETIVO_TEXTO));
}

export function esMac(): boolean {
  const nav = globalThis.navigator as Navigator | undefined;
  if (!nav) return false;
  const plataforma = nav.platform ?? '';
  const agente = nav.userAgent ?? '';
  return /mac|iphone|ipad|ipod/i.test(plataforma) || /mac os x|iphone|ipad/i.test(agente);
}

function primarioPulsado(event: KeyboardEvent): boolean {
  return event.metaKey || event.ctrlKey;
}

export function normalizarTecla(key: string): string {
  return key === ' ' ? 'espacio' : key.toLocaleLowerCase();
}

/** `suprimir` cubre Supr y ⌫: los dos borran, también en los teclados de portátil. */
function teclasCoinciden(tecla: string, esperada: string, event: KeyboardEvent): boolean {
  if (esperada === 'suprimir') return tecla === 'delete' || tecla === 'backspace';
  if (esperada === '?' && tecla === '/' && event.shiftKey) return true;
  return tecla === esperada;
}

export function coincideAtajo(event: KeyboardEvent, atajo: AtajoLienzo): boolean {
  if (atajo.tipo !== 'tecla') return false;
  const tecla = normalizarTecla(event.key);
  const esperada = atajo.tecla === ' ' ? 'espacio' : atajo.tecla.toLocaleLowerCase();
  if (!teclasCoinciden(tecla, esperada, event)) return false;
  if (Boolean(atajo.modificadores.primario) !== primarioPulsado(event)) return false;
  if (Boolean(atajo.modificadores.alt) !== event.altKey) return false;
  // `?` ya lleva Shift dentro de `event.key`; el resto exige la coincidencia exacta.
  if (esperada === '?') return true;
  return Boolean(atajo.modificadores.shift) === event.shiftKey;
}

export function atajoParaEvento(event: KeyboardEvent): AtajoLienzo | null {
  return ATAJOS_LIENZO.find((atajo) => coincideAtajo(event, atajo)) ?? null;
}

const ETIQUETAS_TECLA: Record<string, string> = {
  suprimir: 'Supr / ⌫',
  espacio: 'Espacio',
  escape: 'Esc',
  arrowleft: '←',
  arrowright: '→',
  arrowup: '↑',
  arrowdown: '↓',
  '?': '?',
};

export function etiquetaDeTecla(tecla: string): string {
  return ETIQUETAS_TECLA[tecla] ?? tecla.toLocaleUpperCase();
}

/** Texto final del atajo para el panel de ayuda. */
export function textoAtajo(atajo: AtajoLienzo): string {
  if (atajo.tipo === 'gesto') return atajo.tecla;
  const partes: string[] = [];
  if (atajo.modificadores.primario) partes.push(esMac() ? '⌘' : 'Ctrl');
  if (atajo.modificadores.alt) partes.push(esMac() ? '⌥' : 'Alt');
  if (atajo.modificadores.shift) partes.push('⇧');
  partes.push(etiquetaDeTecla(atajo.tecla));
  return partes.join(' + ');
}

const GRUPOS: GrupoAyuda[] = ['Selección', 'Edición', 'Mover', 'Orden', 'Lienzo', 'Vistas', 'Herramientas'];

export const ATAJOS_LIENZO: AtajoLienzo[] = [
  // Selección
  { id: 'seleccionar-todo', tipo: 'tecla', tecla: 'a', modificadores: { primario: true }, accion: 'seleccionarTodo', descripcion: 'Seleccionar todas las tarjetas visibles', grupo: 'Selección' },
  { id: 'cerrar', tipo: 'tecla', tecla: 'escape', modificadores: {}, accion: 'cerrar', descripcion: 'Cerrar el diálogo abierto o deseleccionar', grupo: 'Selección' },
  { id: 'seleccion-anadir', tipo: 'gesto', tecla: '⇧ + clic', modificadores: {}, accion: 'pan', descripcion: 'Alternar una tarjeta en la selección', grupo: 'Selección' },
  { id: 'seleccion-restar', tipo: 'gesto', tecla: '⌥ + marquesina', modificadores: {}, accion: 'pan', descripcion: 'Restar del rectángulo las tarjetas que toca', grupo: 'Selección' },

  // Edición
  { id: 'borrar', tipo: 'tecla', tecla: 'suprimir', modificadores: {}, accion: 'borrar', descripcion: 'Eliminar la selección al instante', grupo: 'Edición' },
  { id: 'agrupar', tipo: 'tecla', tecla: 'g', modificadores: { primario: true }, accion: 'agrupar', descripcion: 'Agrupar la selección en un marco', grupo: 'Edición' },
  { id: 'desagrupar', tipo: 'tecla', tecla: 'g', modificadores: { primario: true, shift: true }, accion: 'desagrupar', descripcion: 'Desagrupar sin mover nada', grupo: 'Edición' },
  { id: 'duplicar', tipo: 'tecla', tecla: 'd', modificadores: { primario: true }, accion: 'duplicar', descripcion: 'Duplicar la selección', grupo: 'Edición' },
  { id: 'copiar', tipo: 'tecla', tecla: 'c', modificadores: { primario: true }, accion: 'copiar', descripcion: 'Copiar las tarjetas seleccionadas', grupo: 'Edición' },
  { id: 'cortar', tipo: 'tecla', tecla: 'x', modificadores: { primario: true }, accion: 'cortar', descripcion: 'Cortar las tarjetas seleccionadas', grupo: 'Edición' },
  { id: 'pegar', tipo: 'tecla', tecla: 'v', modificadores: { primario: true }, accion: 'pegar', descripcion: 'Pegar tarjetas copiadas o cortadas', grupo: 'Edición' },
  { id: 'deshacer', tipo: 'tecla', tecla: 'z', modificadores: { primario: true }, accion: 'deshacer', descripcion: 'Deshacer', grupo: 'Edición' },
  { id: 'rehacer', tipo: 'tecla', tecla: 'z', modificadores: { primario: true, shift: true }, accion: 'rehacer', descripcion: 'Rehacer', grupo: 'Edición' },

  // Mover
  { id: 'mover-izquierda', tipo: 'tecla', tecla: 'arrowleft', modificadores: {}, accion: 'moverIzquierda', descripcion: 'Mover la selección 1 px (⇧: 10 px)', grupo: 'Mover', repetible: true },
  { id: 'mover-derecha', tipo: 'tecla', tecla: 'arrowright', modificadores: {}, accion: 'moverDerecha', descripcion: 'Mover la selección 1 px (⇧: 10 px)', grupo: 'Mover', repetible: true, oculto: true },
  { id: 'mover-arriba', tipo: 'tecla', tecla: 'arrowup', modificadores: {}, accion: 'moverArriba', descripcion: 'Mover la selección 1 px (⇧: 10 px)', grupo: 'Mover', repetible: true, oculto: true },
  { id: 'mover-abajo', tipo: 'tecla', tecla: 'arrowdown', modificadores: {}, accion: 'moverAbajo', descripcion: 'Mover la selección 1 px (⇧: 10 px)', grupo: 'Mover', repetible: true, oculto: true },
  { id: 'mover-izquierda-10', tipo: 'tecla', tecla: 'arrowleft', modificadores: { shift: true }, accion: 'moverIzquierda10', descripcion: 'Mover la selección 10 px', grupo: 'Mover', repetible: true },
  { id: 'mover-derecha-10', tipo: 'tecla', tecla: 'arrowright', modificadores: { shift: true }, accion: 'moverDerecha10', descripcion: 'Mover la selección 10 px', grupo: 'Mover', repetible: true, oculto: true },
  { id: 'mover-arriba-10', tipo: 'tecla', tecla: 'arrowup', modificadores: { shift: true }, accion: 'moverArriba10', descripcion: 'Mover la selección 10 px', grupo: 'Mover', repetible: true, oculto: true },
  { id: 'mover-abajo-10', tipo: 'tecla', tecla: 'arrowdown', modificadores: { shift: true }, accion: 'moverAbajo10', descripcion: 'Mover la selección 10 px', grupo: 'Mover', repetible: true, oculto: true },

  // Orden
  { id: 'adelante', tipo: 'tecla', tecla: ']', modificadores: {}, accion: 'traerAdelante', descripcion: 'Traer adelante un paso', grupo: 'Orden' },
  { id: 'atras', tipo: 'tecla', tecla: '[', modificadores: {}, accion: 'enviarAtras', descripcion: 'Enviar atrás un paso', grupo: 'Orden' },
  { id: 'frente', tipo: 'tecla', tecla: ']', modificadores: { primario: true }, accion: 'alFrente', descripcion: 'Traer al frente', grupo: 'Orden' },
  { id: 'fondo', tipo: 'tecla', tecla: '[', modificadores: { primario: true }, accion: 'alFondo', descripcion: 'Enviar al fondo', grupo: 'Orden' },

  // Lienzo
  { id: 'pan', tipo: 'tecla', tecla: 'espacio', modificadores: {}, accion: 'pan', descripcion: 'Espacio + arrastrar: mover el lienzo', grupo: 'Lienzo', repetible: true },
  { id: 'marquesina', tipo: 'gesto', tecla: 'Arrastrar el fondo', modificadores: {}, accion: 'pan', descripcion: 'Seleccionar tarjetas con un rectángulo (reemplaza la selección)', grupo: 'Lienzo' },
  { id: 'marquesina-anadir', tipo: 'gesto', tecla: '⇧ + arrastrar el fondo', modificadores: {}, accion: 'pan', descripcion: 'Sumar el rectángulo a la selección actual', grupo: 'Lienzo' },
  { id: 'rueda', tipo: 'gesto', tecla: 'Rueda o dos dedos', modificadores: {}, accion: 'pan', descripcion: 'Mover el lienzo', grupo: 'Lienzo' },
  { id: 'zoom', tipo: 'gesto', tecla: '⌘/Ctrl + rueda', modificadores: {}, accion: 'pan', descripcion: 'Acercar y alejar', grupo: 'Lienzo' },
  { id: 'duplicar-arrastrando', tipo: 'gesto', tecla: 'Alt/Opción + arrastrar', modificadores: {}, accion: 'pan', descripcion: 'Duplicar una tarjeta', grupo: 'Lienzo' },

  // Vistas
  { id: 'pliego', tipo: 'gesto', tecla: 'Doble clic en un proyecto', modificadores: {}, accion: 'pan', descripcion: 'Abrir el pliego de dos páginas', grupo: 'Vistas' },
  { id: 'diapositiva', tipo: 'gesto', tecla: '← →', modificadores: {}, accion: 'pan', descripcion: 'Cambiar diapositiva en Archivo o Muro (sin selección)', grupo: 'Vistas' },
  { id: 'renombrar', tipo: 'gesto', tecla: 'Doble clic en el título', modificadores: {}, accion: 'pan', descripcion: 'Renombrar una tarjeta o un marco', grupo: 'Vistas' },

  // Herramientas
  { id: 'herramientas', tipo: 'tecla', tecla: 'n', modificadores: {}, accion: 'herramientas', descripcion: 'Abrir la biblioteca de herramientas', grupo: 'Herramientas' },
  { id: 'ayuda', tipo: 'tecla', tecla: '?', modificadores: {}, accion: 'ayuda', descripcion: 'Abrir o cerrar este panel', grupo: 'Herramientas' },
];

export interface GrupoDeAyuda {
  grupo: GrupoAyuda;
  items: AtajoLienzo[];
}

/** La ayuda se arma con la misma tabla que ejecuta los atajos. */
export function gruposDeAyuda(): GrupoDeAyuda[] {
  return GRUPOS
    .map((grupo) => ({
      grupo,
      items: ATAJOS_LIENZO.filter((atajo) => atajo.grupo === grupo && !atajo.oculto),
    }))
    .filter((grupo) => grupo.items.length > 0);
}
