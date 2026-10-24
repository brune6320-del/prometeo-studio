# Lienzo Archivo · el lienzo en blanco de Prometeo Studio

**Corrección de Bruno (24-oct, tarde):** la base es la **pizarra infinita** (LUNA). Esta página tipo ireneguerra.xyz es una **herramienta** que se construye encima: un marco con «Ver como Archivo» (encargo H-4 de la campaña 2). Todo lo que sigue describe cómo se ve esa vista.

Fuente del estudio: los 6 vídeos de `Desktop/deepseek-trabajo/ig-DeYyIjMjDpu/` y un recorrido real de la web con REA y Brave (§0). Está hecha con Cargo (cargo.site).

**Uso privado (decisión de Bruno, 24-oct):** Prometeo nunca se publica ni se distribuye. Por eso se busca **fidelidad máxima** a la referencia: medidas, tipografía, espaciado, ritmo y gestos lo más parecidos posible. Se puede guardar la web en local para estudiarla (encargo L-0) y usar sus imágenes como contenido de prueba. Si algún día Prometeo se compartiera, habría que revisar este documento antes.

---

## 0. Lo que se vio de verdad (REA + Brave, 24-oct)

Recorrido con REA (`capture_browser_scenario`, Brave, 1440×900 y 390×844). Evidencias en `~/Desktop/deepseek-trabajo/referencia-web/rea-evidencia-*.json` y capturas en `referencia-web/capturas/`.

- **Portada** (`/`): una foto a pantalla completa de una mesa de luz con objetos. Toda la imagen es un enlace que entra al sitio (`/selectedesktop` en escritorio y `/selectedmobile` en móvil).
- **Escritorio** (`/selectedesktop`): tres columnas. Izquierda y derecha **quedan fijas**; solo baja el centro.
  - Izquierda «IRENE GUERRA®»: bio, correo, Instagram y reloj vivo gris abajo (`11:09:08`).
  - Centro «BARATTOLO»: un **feed vertical de proyectos**. Cada proyecto es un carrusel (`gallery-slideshow`, `navigation="cursor-zones"`, sin autoplay, sin zoom, transición 0,5 s) con 2–6 imágenes o vídeos en bucle; debajo, dos columnas: `código / título / ESTADO` a la izquierda y el texto largo a la derecha. Entre proyectos va una línea punteada. Al final: «© MORE PROJECTS ON @IRENEGUERRRA».
  - Derecha «CV»: tabla de dos columnas (Education, Employment, Exhibitions…) con su propio scroll y una línea punteada entre secciones.
- **El clic en la imagen pasa de diapositiva** (comprobado: el pliego cambia en cada clic). La mitad izquierda retrocede y la derecha avanza (cursor-zones).
- **La carpeta con anillas es una FOTO**, no interfaz: cada diapositiva es una foto cenital de un archivador abierto con dos hojas. Lo mismo con el monitor CRT de Auris.
- **Móvil**: `/selectedmobile` muestra una diapositiva, la bio y un menú `WORK · CV · CONTACT`. `WORK` lleva al mismo feed apilado en una columna, con una barra fija abajo `HOME WORK CV · CONTACT`.
- **Lo que NO está en la web actual**: las filas por año con «More →», las láminas que se deslizan y el muro denso de los vídeos 4–6. No aparecen ni en escritorio ni en móvil; serían una versión anterior o montajes para Instagram. En Prometeo son **zonas propias inspiradas en los vídeos** (D, E y F), no copia de la web.

Proyectos del feed (sirven de contenido de prueba): DE-P01.01 Pareidolìa (IN EXHIBITION), AR-P01.01 Outdated Architecture (RESEARCH), DE-P02.01 Persona, DE-P03.01 Auris, FA-P01.01 Lacera, AR-P02.01 The Century of the Bed, FI-P01.01 Mania, FI-P01.01 Auris Liveset (RADIO STREAMING).

