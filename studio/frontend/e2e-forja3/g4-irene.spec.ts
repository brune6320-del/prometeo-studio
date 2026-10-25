import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { abrirTableroCon, capturar } from './helpers';

const IMAGEN = path.resolve('e2e-forja3/fixtures/imagen-1920.png');
const VIDEO = path.resolve('e2e-forja3/fixtures/video-1920.mp4');
const IMAGEN_B64 = fs.readFileSync(IMAGEN).toString('base64');
const VIDEO_B64 = fs.readFileSync(VIDEO).toString('base64');

function imagen(id: string, title: string, x = 40, y = 100, datos?: Record<string, unknown>) {
  return {
    id,
    type: 'media',
    title,
    body: '',
    x,
    y,
    width: 260,
    color: 'paper',
    datos,
    media: { name: `${id}.png`, mimeType: 'image/png', dataUrl: `data:image/png;base64,${IMAGEN_B64}`, kind: 'image' },
  };
}

function video(id: string, title: string, x = 40, y = 500) {
  return {
    id,
    type: 'media',
    title,
    body: '',
    x,
    y,
    width: 260,
    color: 'paper',
    media: { name: `${id}.mp4`, mimeType: 'video/mp4', dataUrl: `data:video/mp4;base64,${VIDEO_B64}`, kind: 'video' },
  };
}

const SEMILLA = () => [
  { id: 'g4-nota', type: 'note', title: 'IRENE GUERRA®', body: 'Una nota fija que describe el archivo.\n\nSegundo párrafo con el correo.', x: 600, y: 100, width: 300 },
  { id: 'g4-etq', type: 'etiqueta', title: 'IN EXHIBITION', body: 'DE-P01.01', x: 600, y: 180, width: 220 },
  imagen('g4-m1', 'Pareidolìa 01', 600, 220),
  imagen('g4-m2', 'Pareidolìa 02', 600, 300),
  video('g4-v1', 'Pareidolìa en bucle', 600, 420),
  { id: 'g4-texto', type: 'note', title: 'Pareidolìa', body: 'Un dispositivo especulativo sobre la imagen.\n\nComponentes de un ordenador desmontado.', x: 600, y: 520, width: 300 },
  { id: 'g4-enlace', type: 'link', title: 'Referencia', body: '', url: 'https://example.com/pareidolia', x: 600, y: 600, width: 300 },
  { id: 'g4-etq2', type: 'etiqueta', title: 'RESEARCH', body: 'AR-P01.01', x: 600, y: 660, width: 220 },
  imagen('g4-m3', 'The Century of the Bed 1999', 600, 700),
  { id: 'g4-etq3', type: 'etiqueta', title: 'RADIO STREAMING', body: 'FI-P01.01', x: 600, y: 760, width: 220 },
  imagen('g4-m4', 'Auris Liveset', 600, 800, { año: 2024 }),
  {
    id: 'g4-marco',
    type: 'marco',
    title: 'BARATTOLO',
    x: 980,
    y: 100,
    width: 840,
    datos: { alto: 800, hijos: ['g4-nota', 'g4-etq', 'g4-m1', 'g4-m2', 'g4-v1', 'g4-texto', 'g4-enlace', 'g4-etq2', 'g4-m3', 'g4-etq3', 'g4-m4'], vista: 'archivo' },
  },
];

async function abrir(page: Page) {
  await abrirTableroCon(page, SEMILLA());
  await page.waitForTimeout(500);
  const toast = page.locator('.board-toast button');
  if (await toast.count()) await toast.click({ timeout: 1000 }).catch(() => {});
  await expect(page.locator('.board-archivo').first()).toBeVisible();
}

async function irAVista(page: Page, vista: 'archivo' | 'muro' | 'mesa') {
  await page.locator('select[aria-label^="Ver como"]').first().selectOption(vista);
  await page.waitForTimeout(250);
}

async function abrirPantallaCompleta(page: Page) {
  await page.locator('.board-frame').first().dispatchEvent('dblclick');
  await expect(page.locator('.board-archive-fullscreen')).toBeVisible();
  await page.waitForTimeout(300);
}

