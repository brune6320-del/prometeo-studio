---
name: prometeo-auditor
description: Audita la experiencia de Prometeo Studio como un auditor de producto: compara con herramientas de oficio y vanguardias, recorre escenarios, debate argumento y contraargumento, y termina en una filosofía de diseño con pruebas. Usar antes de diseñar una función, al revisar una forja, o cuando Bruno dice que algo «no funciona» o «está seco».
---

# Prometeo · Auditor de experiencia («REA del lado social»)

REA hace ingeniería inversa de binarios: qué hace el programa por dentro. Este auditor hace lo mismo con la experiencia: qué hace el producto con la persona, qué promete, qué esconde y dónde se rompe. No opina por gusto; cada hallazgo tiene evidencia, escenario y prueba.

## Fuentes legítimas
- El código de Prometeo (lectura) y la app corriendo.
- Lo que cualquiera ve usando las herramientas de referencia: Figma, Canva, Illustrator/InDesign, Fusion 360/AutoCAD, Keynote/Freeform, Milanote, Are.na, Procreate, Notion. Centros de ayuda públicos y listas de atajos oficiales.
- Papers y estudios (ver skill prometeo-lienzo-saber y lecturas/indice.md).
- No se descompilan ni se raspan productos de terceros (Milanote prohíbe la ingeniería inversa en sus términos). Se aprende su comportamiento visible, no su código.

## El método, en 6 pasos

1. **Inventario de oficio.** Para la función auditada, lista lo que TODA herramienta profesional da por hecho (atajos, deshacer, selección, arrastre, estados vacíos, errores, accesibilidad). Marca en Prometeo: existe / a medias / no existe, con el archivo y la línea.
2. **Escenarios.** Recorre la matriz persona × momento × estado:
   - Personas: Bruno con prisa, alguien nuevo sin instrucciones, alguien experto en Figma, alguien con solo teclado, alguien en iPad.
   - Momentos: primer minuto, tablero con 500 tarjetas, después de un error, al volver al día siguiente.
   - Estados: vacío, lleno, sin red, sin clave de IA, documento pesado.
   Para cada celda relevante: qué espera la persona, qué pasa de verdad.
3. **Debate.** Por cada hueco importante escribe:
   - Tesis: cómo lo resuelven las herramientas de oficio.
   - Antítesis: el mejor argumento en contra (vanguardias, el espíritu japonés del vacío, el caso de Milanote, el costo para el usuario nuevo).
   - Síntesis: lo que hará Prometeo y por qué, en una frase.
   Ganar el debate no es dar la razón a la mayoría: es encontrar la razón que sobrevive a la objeción más fuerte.
4. **Curiosidad.** Una pregunta abierta por auditoría que nadie ha contestado aún (p. ej. «¿qué significa deshacer en un collage que se ordena solo?»). Se guarda en la lista de preguntas.
5. **Filosofía.** Si la síntesis vale para más de una función, se convierte en principio y se propone como regla de prometeo-lienzo-saber, con su prueba.
6. **Veredicto y encargo.** Hallazgos ordenados por gravedad (rompe / frustra / pule), cada uno con prueba automática propuesta. Lo que «rompe» se convierte en encargo para DeepSeek.

## Formato del informe
REPORTES/AUDITORIA-<tema>.md con: inventario (tabla), escenarios (tabla corta), debates (tesis/antítesis/síntesis), pregunta abierta, principios propuestos, veredicto.

## Registro
- 25-oct: v1. Nace tras descubrir que Supr, Cmd+A y el borrado sin diálogo nunca existieron (T-2): faltaba alguien que preguntara «¿qué da por hecho una herramienta profesional?» antes de construir.
