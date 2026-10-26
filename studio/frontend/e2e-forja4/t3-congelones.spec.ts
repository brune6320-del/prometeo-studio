/**
 * T-3 · soak con grabación de congelones.
 *
 * Además de los fotogramas mide:
 *  - `longtask` con atribución (ventana/iframe y contenedor);
 *  - `long-animation-frame` (LoAF) con los scripts culpables y el tiempo de
 *    estilo/layout forzado;
 *  - marcas de la app: autosave, flushBoardWrites, historial de 30 días,
 *    LOD, índice H5 y cambio de `contain`.
 *
 * Cada fotograma > 100 ms se cruza con la acción del guion y las marcas
 * activas. El volcado completo queda en `test-results/t3-soak.json`.
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { abrirTableroSembrado, mockReadyBackend, nota, tablero } from './helpers';

const MINUTOS = Number(process.env.T3_MINUTOS ?? 15);
const TARJETAS = Number(process.env.T3_TARJETAS ?? 500);
const DIAGNOSTICO = process.env.T3_DIAGNOSTICO === '1';
const SALIDA = process.env.T3_JSON ?? 'test-results/t3-soak.json';
const CADENCIA_MS = Number(process.env.T3_CADENCIA ?? 1600);

interface Marca { nombre: string; t: number; detalle?: string; dur?: number }
interface Accion { nombre: string; t: number }
interface Fotograma { t: number; d: number }
interface TareaLarga { startTime: number; duration: number; name: string; attribution: Array<{ name?: string; containerType?: string; containerSrc?: string; containerName?: string }> }
interface ScriptLoaf { sourceURL?: string; sourceFunctionName?: string; invoker?: string; duration?: number; forcedStyleAndLayoutDuration?: number; pauseDuration?: number; windowAttribution?: string; sourceCharPosition?: number }
interface Loaf { startTime: number; duration: number; blockingDuration?: number; renderStart?: number; styleAndLayoutStart?: number; firstUIEventTimestamp?: number; scripts: ScriptLoaf[] }

function nombreDeAccion(acciones: Accion[], t: number): string {
  let actual = '(inicio)';
  for (const accion of acciones) {
    if (accion.t > t) break;
    actual = accion.nombre;
  }
  return actual;
}

/** Marcas que estaban dentro del pico o de los 2 s anteriores. */
function marcasCercanas(marcas: Marca[], t: number, duracion: number): string {
  const desde = t - 2000;
  const hasta = t + duracion;
  return marcas
    .filter((m) => m.t >= desde && m.t <= hasta)
    .slice(-14)
    .map((m) => `${m.nombre}${m.detalle ? `(${m.detalle})` : ''}${m.dur != null ? ` ${m.dur.toFixed(1)}ms` : ''} @${(m.t - t).toFixed(0)}`)
    .join(' · ') || '—';
}

function scriptCulpable(loaf: Loaf[] | undefined): string {
  if (!loaf?.length) return '—';
  const scripts = loaf.flatMap((entrada) => entrada.scripts ?? [])
    .filter((script) => (script.duration ?? 0) >= 5)
    .sort((a, b) => (b.duration ?? 0) - (a.duration ?? 0));
  return scripts.slice(0, 3).map((script) => {
    const archivo = script.sourceURL ? path.basename(script.sourceURL) : '(sin URL)';
    const funcion = script.sourceFunctionName || script.invoker || '(anónima)';
    return `${funcion} @ ${archivo} · ${(script.duration ?? 0).toFixed(1)} ms · layout ${(script.forcedStyleAndLayoutDuration ?? 0).toFixed(1)} ms`;
  }).join(' | ') || '—';
}

