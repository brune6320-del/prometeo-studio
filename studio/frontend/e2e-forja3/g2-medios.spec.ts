import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { abrirTableroCon, capturar, tarjeta } from './helpers';

const VIDEO = path.resolve('e2e-forja3/fixtures/video-1920.mp4');
const IMAGEN = path.resolve('e2e-forja3/fixtures/imagen-1920.png');

async function subirVideo(page: Page) {
  const input = page.locator('input[type="file"][accept*="video"]');
  await input.setInputFiles(VIDEO);
  const media = page.locator('.board-free-media').first();
  await expect(media).toBeVisible({ timeout: 15_000 });
  await expect(media.locator('video')).toBeVisible();
  return media;
}

async function zoomAl200(page: Page) {
  await page.locator('.board-zoom-value').click();
  await page.waitForTimeout(120);
  const zoom = await page.evaluate(() => {
    const stage = document.querySelector<HTMLElement>('.board-stage');
    return stage ? new DOMMatrixReadOnly(getComputedStyle(stage).transform).a : 1;
  });
  const deltaY = -Math.log(2 / zoom) / 0.0012;
  const caja = await page.locator('.board-viewport').boundingBox();
  if (!caja) throw new Error('Sin viewport');
  await page.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2);
  await page.keyboard.down('Control');
  await page.mouse.wheel(0, deltaY);
  await page.keyboard.up('Control');
  await page.waitForTimeout(220);
  await expect(page.locator('.board-zoom-value')).toHaveText('200%');
}

