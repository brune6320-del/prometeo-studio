# ADN tipográfico — contrato Forja 4, versión 1.0.0

Un `pagina-NNNN/adn.json` por página. `manifest.json` lista las páginas en A.
`version` es semver. Cambiar nombres, unidades, nulabilidad o significado exige
subir la versión; los consumidores deben rechazar versiones mayores desconocidas.

Raíz: `version`, `pagina` (desde 1), `ancho_pt`, `alto_pt`, `sha256_origen`,
`spans` y `advertencias`. El texto OCR y las marcas ortográficas son opcionales.
A usa página sin rotación y coordenadas PyMuPDF; B usa la orientación EXIF aplicada.
`bbox` siempre es `[x0,y0,x1,y1]`, origen superior izquierdo, unidades pt, extremos
finales exclusivos. Un punto = 1/72 pulgada. B requiere DPI físico suministrado.

| Campo del span | Tipo / significado |
|---|---|
| pagina | entero >=1 |
| bbox | cuatro números finitos en pt |
| texto | Unicode original o leído por OCR; nunca autocorregido |
| fuente | nombre declarado A o familia de catálogo más parecida B; null si no identificable |
| tamano_pt | número positivo; null si no estimable |
| peso | 100–900 aproximado; A flags 400/700, B estilo del vecino; null si desconocido |
| inclinacion | grados de la línea base, positivos hacia abajo; null si desconocida |
| cursiva | booleano adicional, distinto de inclinación; null si desconocido |
| tinta_lab | [L*, a*, b*], CIELAB D65/observador 2°, convertido de sRGB; null si desconocida |
| interletra | pt; A residual entre avance observado y ancho nominal, mediana del span; B hueco entre cajas OCR; null si no medible |
| interlinea | distancia entre líneas base en pt dentro del bloque; null en última línea |
| linea_base | {origen: [x,y], direccion: [dx,dy]}, pt y vector unitario; B añade metodo aproximado |
| origen | "nativo" o "inferido" |
| confianza | número [0,1]; integridad de extracción en A, margen de vecino sin calibrar en B |
| ortografia | lista {texto,inicio,fin,marca:"revisar"}; índices Unicode del texto revisado |

A conserva además `caracteres` con c, bbox, origin (nombre de RAWDICT), fuente,
tamano_pt, flags, color_srgb y tinta_lab; bloque y línea identifican agrupación.
La extracción no necesita red. Fuentes incrustadas se guardan fuera de Git con
xref, ruta y SHA; fuentes Base14 pueden carecer de archivo incrustado. B emite
un span por carácter y `palabra_ocr`; sus marcas ortográficas indexan esa palabra.
La raíz B también contiene marcas sobre `texto_ocr` completo.

`confianza=1` en A significa valor leído del PDF; NO implica apariencia perfecta,
certeza de ortografía, peso CSS exacto ni equivalencia colorimétrica de imprenta.
PyMuPDF devuelve color interpretado sRGB: perfiles ICC/tintas planas originales
no se reconstruyen. Texto en curvas no es texto nativo; ligaduras, sustituciones,
fuentes subset, clipping, matrices y transparencias pueden impedir reconstruirlo.
Bloques no horizontales se extraen pero la prueba de render los marca no soportados.
La prueba de render compara el bloque completo contra fondo blanco y da MAE de
píxel, fracción distinta y MAE sobre tinta; gráficos/fondos afectan la métrica.
