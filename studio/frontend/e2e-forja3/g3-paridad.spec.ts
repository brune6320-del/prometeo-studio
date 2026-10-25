import { expect, test, type Page } from '@playwright/test';
import { abrirTableroCon, capturar, json } from './helpers';

const tarjeta = (id: string, type: string, title: string, x: number, y: number, extra: Record<string, unknown> = {}) => ({
  id,
  type,
  title,
  body: '',
  x,
  y,
  width: 280,
  color: 'paper',
  ...extra,
});

const tareas = (id: string, x: number, y: number) => tarjeta(id, 'tareas', 'Checklist', x, y, {
  datos: { tareas: [
    { id: 't1', texto: 'Revisar referencias', hecha: false, nivel: 0 },
    { id: 't2', texto: 'Elegir paleta', hecha: true, nivel: 0 },
  ] },
});

const columna = (id: string, x: number, y: number, hijos: string[] = []) => tarjeta(id, 'columna', 'Por hacer', x, y, {
  width: 300,
  datos: { hijos, plegada: false },
});

async function puntoDeArrastre(page: Page, id: string, selector = '.board-card-head') {
  const cabecera = page.locator(`[data-card-id="${id}"]`).locator(selector).first();
  const caja = await cabecera.boundingBox();
  if (!caja) throw new Error(`Sin cabecera para ${id}`);
  return { x: caja.x + Math.min(60, caja.width / 3), y: caja.y + caja.height / 2 };
}

async function moverDesdeCabeza(page: Page, id: string, dx: number, dy: number) {
  const { x, y } = await puntoDeArrastre(page, id);
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx, y + dy, { steps: 12 });
  await page.mouse.up();
}

