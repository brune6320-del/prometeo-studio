---
name: prometeo-lienzo-saber
description: Principios de lienzo, gesto, documento y diseño destilados de papers y estudios (Warburg, VIKI, Shneiderman, Lucero, Sensecape, Thinkink, Hara, Fukasawa, EditTrans, LaTeX2Layout). Úsala antes de diseñar o revisar cualquier interacción del tablero de Prometeo.
---

# Saber del lienzo (versión 1.5 · 26-oct-2026)

Cada regla tiene: de dónde sale, qué hacer y cómo comprobarlo. Se actualiza a diario con lecturas nuevas (ver /mnt/project-files/prometeo/lecturas/). Una regla que falla su prueba dos veces se reescribe o se borra.

## Reglas

1. **El espacio es el significado** (Warburg, VIKI). Cercanía, alineación y pilas expresan relaciones antes de que el usuario las nombre.
   Hacer: detectar grupos, filas y pilas implícitos y ofrecer convertirlos en marco/columna, sin imponerlo.
   Prueba: 6 tarjetas en 2 grupos visuales → el lienzo propone 2 marcos.
2. **Manipulación directa** (Shneiderman). El objeto siempre visible, acción física, efecto inmediato, todo reversible paso a paso.
   Hacer: nada de diálogos para mover, estirar o agrupar; Cmd+Z deshace cada gesto.
   Prueba: estirar, mover y agrupar sin abrir ningún menú; 3 Cmd+Z vuelven al estado inicial.
3. **Sigue al dedo 1:1** (Apple). Durante el gesto solo se mueve una capa; cero trabajo pesado hasta soltar.
   Trackpad (wheel y pellizco): delta 1:1 en el mismo frame, sin muelle ni inercia propia; macOS ya pone la inercia. La física propia solo para arrastre con puntero.
   Prueba: traza de Performance con pellizco de 5 s, frame p95 ≤ 16,7 ms y cola de animación tras el último evento ≤ 16 ms.
4. **Los cinco usos del moodboard** (Lucero 2012): framing, aligning, paradoxing, abstracting, directing.
   Hacer: un gesto para cada uno. Paradoxing = Entropía. Abstracting = extraer paleta/ritmo (ADN de diseño). Directing = fijar un tablero norte.
   Prueba: lista de gestos de la app cubre los 5.
5. **Vacío como recipiente** (Kenya Hara, ma). La interfaz cede espacio al contenido; los controles aparecen al acercarse y se van.
   Prueba: en reposo, ≥ 85 % de la pantalla es lienzo.
6. **Sin pensar** (Fukasawa; Klein, TU Wien 2023). Un gesto debe calzar con algo que la mano ya hace: arrastrar el borde estira, doble clic edita, soltar sobre un marco lo mete. En un lienzo infinito, quien llega nuevo necesita tareas y entradas simples; la profundidad es para quien la busca.
   Prueba: Bruno hace las 5 acciones básicas sin instrucciones.
7. **Densidad a un gesto** (diseño chino contemporáneo). Muchas herramientas, ninguna a la vista si no se usa: búsqueda, «+ Más», menú contextual.
   Prueba: cualquier herramienta a ≤ 2 gestos.
8. **Lo que haces no se confirma; lo que propone la máquina, sí** (Thinkink 2026, Sensecape 2023, Sanna et al. APEGA 2025). La IA escribe en el mismo lienzo, pero como propuesta translúcida en su sitio final: un gesto la acepta, Esc la descarta. Siempre se ve en qué modo estás. Y la IA se guía por lo curado (la selección o el tablero), no solo por un texto.
   Prueba: ninguna acción de IA cambia el tablero sin un Aceptar visible; generar con 3 referentes seleccionados usa esos 3 como contexto.
9. **Esencia, no posición.** De un referente se aprenden paleta, retícula, escala tipográfica, peso y vacío; no se copian coordenadas.
   Prueba: un sistema derivado de un referente no tiene ninguna posición copiada y sí sus tokens.
10. **Borrar es barato, deshacer es la red** (Figma, Canva, Illustrator, Fusion 360). Supr borra al instante, Cmd+A selecciona todo, y nunca se pregunta «¿seguro?» por algo que Cmd+Z repara: se avisa «Eliminado · Deshacer». Los atajos de oficio (Cmd+A/C/X/V/D/Z, flechas, [ ]) existen y salen de una sola tabla.
   Fuente adicional: Blender quitó cinco diálogos de confirmación en 2024 porque «son acciones muy explícitas y se deshacen fácil».
   Borrar es inmediato; olvidar no: tableros, referencias y tarjetas borrados quedan en una memoria de 30 días (A-1, D3), sin papelera visible.
   Prueba: Cmd+A + Supr vacía el tablero sin diálogo y Cmd+Z lo devuelve idéntico; borrar un tablero, recargar y recuperarlo.
11. **Toca solo lo que cambia** (EditTrans, TU Darmstadt 2025). En un documento, cada trozo se clasifica en conservar / editar / insertar, y solo se rehace lo que cambia; el resto queda idéntico.
   Hacer: al editar una palabra de un PDF, los demás spans no se re-rasterizan ni se re-fuentean.
   Prueba: editar una palabra deja byte-idénticos los objetos de texto de las otras líneas de la página.
