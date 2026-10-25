# A-2 · Auditoría de cierre de Forja 4

Fecha: 25-oct-2026 · Rama: `studio/collage` · Sin push.
Método: skill `prometeo-auditor` + repetición de las observaciones de A-1 contra el código y la app corriendo.
Alcance: los 15 huecos del Top 15 de `REPORTES/AUDITORIA-1.md`, cerrados en H1–H8.

---

## 1. Veredicto en una frase

La gramática de manipulación que faltaba ya existe: **seleccionar, agrupar, redimensionar, deshacer, encontrar, pegar, navegar con el cuerpo y editar un documento sin fingir**. Lo que A-1 llamó «contratos de interacción» está ahora en el código y en una prueba que se puede repetir; lo que sigue sin probarse es el cuerpo de Bruno (iPad físico, VoiceOver real, trackpad físico), no la lógica.

---

## 2. Las 14 pruebas temporales de A-1, repetidas

A-1 ejecutó 14 pruebas temporales con 15 observaciones. No se conservaron como suite; Forja 4 las convirtió en pruebas permanentes. Esta es la repetición:

| # | Observación original de A-1 | Ahora | Prueba que lo demuestra |
|---|---|---|---|
| 1 | Marquesina sin ⇧ sumaba | Reemplaza; ⇧ suma; ⌥ resta | `e2e-forja4/h2-seleccion-marcos.spec.ts` · «la marquesina reemplaza…» |
| 2 | ⇧+clic solo añadía | Alterna (añade y quita) | misma prueba |
| 3 | Hijo de marco no salía al vacío | Arrastrar al vacío limpia `hijos` y un ⌘Z lo devuelve | `h2` · «sacar un hijo lo desvincula…» |
| 4 | Enter no seleccionaba marcos/columnas | Enter y Espacio seleccionan ambos | `h4-teclado-foco.spec.ts` · «Tab entra, Alt+flechas…» |
| 5 | Tirador del marco no respondía a flechas | ⌘+flechas cambian ancho y alto de marco/nota | misma prueba |
| 6 | Copiar solo dejaba una marca | Portapapeles del sistema lleva marca + texto legible | `h6-asas-pegado-medios.spec.ts` · «pegar texto, URL, imagen…» |
| 7 | Pegar texto plano no creaba nada | Crea una nota en el cursor | misma prueba |
| 8 | Buscar solo atenuaba | Resultados, contador, alcance y Enter que centra | `h5-indice-busqueda.spec.ts` · «⌘F encuentra…» |
| 9 | Diálogo de atajos dejaba el foco fuera | Atrapa el foco y lo devuelve al disparador | `h4` · «Tab no queda atrapado…» |
| 10 | `aria-selected` null y sin contador vivo | `aria-selected` + región `aria-live` | `h4` · «Tab entra…» |
| 11 | Tras recargar, Deshacer deshabilitado | Historial restaurado o «sesión nueva» declarada | `h1-memoria.spec.ts` · «el historial de deshacer se restaura…» |
| 12 | Tablero borrado desaparecía a los 5 s | Memoria de 30 días en Archivo, recuperable tras recargar | `h1` · «un tablero borrado se recupera…» |
| 13 | Tab atrapado en Tareas | Tab pasa al siguiente control | `h4` · «Tab no queda atrapado…» |
| 14 | PDF sin selección ni controles | Texto seleccionable, capacidades y tipografía verificada | `h8-documento.spec.ts` · «capacidades, selección de texto…» |
| 15 | Zoom 240 % y sin ⌘0/⌘+/- | 25–800 % en tablero y PDF, con atajos | `h7-proyectos-zoom.spec.ts` · «zoom del tablero…» y «el PDF también…» |

Resultado: **15/15 observaciones cerradas**. La suite `e2e-forja4` tiene 28 pruebas (H0–H9) y corre en verde con Brave.

---

## 3. Inventario por zona (después)

| Zona | Oficio | Estado |
|---|---|---|
| Lienzo | Marquesina con modificadores, ⇧+clic, ⌘A, Supr, ⌘Z | ✅ |
| Lienzo | Marcos: contenedor + lente, sacar, agrupar/desagrupar, candado | ✅ |
| Lienzo | Asas de nota (ancho), 8 asas en marco/columna, selección múltiple | ✅ |
| Lienzo | Teclado: Tab entra, Alt+flechas vecino, Enter, Esc sale, resize | ✅ |
| Lienzo | Táctil: 1 dedo marquesina, 2 dedos paneo/pellizco, Mano, 24/44 px | ✅ (eventos sintéticos; falta iPad físico) |
| Lienzo | Índice virtualizado, búsqueda con alcance y salto | ✅ |
| Tarjetas | Pegar texto/URL/imagen/tarjetas en el cursor; copia legible | ✅ |
| Tarjetas | Imagen/vídeo: título, pie, alt, reemplazo, recorte en edición | ✅ |
| Tarjetas | Columna: orden explícito en `datos.hijos`, reordenar, sacar | ✅ |
| Documento | Capacidades declaradas, texto seleccionable, tipografía verificada | ✅ |
| Documento | Capa de anotación propia, páginas (orden/rotar/quitar/unir) | ✅ |
| Documento | Original inmutable y SHA-256 en cada copia nueva | ✅ |
| Historial | 30 días para tablero/referencia/tarjetas/proyecto, 100 pasos | ✅ |
| Historial | Cierre fuerza el volcado; «Guardado» solo tras IndexedDB | ✅ |
| Historial | Deshacer/rehacer en el staging PDF | ✅ |
| Biblioteca | Proyectos: F2, mover tablero, archivar, borrar con nombre | ✅ |
| Accesibilidad | Diálogos atrapan y devuelven el foco; `aria-selected` y `aria-live` | ✅ |
| Accesibilidad | VoiceOver real | ⚠ no verificado |
| Gestos | Trackpad 1:1 de T-1 intacto | ✅ (código y pruebas; falta hardware de Bruno) |

