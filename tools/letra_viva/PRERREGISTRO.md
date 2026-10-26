# D-12 · Prerregistro v1 · 26-10-2026

ANTES de métricas y entrenamiento. Semilla 2610. Estable D-10 permanece
separado; solo tools/letra_viva. Un proceso GPU a la vez, únicamente Colab
de Bruno, saldo compartido con D-10 <=20 unidades. No se autoriza descargar
pesos por este protocolo; se requiere licencia/procedencia y permiso vigente.

## Pregunta

¿Una lección de estilo del documento permite reconstruir palabras nuevas
mejor que padre, maestro y la combinación simple de muestras/trazos? No se
confunde recuperación de memoria externa (glifos) con entrenamiento de pesos.

El plano de desarrollo es de autoría compartida confirmada por el usuario:
SHA ff05702c3fe241d53bcab7fdcd37a925bb619e54313b6074bdedc68e32e9b1a9.
Una página y un origen, ya vistos por el constructor. SOLO DESARROLLO: no se
puede obtener una reserva independiente repartiendo recortes de esa página.
Custodio distinto (Claude/Bruno) debe aportar otros documentos propios o
ejemplos de Prometeo, separar por SHA de origen y sellar DESPUÉS del candidato.
Este constructor no abre esa reserva ni d10-examen. Copias/transformaciones
del plano son una evidencia, no réplicas independientes.

## Brazos y orden

Primero padre sin lección y baseline: fuente nativa reutilizable cuando su
mapeo Unicode esté disponible; si no, fuente derivada de muestras observadas
y medoid por carácter. Missing glyph baseline: composición explícita de
trazos/glifos observados, nunca alfabeto inventado ni fallback silencioso.
Sin regla de composición o muestras suficientes, abstenerse y contar cobertura.
Maestro: origen nativo A, informa geometría y tinta; no juzga la reserva.
Alumno generativo: aún no ejecutable hasta resolver código/pesos compatibles,
corpus de entrenamiento autorizado y presupuesto. Placebo: lección permutada
de igual tamaño/arquitectura/coste; sin éste no atribuir mejora al maestro.
Si padre ya llega al techo o al suelo, parar y rediseñar con desarrollo.

## Rehacer y medir

Solo regiones explícitas autorizadas, jamás firma/sello ni marca educativa.
Comprobar que TODO píxel fuera del rectángulo autorizado es idéntico. Mantener
historial con origen, región, parámetros y hashes antes/después, más parches
reversibles locales. Un editor raster no afirma conservar objetos PDF.
Se mide SSIM RGB (data_range=255) del recorte, MAE y cobertura; LPIPS solo con
pesos aprobados y verificados, de lo contrario null/NO VERIFICADO. No sustituir
LPIPS por una red aleatoria ni inventar cifras. Registrar DPI, tiempo y coste.
Medir tinta Lab, tamaño, inclinación, textura y residual de línea base;
sin certeza suficiente, informar limitación o abstenerse.

En desarrollo: regenerar texto de spans horizontales del mismo plano, pero
excluir todas sus cajas de las muestras que construyen la fuente. No entrenar
con esas cajas. Como hay un solo origen, sigue siendo desarrollo intrasource,
no transferencia ni holdout independiente. Caso fijo inicial: span 18 del ADN
nativo (índice desde cero). No elegir después el recorte que mejor salga.
Comparar baseline de fondo plano y escritura simple vs inpainting y estilo
medido, ambos con la MISMA fuente y la MISMA región. No adjudicar ventaja a
un alumno generativo que no se ha ejecutado.

## A/B ciega

El generador mezcla pares original/rehecho con semilla fijada y guarda clave
separada para custodio. La interfaz del participante no recibe la clave;
respuestas persistentes y rechazadas si se repiten. No se rellenan por Bruno.
En la reserva nueva, mínimo 100 palabras y >=10 páginas, agrupación por origen.
Meta puntual <=55% de identificación humana; reportar intervalo Wilson 95%
y n (con agrupación por origen al interpretar). No afirmar indistinguibilidad
estadística con pocos ejemplos o IC compatible con >55%. El caso de desarrollo
solo prueba el mecanismo de presentación y respuesta, no el objetivo A/B.

## Muerte, regresiones, recuperación y FICHA

No promover si cobertura <1 en población prerregistrada, altera un píxel
externo, no mejora baseline, falla integridad, no hay ventaja frente a placebo
o no cumple A/B en reserva independiente. Guardar negativos y abstenciones.
Después de cada ronda medir tarea anterior para olvido, con checkpoint a Drive
antes de continuar. Sin GPU/corpus/licencia: registrar bloqueo y experimento
barato en SEGUNDA-MIRADA.md, no afirmar que la capacidad no existe.

FICHA D12-2610; productor Codex C3; experiencia: rehacer texto propio sin
plantilla; maestro A; estudiante generativo pendiente; evaluación de estudiante
pendiente custodio; información heredable: muestras/contornos, procedencia y
eventuales pesos por separado. Beneficio/regresiones/transferencia: por medir.
Caduca al cambiar fuente, extracción, origen, presupuesto, licencia o método.
Pesos entrenados: ninguno. No se integran ni duplican núcleos FORGE252 A/B/C.
