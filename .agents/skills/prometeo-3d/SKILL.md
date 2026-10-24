---
name: prometeo-3d
description: Carril 3D de Prometeo Studio. Blender como taller de activos, glTF (.glb) como formato de paso, three.js para verlo en el tablero y Unity como destino opcional. Úsala al tocar modelos 3D, el modo Universo o los puentes.
license: Propietaria del autor
---
# 3D en Prometeo

## Reparto (no mezclar)
- **Blender** (GPL, app aparte): crea y limpia activos. Lo que exportas NO es GPL. Se controla desde el agente con `ahujasid/mcp-for-blender` (MIT). Apaga su telemetría opcional.
- **glTF/.glb**: único formato de intercambio. Cada .glb ≤ 5 MB, ejes Y-arriba y metros. Su licencia va en medio.licencia.
- **three.js** (MIT): única librería 3D dentro de Prometeo. Carga diferida (import dinámico): el tablero 2D no la carga si no hay modelos.
- **Unity** (motor propietario, app aparte): solo lee tablero.json y .glb mediante glTFast (Apache-2.0). Para controlarlo con el agente: `CoplayDev/unity-mcp` (MIT). Nada de Unity dentro de Prometeo.
- **USD/Omniverse**: fuera de alcance (lo decidió Sala Oscura).

## Reglas
- Un modelo 3D es un MEDIO de tipo modelo3d con su miniatura PNG. En el tablero 2D se ve la miniatura; el visor 3D solo se abre al pedirlo.
- Los activos generados con IA llevan origen y coste en medio.origen. Los CC BY se anotan en CREDITS.md.
- Nunca subas .blend, .glb ni proyectos Unity a git sin Git LFS: anótalo como duda.
