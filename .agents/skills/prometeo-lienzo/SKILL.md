---
name: prometeo-lienzo
description: El Lienzo Archivo de Prometeo Studio, una página-archivo editable al estilo de ireneguerra.xyz con nota fija, feed de proyectos con carrusel, índice/CV fijo y vistas extra (filas por año, láminas, muro). Úsala en cualquier encargo L-x o al tocar la vista principal.
license: Propietaria del autor
---
# Lienzo Archivo (resumen de docs/STUDIO/LIENZO-ARCHIVO.md)

Escritorio, tres columnas ≈25/50/25 %:
- A nota fija (izquierda, NO baja) con reloj vivo gris abajo.
- B feed de proyectos (centro, es lo único que baja). Cada bloque: carrusel → debajo `CÓDIGO / Título / ESTADO` (izq.) + texto largo (der.) → línea punteada.
- C índice + CV (derecha, fija, scroll propio). Un código en C hace scroll a su bloque en B.
Móvil 390 px: una columna; barra fija abajo `HOME WORK CV · CONTACT`.
Vistas extra (propias, no están en la web): D filas por año, E láminas, F muro + caja de luz.

Reglas:
- Carrusel: clic en la mitad izquierda = atrás, derecha = adelante (cursor-zones), también ← →. Transición 0,5 s, sin autoplay, sin zoom. Vídeos: autoplay, muted, loop.
- La carpeta con anillas de la referencia es una FOTO. No dibujes anillas en CSS: el objeto lo pone la imagen.
- Tokens: base 12.96 px, cuerpo 0.95 rem, letter-spacing -0.02em, padding 1 rem, línea punteada gris 1 px. Diatype Mono si está en referencia-web/, si no JetBrains Mono / IBM Plex Mono. Usa variables CSS, nunca colores sueltos.
- Códigos `XX-Pnn.vv` = subtablero.
- Medio ≠ pieza: soltar un archivo lo manda a la biblioteca; la zona decide cómo se ve.
- Edición en el sitio: doble clic en el texto; Esc cancela, ⌘↵ guarda; un gesto = un deshacer (saveQueue).
- La pizarra libre de LUNA no se borra: es la «Mesa de trabajo» detrás de «Editar disposición».
- Fidelidad máxima a ~/Desktop/deepseek-trabajo/referencia-web/ (capturas/ y LIENZO-TOKENS.md). Ante una duda de medida, gana la referencia.
