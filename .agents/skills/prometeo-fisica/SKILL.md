---
name: prometeo-fisica
description: Física del movimiento de Prometeo Studio (muelles, inercia, rubber-band, curvas y duraciones). Úsala al tocar gestos, zoom, pan, arrastre, edición en el sitio o cualquier animación de studio/frontend.
license: Propietaria del autor
---
# Física del tacto de Prometeo

Fuente medida: `~/Desktop/FABCORE-ROBOT/sala-oscura/sala-oscura.html`. Es código propio
(vanilla, sin librería de movimiento); la ley viene de FKU2 v3.2 §9. No hay dependencia
externa que licenciar. Copiar valores, no código a ciegas.

## La ley

`pos += (objetivo − pos) · (1 − e^(−dt/τ))` — sala-oscura.html:8878.
Una exponencial nunca llega: por debajo del imán se pega (`sala-oscura.html:8879`).

| Token | Valor | Origen | Uso |
|---|---|---|---|
| `--motion-tau-seco` | 35 ms | :8876 `TAU_MIN` | sigue al dedo, masa 0.2 |
| `--motion-tau-suave` | 160 ms | :8876 `TAU_MAX` | filtra temblor, masa 1.2 |
| `--motion-masa` | 0.2–1.2 | :8876 | τ = 35 + t·125 ms |
| `--motion-iman` | 0.0018 rad / 0.004 | :8877, :7399 | umbral de pegado |
| `--motion-ataque` | 40 ms | :8875 `ATAQUE` | envolvente al empezar |
| `--motion-release` | 220 ms | :8875 `RELEASE` | envolvente al soltar |
| `--motion-tau-anim` | 85 ms | :7381 `TAU_MOTION` | animar geometría |
| `--motion-tau-rubber` | 120 ms | :9002 | banda elástica |
| `--motion-give` | 0.55 | :9002 | cuánto cede el límite |

Muelle de PROMETEO (derivado, no copiado): `src/motion/muelle.ts`.
`MUELLES.firme` (k 520, c 48) para asentar; `MUELLES.suave` (k 170, c 27) para
abrir/cerrar; `MUELLES.seco` (k 900, c 62) para respuesta inmediata. Los tres son
sobreamortiguados: sin rebote. Inercia: fricción 3.2 s⁻¹, parada a 0.02 px/ms.

## Cuándo usar cada uno

1. **Arrastre, pan y zoom directo:** 0 ms. El puntero manda 1:1; nada de easing
   mientras el dedo está abajo (`--duration-instant`).
2. **Seguir un objetivo (cámara, cursor, autoscroll):** `seguir()` con τ según masa.
3. **Asentar al soltar:** `Muelle('firme')`; si hay velocidad, `inercia` primero.
4. **Abrir/cerrar ficha, panel, menú:** `Muelle('suave')` o 180 ms `--ease-out`.
5. **Hover, foco, selección:** 120 ms `--ease-standard`; pulsado 80 ms.
6. **Diálogo, hoja, cambio de vista:** 280 ms `--ease-emphasis`.
7. **Límite de lienzo o lista:** `rubberBand()`, nunca un corte seco.
8. **Más de 220 elementos animándose** (sala-oscura.html:7388): degradar a salto
   instantáneo. Degradar y decirlo es mejor que ir a tirones.

## Reglas Apple (no negociables)

- **Sigue al dedo 1:1.** Mientras hay puntero abajo no se interpone ninguna animación.
- **Todo es interrumpible.** Un gesto nuevo toma el relevo del anterior; jamás se
  encola ni se espera a que termine una animación.
- **Nada bloquea la mano.** Ni modales para arrastrar, ni esperas de guardado, ni
  `preventDefault` fuera del gesto.
- **La inercia no retrasa el puntero:** solo actúa después de `pointerup`.
- **Un gesto = un paso de Deshacer.** La coalescencia es por sesión de texto/gesto.
- **`prefers-reduced-motion: reduce`:** duración 1 ms, sin desplazamientos ni inercia;
  el estado final se aplica de golpe.
- **Solo `transform` y `opacity`.** Nunca `top/left/width/height` animados.
- **60 fps con 300 tarjetas:** un solo transform en una capa, en `requestAnimationFrame`,
  sin `setState` por evento.

## Antes de entregar

1. `npx tsc -b` 2. `npx vitest run` 3. `npx oxlint` 4. `npx vite build`.
   Si algo falla, se dice; no se tapa.