test.describe('G4 · Irene, segunda pasada', () => {
  test.setTimeout(150_000);

  test('contador 1/3, flechas y solo el vídeo activo se reproduce', async ({ page }) => {
    await abrir(page);
    const bloque = page.locator('.archivo-block').first();
    const contador = bloque.locator('.archivo-counter');
    await expect(contador).toHaveText('1 / 3');

    const video = bloque.locator('video');
    await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).paused)).toBe(true);

    await bloque.locator('.archivo-zone.next').click({ position: { x: 40, y: 30 } });
    await expect(contador).toHaveText('2 / 3');
    await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).paused)).toBe(true);

    await bloque.locator('.archivo-zone.next').click({ position: { x: 40, y: 30 } });
    await expect(contador).toHaveText('3 / 3');
    await expect.poll(() => video.evaluate((element) => !(element as HTMLVideoElement).paused)).toBe(true);

    await bloque.locator('.archivo-zone.previous').click({ position: { x: 40, y: 30 } });
    await expect(contador).toHaveText('2 / 3');
    await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).paused)).toBe(true);

    await page.locator('.board-archivo').first().focus();
    await page.keyboard.press('ArrowRight');
    await expect(contador).toHaveText('3 / 3');
    await page.keyboard.press('ArrowLeft');
    await expect(contador).toHaveText('2 / 3');
  });

  test('doble clic abre el pliego de dos páginas, con flechas y Esc', async ({ page }) => {
    await abrir(page);
    await page.locator('.archivo-block').first().dblclick();
    const pliego = page.locator('.archivo-spread');
    await expect(pliego).toBeVisible();
    await expect(pliego.locator('.spread-page')).toHaveCount(2);
    await expect(pliego.locator('.spread-head-title')).toHaveText('Pareidolìa 01');
    await expect(pliego.locator('.spread-counter')).toHaveText('1 / 3');
    await expect(page.locator('.board-archive-fullscreen')).toHaveCount(0);

    await capturar(page, '../../REPORTES/capturas-forja3/g4-despues-pliego.png');

    await pliego.locator('.spread-zone.next').click({ position: { x: 30, y: 30 } });
    await expect(pliego.locator('.spread-counter')).toHaveText('2 / 3');
    await page.keyboard.press('ArrowRight');
    await expect(pliego.locator('.spread-counter')).toHaveText('3 / 3');
    await expect.poll(() => pliego.locator('video').evaluate((element) => !(element as HTMLVideoElement).paused)).toBe(true);
    await page.keyboard.press('ArrowLeft');
    await expect(pliego.locator('.spread-counter')).toHaveText('2 / 3');
    await page.keyboard.press('Escape');
    await expect(pliego).toHaveCount(0);
  });

  test('móvil: una columna, feed primero y barra de secciones', async ({ page }) => {
    await abrir(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(250);
    await abrirPantallaCompleta(page);

    const barra = page.locator('.archivo-mobilebar');
    await expect(barra).toBeVisible();
    await expect(barra.getByRole('button')).toHaveCount(3);

    const pantalla = page.locator('.board-archive-fullscreen');
    const feed = await pantalla.locator('.archivo-feed').boundingBox();
    const nota = await pantalla.locator('.archivo-note').boundingBox();
    const indice = await pantalla.locator('.archivo-index').boundingBox();
    expect(feed && nota && indice).toBeTruthy();
    expect(feed!.y).toBeLessThan(nota!.y);
    expect(nota!.y).toBeLessThan(indice!.y);

    const disposicion = await pantalla.locator('.archivo-columns').evaluate((element) => getComputedStyle(element).display);
    expect(disposicion).toBe('flex');

    await capturar(page, '../../REPORTES/capturas-forja3/g4-despues-movil.png');
  });

  test('mesa por año y muro con tono blanco, punteado y zonas', async ({ page }) => {
    await abrir(page);
    await irAVista(page, 'mesa');
    await page.getByRole('button', { name: 'Por año' }).click();

    const filas = page.locator('.mesa-year');
    await expect(filas).toHaveCount(3);
    await expect(filas.first().locator('.mesa-year-label')).toHaveText('2024');
    await expect(filas.nth(1).locator('.mesa-year-label')).toHaveText('1999');
    await expect(filas.nth(2).locator('.mesa-year-label')).toHaveText('Sin año');

    const tono = await page.locator('.board-mesa').evaluate((element) => {
      const style = getComputedStyle(element);
      const fila = document.querySelector<HTMLElement>('.mesa-year');
      return {
        fondo: style.backgroundColor,
        familia: style.fontFamily,
        borde: fila ? getComputedStyle(fila).borderBottomStyle : '',
      };
    });
    expect(tono.fondo).toBe('rgb(255, 255, 255)');
    expect(tono.familia.toLowerCase()).toMatch(/mono/);
    expect(tono.borde).toBe('dashed');

    await filas.first().locator('.mesa-year-more').click();
    await expect(page.locator('.archivo-spread')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('.archivo-spread')).toHaveCount(0);

    await capturar(page, '../../REPORTES/capturas-forja3/g4-despues-anos.png');

    await irAVista(page, 'muro');
    const muro = page.locator('.board-muro');
    await expect(muro).toBeVisible();
    const tonoMuro = await muro.evaluate((element) => ({
      fondo: getComputedStyle(element).backgroundColor,
      familia: getComputedStyle(element).fontFamily,
    }));
    expect(tonoMuro.fondo).toBe('rgb(255, 255, 255)');
    expect(tonoMuro.familia.toLowerCase()).toMatch(/mono/);

    const miniaturas = page.locator('.muro-thumb');
    await expect(miniaturas).toHaveCount(5);
    await miniaturas.first().click();
    const caja = page.locator('.board-muro-lightbox');
    await expect(caja).toBeVisible();
    await expect(caja.locator('.muro-lightbox-count')).toHaveText('1 / 5');
    await caja.locator('.muro-lightbox-zone.next').click({ position: { x: 20, y: 30 } });
    await expect(caja.locator('.muro-lightbox-count')).toHaveText('2 / 5');
    await page.keyboard.press('Escape');
    await expect(caja).toHaveCount(0);
  });

  test('captura de escritorio con el tono nuevo', async ({ page }) => {
    await abrir(page);
    await abrirPantallaCompleta(page);
    await expect(page.locator('.board-archivo.is-fullscreen .archivo-counter').first()).toHaveText('1 / 3');
    await capturar(page, '../../REPORTES/capturas-forja3/g4-despues.png');
  });
});
