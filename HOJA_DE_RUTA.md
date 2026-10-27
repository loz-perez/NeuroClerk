# Hoja de ruta de NeuroClerk

*Actualizada el 27 de octubre de 2026.*

NeuroClerk responde consultas farmacológicas y clínicas con RAG sobre 59 documentos de referencia, y cita el archivo y la página de cada dato. Un conjunto de 19 pruebas mide la búsqueda y las respuestas sobre todos los tipos de documento: hoy encuentra la tabla correcta en 7 de 7 casos, una fuente válida en 17 de 17, y responde bien en 13 de 17, más 2 de 2 abstenciones. Para cerrar la fase 2 faltan tres fallos de búsqueda, la regla de seguridad sobre dosis y el flujo de advertencias; después vienen el módulo de notas clínicas y la interfaz web.

## De un vistazo

| Fase | Contenido | Estado |
| --- | --- | --- |
| 1 | Entorno y fundamentos de RAG | ✅ Completada |
| 2 | Consulta farmacológica con RAG | 🔵 Casi completa: respuestas 13/17, faltan la regla de dosis y las advertencias |
| 3 | Módulo de documentación clínica (notas SOAP) | ⚪ Pendiente |
| 4 | Interfaz y pruebas con usuarios | ⚪ Pendiente |

La consulta farmacológica va primero porque el RAG es la base del resto del proyecto.

## Stack

La búsqueda corre siempre en local. La respuesta la redacta un modelo gratuito en la nube, más rápido, o uno local cuando los datos no deben salir de la computadora. El RAG está escrito a mano, sin framework, para entender cada pieza.

| Componente | Elección | Por qué |
| --- | --- | --- |
| Lenguaje | Python 3.12 | Las versiones más nuevas todavía no tienen PyTorch disponible |
| Modelo de lenguaje | `gemini-3.8-flash` (nube); `openai/gpt-oss-120b` en Groq y `qwen3:8b` en Ollama como alternativas | Gemini responde en segundos y usa bien las tablas; Ollama queda para datos que no deben salir de la PC |
| Modelo para las pruebas | `gemini-3.5-flash-lite` | Su cupo gratuito alcanza para correr las 19 pruebas seguidas |
| Framework RAG | Código propio en `rag.py` | Para aprender cómo funciona cada paso; un framework queda para más adelante |
| Embeddings | `intfloat/multilingual-e5-base` | Lee unas 300 palabras por fragmento; MiniLM solo leía unas 80 |
| Base vectorial | ChromaDB 1.5.9, guardada en disco | Evita recalcular los vectores en cada ejecución |
| Lectura de PDFs | pypdf (texto) y pdfplumber (tablas por filas y categorías) | pypdf convierte las tablas en listas sin título que la búsqueda no encuentra |
| Indexación | Local, o en Google Colab con GPU | Indexar ~3.200 páginas en CPU tarda horas |
| Pruebas | `probar_rag.py` y la planilla `casos_de_prueba_NeuroClerk.xlsx` | Medir cada cambio con los mismos casos y guardar el historial |
| Interfaz | Terminal; Streamlit en la fase 4 | Para probar sin depender de una interfaz |
| Control de versiones | Git y GitHub (repositorio privado), una rama por función | Para volver a una versión que funciona si algo se rompe |

## Fases

### Fase 1: Entorno y fundamentos de RAG — completada

El entorno de desarrollo y la base de conocimiento, con documentos reales de referencia.

- VS Code, entorno virtual con Python 3.12, Git y GitHub.
- Base de conocimiento de 59 PDFs (~3.200 páginas, ~13.400 fragmentos): 51 fichas técnicas de CIMA, el libro de interacciones de la SEFH, la tabla CYP450 de Flockhart, el DSM-5, la guía de referencia de la CIE-11, la guía mhGAP, el Formulario Terapéutico del MSP y las escalas PHQ-9, GAD-7, YMRS y PANSS.
- Herramientas para mantenerla: `descargar_fichas.py` (descarga automática desde CIMA), `revisar_datos.py` (control de la carpeta antes de indexar) y `fuentes.csv` (registro de cada documento).

### Fase 2: Consulta farmacológica con RAG — casi completa

Es la base del resto del proyecto. Responde preguntas cruzando varias fuentes y cita el archivo y la página de cada dato.

Hecho:

- Búsqueda por archivo, con un cupo de candidatos proporcional al tamaño de cada documento (de 3 a 15).
- Filtros sobre los candidatos:
  - Descarta los fragmentos que quedan a más de 0.03 del mejor.
  - Hasta 2 fragmentos por página, para que una sola tabla no desplace a las otras fuentes.
  - Descarta los casi duplicados de una misma página, como un recuadro leído como texto y como tabla.
  - Hasta 12 fragmentos por pregunta.
- Prompt con reglas: citar después de cada afirmación, no agregar nada fuera del contexto e incluir todas las fuentes relevantes; temperatura 0.1.
- Tablas extraídas con pdfplumber: un fragmento por fila, uno por categoría (*Sustratos*, *Inhibidores*, *Inductores*) y título heredado en las continuaciones.
- Limpieza del texto escaneado (palabras cortadas con guion).
- Modelo en la nube (Gemini o Groq) con streaming y reintentos automáticos ante errores pasajeros y límites de uso.
- Indexación en Colab con GPU, con huella por contenido para reutilizar la base en la PC.
- Pruebas automáticas con `probar_rag.py`: 19 casos sobre tablas de interacciones, fichas técnicas, criterios del DSM-5, la CIE-11, la guía mhGAP, el Formulario, las escalas, un caso clínico y dos preguntas en las que debe abstenerse.
  - Antes de medir, `--verificar` comprueba que cada palabra clave esté en su fuente.
  - Para diagnosticar un fallo, `--buscar` y `--ranking` muestran qué fragmentos existen y cuál de los filtros los deja afuera.

