---
name: prometeo-biblioteca
description: Biblioteca de referentes de Prometeo y el ritual «Volver a mirar con otros ojos». Úsala en los encargos R-x o al tocar referentes, lecturas o la semilla de archivos.
license: Propietaria del autor
---
# Biblioteca de referentes

Referente = tarjeta con: id, nombre, url, archivo de origen, autor, año, licencia declarada, por qué lo guardé, etiquetas, imágenes (medios en la biblioteca, medio ≠ pieza), `vistoEn` (fechas) y `lecturas[]`.

Lectura = { fecha, proyecto, ojos, texto, modelo, aceptada: boolean }. Es una **propuesta**: no cambia nada hasta que Bruno la acepta.

«Volver a mirar»:
1. Elige 3 referentes: el que lleva más tiempo sin mirarse, uno al azar con semilla y uno ligado al proyecto abierto.
2. Elige unos «ojos» de `ojos.json` (tipógrafo Bauhaus, collagista dadá, arquitecta, DJ, niño de 7 años, archivista, Irene Guerra…).
3. Pregunta a DeepSeek en ≤120 palabras: «Con estos ojos, ¿qué le sirve hoy a <proyecto> de este referente?».
4. Guarda la lectura con la semilla y el modelo. Sin red, sale el mismo ritual sin texto, para que Bruno escriba a mano.
Nunca descargues en masa de un archivo; guarda lo que Bruno elige, con su fuente.