test(`T-3 · ${MINUTOS} min con ${TARJETAS} tarjetas: fotogramas, longtask y LoAF`, async ({ page }) => {
  test.setTimeout((MINUTOS + 6) * 60 * 1000);
  const errores: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') errores.push(`console: ${message.text()}`); });
  page.on('pageerror', (error) => errores.push(`pageerror: ${error.message}`));

  await page.addInitScript(() => {
    const techo = 4000;
    const registro = {
      activo: true,
      marcas: [] as unknown[],
      acciones: [] as unknown[],
      frames: [] as unknown[],
      longtasks: [] as unknown[],
      loaf: [] as unknown[],
      resumen: { cuenta: 0, suma: 0, max: 0, sobre33: 0 },
    };
    (window as unknown as { __prometeoT3: typeof registro }).__prometeoT3 = registro;
    const guardar = (lista: unknown[], valor: unknown) => {
      if (lista.length < techo) lista.push(valor);
    };
    try {
      new PerformanceObserver((lista) => {
        for (const entrada of lista.getEntries()) {
          const tarea = entrada as PerformanceEntry & { attribution?: Array<Record<string, unknown>> };
          guardar(registro.longtasks, {
            startTime: tarea.startTime,
            duration: tarea.duration,
            name: tarea.name,
            attribution: (tarea.attribution ?? []).map((item) => ({
              name: item.name,
              containerType: item.containerType,
              containerSrc: item.containerSrc,
              containerName: item.containerName,
            })),
          });
        }
      }).observe({ type: 'longtask', buffered: true });
    } catch { /* Navegador sin longtask. */ }
    try {
      new PerformanceObserver((lista) => {
        for (const entrada of lista.getEntries()) {
          const loaf = entrada as PerformanceEntry & {
            blockingDuration?: number;
            renderStart?: number;
            styleAndLayoutStart?: number;
            firstUIEventTimestamp?: number;
            scripts?: Array<Record<string, unknown>>;
          };
          guardar(registro.loaf, {
            startTime: loaf.startTime,
            duration: loaf.duration,
            blockingDuration: loaf.blockingDuration,
            renderStart: loaf.renderStart,
            styleAndLayoutStart: loaf.styleAndLayoutStart,
            firstUIEventTimestamp: loaf.firstUIEventTimestamp,
            scripts: (loaf.scripts ?? []).map((script) => ({
              sourceURL: script.sourceURL,
              sourceFunctionName: script.sourceFunctionName,
              invoker: script.invoker,
              duration: script.duration,
              forcedStyleAndLayoutDuration: script.forcedStyleAndLayoutDuration,
              pauseDuration: script.pauseDuration,
              windowAttribution: script.windowAttribution,
              sourceCharPosition: script.sourceCharPosition,
            })),
          });
        }
      }).observe({ type: 'long-animation-frame', buffered: true });
    } catch { /* Navegador sin LoAF. */ }
  });

  const cartas = Array.from({ length: TARJETAS }, (_, indice) => nota(
    `n${indice}`,
    (indice % 25) * 280,
    Math.floor(indice / 25) * 210,
    `Tarjeta ${indice}`,
    `cuerpo ${indice}`,
  ));
  await mockReadyBackend(page);
  await page.goto('/');
  await abrirTableroSembrado(page, tablero(cartas, 'board-soak', `Soak ${TARJETAS}`));
  await expect(page.locator('[data-card-id]')).toHaveCount(TARJETAS);

  await page.evaluate(() => {
    const registro = (window as unknown as { __prometeoT3: { frames: unknown[]; resumen: { cuenta: number; suma: number; max: number; sobre33: number } } }).__prometeoT3;
    let ultimo = performance.now();
    const tick = (ahora: number) => {
      const delta = ahora - ultimo;
      ultimo = ahora;
      registro.resumen.cuenta += 1;
      registro.resumen.suma += delta;
      registro.resumen.max = Math.max(registro.resumen.max, delta);
      if (delta > 33.4) registro.resumen.sobre33 += 1;
      if (delta > 50) (registro.frames as Array<{ t: number; d: number }>).push({ t: ahora, d: delta });
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  const accion = async (nombre: string, ejecutar: () => Promise<void>) => {
    await page.evaluate((n) => {
      const registro = (window as unknown as { __prometeoT3: { acciones: Array<{ nombre: string; t: number }> } }).__prometeoT3;
      registro.acciones.push({ nombre: n, t: performance.now() });
    }, nombre);
    await ejecutar();
  };

  const viewport = await page.locator('.board-viewport').boundingBox();
  if (!viewport) throw new Error('Sin viewport.');
  const centro = { x: viewport.x + viewport.width / 2, y: viewport.y + viewport.height / 2 };
  const inicio = Date.now();
  let iteracion = 0;
  while (Date.now() - inicio < MINUTOS * 60 * 1000) {
    iteracion += 1;
    await accion('rueda', async () => {
      await page.mouse.move(centro.x + (iteracion % 7) * 20, centro.y + (iteracion % 5) * 16);
      await page.mouse.wheel(0, iteracion % 2 === 0 ? 48 : -32);
    });

    if (iteracion % 6 === 0) {
      await accion('zoom', async () => {
        for (let i = 0; i < 3; i += 1) await page.keyboard.press('Meta+=');
        for (let i = 0; i < 3; i += 1) await page.keyboard.press('Meta+-');
      });
    }
    if (iteracion % 10 === 0) {
      await accion('indice', async () => {
        await page.keyboard.press('l');
        await page.getByLabel('Buscar en el índice').fill(`Tarjeta ${iteracion % TARJETAS}`);
        await page.waitForTimeout(40);
        await page.keyboard.press('Escape');
      });
    }
    if (iteracion % 12 === 0) {
      await accion('busqueda', async () => {
        await page.keyboard.press('Meta+f');
        const buscador = page.getByLabel('Buscar tarjetas');
        await buscador.fill(`${iteracion % TARJETAS}`);
        await page.waitForTimeout(40);
        await page.keyboard.press('Escape');
      });
    }
    if (iteracion % 25 === 0) {
      await accion('lod-sostenido', async () => {
        for (let i = 0; i < 6; i += 1) await page.keyboard.press('Meta+=');
        await page.waitForTimeout(1200);
        for (let i = 0; i < 6; i += 1) await page.keyboard.press('Meta+-');
        await page.waitForTimeout(500);
      });
    }
    if (iteracion % 15 === 0) {
      await accion('marquesina', async () => {
        await page.mouse.move(viewport.x + 160, viewport.y + 160);
        await page.mouse.down();
        await page.mouse.move(viewport.x + 360, viewport.y + 300, { steps: 4 });
        await page.mouse.up();
        await page.keyboard.press('Escape');
      });
    }
    if (iteracion % 20 === 0) {
      await accion('seleccionar-todo', async () => {
        await page.keyboard.press('Meta+a');
        await page.waitForTimeout(60);
        await page.keyboard.press('Escape');
      });
    }
    await page.waitForTimeout(CADENCIA_MS);
  }

  const datos = await page.evaluate(() => {
    const registro = (window as unknown as {
      __prometeoT3: {
        marcas: Marca[];
        acciones: Accion[];
        frames: Fotograma[];
        longtasks: TareaLarga[];
        loaf: Loaf[];
        resumen: { cuenta: number; suma: number; max: number; sobre33: number };
      };
    }).__prometeoT3;
    return {
      marcas: registro.marcas,
      acciones: registro.acciones,
      frames: registro.frames,
      longtasks: registro.longtasks,
      loaf: registro.loaf,
      resumen: registro.resumen,
    };
  });

  const fotogramas = datos.frames;
  const maximo = Math.max(datos.resumen.max, fotogramas.reduce((maximo, frame) => Math.max(maximo, frame.d), 0));
  const sobre33 = datos.resumen.sobre33;
  const sobre100 = fotogramas.filter((frame) => frame.d > 100);
  const totalFrames = datos.resumen.cuenta;
  const fps = datos.resumen.suma > 0 ? 1000 / (datos.resumen.suma / datos.resumen.cuenta) : 0;
  const tareasLargas = datos.longtasks.filter((tarea) => tarea.duration >= 100);
  const loafLargos = datos.loaf.filter((entrada) => entrada.duration >= 100);

  const picos = sobre100.map((frame) => {
    const cercanas = datos.longtasks.filter((tarea) => tarea.startTime + tarea.duration >= frame.t - frame.d && tarea.startTime <= frame.t);
    const loaf = datos.loaf.filter((entrada) => entrada.startTime + entrada.duration >= frame.t - frame.d && entrada.startTime <= frame.t);
    return [
      `| ${(frame.t / 1000).toFixed(1)} s | ${frame.d.toFixed(1)} ms | ${nombreDeAccion(datos.acciones, frame.t - frame.d)} | ${cercanas.map((t) => `${t.duration.toFixed(1)} ms`).join(', ') || '—'} | ${scriptCulpable(loaf)} | ${marcasCercanas(datos.marcas, frame.t - frame.d, frame.d)} |`,
    ].join(' ');
  });

  const tareas = tareasLargas.map((tarea) => [
    `| ${(tarea.startTime / 1000).toFixed(1)} s | ${tarea.duration.toFixed(1)} ms | ${nombreDeAccion(datos.acciones, tarea.startTime)} | ${scriptCulpable(datos.loaf.filter((entrada) => Math.abs(entrada.startTime - tarea.startTime) < 50))} | ${marcasCercanas(datos.marcas, tarea.startTime, tarea.duration)} |`,
  ].join(' '));

  console.log(`\nT-3 · ${iteracion} iteraciones · ${TARJETAS} tarjetas · ${MINUTOS} min`);
  console.log(`Fotogramas > 50 ms grabados: ${fotogramas.length} · máximo ${maximo.toFixed(1)} ms · > 33 ms ${sobre33} · > 100 ms ${sobre100.length}`);
  console.log(`Longtasks >= 100 ms: ${tareasLargas.length} · LoAF >= 100 ms: ${loafLargos.length}`);
  if (tareas.length) {
    console.log('\n| t | longtask | acción | script (LoAF) | marcas |');
    console.log('|---|---|---|---|---|');
    for (const linea of tareas) console.log(linea);
  }
  if (picos.length) {
    console.log('\n| t | fotograma | acción | longtask | script (LoAF) | marcas |');
    console.log('|---|---|---|---|---|---|');
    for (const linea of picos) console.log(linea);
  }

  const resumen = {
    fecha: new Date().toISOString(),
    minutos: MINUTOS,
    tarjetas: TARJETAS,
    iteraciones: iteracion,
    maximo,
    sobre33,
    sobre100: sobre100.length,
    totalFrames,
    fps,
    errores,
    longtasks: datos.longtasks,
    loaf: datos.loaf,
    marcas: datos.marcas,
    acciones: datos.acciones,
    frames: datos.frames,
  };
  fs.mkdirSync(path.dirname(SALIDA), { recursive: true });
  fs.writeFileSync(SALIDA, JSON.stringify(resumen, null, 2));

  expect(errores, errores.join('\n')).toEqual([]);
  expect(resumen.fps).toBeGreaterThan(20);
  if (!DIAGNOSTICO) {
    expect(maximo, `fotograma máximo ${maximo.toFixed(1)} ms`).toBeLessThan(100);
    expect(sobre33 / totalFrames, `${sobre33}/${totalFrames} fotogramas > 33 ms`).toBeLessThan(0.002);
    expect(tareasLargas, 'longtasks >= 100 ms').toEqual([]);
  }
});
