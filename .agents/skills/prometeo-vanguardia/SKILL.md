---
name: prometeo-vanguardia
description: Combinador de entropía de Prometeo, que mezcla referentes, herramientas y reglas de vanguardias para generar collages con semilla, y la memoria de gusto ♥/✕. Úsala en los encargos V-x.
license: Propietaria del autor
---
# Vanguardia / entropía

Combinación = { semilla, referentes[2-3], herramienta, regla, restricción }. Misma semilla = mismo resultado, siempre.

Reglas de collage (`board/vanguardia/reglas.ts`), cada una una función pura (piezas, semilla) → disposición:
- dada: recortes rotados al azar, superpuestos, texto suelto.
- bauhaus: retícula de 12, rojo/amarillo/azul, círculo-cuadrado-triángulo.
- constructivista: diagonal de 30°, bloques en tensión, tipografía grande.
- fluxus: partitura con instrucciones numeradas y tiempo.
- situacionista: deriva; las piezas siguen un recorrido sobre un mapa (NYPL maps).
- suizo: rejilla estricta, una sola familia, mucho blanco.
- irene: archivador fotografiado + mono pequeña (herramienta Archivo).
Restricciones (estilo Oblique Strategies, texto propio): «solo dos colores», «quita lo más bonito», «una pieza al revés»…

Memoria de gusto: `gustos.json` = { pesos por referente, regla, herramienta y par }. ♥ suma 1, ✕ resta 1 y los pesos se recortan a [0.2, 5]. La elección es aleatoria ponderada con semilla, y un 20 % siempre es azar puro para que la entropía no muera.
Todo resultado es una pieza nueva con procedencia: semilla + ids de las fuentes.