## 1. Gramática (lo que hace que funcione)

1. **Texto monoespaciado pequeño sobre blanco.** La imagen pone el color; la interfaz casi no tiene.
2. **Tres columnas con etiqueta gris arriba** y una línea punteada debajo de la etiqueta. Líneas verticales punteadas entre columnas.
3. **Códigos de catálogo**: `DE-P01.01 / Pareidolia / IN EXHIBITION`, en tres renglones. Área-Proyecto.versión y luego estado.
4. **Reloj vivo** gris abajo a la izquierda. La página está «encendida».
5. **Cero botones.** Se navega con el cursor: clic a la izquierda o derecha de la imagen para pasar.
6. **Las imágenes son objetos fotografiados** (archivador, monitor, hojas con sombra) sobre fondo blanco. El «objeto» lo pone la foto, no el CSS.
7. **Columnas laterales fijas, centro que fluye.** Leer un proyecto nunca hace perder la bio ni el CV.

## 2. Las zonas del lienzo

Escritorio (1440 px; columnas ≈ 25 % · 50 % · 25 %):

```
┌ ETIQUETA (fija) ────┬ ETIQUETA ─────────────────────────┬ ETIQUETA (fija) ─────┐
│ ··················· │ ································· │ ···················· │
│ A. NOTA FIJA        │ B. FEED DE PROYECTOS (baja)       │ C. ÍNDICE / CV       │
│ bio del proyecto    │  [ carrusel: ◀ mitad │ mitad ▶ ]  │ Sección   Entradas   │
│ correo · enlaces    │  CÓDIGO        texto largo del    │ ···················· │
│                     │  Título        proyecto, en la    │ Sección   Entradas   │
│                     │  ESTADO        segunda columna    │ (scroll propio)      │
│                     │ ································· │                      │
│                     │  [ siguiente proyecto … ]         │                      │
│ 11:09:08            │ © pie                             │                      │
└─────────────────────┴───────────────────────────────────┴──────────────────────┘
```

- **A** fija. **C** fija con scroll propio. **B** es la que baja.
- En C, cada código de proyecto es un enlace que hace scroll hasta su bloque en B (en la web real C es solo CV; en Prometeo C es índice + CV).

Móvil (390 px): una sola columna. Portada → diapositiva + bio + `WORK · CV · CONTACT`. `WORK` = feed B apilado; barra fija abajo `HOME WORK CV · CONTACT`.

Zonas propias (inspiradas en los vídeos, no en la web actual), como vistas alternativas del mismo feed:

- **D. Filas por año**: `■ 2026 · Título · More →` con una tira horizontal de piezas de igual altura; los vídeos se reproducen solos y silenciados (vídeo 6).
- **E. Láminas**: proyectos como hojas apiladas que se deslizan una sobre otra (vídeo 5).
- **F. Muro denso + caja de luz**: columnas estrechas de miniaturas con su código; clic → caja de luz blanca con ⓧ y flechas (vídeo 4).

## 3. Cómo entra Milanote aquí dentro (sin perder lo hecho en LUNA)

| Milanote / LUNA | En el Lienzo Archivo |
|---|---|
| Proyecto | Un lienzo con su código de área (DE, AR, FA, FI…; los define el usuario) |
| Subtablero (P0) | Una entrada del índice C con código `XX-Pnn.vv`. Es un bloque del feed B; en C, su código hace scroll hasta él. Las migas son el propio código |
| Nota | El texto de la zona A o el texto largo del bloque. Se edita en el sitio con doble clic |
| Columna (P1) | Una columna del muro F o una fila D. Mantiene orden explícito y se puede plegar |
| Tarea (P1) | Una línea del índice C con casilla `[ ]`. Es la misma tipografía y no hace falta otro panel |
| Imagen, vídeo o archivo | Una diapositiva del carrusel de B, un fotograma de la fila D o una miniatura del muro F (misma pieza, distinta zona) |
| Referencia PDF (L2) | Una diapositiva con la página del PDF. Doble clic abre el visor |
| Relaciones | Aparecen como códigos citados en el texto (`ver AR-P01.01`), que son enlaces |
| Pizarra libre (vista actual) | **Mesa de trabajo**: el modo edición detrás del lienzo. Se abre con «Editar disposición» y se cierra para volver al lienzo |
| Exportación Obsidian | Se mantiene |
| **Nuevo**: publicar | El lienzo se exporta tal cual como web estática. Lo que ves es lo que publicas |

