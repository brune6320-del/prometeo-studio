---
name: prometeo-herramientas
description: Cómo añadir una herramienta o tipo de tarjeta nuevo a la pizarra infinita de Prometeo sin tocar las que existen. Úsala en los encargos H-x y siempre que crees un tipo de tarjeta, marco o vista.
license: Propietaria del autor
---
# Herramientas sobre la pizarra

La pizarra LUNA (board/model.ts: note, link, media + relaciones) es la base. Todo lo nuevo entra por el registro `board/tools/registry.ts`.

Contrato de una herramienta (no lo cambies sin un encargo):
```ts
export interface BoardTool<D = unknown> {
  id: string;            // 'archivo', 'muro', 'referente', 'collage'…
  nombre: string;        // lo que ve Bruno
  tipo: 'tarjeta' | 'marco';  // marco = contiene otras tarjetas
  crear(x: number, y: number): D;          // datos iniciales
  validar(d: unknown): d is D;             // al cargar un tablero viejo
  Vista: React.FC<{ datos: D; hijos?: BoardCard[]; editar: (d: D) => void }>;
  exportarMarkdown?(d: D): string;         // Obsidian
}
```
Reglas:
- Registrar, no reescribir: note, link y media se registran tal cual, con cero cambios de comportamiento.
- Un tipo desconocido al cargar se muestra como tarjeta «herramienta no instalada», con los datos intactos. Nunca se borra.
- Un marco guarda solo ids de hijos; mover el marco mueve a los hijos; quitar el marco deja a los hijos en la pizarra.
- Cada cambio pasa por saveQueue (un gesto = un deshacer).
- El menú «+» se arma leyendo el registro. Para añadir una herramienta basta con un archivo nuevo más una línea en el registro.
