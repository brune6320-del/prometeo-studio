# G4 · Irene Guerra, segunda pasada

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Base | G3 cerrada en `7e89ae2` |
| Referencias | `docs/STUDIO/04-LIENZO-ARCHIVO.md`, capturas `~/Desktop/deepseek-trabajo/referencia-web/capturas/` (`selectedesktop-s1w.png`, `work-w0.png`, `mob-m0.png`) |
| Propiedad | Inspiración, no copia: no se usan textos ni imágenes de ireneguerra.xyz |

## 1. Lectura de la referencia (E1, capturas + doc)

Lo que de verdad hace el tono:

- **Mono pequeña sobre blanco.** La imagen pone el color; la interfaz casi no tiene. Etiquetas en gris, mayúsculas, `letter-spacing` negativo.
- **Líneas punteadas**: bajo cada etiqueta, entre columnas y entre proyectos. No hay cajas ni sombras de interfaz.
- **Tres columnas** (25/50/25) con laterales fijos y solo el centro fluyendo; reloj vivo abajo a la izquierda.
- **Carrusel sin botones**: mitad izquierda retrocede, mitad derecha avanza; sin autoplay y sin zoom.
- **La doble página es una foto de archivador abierto**: dos hojas, anillas al centro. En Prometeo se traduce como un **pliego tipográfico** (dos páginas blancas, lomo punteado y anillas dibujadas), no como copia de la foto.
- **Filas por año** y **muro denso** no están en la web actual: son las zonas D y F del documento, inspiradas en los vídeos. Se construyen como vistas propias.
- **Móvil**: una columna, una diapositiva, barra fija abajo. Se adapta, no se copia el menú literal.

## 2. Deuda H-4 que se cierra en esta fase

| Deuda | Decisión |
|---|---|
| Vídeos inactivos siguen reproduciéndose | `MediaObject` reproduce solo la diapositiva activa; el resto se pausa al cambiar y al montar |
| Flechas del teclado | `←`/`→` mueven el carrusel del bloque activo. En línea, con el foco dentro de la vista; a pantalla completa, con un listener de ventana que no roba teclas a campos de texto ni al pliego |
| Contador | `1 / 3` visible dentro del carrusel, con `aria-live="polite"` |
| Versión móvil | Una columna (feed primero), pliego apilado y barra fija `Inicio · Feed · Índice` a pantalla completa por debajo de 900 px |

## 3. Alcance visual por vista

### Archivo

- Tipografía mono pequeña, fondo blanco, tinta negra, etiquetas grises y punteadas (se corrige el texto largo: la referencia no lo pone en cursiva).
- Carrusel con zonas de cursor ya existente + contador + pista `‹ ›` + pausa de vídeo.
- **Pliego**: doble clic en un bloque con medios abre `BookSpread` (dos páginas: medios a la izquierda, código/título/estado/texto/enlace a la derecha). `←`/`→` pasan diapositiva, `Esc` cierra.
- Barra móvil y apilado.

### Muro

- Pasa de papel marrón a **blanco/negro/gris**, mono pequeña, líneas punteadas y sin sombras de interfaz.
- La caja de luz gana **zonas de cursor** (mitad izquierda/derecha) además de las flechas; el vídeo solo suena/reproduce en la caja de luz.
- Contador `n / total` se conserva.

### Mesa de luz

- Mismo tono blanco/negro/punteado; piezas con sombra leve de objeto, no de panel.
- Nuevo modo **«Por año»**: filas `■ 2026 · N proyectos` con tira horizontal de piezas a altura común y `More →` que abre el pliego del primer proyecto de ese año. Los años salen de `datos.año`/`datos.year` o del primer año de 4 cifras en código, título o texto; sin año van a una fila final.
- Se mantiene «Ordenar en muro» en el modo mesa.

## 4. Archivos previstos

- Nuevo `src/components/MediaObject.tsx`: imagen/vídeo/audio/archivo con reproducción ligada a `playing`.
- Nuevo `src/components/BookSpread.tsx`: pliego modal de dos páginas, teclado, zonas de cursor y contador.
- `src/board/archivo.ts`: `slideCounter`, `blockYear`, `groupBlocksByYear`.
- `src/components/ArchivoView.tsx`, `MuroView.tsx`, `MesaView.tsx`: cambios descritos.
- `src/components/board.css`: tono y pliego; responsive.
- Tests: unitarios en `src/tests/archivo.test.tsx`, E2E `e2e-forja3/g4-irene.spec.ts`.

## 5. Verificación prevista

1. `npx tsc -b`
2. `npx vitest run`
3. `npx oxlint`
4. `npx vite build`
5. `npx playwright test -c playwright.forja3.config.ts g4-irene.spec.ts`
6. Capturas `g4-antes.png`, `g4-antes-completo.png`, `g4-despues.png`, `g4-despues-movil.png`, `g4-despues-pliego.png`, `g4-despues-anos.png`.

## 6. Límites que se dirán en el cierre

- El pliego es una traducción tipográfica del archivador, no una foto ni un asset de la referencia.
- La agrupación por año depende de que el usuario escriba el año en `datos.año`, el código, el título o el texto; no se inventa.
- Las fuentes reales (Diatype/Monument) siguen sin copia local; se usa la pila mono de respaldo.
- El teclado y el pliego se prueban con Playwright; la prueba con dedos y trackpad reales sigue siendo de Bruno.
