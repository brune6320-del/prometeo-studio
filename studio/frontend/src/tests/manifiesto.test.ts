import { afterEach, describe, expect, it, vi } from 'vitest';
import { studioApi } from '../api/client';
import { buildArchive } from '../board/archivo';
import type { BoardCard, BoardDocument } from '../board/model';
import { boardToMarkdown } from '../board/model';
import {
  buildPublishPage,
  collectPublishPieces,
  publishFileName,
  type PublishMediaEntry,
} from '../board/publicar';
import { readFrameData } from '../board/frames';
import type { Referente } from '../board/referentes/model';
import { normalizarReferente } from '../board/referentes/model';
import type { EntropiaDatos, FuenteEntropia } from '../board/vanguardia/entropia';
import { gustosVacios, type Gustos } from '../board/vanguardia/gustos';
import {
  MAX_COLLAGES_MANIFIESTO,
  MAX_LINEAS_MANIFIESTO,
  collageADataUrl,
  crearMarcoManifiesto,
  normalizarLineasManifiesto,
  pedidoDeSeleccion,
  pedirManifiesto,
  plantillaManifiesto,
  seleccionarSemana,
} from '../board/vanguardia/manifiesto';

const AHORA = new Date('2026-10-24T12:00:00.000Z');

function tablero(cards: BoardCard[]): BoardDocument {
  return {
    schemaVersion: 1,
    id: 'board-semana',
    title: 'Semana',
    createdAt: '2026-10-01T00:00:00.000Z',
    updatedAt: '2026-10-24T00:00:00.000Z',
    cards,
    relations: [],
  };
}

function tirada(semilla: string): EntropiaDatos {
  return {
    modo: 'entropia',
    semilla,
    regla: 'dada',
    reglaNombre: 'Dadá',
    restriccion: 'solo dos colores',
    herramienta: 'note',
    fuentes: ['f1', 'f2'],
    disposicion: [
      { id: 'f1', x: 0, y: 0, w: 200, h: 160, rot: 4, z: 1 },
      { id: 'f2', x: 80, y: 60, w: 180, h: 140, rot: -6, z: 2 },
    ],
    ancho: 320,
    alto: 240,
    azarPuro: false,
    guardado: true,
    creado: '2026-10-24T10:00:00.000Z',
  };
}

function collage(id: string, creado: string, semilla = id): BoardCard {
  return {
    id,
    type: 'marco',
    title: `Collage ${id}`,
    body: '',
    x: 0,
    y: 0,
    width: 320,
    color: 'paper',
    datos: { ...tirada(semilla), creado },
  };
}

function referente(id: string, nombre: string, lecturas: Referente['lecturas']): BoardCard {
  return {
    id,
    type: 'referente',
    title: nombre,
    body: '',
    x: 0,
    y: 0,
    width: 260,
    color: 'paper',
    datos: { ...normalizarReferente({ nombre, lecturas }) } as Record<string, unknown>,
  };
}

const FUENTES: FuenteEntropia[] = [
  { id: 'f1', nombre: 'Letra', etiquetas: ['tipo'], imagen: { src: 'data:image/png;base64,AAAA', nombre: 'letra.png' } },
  { id: 'f2', nombre: 'Mapa', etiquetas: ['territorio'] },
];

function gustosDePrueba(): Gustos {
  return {
    version: 1,
    referentes: { f1: 4, f2: 2.5, f3: 1 },
    reglas: { dada: 5, suizo: 0.4 },
    herramientas: { note: 3.5 },
    pares: { 'f1|f2': 3 },
  };
}

