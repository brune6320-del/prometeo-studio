# D-12 · Letra viva · laboratorio CPU

Estado: implementación parcial TESTED por Codex3-macmini, no VERIFIED por
custodio. Generación neuronal y evaluación en reserva BLOQUEADAS. No integrar
la variante de estilo: perdió contra la referencia simple en desarrollo.

## Alcance implementado

`fuente.py` usa cajas de caracteres del ADN (nativas o aportadas por OCR),
selecciona medoid por carácter, vectoriza contornos y huecos con OpenCV y crea
TTF con fontTools. El contenedor de entrada es PDF; un escaneo debe llegar
como página PDF con ADN compatible que incluya cajas, carácter, origen de
línea, tamaño y tinta. No implementa un OCR ni acepta JPG directamente.
Seleccionar una sola fuente/estilo con `--fuente-xref` si hay varios.

La fuente incrustada se devuelve como preferida, sin modificar sus bytes,
cuando tiene contenedor sfnt, mapeo Unicode suficiente y no declara restricciones
de edición comprobadas por el módulo. El plano disponible contiene CID sin
cmap Unicode reutilizable por esta implementación: se conservó aparte y se
usó la TTF observada. Eso NO demuestra imposibilidad de reutilizar CID; falta
implementar el mapeo PDF CID/ToUnicode y verificar su licencia de uso.

La falta de X se resolvió con una baseline explícita: trazos de x escalados
a las dimensiones de A. No es una muestra real ni un glifo aprendido.
`componer_faltante` también ofrece unión/intersección de máscaras ya alineadas.
No completa el alfabeto silenciosamente.

`editar.py` mide tinta Lab, tamaño, residual de línea base y textura; usa
inpainting Telea local, escribe y repone solo el rectángulo autorizado.
Texto inclinado/página rotada se rechazan, no se normalizan silenciosamente.
El resultado es PNG raster a 144 dpi, no un PDF editable ni una integración
en la bandeja del editor. El original permanece intacto. Registros y parches
permiten restauración exacta con `restaurar.py`.

## Ejecución

Desde la raíz del repo, con el Python del venv C3 (ver ENTORNO en la entrega).
`$PY` representa esa ruta; todos los destinos deben ser externos al repo.

```sh
nice -n 15 "$PY" -m unittest tools.letra_viva.test_letra_viva -v
nice -n 15 "$PY" -m tools.letra_viva --help
nice -n 15 "$PY" -m tools.letra_viva fuente plano.pdf plano.adn.json /ruta/privada/fuente --propio --excluir-span 18
nice -n 15 "$PY" -m tools.letra_viva completar /ruta/privada/fuente/observada.ttf /ruta/privada/completa.ttf --destino X --modelo x --altura A
nice -n 15 "$PY" -m tools.letra_viva editar plano.pdf plano.adn.json /ruta/privada/completa.ttf /ruta/privada/edicion --propio --span 18 --region 1801.19384765625 251.4849853515625 1887.8385009765625 276.5003662109375 --metodo simple
nice -n 15 "$PY" -m tools.letra_viva restaurar /ruta/privada/edicion /ruta/privada/restaurada.png
```

La región del ejemplo solo corresponde al SHA del plano en RESULTADOS.json.
Para otro documento, seleccionar y revisar sus regiones. `--excluir-region`
es repetible; intersecar una zona excluida cancela la operación. Se rechazan
documentos firmados o con anotaciones de sello. Las marcas rasterizadas
requieren revisión y delimitación humana; no hay detector universal.

## A/B

`ab` recibe un JSON con lista de pares y campos `original`, `rehecha` (rutas
de PNG) y `sha256_origen`. Escribe participante y custodio en carpetas
separadas. Abrir `participante/index.html`, responder y descargar JSON.
Evaluar con `python -m tools.letra_viva evaluar-ab respuestas.json custodio/clave.json`.
No entregar la clave ni el ZIP maestro al evaluador antes de responder.
La interfaz tiene persistencia local, no autenticación ni protección contra
un participante que manipule el navegador. El custodio valida duplicados y
sesión. Solo se preparó un par de desarrollo, sin respuestas humanas.

## Colab y dependencias

`colab.ipynb` contiene el código de baseline, guarda resultados y hashes en
Drive y registra el bloqueo neuronal. NO contiene un entrenador ejecutable,
ni pesos, ni descarga automática de dependencias. Se comprobó la sintaxis y
el contenido embebido en local, no se ejecutó en Colab. Entrenar requiere
resolver código/pesos compatibles, permiso para pesos, corpus y reserva,
además de registrar saldo compartido D-10/D-12 <=20 unidades y exclusión GPU.

`requirements-c3.txt` fija las nuevas dependencias del venv aislado. Reutiliza
PyMuPDF preexistente (AGPL/comercial), sin instalarlo ni relicenciarlo. El
experimento local no acredita compatibilidad de su distribución en Prometeo.
No se incluyen binarios de dependencias, fuentes ni datos privados en Git.

## Resultados y límites

Ver RESULTADOS.json y SEGUNDA-MIRADA.md. Un origen, una página, un span de
desarrollo excluido de extracción; no equivale a reserva por origen. No hubo
aprendizaje de pesos, transferencia, placebo neuronal ni examen de olvido.
LPIPS y A/B humano pendientes. No se abrió d10-examen ni se usó GPU.
El texto nuevo y la reversión se prueban aparte como funcionamiento; no se
comparan contra una verdad inexistente para fabricar una métrica estética.