test.describe('G3 · paridad Milanote', () => {
  test.setTimeout(120_000);

  test('conector con tirador, ancla, etiqueta y seguimiento al mover', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta('g3-a', 'note', 'Origen', 140, 140),
      tarjeta('g3-b', 'note', 'Destino', 620, 320),
    ]);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    const a = page.locator('[data-card-id="g3-a"]');
    const b = page.locator('[data-card-id="g3-b"]');
    await a.hover();
    const handle = a.locator('.board-connector-handle');
    await expect(handle).toBeVisible();
    const desde = await handle.boundingBox();
    const hasta = await b.boundingBox();
    if (!desde || !hasta) throw new Error('Sin cajas para conectar');
    await page.mouse.move(desde.x + desde.width / 2, desde.y + desde.height / 2);
    await page.mouse.down();
    await page.mouse.move(hasta.x + hasta.width / 2, hasta.y + hasta.height / 2, { steps: 12 });
    await page.mouse.up();
    const linea = page.locator('.board-relation-path');
    await expect(linea).toHaveCount(1);
    const antes = await linea.getAttribute('d');
    expect(antes?.startsWith('M ')).toBe(true);

    page.once('dialog', (dialog) => dialog.accept('depende de'));
    await linea.dispatchEvent('dblclick');
    await expect(page.locator('.board-relation-label')).toHaveText('depende de');

    await moverDesdeCabeza(page, 'g3-b', -160, 90);
    await expect.poll(async () => linea.getAttribute('d')).not.toBe(antes);
    await expect(linea).toHaveCount(1);
  });

  test('selección múltiple con ⇧ + rectángulo', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta('g3-m1', 'note', 'Uno', 140, 140),
      tarjeta('g3-m2', 'note', 'Dos', 480, 160),
      tarjeta('g3-m3', 'note', 'Tres', 280, 420),
    ]);
    const cajas = await Promise.all(['g3-m1', 'g3-m2', 'g3-m3'].map(async (id) => page.locator(`[data-card-id="${id}"]`).boundingBox()));
    const validas = cajas.filter((caja): caja is NonNullable<typeof caja> => Boolean(caja));
    const left = Math.min(...validas.map((caja) => caja.x)) - 40;
    const top = Math.min(...validas.map((caja) => caja.y)) - 40;
    const right = Math.max(...validas.map((caja) => caja.x + caja.width)) + 40;
    const bottom = Math.max(...validas.map((caja) => caja.y + caja.height)) + 40;

    await page.keyboard.down('Shift');
    await page.mouse.move(left, top);
    await page.mouse.down();
    await page.mouse.move(right, bottom, { steps: 14 });
    await expect(page.getByTestId('board-marquee')).toBeVisible();
    await page.mouse.up();
    await page.keyboard.up('Shift');
    await expect(page.locator('.board-card.selected')).toHaveCount(3);
    await expect(page.locator('.board-selection-bar')).toBeVisible();
    await expect(page.locator('.board-selection-count')).toContainText('3');
  });

  test('Alt/Opción + arrastrar duplica sin perder el original', async ({ page }) => {
    await abrirTableroCon(page, [tarjeta('g3-alt', 'note', 'Original', 260, 220)]);
    const card = page.locator('[data-card-id="g3-alt"]');
    const { x, y } = await puntoDeArrastre(page, 'g3-alt');
    await page.keyboard.down('Alt');
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(x + 190, y + 90, { steps: 14 });
    await page.mouse.up();
    await page.keyboard.up('Alt');
    await expect(page.locator('[data-card-type="note"]')).toHaveCount(2);
    await expect(card).toBeVisible();
    const copia = page.locator('.board-card.selected');
    await expect(copia).toHaveCount(1);
    expect(await copia.getAttribute('data-card-id')).not.toBe('g3-alt');
  });

  test('columna contenedora: recibe, ordena y se pliega', async ({ page }) => {
    await abrirTableroCon(page, [
      columna('g3-col', 140, 140),
      tarjeta('g3-suelta', 'note', 'Entra en la columna', 700, 260),
    ]);
    const col = page.locator('[data-card-id="g3-col"]');
    const destino = await col.boundingBox();
    const origen = await puntoDeArrastre(page, 'g3-suelta');
    if (!destino) throw new Error('Sin cajas');
    await page.mouse.move(origen.x, origen.y);
    await page.mouse.down();
    await page.mouse.move(destino.x + destino.width / 2, destino.y + 120, { steps: 14 });
    await page.mouse.up();
    await expect(col.locator('.board-column-item')).toHaveCount(1);
    await expect(col.locator('.board-column-item')).toContainText('Entra en la columna');
    await expect(page.locator('[data-card-id="g3-suelta"]')).toHaveCount(0);

    await col.locator('.board-column-fold').click();
    await expect(col).toHaveAttribute('data-columna-plegada', 'si');
    await expect(col.locator('.board-column-body')).toHaveCount(0);
    await expect(col.locator('.board-column-folded-hint')).toContainText('1');
    await col.locator('.board-column-fold').click();
    await expect(col).toHaveAttribute('data-columna-plegada', 'no');
  });

  test('lista de tareas: casilla, texto y tarea nueva', async ({ page }) => {
    await abrirTableroCon(page, [tareas('g3-tar', 240, 180)]);
    const card = page.locator('[data-card-id="g3-tar"]');
    const primera = card.locator('.board-task').first();
    await primera.locator('input[type="checkbox"]').check();
    await expect(primera).toHaveClass(/is-done/);
    await card.locator('.board-tasks-add').click();
    await expect(card.locator('.board-task')).toHaveCount(3);
    const nueva = card.locator('.board-task').last().locator('.board-task-text');
    await nueva.fill('Una tarea nueva');
    await nueva.press('Enter');
    await expect.poll(async () => nueva.inputValue()).toBe('');
  });

  test('URL pegada: el backend local devuelve título, descripción e imagen', async ({ page }) => {
    await abrirTableroCon(page, [tarjeta('g3-n', 'note', 'Nota', 180, 180)]);
    await page.route('**/api/url-preview*', (route) => json(route, {
      ok: true,
      url: 'https://example.com/articulo',
      titulo: 'Un artículo de ejemplo',
      descripcion: 'Descripción leída del open graph.',
      imagen: 'https://example.com/og.png',
    }));
    await page.getByRole('button', { name: 'Añadir enlace' }).click();
    await page.getByLabel('Dirección web').fill('https://example.com/articulo');
    await page.getByRole('button', { name: 'Agregar enlace' }).click();
    const preview = page.locator('.board-link-preview');
    await expect(preview).toBeVisible();
    await expect(preview).toContainText('Un artículo de ejemplo');
    await expect(preview).toContainText('Descripción leída del open graph.');
    await expect(preview.locator('img')).toHaveAttribute('src', 'https://example.com/og.png');
  });

  test('tablero dentro de tablero y plantillas', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta('g3-tab', 'tablero', 'Tablero Forja 2', 200, 160, {
        datos: { boardId: 'board-forja2', boardTitle: 'Tablero Forja 2' },
      }),
    ]);
    await expect(page.locator('.board-nested')).toContainText('Tablero Forja 2');
    await expect(page.locator('.board-nested-open')).toBeVisible();
    await page.getByRole('button', { name: 'Más' }).click();
    await page.getByRole('menuitem', { name: 'Tablero anidado' }).click();
    await expect(page.getByRole('dialog', { name: 'Anidar un tablero' })).toBeVisible();
    await page.locator('.board-template-card').first().click();
    await expect(page.locator('[data-card-type="tablero"]')).toHaveCount(2);

    await page.getByRole('button', { name: 'Plantillas de tablero' }).click();
    await expect(page.getByRole('dialog', { name: 'Plantillas de tablero' })).toBeVisible();
    await page.getByRole('button', { name: /Proyecto.*columnas/ }).click();
    await expect(page.locator('.board-column')).toHaveCount(3);
    await expect(page.locator('.board-column').first()).toContainText('Por hacer');
  });

  test('bloquear tarjeta: no se mueve ni se borra hasta desbloquear', async ({ page }) => {
    await abrirTableroCon(page, [tarjeta('g3-lock', 'note', 'Fija', 300, 240, { locked: true })]);
    const card = page.locator('[data-card-id="g3-lock"]');
    await expect(card).toHaveAttribute('data-locked', 'si');
    const antes = await card.boundingBox();
    if (!antes) throw new Error('Sin caja');
    await page.mouse.move(antes.x + 30, antes.y + 16);
    await page.mouse.down();
    await page.mouse.move(antes.x + 220, antes.y + 110, { steps: 10 });
    await page.mouse.up();
    const despues = await card.boundingBox();
    expect(Math.round(despues!.x)).toBe(Math.round(antes.x));
    await expect(card.locator('.board-card-delete')).toBeDisabled();
    await card.locator('.board-card-lock').click();
    await expect(card).toHaveAttribute('data-locked', 'no');
    await expect(card.locator('.board-card-delete')).toBeEnabled();
  });

  test('nota con formato mínimo visible al abrir', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta('g3-md', 'note', 'Formato', 260, 180, {
        body: '# Título\n\n**Negrita** y `código`\n\n- Uno\n- Dos\n\n> Cita\n\n```\nx = 1\n```',
      }),
    ]);
    const card = page.locator('[data-card-id="g3-md"]');
    await expect(card.locator('h3')).toHaveText('Título');
    await expect(card.locator('strong')).toHaveText('Negrita');
    await expect(card.locator('li')).toHaveCount(2);
    await expect(card.locator('blockquote')).toHaveText('Cita');
    await expect(card.locator('pre')).toContainText('x = 1');
    await card.locator('.board-note-read').dblclick();
    await expect(card.locator('.board-note-toolbar')).toBeVisible();
    await expect(card.locator('.board-note-toolbar button')).toHaveCount(6);
  });

  test('captura de la fase con todas las piezas juntas', async ({ page }) => {
    await page.route('**/api/url-preview*', (route) => json(route, {
      ok: true,
      url: 'https://example.com/moodboard',
      titulo: 'Referencia con vista previa',
      descripcion: 'Título, descripción e imagen leídos por el backend local.',
      imagen: 'https://example.com/og.png',
    }));
    await abrirTableroCon(page, [
      tarjeta('g3-cap-a', 'note', 'Idea con formato', 80, 90, { body: '# Dirección\n\n**Cálido** y sobrio.\n\n- Papel\n- Arena' }),
      tarjeta('g3-cap-b', 'link', 'Referencia', 470, 90, {
        url: 'https://example.com/moodboard',
        datos: { vistaPrevia: { titulo: 'Referencia con vista previa', descripcion: 'Título, descripción e imagen leídos por el backend local.', imagen: 'https://example.com/og.png', sitio: 'example.com' } },
      }),
      tareas('g3-cap-t', 860, 90),
      tarjeta('g3-cap-child', 'note', 'Dentro de la columna', 100, 500),
      columna('g3-cap-c', 70, 440, ['g3-cap-child']),
      tarjeta('g3-cap-l', 'note', 'Tarjeta fija', 470, 440, { locked: true }),
      tarjeta('g3-cap-n', 'tablero', 'Tablero anidado', 860, 440, { datos: { boardId: 'board-forja2', boardTitle: 'Tablero Forja 2' } }),
    ], 'G3 · paridad Milanote', [
      { id: 'g3-rel', from: 'g3-cap-a', to: 'g3-cap-b', label: 'base', tone: 'sage' },
    ]);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    await capturar(page, '../../REPORTES/capturas-forja3/g3-despues.png');
  });
});
