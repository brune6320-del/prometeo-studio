# G6 · Editor PDF

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Base | G5 cerrada en `6f64c7e` |
| Muestras | `case_a.pdf` (texto nativo) y `case_b_scan.pdf` (escaneado) de `fase0/assets/` |
| Alcance | Reintento idempotente, explicación del fallo y ventana estrecha |

## 1. Qué se arregla

### a) «Observación … ya ha sido preparada en esta transacción»

Antes, preparar dos veces la misma observación (o el mismo nodo de texto) devolvía error y obligaba a descartar el cambio. Ahora el motor **reutiliza la operación preparada** y actualiza su `new_text`:

- `stage_raster_edit`: si la observación ya está en la transacción, actualiza el texto y el `raster_op`, conserva `op_id`, devuelve `reused: true` y vuelve a invalidar cualquier copia verificada anterior.
- `stage_edit`: misma regla por `target_id` o `node_id`; un cambio por nodo, actualizado en el sitio.
- La interfaz deja de bloquear el botón para siempre: si el texto cambia después de preparar, ofrece **«Actualizar parche preparado»** / **«Actualizar cambio preparado»**. En texto nativo, mientras el texto preparado siga igual, el botón queda en «Cambio preparado» y deshabilitado.

### b) Por qué falla la verificación

El motor ya sabía qué comprobación falló; la interfaz solo lo enseñaba como JSON en modo técnico. Ahora:

- Los verificadores vectorial y raster emiten una lista `checks` por operación con `label`, `expected`, `actual` y `pass`.
- Vectorial añade `dx_pt`, `dy_pt`, `tolerance_pt`, `expected_font` y `found_fonts`.
- Raster añade `expected_text`, `old_text`, `observed_text` y comprobaciones de fuga fuera del parche, cambio real, borde, fondo, texto nuevo, texto anterior y confianza OCR.
- `VerifierPanel` pinta la tabla **Comprobación · Esperado · Obtenido** solo con las que fallan; si una sesión antigua no trae `checks`, se reconstruye desde los campos antiguos o desde `reasons`. Si no hay nada, se muestra el motivo del verificador, nunca un hueco.
- Al fallar, el panel inferior se expande para que la tabla no quede fuera de vista.

### c) Ventana estrecha

- Botones «Contenido» e «Inspector» en la cabecera: pliegan y despliegan los paneles en cualquier tamaño.
- Por debajo de 1000 px ambos paneles se pliegan y pasan a ser **cajones superpuestos** con fondo oscurecido; el visor ocupa todo el ancho. Al volver a una ventana ancha se recuperan.
- La cabecera ajusta el selector de ejemplo, oculta metadatos secundarios y permite desplazamiento horizontal sin desbordar la página.
- El visor usa `minmax(0, 1fr)` en estrecho: no queda un hueco en blanco ni un ancho mínimo que rompa la página.

## 2. Archivos

- `studio/backend/session.py`: reutilización de operaciones preparadas.
- `fase0/transactions.py`: checks vectoriales con esperado/obtenido.
- `studio/backend/export_pipeline.py`: checks raster y textos esperado/observado.
- `studio/frontend/src/verification/failures.ts`: lectura pura de `verifier_result`.
- `studio/frontend/src/components/VerifierPanel.tsx`: tabla de fallos.
- `studio/frontend/src/components/Inspector.tsx`: etiquetas de actualización y estado del parche.
- `studio/frontend/src/components/Toolbar.tsx`, `src/App.tsx`, `src/index.css`: paneles plegables y responsive.
- Tests: `tests/studio/test_g6_pdf.py` (unittest con el Python empaquetado), `e2e/g6-pdf.spec.ts`, `src/tests/failures.test.ts`.

## 3. Verificación

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 33 archivos, 191 tests |
| `npx oxlint` | 0 errores; sin warnings nuevos |
| `npx vite build` | correcto |
| `npx playwright test -c playwright.forja3.config.ts` | 23/23 (G0–G5) |
| `PROMETEO_PYTHON=… npx playwright test -c playwright.config.ts g6-pdf.spec.ts` | 3/3 con motor real |
| `python3 -m unittest tests.studio.test_g6_pdf` | 3/3 con `case_a.pdf` y `case_b_scan.pdf` |

Tests reales:

1. **Vectorial**: preparar «Contratado: Ana Ruiz» y luego «… (v2)» sobre el mismo nodo de `case_a.pdf` deja **una** operación con el texto nuevo y el mismo `op_id`.
2. **Raster**: preparar «CONTRATO2» y luego «CONTRATO3» sobre `ocr_p0_w4` de `case_b_scan.pdf` deja **un** parche actualizado; no aparece el error de transacción.
3. **Fallo real**: preparar «ZZZZZZZZ» en ese parche y verificar devuelve `FAILED` con `expected_text = ZZZZZZZZ`, `observed_text = DE` y la comprobación `text_new` marcada en falso. La tabla de la interfaz muestra esos dos valores.
4. **Estrecho**: a 760 y 520 px no hay desbordamiento horizontal, el visor conserva más de 500 px, los cajones se abren y cierran, y el documento sigue visible.

Capturas: `g6-antes-760.png`, `g6-antes-520.png`, `g6-despues-760.png`, `g6-despues-520.png`, `g6-despues-reintento.png`, `g6-despues-fallo.png`.

## 4. Límites

- En estrecho los paneles son cajones, no columnas redimensionables; el divisor de ancho sigue existiendo solo en ventana ancha.
- El cajón se cierra tocando el fondo o el mismo botón de la cabecera; no tiene gesto de arrastre.
- La confianza OCR se muestra con el umbral por defecto de 50 %; si un perfil futuro usa otro umbral, el valor esperado deberá acompañarse desde el motor.
- La prueba raster depende de Tesseract y de las observaciones de `case_b_scan.pdf`; si la muestra cambia, el test se salta de forma explícita, no se finge un aprobado.
- El arreglo de reintento reutiliza la operación; no crea una segunda versión ni conserva historial de intentos intermedios.
