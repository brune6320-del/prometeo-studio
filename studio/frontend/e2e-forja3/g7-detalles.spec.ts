import { expect, test, type Page } from '@playwright/test';
import { abrirTablero, abrirTableroCon, capturar, marco, mockBackend, tarjeta } from './helpers';

const LEGACY_KEY = 'prometeo-studio-plantillas-v1';

async function guardado(page: Page) {
  await page.waitForFunction(() => document.querySelector('.board-save-state')?.textContent === 'Guardado', null, { timeout: 10_000 });
}

async function puntoVacio(page: Page) {
  return page.evaluate(() => {
    const vp = document.querySelector<HTMLElement>('.board-viewport');
    if (!vp) throw new Error('Sin viewport');
    const caja = vp.getBoundingClientRect();
    for (let y = caja.top + 90; y < caja.bottom - 120; y += 18) {
      for (let x = caja.left + 120; x < caja.right - 120; x += 18) {
        const el = document.elementFromPoint(x, y);
        if (el && (el.classList.contains('board-viewport') || el.classList.contains('board-stage') || el.classList.contains('board-relations'))) return { x, y };
      }
    }
    return { x: caja.left + caja.width / 2, y: caja.top + caja.height / 2 };
  });
}

async function camara(page: Page) {
  return page.locator('.board-stage').evaluate((element) => {
    const matriz = new DOMMatrixReadOnly(getComputedStyle(element).transform);
    return { x: matriz.e, y: matriz.f, zoom: matriz.a };
  });
}