---

## 4. Escenarios que cambian

| Persona / momento | A-1 | Ahora |
|---|---|---|
| Alguien nuevo pega un texto | No pasaba nada | Nace una nota en el cursor |
| Experto en Figma busca capas | No había | Índice con L, búsqueda, multiselección y traer al frente |
| Solo teclado con marcos | Enter no seleccionaba | Tab entra, Alt+flechas navegan, Enter selecciona, Esc sale |
| iPad, tablero lleno | Un dedo dibujaba; dos no paneaban | Un dedo dibuja; dos panean y pellizcan; botón Mano |
| Borra un tablero y vuelve mañana | Nada | Archivo · Recientes borrados · 30 días |
| Edita y cierra en el mismo segundo | El navegador avisaba | Se fuerza el volcado; si falla no cierra y ofrece exportar |
| Abre un PDF escaneado | «Editor PDF» sin contrato | Declara el motivo y no simula un editor de texto |
| Quiere cambiar una palabra de un PDF | Solo texto | Texto, tamaño, fuente y color con verificación y rechazo explicado |

---

## 5. Debates de A-1: cómo quedaron

- **D1 selección** → la marquesina reemplaza; ⇧ suma; ⌥ resta; ⇧+clic alterna. Implementado y probado.
- **D2 marco** → contenedor y lente con contrato explícito; pertenencia única. Documentado en `DESIGN.md`.
- **D3 papelera** → no hay papelera visible; hay memoria de 30 días en Archivo.
- **D4 tamaño del papel** → la nota cambia de ancho (210–640); el alto sigue al contenido.
- **D5 táctil** → un dedo selecciona; dos panean; pellizco focal; botón Mano.
- **D6 teclado** → lista (índice) y navegación espacial; diálogos con foco atrapado.
- **D7 Acrobat** → Prometeo declara capacidades y supera el recorte con verificación; no hay puente a Acrobat.
- **D8 buscar** → ilumina, cuenta, lleva y permite alcances tablero/proyecto/biblioteca.
- **D9 pegar** → crear en el cursor, con prioridad del sistema sobre la marca interna.
- **D10 capas** → índice, no panel de Adobe; virtualizado a 500.
- **D11 medio** → objeto libre con leyenda editable, reemplazo que conserva caja y recorte en edición.
- **D12 columna** → orden explícito en `datos.hijos`; por `y` solo si nunca se ha soltado.
- **D13 proyecto** → archivar y borrar definitivamente desde Archivo, escribiendo el nombre; 30 días.
- **D14 zoom** → inspección declarada hasta 800 %, LOD intacto bajo 35 %.
- **D15 cerrar** → volcado forzado; el estado «Guardado» sigue siendo honesto.

---

## 6. Pregunta abierta

**¿Qué debe pasar cuando una edición de PDF cambia la tipografía de un span y el texto nuevo cabe pero ya no se parece al original?** Forja 4 verifica que cabe y que los demás objetos quedan idénticos, pero no juzga la equivalencia visual (peso, tracking, tinta). Esa es la frontera de D-10/D-11 y la deuda honesta de H8.

---

## 7. Principios nuevos o precisados

Ninguno nuevo: los 20 de `prometeo-lienzo-saber` v1.4 cubren lo construido. Se precisan dos:
- **Regla 14**: la pertenencia única se guarda en `datos.hijos` y se puede deshacer en un paso.
- **Regla 18**: la copia de documento se entrega con su SHA-256 y el original se verifica antes y después.

---

## 8. Lo que no se pudo verificar

- iPad físico: los gestos se probaron con `PointerEvent` sintéticos y `hasTouch`, no con dedos reales.
- VoiceOver real: se probó foco, Tab, Escape y `aria-selected`/`aria-live`, no el árbol de accesibilidad de macOS.
- Trackpad de Bruno: T-1 sigue intacto por código y pruebas, pero no se repitió la traza de hardware.
- Tipografía PDF: se verifica que cabe y que los demás spans quedan idénticos; no se mide equivalencia tipográfica subjetiva.

---

*Auditoría A-2 · 25-oct-2026 · Sin push.*
