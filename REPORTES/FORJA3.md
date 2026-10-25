# Forja 3 · cierre de campaña

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Estado | **G0–G8 cerradas** |
| Push | **No se hizo push.** El remoto es de Bruno. |
| Base de partida | `8f97dc8` (G0 aún sin abrir) |

## 1. Hashes por fase

| Fase | Commit | Cierre |
|---|---|---|
| G0 · Inventario Milanote | `11bf05f` | Tabla de 18 filas y captura de partida |
| G1 · Trackpad | `2b5394a` | Gestos, inercias, imán, inclinación, 3 E2E |
| G2 · Medios libres | `4796665` | Imagen/vídeo sueltos, Finder y Cmd+V, 2 E2E |
| G3 · Paridad Milanote | `7e89ae2` | Las 10 de G0, 10 E2E |
| G4 · Irene, 2.ª pasada | `4b898f5` | Deuda H-4, pliego, años, móvil, 5 E2E |
| G5 · Open Design | `6f64c7e` | Biblioteca «+ Más» y sistemas por tablero, 2 E2E |
| G6 · Editor PDF | `4c335d6` | Reintento idempotente, tabla de fallo, ventana estrecha |
| G7 · Detalles | `01e31b5` | Renombrar, URL, atajos, plantillas, gestos, 6 E2E |
| G8 · Caza de errores | `f15261f` | 4 graves corregidos, caza + soak de 15 min |

Estado vivo: `REPORTES/FORJA3-ESTADO.md`.

## 2. Tabla Milanote · antes / después

«Antes» es lo comprobado en G0 sobre el código de partida; «después» es el estado de esta campaña. No se hizo ingeniería inversa de Milanote: la columna de la izquierda es su ayuda pública.

| # | Milanote | Antes de Forja 3 | Después |
|---:|---|---|---|
| 1 | Imágenes y vídeos libres | Metidos en una tarjeta con cabecera, colors y 290 px | **Objetos libres** a resolución completa; proporción y drop del Finder (G2) |
| 2 | Arrastrar archivos del Finder | Solo por `<input type="file">` | **Drop del Finder** y Cmd+V de imagen (G2) |
| 3 | Conectores que siguen al mover | Línea centro→centro | **Tirador, ancla lateral, curva, etiqueta** y recálculo al mover (G3) |
| 4 | Selección con rectángulo | No existía; el fondo paneaba | **Arrastrar el fondo selecciona**; `⇧` añade; el pan pasó a `Espacio` + arrastrar y dos dedos (G3, G7) |
| 5 | Duplicar con Alt/Opción | No existía | **Alt/Opción + arrastrar** deja original y copia (G3) |
| 6 | Columnas contenedoras | No existían | **Columna** con orden, plegado y conservación de hijos (G3) |
| 7 | Listas de tareas | No existían | **Tareas** con casilla, texto, sangría y guardado (G3) |
| 8 | URL con vista previa | Solo se pegaba una URL de imagen | **Tarjeta de enlace** con título, descripción e imagen desde el backend local (G3) |
| 9 | Formato de nota | Texto plano | **Título, negrita, listas, cita y código** (G3) |
| 10 | Tablero dentro de tablero | Varios tableros, sin objeto en el lienzo | **Tarjeta de tablero anidado** que abre el otro sin perder el actual (G3) |
| 11 | Bloquear tarjeta | No existía | **Bloqueo** de posición y borrado con desbloqueo (G3) |
| 12 | Plantillas | No existían | **Plantillas** incluidas y guardadas, ahora **dentro del proyecto** (G3, G7) |
| 13 | Comentarios e hilos | No existen | **No** en esta campaña; deuda declarada |
| 14 | Búsqueda en todos los tableros | Filtro del tablero activo | Sigue **solo en el tablero activo**; deuda declarada |
| 15 | Atajos y panel `/` | ⌘Z/⇧⌘Z y `N` | **Panel `?`** con lienzo, tarjetas y vistas; `Espacio`, flechas, `?` y `Esc` (G7) |
| 16 | Colores de tarjeta | Cuatro colores | Se conservan |
| 17 | Buscar/ordenar por visto/modificado | No existía | **No** en esta campaña; deuda declarada |
| 18 | Etiquetas de color y filtros | Herramienta «Etiqueta» propia | No es el sistema de labels de Milanote; deuda declarada |

Fuera de Milanote, la campaña añadió: biblioteca navegable de herramientas, sistemas de diseño por tablero (Forja 2 y Archivo Irene), pliego de dos páginas, filas por año, muro con zonas de cursor, editor PDF con reintento idempotente y explicación de fallos, y paneles plegables.

## 3. Verificación final

