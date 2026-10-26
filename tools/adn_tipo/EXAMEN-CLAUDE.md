# Entrega ciega a Claude

El desarrollador no abre ni ejecuta el examen real. Bruno proporciona PDFs
propios, sin firmas ni sellos de terceros. Claude revisa su elegibilidad y crea
un plan privado fuera de Git con este formato (los hashes deben ser reales):

```json
{"documentos":[{"archivo":"/ruta/propio.pdf","sha256":"64 hex","split":"holdout"}],
 "mapa_fuentes":{"arvo":"Arvo","fjallaone":"Fjalla One"}}
```

El mapa usa nombre PostScript sin prefijo subset, sin espacios ni guiones y en minúscula.
Cada origen aparece una sola vez; elegir documentos completos para train o
holdout ANTES de rasterizar. Las familias holdout son Arvo y Fjalla One en el
catálogo inicial; ningún estilo de ellas entra en train. No retocar el plan
por resultados. Para afinar, añadir PDFs distintos de familias train y marcar
split=train. No reutilizar un PDF con otra compresión como un origen nuevo.

```sh
nice -n 15 python preparar_examen.py plan-privado.json --modo train --salida /ruta/nativo-train --propios-bruno-sin-firmas-ni-sellos
nice -n 15 python preparar_examen.py plan-privado.json --modo holdout --salida /ruta/examen-sellado --propios-bruno-sin-firmas-ni-sellos
```

Claude conserva SHA-256 de SELLO.json, holdout.json y plan; el sello incluye
hash de cada recorte y de cada PDF fuente. El manifiesto de salida no se puede
sobrescribir. Solo nativo-train se entrega a Colab para afinar. Ni imágenes ni
etiquetas del examen se montan en el entorno de entrenamiento. Este preparador
implementa la alternativa permitida de rasterización con ruido; el escáner físico
necesita registro geométrico adicional y no está verificado.

Tras recibir pesos congelados solo de sintético y afinados A, Claude ejecuta
`medir.py EXAMEN --galeria SINTETICO --holdout-sha256 SHA --salida vecino.json`,
luego con `--pesos .../pesos.pt` para cada modelo. Verificar primero SHA de
SELLO.json frente al valor conservado, nunca frente a otro valor leído de la
misma carpeta. `medir.py` verifica holdout y cada imagen, y rechaza familias u
orígenes que entrenaron el modelo. El catálogo es común a las tres filas.

Devolver solo resultados agregados y hashes, GPU, segundos y coste. Si no gana
al vecino en REAL se declara resultado negativo. No enviar recortes ni texto
privado al desarrollador. No afirmar que la firma digital de un tercero se
puede detectar siempre: también se requiere revisión humana de sellos rasterizados.

No se encontró `supercampana/FILOSOFIA-MAESTRO-ESTUDIANTE.md` en la base del repo;
se aplican aquí las leyes descritas en la adenda del usuario. Cotejar el archivo
maestro antes del examen si tiene requisitos adicionales.
