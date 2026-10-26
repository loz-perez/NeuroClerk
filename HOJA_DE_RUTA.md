# Hoja de ruta de NeuroClerk

*Actualizada el 26 de octubre de 2026.*

NeuroClerk ya responde consultas farmacológicas con RAG sobre documentos reales, con citas verificables. Faltan el módulo de documentación clínica (notas SOAP) y la interfaz web.

## De un vistazo

| Fase | Contenido | Estado |
| --- | --- | --- |
| 1 | Entorno y fundamentos de RAG | ✅ Completada |
| 2 | Consulta farmacológica con RAG | 🔵 Avanzada |
| 3 | Módulo de documentación clínica (notas SOAP) | ⚪ Pendiente |
| 4 | Interfaz y pruebas con usuarios | ⚪ Pendiente |

La consulta farmacológica va primero porque el RAG es la base del resto del proyecto.

## Stack

Todo corre en local, para que ningún dato salga de la computadora. El RAG está escrito a mano, sin framework, para entender cada pieza.

| Componente | Elección | Por qué |
| --- | --- | --- |
| Lenguaje | Python 3.12 | Las versiones más nuevas todavía no tienen PyTorch disponible |
| Modelo de lenguaje | `qwen3:8b` en Ollama | Maneja bien el español y se ciñe al contexto; `llama3.2` fallaba la mayoría de las preguntas |
| Framework RAG | Código propio en `rag.py` | Para aprender cómo funciona cada paso; un framework queda para más adelante |
| Embeddings | `intfloat/multilingual-e5-base` | Lee unas 300 palabras por fragmento; MiniLM solo leía unas 80 |
| Base vectorial | ChromaDB 1.5.9, guardada en disco | Evita recalcular los vectores en cada ejecución |
| Lectura de PDFs | pypdf (texto) y pdfplumber (tablas) | pypdf solo convierte las tablas en listas sin título que la búsqueda no encuentra |
| Interfaz | Terminal; Streamlit en la fase 4 | Para probar sin depender de una interfaz |
| Control de versiones | Git y GitHub | Para volver a una versión que funciona si algo se rompe |

## Fases

### Fase 1: Entorno y fundamentos de RAG — completada

El entorno de desarrollo y la base de conocimiento, con documentos reales de referencia.

- VS Code, entorno virtual con Python 3.12, Git y GitHub.
- Ollama con `qwen3:8b`.
- Base de conocimiento: DSM-5 (1000 págs.), *Introducción a las interacciones farmacológicas* de la SEFH (367 págs.) y las fichas técnicas de la AEMPS de sertralina, litio, quetiapina y clozapina.

### Fase 2: Consulta farmacológica con RAG — avanzada

Es la base del resto del proyecto. Ya responde preguntas cruzando varias fuentes y cita el archivo y la página de cada dato.

Hecho:

- Búsqueda por archivo, para que el DSM-5 no acapare los resultados.
- Filtro por similitud: descarta los fragmentos que quedan a más de 0.03 del mejor.
- Prompt con reglas: citar después de cada afirmación, no agregar nada fuera del contexto e incluir todas las fuentes relevantes; temperatura 0.1.
- Tablas extraídas con pdfplumber como fragmentos propios con su título.
- Limpieza del texto escaneado (palabras cortadas con guion).
- Respuesta en streaming, con indicador de progreso y tope de 700 tokens.
- Pruebas automáticas de tablas (`probar_tablas.py`): la búsqueda encuentra 4 de 7 tablas; las 7 respuestas son correctas, pero 3 toman el dato de otras fuentes.

Resultado con la pregunta de referencia sobre el síndrome neuroléptico maligno: pasó de 5 errores a ninguno inventado, combinando tres fuentes; queda alguna cita con la página equivocada.

Falta:

- Un fragmento por fila en las tablas largas con columnas, para que la búsqueda las encuentre (casos 4 y 5 de las pruebas).
- Conservar las columnas de las tablas con encabezados, como *Sustratos* e *Inhibidores* (caso 7).
- Ajustar las palabras clave de las pruebas 4, 5 y 7 a datos que solo estén en la tabla.
- Ampliar las pruebas a 10 preguntas de referencia con su respuesta correcta, más allá de las tablas.
- Un flujo de consulta tipo *"Paciente toma fluoxetina, ¿puedo añadir tramadol?"* con una advertencia destacada. Hoy responde en texto libre.

### Fase 3: Módulo de documentación clínica — pendiente

Estructurar una nota de evolución en formato SOAP a partir de texto libre, extrayendo los elementos del Examen del Estado Mental sin inventar síntomas.

- Escribir 5 notas clínicas ficticias para probar.
- Prompt de sistema para SOAP y Examen del Estado Mental.
- Puede reutilizar el modelo local y la estructura de `rag.py`.

### Fase 4: Interfaz y pruebas — pendiente

- Interfaz en Streamlit con dos pestañas: "Estructurar nota clínica" y "Consulta farmacológica".
- Mostrar los fragmentos usados junto a cada respuesta, como hace hoy la terminal.
- Aviso visible y obligatorio: "Herramienta de apoyo a la decisión clínica. No reemplaza el juicio médico. Verificar siempre las fuentes originales."
- Pruebas con colegas.

## Reglas éticas y técnicas

Las citas por afirmación ya cubren buena parte de la regla más importante, pero ninguna regla está completa todavía.

| Regla | Estado | Qué hay hoy | Qué falta |
| --- | --- | --- | --- |
| Cero alucinaciones en dosis | Parcial | Responde solo con el contexto, cita cada afirmación, temperatura 0.1 | Una regla explícita en el prompt: no dar dosis que no estén textuales en un fragmento citado |
| Humano en el bucle | Parcial | Muestra los fragmentos usados para verificar cada dato | La revisión y firma de notas llega con la fase 3 |
| Datos sintéticos | Pendiente | Todavía no se usan datos de pacientes | Escribir los casos ficticios para las fases 2 y 3 |
| Privacidad | Cumplida | Todo corre en local; los PDFs y la base vectorial no se suben a Git | — |
| Aviso de uso | Parcial | Está en el README | Mostrarlo en la interfaz (fase 4) |

## Próximos pasos

Primero se cierra la fase 2 con una forma de medir la calidad, y después se empieza la documentación clínica.

- [ ] Un fragmento por fila en las tablas con columnas, y volver a correr `probar_tablas.py`.
- [ ] Ajustar las palabras clave de las pruebas 4, 5 y 7.
- [ ] Agregar al prompt la regla de no dar dosis que no estén textuales en un fragmento citado.
- [ ] Ampliar las pruebas a 10 preguntas de referencia con su respuesta correcta.
- [ ] Escribir los casos clínicos ficticios: pacientes con su medicación, para la consulta farmacológica, y notas en texto libre, para el SOAP.
- [ ] Fase 3: prompt y módulo de notas SOAP con Examen del Estado Mental.
- [ ] Fase 4: interfaz en Streamlit con las dos pestañas y el aviso de uso.
- [ ] Más adelante: OCR para PDFs escaneados y comparar el código propio con LlamaIndex o LangChain.
