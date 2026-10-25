# G8 · Caza de errores

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Base | G7 cerrada en `01e31b5` |
| Método | Playwright como Bruno + soak continuo |
| Resultado | 4 fallos graves corregidos; 5 menores documentados; 0 errores de consola en 691 ciclos |

## 1. Recorrido

### Caza guiada (`g8-caza.spec.ts`, 18,7 s, 60 fps)

Un tablero con nota, enlace, tareas, columna, etiqueta, dos imágenes y un marco en Archivo. El recorrido:

- abre y cierra el panel `?`;
- recorre las cinco categorías de «+ Más» y añade Tareas, Referente, Entropía y Tablero anidado;
- renombra una nota y edita una URL;
- recorre Archivo (carrusel, pliego, flechas, Esc), Muro (caja de luz, zona derecha, Esc), Mesa (por año, `More →`, Esc);
- mueve el lienzo con `Espacio` + arrastrar y selecciona con rectángulo;
- cambia a Archivo Irene, guarda una plantilla, recarga y comprueba URL, sistema y plantilla;
- mide `requestAnimationFrame`.

Resultado: **0 errores de consola, 0 `pageerror`, 60 fps**. Solo aparecen `GET /api/samples · net::ERR_ABORTED`, que son cancelaciones esperadas al desmontar la bienvenida al entrar al tablero; no son fallos.

### Soak de 15 minutos (`g8-soak.spec.ts`, 903 s)

- **691 ciclos** de añadir y borrar una nota, alternar Archivo/Muro/Mesa, abrir pliego y caja de luz, abrir atajos, mover el lienzo, cambiar de sistema de diseño y medir el ritmo.
- **15 recargas** completas con recuperación del tablero.
- **Peor FPS: 57**; media del entorno: 60.
- **0 errores de consola y 0 `pageerror`.**

## 2. Fallos encontrados y qué se hizo

| # | Hallazgo | Severidad | Estado |
|---:|---|---|---|
| 1 | `Esc` no cerraba los diálogos del tablero (plantillas, anidar, enlace, proyecto, referencia PDF, referencias y «Volver a mirar»). El foco quedaba atrapado y el teclado prometido no cumplía. | **Grave** | Corregido: `Esc` cierra el diálogo superior antes que cualquier otra capa; comprobado en la caza y en las suites. |
| 2 | Una herramienta nueva podía caer encima del marco en Archivo y **bloquear los clics del carrusel** (Entropía sobre BARATTOLO). | **Grave** | Corregido: búsqueda en espiral del primer hueco visible, usando el tablero más reciente y las medidas reales de las tarjetas. |
| 3 | A 1280 px la cabecera del tablero se quedaba sin sitio y el buscador **tapaba los botones** de crear/importar/eliminar al añadir el botón `?`. | **Grave** | Corregido: por debajo de 1380 px la cabecera envuelve en dos filas; no se oculta ninguna acción. |
| 4 | Las plantillas guardadas vivían en `localStorage` global; cambiar de proyecto o limpiar el navegador las perdía. | **Grave** | Corregido en G7: migración al proyecto en IndexedDB y borrado de la clave antigua. |
| 5 | `/api/samples` aparece como petición abortada al entrar al tablero. | No es fallo | Cancelación esperada de la pantalla que se desmonta; se excluye del recuento. |
| 6 | Borrar una tarjeta pide confirmación nativa; la caza no la aceptaba. | No es fallo | Comportamiento correcto. El soak acepta el diálogo. |
| 7 | Doble clic en el `<select>` de proyecto puede abrir además el desplegable nativo. | Menor | Documentado; el campo de renombrado aparece igualmente. |
| 8 | La cabecera pasa a dos filas por debajo de 1380 px. | Cosmético | Aceptado: conserva todas las acciones y no tapa el lienzo. |
| 9 | En un tablero muy lleno, la espiral puede agotarse y la tarjeta cae en la esquina visible. | Menor | Documentado; el usuario la mueve. |
| 10 | El panel `?` solo existe en el tablero, no en el editor PDF. | Menor | Deuda declarada; el PDF tiene su propia barra y atajos. |

## 3. Lo que se comprobó y no falló

- Las diez herramientas del registro se añaden desde la biblioteca sin excepciones.
- Archivo: carrusel circular, contador, vídeo solo en la diapositiva activa, pliego, flechas, Esc y pantalla completa.
- Muro: hojas de contacto, caja de luz, zonas de cursor y contador.
- Mesa: modo mesa, filas por año, `More →` y pliego.
- Renombrar proyecto, editar URL con validación, panel de atajos, plantillas, migración y recarga.
- Tema Forja 2 ↔ Archivo Irene en el tablero y persistencia tras recargar.
- PDF (G6): reintento de parche, tabla de fallo y ventana estrecha, con motor real.

## 4. Deuda que queda (no se toca en G8)

- Comentarios e hilos, búsqueda global entre tableros y etiquetas de color de Milanote (filas 13, 14, 17 y 18 de `G0-milanote.md`) no entran en Forja 3.
- Columnas sin redimensionado manual; conectores sin selector visual de color/grosor.
- 120 Hz y gestos con dedos reales en WKWebView siguen pendientes de la prueba de Bruno.
- Medios como data URL (límite 12 MB) y sin miniaturas.
- El soak cubre el tablero; el PDF tiene pruebas funcionales, no un soak de 15 minutos.

## 5. Cómo repetir

```bash
cd studio/frontend
npx playwright test -c playwright.forja3.config.ts g8-caza.spec.ts
PROMETEO_SOAK=1 npx playwright test -c playwright.forja3.config.ts g8-soak.spec.ts
```

Captura: `REPORTES/capturas-forja3/g8-despues.png`.