describe('manifiesto: selección de la semana', () => {
  it('toma hasta 9 collages con ♥ de los últimos 7 días, lecturas aceptadas y 5 pesos subidos', () => {
    const cards: BoardCard[] = [];
    for (let indice = 0; indice < 11; indice += 1) {
      const fecha = new Date(AHORA.getTime() - indice * 12 * 60 * 60 * 1000).toISOString();
      cards.push(collage(`c${indice}`, fecha, `s${indice}`));
    }
    cards.push(collage('viejo', '2026-10-10T10:00:00.000Z'));
    cards.push({
      ...collage('sin-guardar', '2026-10-24T11:00:00.000Z'),
      datos: { ...tirada('x'), guardado: false },
    });
    cards.push(referente('r1', 'Letterform', [
      { fecha: '2026-10-22', proyecto: 'Luna', ojos: 'archivista', texto: 'La mancha repite el corte.', modelo: 'deepseek', aceptada: true },
      { fecha: '2026-10-21', proyecto: 'Luna', ojos: 'DJ', texto: 'Propuesta descartada.', modelo: 'deepseek', aceptada: false },
      { fecha: '2026-10-01', proyecto: 'Luna', ojos: 'niño', texto: 'Lectura vieja.', modelo: 'deepseek', aceptada: true },
    ]));

    const seleccion = seleccionarSemana([tablero(cards)], { ahora: AHORA, gustos: gustosDePrueba() });

    expect(seleccion.collages).toHaveLength(MAX_COLLAGES_MANIFIESTO);
    expect(seleccion.collages.some((item) => item.cardId === 'viejo')).toBe(false);
    expect(seleccion.collages.some((item) => item.cardId === 'sin-guardar')).toBe(false);
    expect(seleccion.collages[0].creado).toBe('2026-10-24T12:00:00.000Z');
    expect(seleccion.lecturas).toHaveLength(1);
    expect(seleccion.lecturas[0]).toMatchObject({ referente: 'Letterform', texto: 'La mancha repite el corte.' });
    expect(seleccion.pesos.map((peso) => peso.clave)).toEqual(['dada', 'f1', 'note', 'f1|f2', 'f2']);
    expect(seleccion.pesos.map((peso) => peso.subida)).toEqual([4, 3, 2.5, 2, 1.5]);
  });

  it('sin datos devuelve una semana vacía sin inventar collages', () => {
    const seleccion = seleccionarSemana([tablero([])], { ahora: AHORA, gustos: gustosVacios() });
    expect(seleccion.collages).toEqual([]);
    expect(seleccion.lecturas).toEqual([]);
    expect(seleccion.pesos).toEqual([]);
  });
});

describe('manifiesto: doce líneas como máximo', () => {
  it('recorta y renumera lo que devuelve el modelo', () => {
    const quince = Array.from({ length: 15 }, (_, indice) => `${indice + 1}. Línea ${indice + 1}`).join('\n');
    const lineas = normalizarLineasManifiesto(quince);
    expect(lineas).toHaveLength(MAX_LINEAS_MANIFIESTO);
    expect(lineas[0]).toBe('1. Línea 1');
    expect(lineas[11]).toBe('12. Línea 12');
  });

  it('parte un párrafo en frases y limpia vallas y viñetas', () => {
    const lineas = normalizarLineasManifiesto('```\n- Uno. Dos. Tres.\n```');
    expect(lineas).toEqual(['1. Uno.', '2. Dos.', '3. Tres.']);
    expect(normalizarLineasManifiesto('**1.** Negrita')).toEqual(['1. Negrita']);
  });

  it('la plantilla vacía tiene 12 líneas numeradas y el modo sin red la usa', async () => {
    expect(plantillaManifiesto()).toEqual(Array.from({ length: 12 }, (_, indice) => `${indice + 1}.`));

    const espia = vi.spyOn(studioApi, 'escribirManifiesto').mockRejectedValue(new Error('sin motor'));
    try {
      const resultado = await pedirManifiesto(seleccionarSemana([], { ahora: AHORA }), 'Luna');
      expect(resultado.disponible).toBe(false);
      expect(resultado.lineas).toEqual(plantillaManifiesto());
      expect(resultado.motivo).toContain('Sin conexión');
    } finally {
      espia.mockRestore();
    }
  });
});

function paginaDelMarco(cards: BoardCard[], hijos: string[]) {
  const pieces = collectPublishPieces(cards, hijos, 'archivo');
  const media: PublishMediaEntry[] = pieces.map((piece, indice) => ({
    cardId: piece.id,
    filename: publishFileName(indice, piece, 'svg'),
    width: 320,
    height: 240,
  }));
  return buildPublishPage({ frameTitle: 'Manifiesto', view: 'archivo', cards, childIds: hijos, media });
}

