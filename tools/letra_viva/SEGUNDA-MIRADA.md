# D-12 · FICHA D12-2610 · 26-10-2026

Productor: Codex3-macmini. Habilidad: recuperar caracteres y rehacer una
región propia. Experiencia nueva: reconstrucción del span 18 del plano
registrado, excluido de la extracción de glifos. Maestro: D-10 nativo A,
geometría y tinta; no juez. Estudiante neuronal: aún no implementado/entrenado.
Evaluador actual: mismo constructor, desarrollo; custodio independiente pendiente.

Información heredable: memoria externa de muestras/contornos con procedencia,
fuente derivada, regla explícita x→X, historial reversible y negativo medido.
Cambio de estrategia: elegir referencia simple en esta versión. Entrenamiento
de pesos: ninguno. Aprendizaje y transferencia: no demostrados.

Beneficio implementado: región controlada y restauración exacta. Regresión:
SSIM estilo 0.777454 frente a simple 0.798575 (delta -0.021121); MAE RGB
16.754863 frente a 15.470601. No promover estilo ni cambiar su configuración
después de mirar este resultado para presentarlo como confirmación.
Hallazgo: la fuente incrustada es CID sin cmap sfnt; el raster/medoid pierde
fidelidad de contorno. No atribuir toda la regresión al inpainting, pues
el brazo estilo cambia también colocación y ruido.

Coste observado: simple 2.659 s; estilo 2.329 s, CPU local; GPU 0, tokens
de maestro/alumno neuronal 0. El coste de conversación no está instrumentado.
Recuperación: conservar fuente y parches; restauración píxel a píxel comprobada.
Caducidad: cualquier cambio de fuente, origen, coordenadas, extracción o método.

| Vía pendiente | Bloqueo preciso | Experimento siguiente propuesto |
|---|---|---|
| Generación few-shot | FontDiffuser no comercial; MX-Font incluye FUNIT CC-BY-NC-SA; licencia de pesos no resuelta y descarga no autorizada | Seleccionar código y pesos de procedencia compatible o implementar variante propia; acordar licencia y permiso antes de descarga |
| Entrenamiento Colab | Sin candidato compatible ni corpus; saldo actual compartido no informado | Prerregistrar padre/maestro/simple/placebo y un piloto CPU; luego una única GPU con checkpoints a Drive y saldo explícito |
| Reserva por origen | Único documento de desarrollo ya visto | Custodio reúne otros documentos propios y sella sus SHA después de congelar candidato; constructor no los abre |
| A/B <=55% | Un par de desarrollo y cero respuestas | Custodio ejecuta >=100 palabras y >=10 páginas de reserva, informa n, Wilson y agrupación por origen |
| LPIPS | Pesos no autorizados/descargados | Revisar licencia y SHA del artefacto exacto y obtener permiso específico |
| CID nativo | Mapeo CID/ToUnicode no implementado | Probar renderer de glifos PDF sin rasterizar contornos; comparación congelada en nuevos datos de desarrollo |
| Escaneado y giro | Solo cajas horizontales compatibles, sin OCR aquí | ADN camino B vecino; fixture propio escaneado con cajas supervisadas; no usar CNN derrotada como mejor método |
| Grano y líneas | Calidad visual limitada dentro del área | Ablación separada de colocación, ruido e inpainting en desarrollo nuevo; mantener negativo actual |

Aún no aplica la evaluación de olvido de un alumno entrenado porque no existe
ese alumno. No se confunde mayor cantidad de código con evolución comprobada.
FORGE252 A/B/C y negativos permanecen fuera del alcance, sin duplicar núcleos.
