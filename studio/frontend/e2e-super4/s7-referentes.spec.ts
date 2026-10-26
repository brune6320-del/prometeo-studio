/**
 * I7 · un referente acepta cualquier adjunto y una URL se desarma en piezas.
 * El HTML y las imágenes los descarga el backend; aquí se simula su respuesta.
 */
import { expect, test, type Route } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, leerTablero, mockReadyBackend, referente, tablero } from './helpers';

const CAPTURA = 'data:image/svg+xml;base64,' + Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="#c0392b"/></svg>').toString('base64');
const PIEZA = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

async function json(route: Route, body: unknown) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

test.beforeEach(async ({ page }) => {
  await mockReadyBackend(page);
});

test('I7 · pegar una URL fija el original, «Desarmar» reparte piezas y un PDF entra como adjunto', async ({ page }) => {
  const URL_PAGINA = 'https://example.com/diseno';
  await page.route('**/api/url-preview**', (route) => json(route, {
    ok: true, url: URL_PAGINA, titulo: 'Página de prueba', descripcion: 'Una página para desarmar',
    imagen: 'https://example.com/og.png',
  }));
  await page.route('**/api/referentes/desarmar', (route) => json(route, {
    ok: true, url: URL_PAGINA, titulo: 'Página de prueba', descripcion: 'Una página para desarmar',
    host: 'example.com', captura: CAPTURA, paleta: ['#c0392b', '#faf7f2'], tipografias: ['Georgia, serif'],
    archivos: ['referentes/abc/img-01.png'],
    robots: 'permitido',
    piezas: [
      { kind: 'image', src: PIEZA, name: 'img-01.png', mime: 'image/png', alt: 'Pliegue', fuente: URL_PAGINA },
      { kind: 'text', rol: 'titular', text: 'El pliegue como medida', fuente: URL_PAGINA },
      { kind: 'text', rol: 'texto', text: 'Una hoja doblada cambia la escala.', fuente: URL_PAGINA },
      { kind: 'color', color: '#c0392b', fuente: URL_PAGINA },
      { kind: 'color', color: '#faf7f2', fuente: URL_PAGINA },
      { kind: 'font', font: 'Georgia, serif', fuente: URL_PAGINA },
    ],
  }));

  await abrirTableroSembrado(page, tablero([referente('r1', 200, 180)], 'board-super4-referentes', 'Referentes'));

  const original = page.locator('[data-card-id="r1"]');
  await original.locator('.board-referente-nombre').click();
  await page.evaluate((url) => {
    const datos = new DataTransfer();
    datos.setData('text/plain', url);
    window.dispatchEvent(new ClipboardEvent('paste', { clipboardData: datos, bubbles: true }));
  }, URL_PAGINA);

  await expect(original).toHaveAttribute('data-locked', 'si');
  await expect(original).toContainText('Página de prueba');
  await expect(original.locator('.board-referente-imagen')).toBeVisible();

  await original.getByRole('button', { name: /Desarmar/ }).click();
  await expect.poll(async () => {
    const board = await leerTablero(page, 'board-super4-referentes');
    return board?.cards.filter((card) => card.datos && (card.datos as Record<string, unknown>).desarmadoDe === URL_PAGINA).length ?? 0;
  }).toBe(6);
  const board = await leerTablero(page, 'board-super4-referentes');
  const piezas = board?.cards.filter((card) => card.datos && (card.datos as Record<string, unknown>).desarmadoDe === URL_PAGINA) ?? [];
  expect(piezas.every((card) => (card.datos as Record<string, unknown>).fuente === URL_PAGINA)).toBe(true);
  expect(piezas.some((card) => card.type === 'media')).toBe(true);
  expect(piezas.some((card) => card.title === 'Titular')).toBe(true);
  expect(piezas.some((card) => card.title === '#c0392b')).toBe(true);
  expect(piezas.some((card) => card.title === 'Tipografía')).toBe(true);
  await expect(original).toHaveAttribute('data-locked', 'si');
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.screenshot({ path: path.join(CAPTURAS, 'I7-despues-desarmar.png') });

  // Cualquier adjunto entra en el referente.
  await original.dblclick();
  const adjuntoInput = page.locator('.board-referente-editor input[type="file"]:not([accept])');
  await adjuntoInput.setInputFiles({
    name: 'pagina.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4\n% prueba\n'),
  });
  await expect(page.locator('.board-referente-adjuntos li')).toHaveCount(1);
  await page.locator('.board-referente-save').evaluate((elemento) => (elemento as HTMLButtonElement).click());
  await expect(original.locator('.board-referente-adjuntos a')).toContainText('pagina.pdf');
});
