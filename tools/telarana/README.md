# D-14 · Telaraña · laboratorio local

Rama studio/telarana, base origin/studio/collage e9fa572. Solo tools/telarana
y nuevo panel opt-in: VITE_TELARANA=1. Sin bandera, Studio conserva la entrada
anterior. Panel también disponible sin instalar frontend mediante servidor
Python: exige --habilitar-telarana, escucha solo 127.0.0.1 y protege escrituras
con token y origen local. Nunca publica el proyecto ni modifica el PDF.

```sh
nice -n 15 python -m tools.telarana.demo /ruta/documento-propio.pdf \
  --salida /ruta/fuera-del-repo/proyecto --caja 1000 210 1600 540 --propio
nice -n 15 python -m tools.telarana.servidor /ruta/fuera-del-repo/proyecto \
  --habilitar-telarana
nice -n 15 python -m unittest tools.telarana.test_telarana -v
```

La caja está en puntos PDF y debe elegirse para cada documento. No es una
selección automática. Demo v0 exige página sin rotación. PDF/ADN/imágenes/fuentes
y proyecto permanecen fuera de Git; solo hash de origen y métricas se publican.
No usar documentos de d10-examen. Si se incorpora este origen a ese examen,
el custodio debe excluirlo por exposición; este agente no abre el examen.

## FICHAS y comportamiento

SC-41 no está integrado en esta rama: esquema local v0 declarado, sin asumir
compatibilidad. Cada ficha tiene productor, experiencia, maestro, fecha,
evaluador pendiente, caducidad por dependencia y orígenes deduplicados.
Las conclusiones nombran revisión exacta de sus dependencias. Una corrección
crea evento nuevo, actualiza la región e invalida únicamente sus descendientes;
no reviven por casualidad, requieren nuevas conclusiones. El log encadenado
reconstruye el mismo estado; valida secuencia/hash y rechaza revisiones obsoletas.
Es integridad local, no firma criptográfica ni protección contra quien reescriba
el log y recalcule toda la cadena. Escritura atómica con bloqueo entre procesos.

## Procedencia del código reutilizado

vendor_adn/nativo.py y comun.py: tools/adn_tipo de d8bffe5 en este mismo repo.
Única adaptación: import relativo de comun. No se copian pesos ni entrenamiento.
vendor_d1/recortador.py y modelo.json: studio/recortador
be652b40b2956c81155cbe617825eb1ea4d2accb. Se usan abrir_fuente/exportar_pieza
con caja explícita; SAM NO se ejecutó y su puntuación es null. No se instalaron
ni descargaron pesos. Copia de implementación propia del mismo repositorio,
no incorporación de un motor distinto. D-1 completo requiere sus dependencias
originales si se quisiera ejecutar SAM fuera de esta demo.

## Evidencia y límites

Documento real con autoría compartida confirmada por usuario, SHA-256
ff05702c3fe241d53bcab7fdcd37a925bb619e54313b6074bdedc68e32e9b1a9.
119 regiones de texto de A, una figura recortada D-1 y una copia girada 90°:
121 regiones. Copia controlada, no una segunda aparición hallada automáticamente.
La relación usa ORB, transformación afín RANSAC y textura de tinta suavizada
a sigma=1 px. Geometría/textura/origen explican la propuesta, no prueban identidad
semántica. Todas las copias del mismo documento cuentan como un apoyo.

Prueba real del panel: 3 conclusiones antes; corregir figura invalida 2 y
mantiene 1. 121 fichas permanecen exactamente iguales (las demás cambian por
corrección/invalidation). Reabrir reconstruye SHA idéntico. Corrección ejecutada
por Codex como prueba de interfaz, no se atribuye a Bruno. 7 tests pasan.
Capturas y proyecto se entregan al propietario fuera de Git. Métricas en
resultados/demo-real.json. Cero errores JS en navegador Brave headless.

Fallo de desarrollo conservado: el primer test de textura con ruido aleatorio
rotado rechazó una coincidencia geométrica correcta por aliasing subpíxel;
se definió escala de textura de 1 px, sin cambiar el umbral .7, y se repitió
el caso. No es una mejora de capacidad entrenada ni un examen reservado.

NO VERIFICADO: build completo del frontend React (dependencias no instaladas),
SAM, localización automática general, rotaciones arbitrarias/PDF rotado,
evaluación independiente, corrección por Bruno. El panel local funcional sí
se probó. No hay entrenamiento, transferencia ni actualización de pesos.