test.describe('G2 · imagen y vídeo libres', () => {
  test.setTimeout(120_000);

  test('el vídeo 1920×1080 es libre, se mueve, se redimensiona y conserva calidad al 200 %', async ({ page }) => {
    await abrirTableroCon(page, [tarjeta({ id: 'g2-nota', type: 'note', title: 'Nota de apoyo', body: 'El vídeo debe flotar solo.', x: 120, y: 120, width: 300 })]);
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    const media = await subirVideo(page);

    const inicial = await media.locator('video').evaluate((video) => ({
      ancho: (video as HTMLVideoElement).videoWidth,
      alto: (video as HTMLVideoElement).videoHeight,
      silencio: (video as HTMLVideoElement).muted,
      pausado: (video as HTMLVideoElement).paused,
      marco: Boolean(video.closest('.board-card')),
    }));
    expect(inicial).toEqual({ ancho: 1920, alto: 1080, silencio: true, pausado: true, marco: false });

    const caja = await media.boundingBox();
    expect(caja).not.toBeNull();
    const proporcion = caja!.width / caja!.height;
    expect(proporcion).toBeCloseTo(16 / 9, 1);

    const caption = media.locator('.board-free-media-caption');
    expect(await caption.evaluate((el) => getComputedStyle(el).opacity)).toBe('0');
    await media.hover();
    await page.waitForTimeout(160);
    expect(await caption.evaluate((el) => getComputedStyle(el).opacity)).toBe('1');

    await media.click({ position: { x: 120, y: 80 } });
    await expect.poll(() => media.locator('video').evaluate((video) => !(video as HTMLVideoElement).paused)).toBe(true);
    await media.click({ position: { x: 24, y: 24 } });
    await expect.poll(() => media.locator('video').evaluate((video) => (video as HTMLVideoElement).paused)).toBe(true);

    const handle = media.locator('.board-free-media-handle.se');
    await media.hover();
    const cajaHandle = await handle.boundingBox();
    if (!cajaHandle) throw new Error('Sin tirador SE');
    await page.mouse.move(cajaHandle.x + cajaHandle.width / 2, cajaHandle.y + cajaHandle.height / 2);
    await page.mouse.down();
    await page.mouse.move(cajaHandle.x + cajaHandle.width / 2 + 120, cajaHandle.y + cajaHandle.height / 2 + 40, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(120);
    const redimensionada = await media.boundingBox();
    expect(redimensionada).not.toBeNull();
    expect(redimensionada!.width).toBeGreaterThan(caja!.width + 40);
    expect(redimensionada!.width / redimensionada!.height).toBeCloseTo(16 / 9, 1);

    await zoomAl200(page);
    const al200 = await media.locator('video').evaluate((video) => {
      const rect = video.getBoundingClientRect();
      const stage = video.closest('.board-stage');
      return {
        ancho: (video as HTMLVideoElement).videoWidth,
        alto: (video as HTMLVideoElement).videoHeight,
        visibleAncho: rect.width,
        visibleAlto: rect.height,
        escala: stage ? new DOMMatrixReadOnly(getComputedStyle(stage).transform).a : 0,
      };
    });
    expect(al200.ancho).toBe(1920);
    expect(al200.alto).toBe(1080);
    expect(al200.escala).toBeCloseTo(2, 1);
    expect(al200.visibleAncho / al200.visibleAlto).toBeCloseTo(16 / 9, 1);

    await capturar(page, '../../REPORTES/capturas-forja3/g2-despues.png');
  });

  test('soltar del Finder y pegar una imagen crean objetos libres de resolución completa', async ({ page }) => {
    await abrirTableroCon(page, [tarjeta({ id: 'g2-nota-2', type: 'note', title: 'Nota de apoyo', body: 'Suelta una imagen.', x: 120, y: 120, width: 300 })]);
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    const base64 = fs.readFileSync(IMAGEN).toString('base64');

    const soltado = await page.evaluate(({ base64 }) => {
      const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
      const file = new File([bytes], 'imagen-1920.png', { type: 'image/png' });
      const dt = new DataTransfer();
      dt.items.add(file);
      const vp = document.querySelector<HTMLElement>('.board-viewport');
      if (!vp) return false;
      const caja = vp.getBoundingClientRect();
      const opciones = { bubbles: true, cancelable: true, clientX: caja.left + caja.width / 2, clientY: caja.top + caja.height / 2, dataTransfer: dt };
      vp.dispatchEvent(new DragEvent('dragover', opciones));
      vp.dispatchEvent(new DragEvent('drop', opciones));
      return true;
    }, { base64 });
    expect(soltado).toBe(true);
    await expect(page.locator('.board-free-media img')).toHaveCount(1, { timeout: 15_000 });

    await page.evaluate(({ base64 }) => {
      const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
      const file = new File([bytes], 'pegada-1920.png', { type: 'image/png' });
      const dt = new DataTransfer();
      dt.items.add(file);
      const evento = new Event('paste', { bubbles: true, cancelable: true });
      Object.defineProperty(evento, 'clipboardData', { value: dt });
      window.dispatchEvent(evento);
    }, { base64 });
    await expect(page.locator('.board-free-media img')).toHaveCount(2, { timeout: 15_000 });

    const natural = await page.locator('.board-free-media img').first().evaluate((img) => ({
      ancho: (img as HTMLImageElement).naturalWidth,
      alto: (img as HTMLImageElement).naturalHeight,
      marco: Boolean(img.closest('.board-card')),
    }));
    expect(natural).toEqual({ ancho: 1920, alto: 1080, marco: false });

    const segunda = page.locator('.board-free-media').nth(1);
    await segunda.hover();
    const antes = await segunda.boundingBox();
    if (!antes) throw new Error('Sin segunda imagen');
    const handle = segunda.locator('.board-free-media-handle.se');
    const cajaHandle = await handle.boundingBox();
    if (!cajaHandle) throw new Error('Sin tirador SE');
    await page.keyboard.down('Shift');
    await page.mouse.move(cajaHandle.x + cajaHandle.width / 2, cajaHandle.y + cajaHandle.height / 2);
    await page.mouse.down();
    await page.mouse.move(cajaHandle.x + cajaHandle.width / 2 + 80, cajaHandle.y + cajaHandle.height / 2 + 10, { steps: 6 });
    await page.mouse.up();
    await page.keyboard.up('Shift');
    await page.waitForTimeout(120);
    const despues = await segunda.boundingBox();
    if (!despues) throw new Error('Sin segunda imagen después');
    expect(Math.abs((despues.width / despues.height) - (antes.width / antes.height))).toBeGreaterThan(0.02);

    await capturar(page, '../../REPORTES/capturas-forja3/g2-despues-imagenes.png');
  });
});