test.describe('G7 · detalles', () => {
  test.setTimeout(150_000);

  test('doble clic renombra el proyecto y persiste', async ({ page }) => {
    await abrirTableroCon(page, [tarjeta({ id: 'g7-n1', type: 'note', title: 'Nota', body: 'Proyecto', x: 200, y: 200 })]);
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    const selector = page.locator('#project-select');
    await expect(selector).toBeEnabled({ timeout: 20_000 });

    await selector.dblclick();
    const entrada = page.getByLabel('Nombre del proyecto');
    await expect(entrada).toBeVisible();
    await entrada.fill('Estudio Norte');
    await entrada.press('Enter');
    await expect(page.locator('#project-select')).toBeVisible();
    await expect(page.locator('#project-select option:checked')).toHaveText('Estudio Norte');

    const enBase = await page.evaluate(async () => new Promise<string | null>((resolve) => {
      const request = indexedDB.open('prometeo-studio-project-workspace');
      request.onerror = () => resolve(null);
      request.onsuccess = () => {
        const db = request.result;
        const get = db.transaction('projects', 'readonly').objectStore('projects').getAll();
        get.onsuccess = () => {
          const names = (get.result as Array<{ name?: string }>).map((item) => item.name ?? '');
          resolve(names.includes('Estudio Norte') ? 'Estudio Norte' : null);
        };
        get.onerror = () => resolve(null);
      };
    }));
    expect(enBase).toBe('Estudio Norte');

    await guardado(page);
    await page.reload();
    await abrirTablero(page);
    await expect(page.locator('#project-select option:checked')).toHaveText('Estudio Norte');
  });

  test('doble clic edita la URL de un enlace, valida y persiste', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta({ id: 'g7-link', type: 'link', title: 'Referencia', body: 'Una fuente.', url: 'https://example.com', x: 260, y: 220, width: 300 }),
    ]);
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    const url = page.locator('.board-card[data-card-type="link"] .board-link-url-text');
    await url.dblclick();
    const entrada = page.locator('.board-url-edit input');
    await expect(entrada).toBeVisible();
    await entrada.fill('https://example.org/estudio');
    await entrada.press('Enter');
    await expect(page.locator('.board-card[data-card-type="link"] a[aria-label="Abrir el enlace"]')).toHaveAttribute('href', 'https://example.org/estudio');

    await url.dblclick();
    await page.locator('.board-url-edit input').fill('javascript:alert(1)');
    await page.locator('.board-url-edit input').press('Enter');
    await expect(page.locator('.board-inline-error')).toContainText('http://');
    await page.keyboard.press('Escape');
    await expect(page.locator('.board-url-edit')).toHaveCount(0);
    await expect(page.locator('.board-card[data-card-type="link"] a[aria-label="Abrir el enlace"]')).toHaveAttribute('href', 'https://example.org/estudio');

    await guardado(page);
    await page.reload();
    await abrirTablero(page);
    await expect(page.locator('.board-card[data-card-type="link"] a[aria-label="Abrir el enlace"]')).toHaveAttribute('href', 'https://example.org/estudio');
  });

  test('el panel «?» muestra los atajos y se cierra con Esc', async ({ page }) => {
    await abrirTableroCon(page, [tarjeta({ id: 'g7-n2', type: 'note', title: 'Nota', body: 'Atajos', x: 220, y: 220 })]);
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    await page.keyboard.press('Shift+Slash');
    const panel = page.getByRole('dialog', { name: 'Atajos del tablero' });
    await expect(panel).toBeVisible();
    await expect(panel).toContainText('Espacio + arrastrar');
    await expect(panel).toContainText('Doble clic en la URL');
    await capturar(page, '../../REPORTES/capturas-forja3/g7-despues-atajos.png');
    await page.keyboard.press('Escape');
    await expect(panel).toHaveCount(0);

    await page.getByRole('button', { name: 'Atajos de teclado' }).click();
    await expect(panel).toBeVisible();
    await panel.getByRole('button', { name: 'Entendido' }).click();
    await expect(panel).toHaveCount(0);
  });

  test('arrastrar el fondo selecciona; Espacio + arrastrar mueve el lienzo', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta({ id: 'g7-m1', type: 'note', title: 'Uno', body: '', x: 300, y: 220 }),
      tarjeta({ id: 'g7-m2', type: 'note', title: 'Dos', body: '', x: 680, y: 240 }),
      tarjeta({ id: 'g7-m3', type: 'note', title: 'Tres', body: '', x: 480, y: 480 }),
    ]);
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    const caja = await page.locator('[data-card-id="g7-m1"]').boundingBox();
    if (!caja) throw new Error('Sin tarjeta');
    const inicio = { x: Math.max(16, caja.x - 60), y: Math.max(100, caja.y - 60) };
    await page.mouse.move(inicio.x, inicio.y);
    await page.mouse.down();
    await page.mouse.move(caja.x + caja.width + 70, caja.y + caja.height + 70, { steps: 14 });
    await expect(page.getByTestId('board-marquee')).toBeVisible();
    await page.mouse.up();
    await expect(page.locator('.board-card.selected')).toHaveCount(1);
    await expect(page.locator('.board-card.selected')).toHaveAttribute('data-card-id', 'g7-m1');

    const antes = await camara(page);
    const punto = await puntoVacio(page);
    await page.keyboard.down('Space');
    await expect(page.locator('.board-viewport.space-pan')).toBeVisible();
    await page.mouse.move(punto.x, punto.y);
    await page.mouse.down();
    await page.mouse.move(punto.x + 130, punto.y + 80, { steps: 12 });
    await page.mouse.up();
    await page.keyboard.up('Space');
    const despues = await camara(page);
    expect(Math.abs(despues.x - antes.x)).toBeGreaterThan(100);
    expect(Math.abs(despues.y - antes.y)).toBeGreaterThan(60);
    await expect(page.locator('.board-card.selected')).toHaveCount(1);
  });

  test('las plantillas guardadas se mudan del localStorage al proyecto y sobreviven', async ({ page }) => {
    await mockBackend(page);
    await abrirTablero(page);
    const board = {
      schemaVersion: 1,
      id: 'board-g7-legacy',
      title: 'Heredada',
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-01-01T00:00:00.000Z',
      cards: [{ id: 'legacy-n', type: 'note', title: 'Vieja', body: 'Plantilla anterior', x: 120, y: 120, width: 260, color: 'paper' }],
      relations: [],
    };
    await page.evaluate(({ key, board: seed }) => {
      localStorage.setItem(key, JSON.stringify([{ id: 'plantilla-legacy', nombre: 'Heredada', descripcion: 'Del localStorage', creada: '2026-01-01T00:00:00.000Z', builtin: false, board: seed }]));
    }, { key: LEGACY_KEY, board });
    await page.reload();
    await abrirTablero(page);
    await expect(page.locator('.board-toast')).toContainText(/se movió|se movieron/, { timeout: 20_000 });
    expect(await page.evaluate((key) => localStorage.getItem(key), LEGACY_KEY)).toBeNull();

    await page.getByRole('button', { name: 'Plantillas de tablero' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Plantillas de tablero' });
    await expect(dialogo).toBeVisible();
    await expect(dialogo.locator('.board-template-card').filter({ hasText: 'Heredada' })).toHaveCount(1);

    await dialogo.getByRole('button', { name: 'Guardar este tablero como plantilla' }).click();
    await expect(dialogo.locator('.board-template-card').filter({ hasText: 'Heredada' })).toHaveCount(1);
    await expect(dialogo.locator('.board-template-card')).toHaveCount(6);
    await dialogo.getByRole('button', { name: 'Cerrar' }).last().click();

    const guardadas = await page.evaluate(async () => new Promise<string[]>((resolve) => {
      const request = indexedDB.open('prometeo-studio-project-workspace');
      request.onerror = () => resolve([]);
      request.onsuccess = () => {
        const db = request.result;
        const get = db.transaction('projects', 'readonly').objectStore('projects').getAll();
        get.onsuccess = () => {
          const projects = get.result as Array<{ plantillas?: Array<{ nombre?: string }> }>;
          resolve(projects.flatMap((project) => (project.plantillas ?? []).map((item) => item.nombre ?? '')));
        };
        get.onerror = () => resolve([]);
      };
    }));
    expect(guardadas).toContain('Heredada');

    await page.reload();
    await abrirTablero(page);
    await page.getByRole('button', { name: 'Plantillas de tablero' }).click();
    const despues = page.getByRole('dialog', { name: 'Plantillas de tablero' });
    await expect(despues.locator('.board-template-card').filter({ hasText: 'Heredada' })).toHaveCount(1);
    await expect(despues.locator('.board-template-card')).toHaveCount(6);
  });

  test('captura del tablero con las nuevas piezas', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta({ id: 'g7-c1', type: 'note', title: 'Nota con doble clic', body: 'Renombrar e insertar.', x: 220, y: 180, width: 300 }),
      tarjeta({ id: 'g7-c2', type: 'link', title: 'Enlace', body: '', url: 'https://example.org', x: 620, y: 200, width: 300 }),
      marco('g7-c3', 980, 180, { title: 'BARATTOLO', datos: { alto: 300, hijos: [], vista: 'libre' } }),
    ]);
    await page.waitForTimeout(500);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    await capturar(page, '../../REPORTES/capturas-forja3/g7-despues.png');
  });
});