12. **La verdad se fabrica** (LaTeX2Layout, AAAI 2026). Para entrenar el ojo del documento no se etiqueta a mano: se generan documentos propios cuya fuente, tamaño, tinta y orden se conocen de antemano, y con eso se mide.
   Hacer: D-10 (ADN tipográfico) se evalúa con un banco de PDFs sintéticos de Prometeo con su verdad en JSON.
   Prueba: el banco existe y D-10 reporta acierto de fuente y tamaño contra él.

13. **Seleccionar no acumula sin querer** (Figma, Illustrator, Keynote; A-1 D1). La marquesina reemplaza; ⇧ suma; ⌥ resta; ⇧+clic alterna.
   Prueba: A seleccionada + marquesina sobre B = solo B; ⇧+clic sobre B = A y B; otra vez = solo A.
14. **Un marco es contenedor y lente, con contrato explícito** (A-1 D2). Como lente, cambiar de vista no mueve nada. Como contenedor, arrastrar al vacío desvincula, ⌘G agrupa y ⌘⇧G desagrupa sin mover. La pertenencia nunca es un efecto invisible.
   Prueba: sacar un hijo deja «hijos» sin su id; ⌘⇧G deja las posiciones intactas.
15. **Todo objeto tiene asas, teclado y salida** (WCAG; A-1 D4 y D6). Lo que se hace con el puntero se puede hacer con teclado; los diálogos atrapan y devuelven el foco; Tab nunca queda encerrado. Notas: cambia el ancho (210-640) y el alto sigue al contenido.
   Prueba: Tab en una tarea pasa a la siguiente; Esc devuelve el foco al disparador.
16. **El lienzo se navega con el cuerpo** (Figma iPad; A-1 D5). Un dedo selecciona, dos panean, pellizco acerca, y un botón Mano para quien no conoce el gesto.
   Prueba: en táctil, un dedo no mueve la cámara y dos sí.
17. **Pegar es crear en el cursor; buscar lleva a algún sitio** (Milanote, Freeform; A-1 D8 y D9). Texto → nota, URL → enlace, imagen → medio, tarjetas → copia, en el punto del cursor. Buscar da resultados, contador y salto.
   Prueba: pegar «hola» crea una nota en el cursor; buscar y Enter centra el resultado.
18. **El documento declara lo que puede y no finge** (A-1 D7). Cada PDF muestra qué se puede editar y por qué; lo no verificable no se simula. La meta sigue siendo superar a Acrobat dentro de Prometeo, no mandar a Acrobat.
   Prueba: un escaneado muestra el motivo; un nativo cambia el tamaño verificado o explica el rechazo.
19. **«Guardado» solo en pasado y con prueba** (A-1 D15). El estado dice Guardado cuando el almacén confirma; cerrar fuerza el volcado.
   Prueba: editar y cerrar en el mismo frame; al reabrir, el cambio está.
20. **Definición de terminado** (A-1). Ninguna herramienta nueva entra sin borrado, deshacer, teclado, estado vacío y su prueba.
   Prueba: checklist en la skill y un test por herramienta.
21. **Cultura de ahorro** (Fukasawa, *Without Thought*; Shneiderman, manipulación directa; SUPER-4). La acción más frecuente cuesta un gesto. Añadir algo = 1 clic o 1 tecla. Mover = arrastrar desde cualquier parte. Unir = arrastrar desde el borde. Ningún botón «Confirmar/Añadir» si el gesto ya expresó la intención; el texto explica al pasar el puntero, no antes ni después.
   Hacer: contar los clics de nota, imagen, enlace, columna y marco antes y después de cada cambio de interacción; una tarea que suba de clics se rechaza.
   Prueba: Playwright cuenta los clics por tarea y la tabla no sube respecto a la anterior.

## Registro de aprendizaje
- 25-oct: v1 con 9 reglas.
- 25-oct (entrenamiento): regla 3 FALLÓ contra la traza real de Bruno: cola de 300-900 ms tras cada gesto por inercia propia sumada a la de macOS. Se precisa la regla (v1.1) y el arreglo va a T-1.
- 25-oct (entrenamiento): Bruno no pudo «borrar rápido todo». Revisión: no había Supr, ni Cmd+A, y el borrado usaba window.confirm. Nace la regla 10 (v1.2); el arreglo va a T-2.
- 25-oct (lecturas del día): v1.3. Regla 8 reescrita: «lo que haces no se confirma; lo que propone la máquina, sí» (resuelve la tensión con la regla 10) y suma que la IA se guía por lo curado (Sanna et al.). Regla 10 suma a Blender como fuente. Nuevas 11 (toca solo lo que cambia, EditTrans) y 12 (la verdad se fabrica, LaTeX2Layout), las dos del pilar documentos.
- 25-oct (auditoría A-1 de DeepSeek): v1.4. Entran 13 a 20 desde los principios de la auditoría, fusionando los repetidos (su «borrar es inmediato; olvidar no» va dentro de la 10; su «todo objeto tiene asas» y «teclado no encerrado» se juntan en la 15). En la 18 se corrige la síntesis D7: nada de puente a Acrobat, porque la meta de Bruno es superarlo.
- 26-oct (tacto de SUPER-4): v1.5. Entra la 21 tras probar Forja 4 con las manos: añadir exigía un paso de más, mover pedía acertar una esquina y unir dependía de un botón escondido. La regla no copia a Canva ni a Figma: exige que el gesto ya diga la intención y que la explicación espere al puntero.
