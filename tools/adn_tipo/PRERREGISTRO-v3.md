# D-10 · Prerregistro v3 · 26-10-2026

Estado: protocolo prospectivo. Debe estar comprometido y publicado ANTES de
cualquier corrida v3, incluido humo. No autoriza abrir d10-examen. El custodio
(Claude o Bruno) y el constructor son personas/agentes distintos. El custodio
congela la evaluación nueva después de congelar el candidato. TESTED no es
VERIFIED. Sin ejecución independiente, no se acredita aprendizaje ni mejora.

## Antecedente que no se modifica

PRERREGISTRO.md v2 conserva SHA-256
`16b5a933c466c04eaa9a28e06dcb62ceb4be2c66b73e1391b1a16d546637d776`.
La corrida T4 comunicada por Bruno (Drive Prometeo/ADN/20261026T123853Z) es
negativa: vecino top-1 .739, top-5 .955, MAE 1.30 pt, ΔE2000 6.93;
CNN 20 épocas .457, .927, 2.40 pt, 22.34. Son cifras comunicadas, no verificadas
por este constructor. Los hashes abreviados b8db1a03… y 4ce46eb0…a6e no se
pueden usar como comprobaciones de integridad. Conservar PARCHE.txt original.
La loss 2.45 → 1.32 no demuestra por sí sola falta de convergencia, ni explica
la regresión de color. Nunca reclasificar v2 ni cambiar sus 20 épocas.

## Pregunta única

¿El protocolo v3, con duración elegida exclusivamente en validación de train
y pérdida de color explícita, mejora la tipografía en muestras nuevas respecto
al padre v2 y al vecino? Es una comparación de protocolo conjunto, no una
atribución causal separada al número de épocas o al peso de color.

Alumno: TipoNet, mismos 71.614 parámetros para el vocabulario original.
Maestro: etiquetas del renderizador y, solo para afinado posterior, extractor
nativo A de documentos propios autorizados. El maestro no juzga el examen.
La información heredable son pesos y procedencia; se separan de la memoria
externa (fichas/logs) y del cambio de estrategia (este protocolo).

## Partición antes de gradientes

Semilla 2610. Se mantienen familias canónicas de v2; ni Arvo ni Fjalla One
participan en entrenamiento o validación interna. Solo se lee train.json y
su manifiesto; el hash holdout es metadato, nunca se abre holdout.json para
elegir pesos. Rechazar cualquier fila que no sea de una familia train.

Sintético: agrupar por SHA de archivo fuente + carácter Unicode; todas sus
variaciones de tinta, tamaño, ruido y render pertenecen al mismo grupo.
Ordenar grupos por SHA-256 de «adn-v3:2610:» + identidad; reservar los primeros
ceil(20% de grupos) de CADA familia. Un mismo hash de imagen no puede cruzar
la partición. Se exigen >=2 grupos por familia y presencia de todas las clases
en ambas partes; de lo contrario bloquear y rediseñar solo con desarrollo.

Nativo: agrupar por SHA-256 del DOCUMENTO ORIGEN, nunca por recorte o página.
Reservar ceil(20% de orígenes) con la misma ordenación. Al menos dos orígenes;
si falta una clase en alguna parte, bloquear sin mover orígenes a conveniencia.
No se permiten fuentes previamente vistas por el padre en la validación nativa
cuando ello implique reutilizar el mismo documento de entrenamiento del padre.

Guardar split.json con hashes de train, grupos e índices antes del primer
gradiente. Validación interna sirve para seleccionar, no es evidencia nueva
reservada ni se usa para promoción. El holdout sintético v2, ya observado,
solo es diagnóstico/regresión, no confirmación independiente de v3.

## Entrenamiento y selección fijados

Una GPU/proceso, en serie. Entrada RGB 64×64. AvgPool2d(4, stride=4) reemplaza
el adaptive 16→4 sin parámetros nuevos; determinismo estricto, nunca warn_only.
CUDA no determinista debe fallar, conservar artefactos y detener la corrida.
No prometer reproducibilidad bit a bit entre dispositivos/versiones distintas.

Adam, lr 1e-3 sintético / 1e-4 afinado, batch 64. Máximo 300 épocas sintéticas
o 100 de afinado. Early stopping: paciencia 25 épocas, mejora mínima absoluta
1e-4, seleccionar el menor score de validación; empate conserva el anterior.
Score = CE(clase) + MSE(tamaño/24) + 4*MSE(L/100,a/128,b/128).
Entrenamiento añade el contraste de v2 con peso .2; el score de selección
excluye contraste para no depender de los pares del minibatch de validación.
MSE de color promedia sus tres canales; tamaño es una cabeza separada.
No cambiar estos pesos según holdout. Registrar por separado cada componente.

