/**
 * I1 · editar en el visor, en memoria, sin una copia por palabra.
 * La prueba cuenta peticiones: 1 stage por gesto, 0 exportaciones hasta pulsar
 * «Exportar copia», y el texto aparece en menos de 100 ms.
 */
import { expect, test, type Page, type Route } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS } from './helpers';

const summary = {
  document_id: 'doc_sitio', source_sha256: 'b'.repeat(64), filename: 'contrato.pdf',
  pages_count: 1, total_nodes: 1, text_nodes_count: 1, image_nodes_count: 0, vector_nodes_count: 0,
  docgraph_version: '0.3', session_id: 'studio_sess_sitio', transaction_state: 'READY', staged_count: 0,
  capabilities: { is_born_digital: true, is_raster: false, can_text_edit: true, can_verify_physically: true, capability_badge: 'BORN_DIGITAL_FULL' },
};
const svg = encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="612" height="792"><rect width="100%" height="100%" fill="white"/>'
  + '<text x="72" y="110" font-family="Helvetica" font-size="28" fill="#111">CONTRATO DE SERVICIOS</text>'
  + '<text x="72" y="150" font-family="Helvetica" font-size="14" fill="#222">Contratado: Juan Perez</text></svg>',
);

async function json(route: Route, body: unknown) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

test('I1 · diez palabras en el visor no crean copia; exportar crea una', async ({ page }) => {
  let stages = 0;
  let exports = 0;
  let op = { op_id: 'op_1', type: 'VECTOR_REPLACE_TEXT', node_id: 't1', target_id: 'target_1', original_text: 'Contratado: Juan Perez', new_text: '', status: 'STAGED' };
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const endpoint = new URL(route.request().url()).pathname;
    if (endpoint === '/api/health') return json(route, { ready: true, version: 'super4-mock', ocr_available: false, workspace: { writable: true } });
    if (endpoint === '/api/samples') return json(route, { ok: true, samples: [{ key: 'contrato', description: 'Contrato de servicios' }] });
    if (endpoint === '/api/sessions/open_sample') return json(route, { ok: true, session_id: 'studio_sess_sitio', filename: 'contrato.pdf', summary });
    if (endpoint.endsWith('/nodes')) return json(route, { nodes: [{ id: 't1', type: 'TEXT', page: 0, bbox: [72, 135, 300, 155], text: 'Contratado: Juan Perez' }] });
    if (endpoint.endsWith('/stage_edit')) {
      stages += 1;
      const body = route.request().postDataJSON() as { new_text: string };
      op = { ...op, new_text: body.new_text };
      return json(route, { ok: true, operation: op, staged: op, staged_total: 1, transaction_state: 'STAGED' });
    }
    if (endpoint.endsWith('/transaction')) return json(route, { staged_operations: stages ? [op] : [], transaction_state: stages ? 'STAGED' : 'READY' });
    if (endpoint.endsWith('/preflight')) {
      return json(route, {
        ok: true, preflight: true, transaction_state: 'VERIFIED', original_unchanged: true,
        verifier_result: { ok: true, verdict: 'PASS', status: 'PASS', verified_globally: true, verifier_executed: true, operations_verified: 1, reason: 'Comprobación previa aprobada.' },
      });
    }
    if (endpoint.endsWith('/verify_and_export')) {
      exports += 1;
      return json(route, {
        ok: true, published: true, transaction_state: 'VERIFIED', output_filename: 'contrato.prometeo-v1.pdf',
        output_sha256: 'c'.repeat(64), original_unchanged: true, original_sha256: 'b'.repeat(64),
        verifier_result: { ok: true, verdict: 'PASS', status: 'PASS', verified_globally: true, verifier_executed: true, operations_verified: 1, reason: 'Verifier2 aprobó.' },
      });
    }
    if (endpoint.includes('/render')) return json(route, { page: { page_number: 0, width_pt: 612, height_pt: 792, image_data_url: 'data:image/svg+xml,' + svg } });
    return json(route, { ok: true });
  });

  await page.goto('/');
  await page.selectOption('#sample-select', 'contrato');
  const overlay = page.locator('.overlay[data-node-id="t1"]');
  await expect(overlay).toBeVisible();

  // Esc cancela: no se prepara nada.
  await overlay.dblclick();
  await page.locator('.overlay-text-input').fill('No debe quedar');
  await page.locator('.overlay-text-input').press('Escape');
  await expect(overlay).toContainText('Contratado: Juan Perez');
  expect(stages).toBe(0);

  // Diez palabras en una sola edición: una operación en memoria, ningún archivo.
  await overlay.dblclick();
  await page.locator('.overlay-text-input').fill('Contratado: Ana Ruiz de la Vega');
  const t0 = Date.now();
  await page.locator('.overlay-text-input').press('Enter');
  await expect(overlay).toContainText('Contratado: Ana Ruiz de la Vega');
  expect(Date.now() - t0).toBeLessThan(100);
  expect(stages).toBe(1);
  expect(exports).toBe(0);
  await expect(page.locator('[data-testid="preflight-status"]')).toContainText('aprobada');

  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.screenshot({ path: path.join(CAPTURAS, 'I1-despues-edicion-en-sitio.png') });

  // Solo el gesto de exportar crea la copia.
  await page.getByRole('button', { name: 'Exportar copia' }).click();
  await expect.poll(() => exports).toBe(1);
  expect(stages).toBe(1);
});
