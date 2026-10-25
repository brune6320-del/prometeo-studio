/**
 * H6 · asas, pegado en el cursor, medios y columnas.
 * Top 7, 10, 11 y 12 de A-1; debates D4, D9, D11 y D12.
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, leerTablero, mockReadyBackend, nota, tablero, type SeedCard } from './helpers';

test.use({ permissions: ['clipboard-read', 'clipboard-write'] });

const PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

function media(id: string, x: number, y: number, extra: Partial<SeedCard> = {}): SeedCard {
  return {
    id,
    type: 'media',
    title: 'Imagen',
    body: '',
    x,
    y,
    width: 320,
    height: 220,
    color: 'paper',
    media: { name: 'original.png', mimeType: 'image/png', kind: 'image', dataUrl: `data:image/png;base64,${PNG}` },
    ...extra,
  };
}

async function pegarTexto(page: Page, texto: string) {
  await page.evaluate((contenido) => {
    const datos = new DataTransfer();
    datos.setData('text/plain', contenido);
    const evento = new ClipboardEvent('paste', { bubbles: true, cancelable: true });
    Object.defineProperty(evento, 'clipboardData', { value: datos });
    window.dispatchEvent(evento);
  }, texto);
}

async function pegarImagen(page: Page) {
  await page.evaluate((base64) => {
    const binario = Uint8Array.from(atob(base64), (caracter) => caracter.charCodeAt(0));
    const archivo = new File([binario], 'pegada.png', { type: 'image/png' });
    const datos = new DataTransfer();
    datos.items.add(archivo);
    const evento = new ClipboardEvent('paste', { bubbles: true, cancelable: true });
    Object.defineProperty(evento, 'clipboardData', { value: datos });
    window.dispatchEvent(evento);
  }, PNG);
}

test('H6 · el asa de una nota cambia el ancho y una selección comparte el gesto', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  const board = tablero([nota('a', 120, 140, 'Ancho A'), nota('b', 520, 140, 'Ancho B')], 'board-h6-ancho', 'Anchos');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  const asaA = page.locator('[data-card-id="a"] .board-card-width-handle');
  const cajaAsa = await asaA.boundingBox();
  if (!cajaAsa) throw new Error('Sin asa de ancho.');
  await page.mouse.move(cajaAsa.x + cajaAsa.width / 2, cajaAsa.y + cajaAsa.height / 2);
  await page.mouse.down();
  await page.mouse.move(cajaAsa.x + 100, cajaAsa.y + cajaAsa.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect.poll(async () => (await leerTablero(page, 'board-h6-ancho'))?.cards.find((card) => card.id === 'a')?.width).toBeGreaterThan(300);

  // Dos seleccionadas: el mismo gesto aplica el mismo delta a las dos.
  await page.locator('[data-card-id="a"]').click();
  await page.locator('[data-card-id="b"]').click({ modifiers: ['Shift'] });
  const antes = await leerTablero(page, 'board-h6-ancho');
  const cajaAsaB = await page.locator('[data-card-id="a"] .board-card-width-handle').boundingBox();
  if (!cajaAsaB) throw new Error('Sin asa múltiple.');
  await page.mouse.move(cajaAsaB.x + cajaAsaB.width / 2, cajaAsaB.y + cajaAsaB.height / 2);
  await page.mouse.down();
  await page.mouse.move(cajaAsaB.x + 60, cajaAsaB.y + cajaAsaB.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h6-ancho');
    const a = guardado?.cards.find((card) => card.id === 'a')?.width ?? 0;
    const b = guardado?.cards.find((card) => card.id === 'b')?.width ?? 0;
    const antesA = antes?.cards.find((card) => card.id === 'a')?.width ?? 0;
    const antesB = antes?.cards.find((card) => card.id === 'b')?.width ?? 0;
    return Math.round((a - antesA) - (b - antesB));
  }).toBe(0);
  await page.screenshot({ path: path.join(CAPTURAS, 'H6-despues-anchos.png') });
});

test('H6 · marcos y columnas tienen ocho asas, no solo la esquina', async ({ page }) => {
  const board = tablero([
    { id: 'f1', type: 'marco', title: 'Marco', body: '', x: 120, y: 140, width: 460, color: 'paper', datos: { alto: 320, hijos: [], vista: 'libre' } },
    { id: 'c1', type: 'columna', title: 'Columna', body: '', x: 700, y: 140, width: 300, color: 'paper', datos: { hijos: [], plegada: false } },
  ], 'board-h6-asas', 'Asas');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  await expect(page.locator('[data-card-id="f1"] .board-frame-resize')).toHaveCount(8);
  await expect(page.locator('[data-card-id="c1"] .board-column-resize')).toHaveCount(8);
  await page.screenshot({ path: path.join(CAPTURAS, 'H6-antes-solo-se.png') });
});

test('H6 · pegar texto, URL, imagen y tarjetas nace en el cursor', async ({ page }) => {
  const board = tablero([nota('a', 120, 140, 'Copiable')], 'board-h6-pegar', 'Pegar');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  const viewport = await page.locator('.board-viewport').boundingBox();
  if (!viewport) throw new Error('Sin viewport.');

  // Texto plano → nota en el punto del cursor.
  await page.mouse.move(viewport.x + 260, viewport.y + 240);
  await pegarTexto(page, 'hola desde el portapapeles');
  await expect(page.locator('[data-card-id]')).toHaveCount(2);
  await expect.poll(async () => (await leerTablero(page, 'board-h6-pegar'))?.cards.some((card) => card.body === 'hola desde el portapapeles')).toBe(true);
  const texto = await leerTablero(page, 'board-h6-pegar');
  const notaPegada = texto?.cards.find((card) => card.body === 'hola desde el portapapeles');
  expect(notaPegada?.type).toBe('note');
  const posicionTexto = { x: notaPegada?.x, y: notaPegada?.y };

  // URL → enlace en otro punto.
  await page.mouse.move(viewport.x + 820, viewport.y + 460);
  await pegarTexto(page, 'https://example.com/lectura');
  await expect.poll(async () => (await leerTablero(page, 'board-h6-pegar'))?.cards.some((card) => card.type === 'link' && card.url === 'https://example.com/lectura')).toBe(true);
  const conEnlace = await leerTablero(page, 'board-h6-pegar');
  const enlace = conEnlace?.cards.find((card) => card.type === 'link');
  expect({ x: enlace?.x, y: enlace?.y }).not.toEqual(posicionTexto);

  // Imagen → medio en el cursor.
  await page.mouse.move(viewport.x + 500, viewport.y + 560);
  await pegarImagen(page);
  await expect.poll(async () => (await leerTablero(page, 'board-h6-pegar'))?.cards.some((card) => card.type === 'media' && card.media && (card.media as { name?: string }).name === 'pegada.png')).toBe(true);

  // Copiar una tarjeta deja marca y texto legible; pegarla duplica con ids nuevos.
  await page.locator('[data-card-id="a"]').click();
  await page.keyboard.press('Meta+c');
  const portapapeles = await page.evaluate(() => navigator.clipboard.readText());
  expect(portapapeles).toContain('prometeo-studio/tarjetas:');
  expect(portapapeles).toContain('Copiable');
  const antes = await leerTablero(page, 'board-h6-pegar');
  await page.mouse.move(viewport.x + 300, viewport.y + 620);
  await pegarTexto(page, portapapeles);
  await expect.poll(async () => (await leerTablero(page, 'board-h6-pegar'))?.cards.length).toBe((antes?.cards.length ?? 0) + 1);
  const despues = await leerTablero(page, 'board-h6-pegar');
  const copias = despues?.cards.filter((card) => card.title === 'Copiable') ?? [];
  expect(copias.length).toBe(2);
  expect(copias[0].id).not.toBe(copias[1].id);
  await page.screenshot({ path: path.join(CAPTURAS, 'H6-despues-pegado-cursor.png') });
});

test('H6 · leyenda, alt, reemplazo y recorte del medio libre', async ({ page }) => {
  const board = tablero([media('m1', 160, 160)], 'board-h6-medio', 'Medios');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  const antes = await leerTablero(page, 'board-h6-medio');
  const original = antes?.cards[0];

  const imagen = page.locator('[data-card-id="m1"]');
  await imagen.click();
  const alt = page.getByLabel('Texto alternativo de la imagen');
  await expect(alt).toBeVisible();
  await alt.fill('Una textura de prueba');
  await expect.poll(async () => (await leerTablero(page, 'board-h6-medio'))?.cards[0].datos && ((await leerTablero(page, 'board-h6-medio'))?.cards[0].datos as { alt?: string }).alt).toBe('Una textura de prueba');

  await imagen.getByRole('button', { name: 'Recortar imagen' }).click();
  await expect(imagen.getByRole('button', { name: 'Terminar recorte' })).toBeVisible();
  const zoomRecorte = page.getByLabel('Zoom del recorte');
  await zoomRecorte.focus();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await imagen.getByRole('button', { name: 'Terminar recorte' }).click();
  await expect(page.getByLabel('Zoom del recorte')).toHaveCount(0);
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h6-medio');
    return (guardado?.cards[0].datos as { recorte?: { escala?: number } } | undefined)?.recorte?.escala;
  }).toBeGreaterThan(1);

  // Reemplazar conserva caja y posición; el anterior queda en la tarjeta hasta confirmar.
  const archivo = test.info().outputPath('nueva.png');
  fs.writeFileSync(archivo, Buffer.from(PNG, 'base64'));
  await imagen.getByLabel('Archivo para reemplazar la imagen').setInputFiles(archivo);
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h6-medio');
    return (guardado?.cards[0].media as { name?: string } | undefined)?.name;
  }).toBe('nueva.png');
  const despues = await leerTablero(page, 'board-h6-medio');
  expect({ x: despues?.cards[0].x, y: despues?.cards[0].y, width: despues?.cards[0].width, height: despues?.cards[0].height })
    .toEqual({ x: original?.x, y: original?.y, width: original?.width, height: original?.height });
  expect((despues?.cards[0].datos as { mediaAnterior?: { name?: string } } | undefined)?.mediaAnterior?.name).toBe('original.png');
  await page.screenshot({ path: path.join(CAPTURAS, 'H6-despues-medio-leyenda.png') });
});

test('H6 · la columna reordena dentro, saca al lienzo y conserva el orden al recargar', async ({ page }) => {
  const board = tablero([
    { id: 'c1', type: 'columna', title: 'Columna', body: '', x: 140, y: 140, width: 320, color: 'paper', datos: { hijos: ['a', 'b', 'c'], plegada: false } },
    nota('a', 500, 160, 'A'),
    nota('b', 500, 300, 'B'),
    nota('c', 500, 440, 'C'),
  ], 'board-h6-columna', 'Columna');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  const filas = page.locator('[data-card-id="c1"] .board-column-item');
  await expect(filas).toHaveCount(3);
  // Arrastre HTML5 determinista: el mismo DataTransfer va del origen al destino.
  const transferencia = await page.evaluateHandle(() => new DataTransfer());
  await filas.nth(2).dispatchEvent('dragstart', { dataTransfer: transferencia });
  await filas.nth(0).dispatchEvent('dragover', { dataTransfer: transferencia });
  await filas.nth(0).dispatchEvent('drop', { dataTransfer: transferencia });
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h6-columna');
    return (guardado?.cards.find((card) => card.id === 'c1')?.datos as { hijos?: string[] } | undefined)?.hijos;
  }).toEqual(['c', 'a', 'b']);

  await page.reload();
  await page.getByRole('button', { name: 'Tablero' }).click();
  const trasRecarga = page.locator('[data-card-id="c1"] .board-column-item-title');
  await expect(trasRecarga).toHaveText(['C', 'A', 'B']);

  // Sacar una tarjeta al lienzo la desvincula y le da la posición del cursor.
  const viewport = await page.locator('.board-viewport').boundingBox();
  if (!viewport) throw new Error('Sin viewport.');
  const transferenciaSalida = await page.evaluateHandle(() => new DataTransfer());
  const filaSalida = page.locator('[data-card-id="c1"] .board-column-item').nth(1);
  await filaSalida.dispatchEvent('dragstart', { dataTransfer: transferenciaSalida });
  await page.locator('.board-viewport').dispatchEvent('dragover', { dataTransfer: transferenciaSalida, clientX: viewport.x + 700, clientY: viewport.y + 500 });
  await page.locator('.board-viewport').dispatchEvent('drop', { dataTransfer: transferenciaSalida, clientX: viewport.x + 700, clientY: viewport.y + 500 });
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h6-columna');
    return (guardado?.cards.find((card) => card.id === 'c1')?.datos as { hijos?: string[] } | undefined)?.hijos;
  }).toEqual(['c', 'b']);
  const trasSacar = await leerTablero(page, 'board-h6-columna');
  expect(trasSacar?.cards.find((card) => card.id === 'a')?.x).toBeGreaterThan(0);
  await page.screenshot({ path: path.join(CAPTURAS, 'H6-despues-columna-orden.png') });
});
