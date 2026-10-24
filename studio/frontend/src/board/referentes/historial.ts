import type { BoardCard, BoardDocument } from '../model';
import { readFrameData } from '../frames';
import { buildPublishZip } from '../publicar';
import { leerReferente, type Lectura, type Referente } from './model';

export interface FiltroLecturas {
  proyecto?: string;
  ojos?: string;
}

export interface OpcionesFiltro {
  proyectos: string[];
  ojos: string[];
}

export interface NotaObsidian {
  /** Nombre del archivo sin extensión; es también el texto de los enlaces [[ ]]. */
  nombre: string;
  contenido: string;
}

function valorFecha(fecha: string): number {
  const time = Date.parse(fecha);
  return Number.isFinite(time) ? time : 0;
}

/**
 * Línea de tiempo: de la más reciente a la más antigua. Una fecha vacía o
 * inválida va al final; a igual fecha gana la última añadida. No muta la entrada.
 */
export function ordenarLecturas(lecturas: readonly Lectura[]): Lectura[] {
  return lecturas
    .map((lectura, index) => ({ lectura, index }))
    .sort((a, b) => {
      const fechaA = valorFecha(a.lectura.fecha);
      const fechaB = valorFecha(b.lectura.fecha);
      if (fechaA !== fechaB) return fechaB - fechaA;
      return b.index - a.index;
    })
    .map(({ lectura }) => lectura);
}

function normalizarFiltro(value: string | undefined): string {
  return (value ?? '').trim().toLocaleLowerCase('es');
}

/** Proyecto y ojos vacíos significan «todos»; ambos se aplican a la vez. */
export function filtrarLecturas(lecturas: readonly Lectura[], filtro: FiltroLecturas): Lectura[] {
  const proyecto = normalizarFiltro(filtro.proyecto);
  const ojos = normalizarFiltro(filtro.ojos);
  return lecturas.filter((lectura) => {
    if (proyecto && lectura.proyecto.trim().toLocaleLowerCase('es') !== proyecto) return false;
    if (ojos && lectura.ojos.trim().toLocaleLowerCase('es') !== ojos) return false;
    return true;
  });
}

function unicos(valores: readonly string[]): string[] {
  const vistos = new Set<string>();
  const result: string[] = [];
  for (const valor of valores) {
    const limpio = valor.trim();
    if (!limpio || vistos.has(limpio)) continue;
    vistos.add(limpio);
    result.push(limpio);
  }
  return result.sort((a, b) => a.localeCompare(b, 'es'));
}

/** Valores presentes en las lecturas del referente, sin los vacíos. */
export function opcionesDeFiltro(referente: Referente): OpcionesFiltro {
  return {
    proyectos: unicos(referente.lecturas.map((lectura) => lectura.proyecto)),
    ojos: unicos(referente.lecturas.map((lectura) => lectura.ojos)),
  };
}

