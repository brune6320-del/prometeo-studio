---
name: prometeo-tablero
description: Reglas del tablero visual de Prometeo Studio (vistas Libre, Muro, Cuaderno, Mesa de luz). Úsala al tocar studio/frontend/src/board o el formato tablero.json.
license: Propietaria del autor
---
# Tablero de Prometeo

- Código del tablero: `studio/frontend/src/board/` (React 19 + Vite + TypeScript). Archivos base: model.ts, projectModel.ts, camera.ts, geometry.ts, history.ts, saveQueue.ts, storage.ts, projectStorage.ts.
- **Un modelo, varias vistas.** Libre, Muro, Cuaderno y Mesa de luz leen los mismos datos. Una vista nunca guarda datos propios salvo su estado de UI.
- **Medio ≠ pieza.** Un medio es el archivo (huella SHA-256). Una pieza es su aparición en un tablero. Borrar una pieza no borra el medio.
- El tablero funciona **sin motor PDF**. Nunca importes nada del motor PDF dentro de board/.
- Toda escritura pasa por `saveQueue.ts`. Un gesto equivale a un deshacer (`history.ts`).
- Las migraciones son aditivas: versión nueva con copia recuperable. Rechaza las versiones futuras.
- Los agentes **proponen** (estado `sugerida`) y el usuario confirma. Nunca escriben relaciones o etiquetas confirmadas.

## Antes de entregar
1. `npx tsc -b`  2. `npx vitest run`  3. `npx oxlint`  4. `npx vite build`
Pega la salida real. Si algo falla, dilo; no lo tapes.

## Prohibido
git push, borrar archivos, tocar el motor PDF, añadir dependencias sin pasar por la skill prometeo-licencias.