## 4. Edición «en el sitio» (lo que lo hace lienzo y no solo web)

- **Soltar** archivos en cualquier zona: en un bloque de B se convierten en diapositivas de su carrusel, en D en fotogramas de esa fila y en F en miniaturas de esa columna. Siempre pasan antes por la biblioteca (medio ≠ pieza).
- **Arrastrar** una pieza de una zona a otra solo cambia dónde se muestra; el medio no se duplica.
- **Doble clic en un texto** lo edita. Esc cancela y ⌘↵ guarda. Un gesto equivale a un deshacer, por `saveQueue`.
- **«+» en la etiqueta** de una zona añade una entrada vacía (nota, fila, columna, subtablero o tarea).
- **Pasar diapositivas** con clic en la mitad izquierda o derecha de la imagen (cursor-zones), o con ← →. Transición 0,5 s.
- **Mesa de luz «archivador»**: botón opcional que compone dos piezas como pliego sobre una foto de archivador (como hace la referencia a mano). La caja de luz vive en la zona F.
- **Sin destellos:** nada parpadea; el carrusel usa 0,5 s y el resto 200–300 ms.

## 5. Tokens (medidos en la web real)

- Fondo `#fff`. Texto `#000` aprox. Etiquetas y reloj en gris (`~#8a8a8a`; medir con L-1).
- Base: `--base-size: 12.96px` y padding de página 12.96 px (1 rem).
- Tamaños: cuerpo 0.95 rem, intermedios 1.1 y 1.2 rem. `letter-spacing: -0.02em`. Interlineado ≈ 1.15.
- Fuentes reales (Cargo, de type.cargo.site): **Diatype Mono Variable**, Diatype Semi-Mono y Monument Grotesk (Mono) Variable. Son comerciales (Dinamo); en uso privado se pueden cargar desde la copia guardada en L-0. Respaldo libre: `"JetBrains Mono", "IBM Plex Mono", ui-monospace`.
- Separadores: línea punteada de 1 px en gris claro, horizontal bajo cada etiqueta y entre proyectos; vertical entre columnas.
- Etiqueta arriba a 1 rem; primera línea punteada ≈ 106 px; contenido empieza ≈ 132 px (a 1440×900).
- `column-set` con separación 1 rem; CV con columnas 4/8; bloque de proyecto 6/6.
- Carrusel: `gutter 1rem`, transición 0,5 s, sin autoplay, sin zoom.
- Si una medida de L-1 difiere de esta lista, gana L-1.

## 5b. Figma es el plano

Antes de programar las zonas, el lienzo se arma en Figma (archivo «Prometeo · Lienzo Archivo»): referencia capturada, variables, componentes y frames de 1440 y 390. Las variables pasan a CSS (F-2) y después de cada encargo L se compara la app con Figma (F-3). Lo mismo vale para Sala Oscura, que ya tiene su skill de Figma.

## 6. Lo único que queda fijo

- **Milanote:** sus términos prohíben la ingeniería inversa, y eso es un contrato aunque el uso sea privado. Se sigue trabajando con su ayuda pública (ya hecho en LUNA).
- **No perder datos:** la pizarra libre de LUNA no se borra; pasa a ser la Mesa de trabajo. Rige la Adenda 001.
- **Tus copias:** nada se sube a internet. «Publicar» (L-7) genera una carpeta local para verla en tu navegador.
