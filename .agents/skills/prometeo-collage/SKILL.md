---
name: prometeo-collage
description: Gestos y reglas del collage (Mesa de luz y Muro) heredados de Sala Oscura, reescritos para Prometeo. Úsala al implementar arrastrar, apilar, escalar u ordenar piezas.
license: Propietaria del autor
---
# Collage

Reglas comprobadas en Sala Oscura (README, sección Collage). Se reimplementan en TypeScript sin copiar su HTML.

- Cargar un archivo lo mete en la **biblioteca**; no lo coloca. Así se evita sembrar copias sin querer.
- La miniatura muestra nombre y `×N` (cuántas piezas usan ese medio).
- Clic en miniatura = «coger». Clic en el lienzo = pegar y soltar. Doble clic = modo sembrar. Esc = soltar.
- Varias piezas apiladas: cada clic baja una en la pila y vuelve arriba al final. El estado dice «3 de 5 aquí».
- arrastrar = mover · Shift+arrastrar = escalar · Cmd/Ctrl+arrastrar = girar · Supr = quitar la pieza (el medio sigue en la biblioteca).
- **Ordenar en muro**: filas justificadas que respetan el aspecto de cada imagen (altura de fila fija y ancho total igual).
- La sesión guarda miniaturas ≤192 px. Los originales se referencian por huella.
- Dos modos que no se mezclan: colocar piezas o ajustar el marco. Un interruptor, nunca por precedencia.
