---
name: prometeo-figma
description: Figma como plano del Lienzo Archivo de Prometeo. Variables, componentes, frames 1440/390 y el paso de Figma a código. Úsala en los encargos F-x o al comparar la app con el diseño.
license: Propietaria del autor
---
# Figma en Prometeo

Basada en la skill sala-oscura-figma (FABCORE-ROBOT/.agents/skills). Figma es el **plano**; la app es lo que funciona. Figma nunca es el renderer.

## Conexión
- OpenCode usa el servidor MCP de Figma: el de la app de escritorio (Preferencias → Dev Mode MCP, sirve en local) o el remoto de Figma. Lo que puedes hacer depende de tu plan de Figma.
- Usa el archivo exacto que te pasen. No adivines file key ni node ID. Si no existe y el encargo pide crearlo, créalo con ese nombre exacto.

## Archivo «Prometeo · Lienzo Archivo»
- Página **Referencia**: captura de la web guardada (solo para medir; no es el entregable).
- Página **Lienzo**: frames Escritorio 1440 y Móvil 390, con capas editables (no capturas con cosas encima).
- Página **Componentes**: Hoja, Carpeta (pliego + anillas), Código (XX-Pnn.vv · título · estado), Fila-año, Lámina, Columna-muro, Caja de luz, Reloj, Etiqueta, Separador punteado.
- **Variables**: color (fondo, texto, etiqueta, separador, sombra), tipo (familia, 11.5, interlineado), espacio (columna, margen, hueco). Nombres en español y semánticos.

## Reglas
- Carga las fuentes antes de editar texto e inspecciona cada nodo después de modificarlo.
- Los textos de la interfaz, en español.
- Cuando Figma y la referencia difieran en una medida, gana la referencia. Cuando la app y Figma difieran, gana Figma: corrige la app.