Ejecutado en `studio/frontend` salvo lo indicado:

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 34 archivos, 195 tests |
| `npx oxlint` | 0 errores; 27 warnings preexistentes (pureza/refs/estado en efecto) |
| `npx vite build` | correcto; aviso de chunk > 500 kB, ya existente |
| `npx playwright test -c playwright.forja3.config.ts` | 30/30 (G0–G8; el soak de 15 min queda detrás de `PROMETEO_SOAK=1`) |
| `playwright.config.ts g6-pdf.spec.ts` con motor real | 3/3 |
| `python -m unittest tests.studio.test_g6_pdf` | 3/3 con `case_a.pdf` y `case_b_scan.pdf` |
| Soak G8 | 903 s, 691 ciclos, 15 recargas, 0 errores, peor FPS 57 |

El soak se ejecutó con el código final de G8, sin otras suites en paralelo, y se repitió la caza guiada (14,6 s en la última pasada, 60 fps, 0 errores).

## 4. FPS y entorno

- **G1:** 61,7 fps con `requestAnimationFrame` en Brave headless, 1440×900.
- **G8 caza:** 60 fps.
- **G8 soak:** peor ventana 57 fps; media 60.
- **No medido:** WKWebView empaquetado, 120 Hz real, trackpad físico y dedos reales. Esa prueba es de Bruno.

## 5. Capturas

En `REPORTES/capturas-forja3/`:

- G0: `g0-antes.png`, `g0-despues.png`.
- G1: `g1-antes.png`, `g1-despues.png`.
- G2: `g2-antes.png`, `g2-despues.png`, `g2-despues-imagenes.png`.
- G3: `g3-despues.png`.
- G4: `g4-antes.png`, `g4-antes-completo.png`, `g4-despues.png`, `g4-despues-movil.png`, `g4-despues-pliego.png`, `g4-despues-anos.png`.
- G5: `g5-antes-mas.png`, `g5-despues-mas.png`, `g5-despues-irene.png`.
- G6: `g6-antes-760.png`, `g6-antes-520.png`, `g6-despues-760.png`, `g6-despues-520.png`, `g6-despues-reintento.png`, `g6-despues-fallo.png`.
- G7: `g7-despues.png`, `g7-despues-atajos.png`.
- G8: `g8-despues.png` (tablero después del recorrido y las recargas).

## 6. Lo que Bruno debe probar a mano

1. **Trackpad real:** abrir la app, entrar al tablero y probar dos dedos (mover), pellizco (zoom), `Espacio` + arrastrar (mover) y arrastrar el fondo (seleccionar). A 1440 la cabecera debe ir en una fila; a 1280, en dos sin tapar botones.
2. **Archivo/Muro/Mesa:** en un marco con medios, doble clic en un proyecto (pliego), `←`/`→`, `Esc`; en Muro, clic en una miniatura y zonas izquierda/derecha; en Mesa, «Por año» y `More →`.
3. **Biblioteca y sistema:** «+ Más» → buscar «enlace» → vista previa → añadir. Cambiar «Sistema» a **Archivo Irene**, recargar y comprobar que el tablero sigue en Irene y el otro tablero sigue en Forja 2.
4. **Edición en el sitio:** doble clic en el nombre del proyecto y en la URL de un enlace; guardar una plantilla; recargar y comprobar que las tres cosas siguen.
5. **PDF:** abrir el ejemplo escaneado, activar Capa OCR, elegir «CONTRATO», preparar parche, cambiar el texto y pulsar «Actualizar parche preparado». Luego escribir `ZZZZZZZZ`, verificar y leer la tabla «Qué falló».
6. **Ventana estrecha:** a 760 y 520 px abrir y cerrar Contenido e Inspector, comprobar que no hay huecos en blanco y que el documento sigue visible; recargar una vez.

## 7. Deuda y límites

- Comentarios, búsqueda global entre tableros y etiquetas de color de Milanote no entran en Forja 3.
- Columnas sin redimensionar a mano; conectores sin selector visual; medios en data URL (12 MB) sin miniaturas.
- Renombrar proyecto con doble clic en el `<select>` puede abrir además el desplegable nativo en algunos navegadores.
- El PDF tiene pruebas funcionales y de ventana estrecha, pero no un soak de 15 minutos.
- La campaña se cerró sin push; el remoto lo sube Bruno.

## 8. Cierre

- **Fases contadas:** 9 de 9 (100 %).
- **Fases pesadas por tamaño:** 100 % (G0 5, G1 10, G2 10, G3 20, G4 15, G5 15, G6 12, G7 8, G8 5).
- **Producto usable de Forja 3:** ~90 % (todo lo encargado está implementado y probado; quedan las pruebas de hardware/WKWebView y las funciones de Milanote declaradas fuera de alcance).