describe('manifiesto: marco en vista Archivo listo para publicar', () => {
  it('abre en Archivo, deja el manifiesto como nota fija y cada collage en el feed', () => {
    const seleccion = seleccionarSemana([tablero([
      collage('c1', '2026-10-24T09:00:00.000Z', '111'),
      collage('c2', '2026-10-23T09:00:00.000Z', '222'),
      referente('r1', 'Letterform', [
        { fecha: '2026-10-22', proyecto: 'Luna', ojos: 'archivista', texto: 'La mancha repite el corte.', modelo: 'deepseek', aceptada: true },
      ]),
    ])], { ahora: AHORA, gustos: gustosDePrueba() });

    const { frame, cards } = crearMarcoManifiesto(seleccion, ['1. Cortar.', '2. Repetir.'], {
      x: 1200,
      y: 80,
      fuentes: FUENTES,
      ahora: AHORA,
    });
    const datos = readFrameData(frame);
    expect(datos.vista).toBe('archivo');
    expect(datos.alto).toBe(460);
    expect(datos.hijos).toHaveLength(5);

    const archivo = buildArchive(cards, datos.hijos);
    expect(archivo.note?.title).toBe('Manifiesto semanal · 2026-10-24');
    expect(archivo.note?.body).toBe('1. Cortar.\n2. Repetir.');
    expect(archivo.blocks).toHaveLength(2);
    expect(archivo.blocks.every((block) => block.items.length === 1)).toBe(true);
    expect(archivo.blocks[0].code).toBe('semilla 111');
    expect(archivo.blocks[1].status).toBe('Collage 02');

    const page = paginaDelMarco(cards, datos.hijos);
    expect(page.media).toHaveLength(2);
    expect(page.html).toContain('1. Cortar.');
    expect(page.html).toContain('data-carousel');
    expect(page.html).toContain('src="media/01-collage-c1.svg"');
  });

  it('el SVG incrusta la imagen local y una clave devuelta por el modelo no entra en el export', async () => {
    const secreto = 'sk-manifiesto-no-debe-salir-2026';
    vi.stubEnv('DEEPSEEK_API_KEY', secreto);
    const seleccion = seleccionarSemana([tablero([
      collage('c1', '2026-10-24T09:00:00.000Z', '111'),
      referente('r1', 'Letterform', [
        { fecha: '2026-10-22', proyecto: 'Luna', ojos: 'archivista', texto: 'La mancha repite el corte.', modelo: 'deepseek', aceptada: true },
      ]),
    ])], { ahora: AHORA, gustos: gustosDePrueba() });

    const pedido = pedidoDeSeleccion(seleccion, 'Luna');
    expect(JSON.stringify(pedido)).not.toContain(secreto);

    const espia = vi.spyOn(studioApi, 'escribirManifiesto').mockResolvedValue({
      ok: true,
      disponible: true,
      modelo: 'deepseek-chat',
      lineas: [`1. ${secreto}`, '2. Repetir.'],
    });
    const resultado = await pedirManifiesto(seleccion, 'Luna');
    espia.mockRestore();
    expect(resultado.lineas.join('\n')).not.toContain(secreto);
    expect(resultado.lineas.join('\n')).toContain('[clave oculta]');

    const { frame, cards } = crearMarcoManifiesto(seleccion, resultado.lineas, {
      x: 1200,
      y: 80,
      fuentes: FUENTES,
      ahora: AHORA,
    });
    const dataUrl = collageADataUrl(seleccion.collages[0].datos, FUENTES);
    expect(dataUrl.startsWith('data:image/svg+xml;base64,')).toBe(true);
    expect(atob(dataUrl.split(',')[1])).toContain('data:image/png;base64,AAAA');

    const datos = readFrameData(frame);
    const page = paginaDelMarco(cards, datos.hijos);
    const markdown = boardToMarkdown(tablero(cards));
    expect(JSON.stringify(cards)).not.toContain(secreto);
    expect(page.html).not.toContain(secreto);
    expect(markdown).not.toContain(secreto);
    vi.unstubAllEnvs();
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
