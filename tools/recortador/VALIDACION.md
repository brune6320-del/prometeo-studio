# Validación D-1

- Base: `origin/studio/collage` en `d6d3558`; solo se escribe en `tools/recortador/`.
- Mac con 8 GiB de memoria física (`hw.memsize=8589934592`).
- Pesos descargados directamente del enlace oficial y huella comparada antes de cada carga.
- Sintéticos: generados por `sinteticos.py`, nunca se suben PNG/PDF ni pesos al repositorio.
- Contrato del tablero: `normalizeBoard` real preservó sin cambios el BoardExport generado por el clic del navegador, incluido el marco con vista Mesa y el PNG embebido.
- Interfaz: carga de PNG, clic positivo, inferencia CPU, pieza visible sobre damero y enlaces a PNG/piezas.json/tablero.json comprobados en el navegador local.
- PDF sintético: raster de 834 × 625 a 150 ppp inspeccionado visualmente; dos bloques de texto dibujado y una tabla completos, sin cortes.
- Los resultados numéricos reproducibles de las pruebas SAM están en `evidencia-cpu.json` y `evidencia-mps.json`; incluyen el estado de la batería y la configuración usada.
- MPS requiere fallback a CPU para interpolación bicúbica con la versión fijada de Torch. La primera prueba sin fallback falló; no se presenta como MPS puro.
- Se corrigió el instalador para instalar Torch antes de preparar los metadatos de SAM; `pip check` no detectó dependencias rotas en el entorno usado.

NO VERIFICADO: fotos/planos reales; importación desde la interfaz completa de Prometeo; segunda Mac; ejecución totalmente en MPS. No se identificó con certeza el runner antiguo de PRAGMA de 26 cajas. No se deduce exactitud semántica de las puntuaciones SAM ni de las cajas suministradas por el usuario.

Resultado final: **17 pruebas correctas en CPU** (14 de contrato/HTTP y 3 de
integración SAM) y **3 correctas en MPS con fallback CPU**. Mayor error relativo
de área en las tres formas: 0,320862 % en CPU y 0,6025 % en MPS; todas con
IoU ≥0,95. Los tres bloques de documento conservaron exactamente el área de las
cajas rasterizadas indicadas. En rejilla 4×4 quedó la propuesta del rectángulo;
la prueba exige ±5 % para cada propuesta retenida. Comprobación del normalizador,
`node --check`, `sh -n`, `pip check` y `git diff --check`: correctas.