function slug(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('es')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

function nombreUnico(base: string, usados: Set<string>): string {
  let nombre = base || 'referente';
  let sufijo = 2;
  while (usados.has(nombre.toLocaleLowerCase('es'))) {
    nombre = `${base || 'referente'}-${sufijo}`;
    sufijo += 1;
  }
  usados.add(nombre.toLocaleLowerCase('es'));
  return nombre;
}

function yamlValor(value: string): string {
  return JSON.stringify(value);
}

function yamlLista(clave: string, valores: readonly string[]): string[] {
  if (!valores.length) return [`${clave}: []`];
  return [`${clave}:`, ...valores.map((valor) => `  - ${yamlValor(valor)}`)];
}

function metaLinea(etiqueta: string, value: string): string | null {
  return value.trim() ? `**${etiqueta}:** ${value.trim()}` : null;
}

function contenidoNota(
  nombre: string,
  referente: Referente,
  enlaces: readonly string[],
): string {
  const lineas: string[] = ['---'];
  lineas.push(`fuente: ${yamlValor(referente.url.trim())}`);
  lineas.push(...yamlLista('etiquetas', referente.etiquetas));
  lineas.push(...yamlLista('vistoEn', referente.vistoEn));
  lineas.push('---', '');
  lineas.push(`# ${referente.nombre.trim() || nombre}`, '');

  const meta = [
    metaLinea('Archivo de origen', referente.archivoOrigen),
    metaLinea('Autor', referente.autor),
    metaLinea('Año', referente.anio),
    metaLinea('Licencia', referente.licencia),
  ].filter((linea): linea is string => Boolean(linea));
  if (meta.length) lineas.push(...meta, '');

  if (referente.porQue.trim()) {
    lineas.push('## Por qué lo guardé', '', referente.porQue.trim(), '');
  }

  const aceptadas = ordenarLecturas(referente.lecturas).filter((lectura) => lectura.aceptada);
  lineas.push('## Lecturas aceptadas', '');
  if (!aceptadas.length) {
    lineas.push('_Sin lecturas aceptadas._', '');
  } else {
    for (const lectura of aceptadas) {
      const cabecera = [lectura.fecha, lectura.ojos, lectura.proyecto].filter((parte) => parte.trim()).join(' · ');
      lineas.push(`### ${cabecera || 'Lectura sin fecha'}`, '');
      if (lectura.texto.trim()) lineas.push(lectura.texto.trim(), '');
    }
  }

  if (enlaces.length) {
    lineas.push('## Mismo marco', '', ...enlaces.map((enlace) => `- [[${enlace}]]`), '');
  }

  return `${lineas.join('\n').trimEnd()}\n`;
}

interface Entrada {
  board: BoardDocument;
  card: BoardCard;
  referente: Referente;
  nombre: string;
  enlaces: Set<string>;
}

/**
 * Una nota por referente con frontmatter (fuente, etiquetas y vistoEn), sus
 * lecturas aceptadas y enlaces [[ ]] a los otros referentes del mismo marco.
 */
export function notasObsidian(boards: readonly BoardDocument[]): NotaObsidian[] {
  const entradas: Entrada[] = [];
  const usados = new Set<string>();

  for (const board of boards) {
    const referentesPorId = new Map<string, Entrada>();
    for (const card of board.cards) {
      if (card.type !== 'referente') continue;
      const referente = leerReferente(card);
      const base = slug(referente.nombre || card.title || card.id);
      const entrada: Entrada = {
        board,
        card,
        referente,
        nombre: '',
        enlaces: new Set<string>(),
      };
      entrada.nombre = nombreUnico(base, usados);
      referentesPorId.set(card.id, entrada);
      entradas.push(entrada);
    }
    // Los hijos de un mismo marco se enlazan entre sí.
    for (const card of board.cards) {
      if (card.type !== 'marco') continue;
      const hijos = readFrameData(card).hijos
        .map((id) => referentesPorId.get(id))
        .filter((entrada): entrada is Entrada => Boolean(entrada));
      if (hijos.length < 2) continue;
      for (const entrada of hijos) {
        for (const otro of hijos) {
          if (otro !== entrada) entrada.enlaces.add(otro.nombre);
        }
      }
    }
  }

  return entradas
    .map((entrada) => ({
      nombre: entrada.nombre,
      contenido: contenidoNota(
        entrada.nombre,
        entrada.referente,
        [...entrada.enlaces].sort((a, b) => a.localeCompare(b, 'es')),
      ),
    }))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
}

/** ZIP «store» con una nota .md por referente, listo para arrastrarlo a Obsidian. */
export function construirZipObsidian(boards: readonly BoardDocument[]): Uint8Array {
  const encoder = new TextEncoder();
  return buildPublishZip(
    notasObsidian(boards).map((nota) => ({
      name: `referentes/${nota.nombre}.md`,
      bytes: encoder.encode(nota.contenido),
    })),
  );
}