Evolución de las pruebas:

| Cambio | Tabla | Fuente | Respuesta | Abstención |
| --- | --- | --- | --- | --- |
| Tablas por filas y categorías, cupo proporcional | 7/7 | 16/17 | 12/17 | 2/2 |
| Límite de 2 fragmentos por página | 7/7 | 16/17 | 14/17 | 2/2 |
| Filtro de casi duplicados y caso de la CIE-11 rehecho | 7/7 | 17/17 | 13/17 | 2/2 |

Falta:

- Resolver los tres fallos de búsqueda que quedan:
  - **mhGAP:** la página con los antidepresivos recomendados queda en el puesto 11. El tope ya subió a 12; falta medirlo.
  - **CIE-11:** llega la tabla de equivalencias con la CIE-10, pero no la fila de la esquizofrenia. La pregunta ya está reformulada sin el código; falta medirlo.
  - **PHQ-9:** llega un solo fragmento del cuestionario, sin el puntaje máximo.
- Revisar si el límite por página corta listas largas: en la tabla de inhibidores del CYP2D6, la continuación queda afuera.
- Agregar al prompt la regla de no dar dosis que no estén textuales en un fragmento citado, y medirla con las pruebas.
- Un flujo de consulta tipo *"Paciente toma fluoxetina, ¿puedo añadir tramadol?"* con una advertencia destacada. Hoy responde en texto libre.

### Fase 3: Módulo de documentación clínica — pendiente

Estructurar una nota de evolución en formato SOAP a partir de texto libre, extrayendo los elementos del Examen del Estado Mental sin inventar síntomas.

- Escribir 5 notas clínicas ficticias para probar, en `pruebas/` y fuera de la carpeta `datos/`.
- Prompt de sistema para SOAP y Examen del Estado Mental.
- Puede reutilizar la estructura de `rag.py`, con el modelo local (Ollama) para cualquier nota que se parezca a datos reales.
- Casos de prueba propios, con el mismo esquema que `probar_rag.py`.

### Fase 4: Interfaz y pruebas — pendiente

- Interfaz en Streamlit con dos pestañas: "Estructurar nota clínica" y "Consulta farmacológica".
- Mostrar los fragmentos usados junto a cada respuesta, como hace hoy la terminal.
- Elegir el proveedor del modelo desde la interfaz, con el modelo local como opción para datos sensibles.
- Aviso visible y obligatorio: "Herramienta de apoyo a la decisión clínica. No reemplaza el juicio médico. Verificar siempre las fuentes originales."
- Pruebas con colegas.

## Reglas éticas y técnicas

Las citas por afirmación y las pruebas automáticas cubren buena parte de la regla más importante, pero ninguna regla está completa todavía.

| Regla | Estado | Qué hay hoy | Qué falta |
| --- | --- | --- | --- |
| Cero alucinaciones en dosis | Parcial | Responde solo con el contexto, cita cada afirmación, temperatura 0.1; una prueba comprueba que no invente la dosis de un fármaco que no está en los documentos | Una regla explícita en el prompt: no dar dosis que no estén textuales en un fragmento citado |
| Humano en el bucle | Parcial | Muestra los fragmentos usados para verificar cada dato | La revisión y firma de notas llega con la fase 3 |
| Datos sintéticos | Pendiente | Todavía no se usan datos de pacientes | Escribir los casos ficticios para las fases 2 y 3 |
| Privacidad | Parcial | La búsqueda es local; los PDFs, la base vectorial y las claves no se suben a Git, y el repositorio es privado; Ollama permite trabajar sin enviar nada fuera | Con Gemini o Groq, la pregunta y los fragmentos salen a la nube: datos de pacientes, solo con Ollama |
| Derechos de autor | Parcial | Los documentos con licencia (DSM-5, PANSS) quedan solo en la PC | Confirmar la licencia de la YMRS antes de cualquier uso compartido |
| Aviso de uso | Parcial | Está en el README | Mostrarlo en la interfaz (fase 4) |

## Próximos pasos

Primero se cierra la fase 2 con los fallos de búsqueda y las reglas de seguridad, y después se empieza la documentación clínica.

- [x] Un fragmento por fila en las tablas con columnas.
- [x] Pruebas de referencia sobre todos los tipos de documento: 19 casos en `probar_rag.py`, con la planilla de resultados.
- [x] Límite de fragmentos por página y filtro de casi duplicados.
- [ ] Medir el tope de 12 fragmentos y la pregunta nueva de la CIE-11.
- [ ] Resolver el caso del PHQ-9.
- [ ] Agregar al prompt la regla de no dar dosis que no estén textuales en un fragmento citado.
- [ ] Flujo de advertencias para consultas de combinación de fármacos.
- [ ] Escribir los casos clínicos ficticios: pacientes con su medicación, para la consulta farmacológica, y notas en texto libre, para el SOAP.
- [ ] Fase 3: prompt y módulo de notas SOAP con Examen del Estado Mental.
- [ ] Fase 4: interfaz en Streamlit con las dos pestañas y el aviso de uso.
- [ ] Más adelante: OCR para PDFs escaneados, guías de GuíaSalud y NICE, y comparar el código propio con LlamaIndex o LangChain.