Lab conserva signo en a/b, L en [0,100]; no aplicar sigmoid al vector completo.
Validar valores finitos y rangos físicos conservadores de entrada. Diagnóstico:
v2 promedia tamaño y tres canales normalizados juntos, así que ΔE físico no
coincide con esa loss. Esto es una hipótesis de escala/ponderación, no una causa
demostrada. Reportar MAE L/a/b, tamaño y ΔE2000 contra etiquetas reales en
validación y, por separado, en evaluación autorizada. No transformar MSE en ΔE.

Cada época produce predicciones de validación contra etiquetas y guarda su
checkpoint inmutable en Drive ANTES de avanzar, con SHA-256, estado del
optimizador, época, métricas y split. Guardar mejor y último, nunca borrar
generaciones previas. No generar curvas mediante fórmulas.

Local: solo humo CPU de una época con fixtures propios, identificado como
HUMO_NO_EVIDENCIA; nunca una búsqueda de hiperparámetros. Colab: Bruno ejecuta.
Antes de arrancar se registra saldo disponible real del presupuesto compartido
con D-12 (<=20 unidades entre ambos según la campaña), tarifa unidades/h y
tope de segundos conservador. Si falta información de consumo, bloquear GPU.
La estimación por tiempo no sustituye el contador real de Colab; Bruno vigila
el límite y detiene al alcanzarlo. Registrar segundos, unidades reales o null,
tarifa y coste, sin asumir cero. No ejecutar c1001-sc38 ni C-1001.

## Rivales, placebo y criterio de muerte

Antes de entrenar, medir padre v2 congelado y vecino en desarrollo permitido.
Si tarea en techo/suelo impide observar diferencias, parar y rediseñar con
desarrollo, documentando un nuevo protocolo antes de entrenar. No adaptar el
examen. Maestro nativo se informa por separado: aporta etiquetas de referencia,
no constituye un clasificador comparable en escaneados sin nativo emparejado.

Filas distintas: padre v2, vecino, maestro A (cobertura/límites), alumno v3,
y control v3 con etiquetas de familia, tamaño y color permutadas conjuntamente
solo dentro del train de optimización (seed 2610, igual n/arquitectura/presupuesto).
Validación usa etiquetas correctas; el control registra sus propias épocas y
costes. No evaluar el placebo como si fuera el maestro. Si no hay presupuesto
para control y rivales, ensayo causal bloqueado, aunque exista humo funcional.

Umbrales v2 intactos: top-1 >=.80 y >=.05 absoluto sobre vecino; top-5 >=.95;
MAE tamaño <=1.0 pt; ΔE2000 medio <=3.0. Informar n, cobertura, mediana y p95.
Mejorar al padre no basta. Antes de medir fijar muerte: si no cumple todos los
umbrales o no supera al vecino, NO PROMOVER; conservar el negativo. Sin ventaja
sobre placebo, no atribuir beneficio al contenido de la lección.

Después del afinado, repetir la tarea sintética anterior para medir olvido;
reportar deltas frente al padre sintético, separados de mejora en real. Un
adaptador independiente no demuestra aprendizaje acumulativo. La promoción
necesita evaluación nueva reservada del custodio, comparación con antecesor
y baseline, regresiones y costes. El examen real de Bruno sigue cerrado hasta
terminar y congelar v3; la compatibilidad del runner de examen con v3 requiere
revisión del custodio ANTES de su única ejecución, sin leer los PDFs.

## FICHA y recuperación

ID D10-V3-2610; productor Codex C3; fecha 2026-10-26; fallo origen: negativo v2
y backward CUDA adaptive; maestro: renderizador/A; estudiante: TipoNet.
Evaluador: pendiente Claude/Bruno. Caduca al cambiar corpus, etiquetas, modelo,
dependencias o protocolo. Evidencia independiente: ninguna todavía. Copias de
un log cuentan como un apoyo, no como replicaciones. Beneficio, aprendizaje,
transferencia y regresiones empíricas: NO VERIFICADO. Entrenamiento de pesos:
NO EJECUTADO. Coste de GPU de esta preparación: 0 unidades.

Estable: dc5ddd5 y v2 conservados; laboratorio: v3 en módulos separados y
salidas nuevas. Recuperación: checkout del commit previo o cargar checkpoint
anterior verificado; nunca sobrescribir pesos. Las líneas A/B/C de FORGE252
no se integran ni se modifican aquí. Ver SEGUNDA-MIRADA.md para bloqueos y
pruebas baratas que permitan reconsiderar capacidades aún no aplicables.
