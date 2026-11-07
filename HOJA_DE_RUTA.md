# Hoja de ruta de NeuroClerk

*Actualizada el 7 de noviembre de 2026.*

NeuroClerk responde consultas farmacológicas y clínicas con RAG sobre 61 documentos de referencia, y cita el archivo y la página de cada dato. Un conjunto de 28 pruebas mide la búsqueda y las respuestas sobre todos los tipos de documento: hoy encuentra la tabla correcta en 7 de 7 casos, una fuente válida en 17 de 17, y responde bien en 17 de 17, más 2 de 2 abstenciones y 9 de 9 casos de dosis. La fase 2 queda cerrada y el módulo de notas clínicas también; sigue la interfaz web.

## De un vistazo

| Fase | Contenido | Estado |
| --- | --- | --- |
| 1 | Entorno y fundamentos de RAG | ✅ Completada |
| 2 | Consulta farmacológica con RAG | ✅ Completada: 17/17, 2/2 y 9/9 |
| 3 | Módulo de documentación clínica (notas SOAP) | ✅ Completada: 5/5 notas |
| 4 | Interfaz y pruebas con usuarios | ⚪ Pendiente |

La consulta farmacológica va primero porque el RAG es la base del resto del proyecto.

## Stack

La búsqueda corre siempre en local. La respuesta la redacta un modelo gratuito en la nube, más rápido, o uno local cuando los datos no deben salir de la computadora. El RAG está escrito a mano, sin framework, para entender cada pieza.

| Componente | Elección | Por qué |
| --- | --- | --- |
| Lenguaje | Python 3.12 | Las versiones más nuevas todavía no tienen PyTorch disponible |
| Modelo de lenguaje | `gemini-3.5-flash-lite` (nube); `openai/gpt-oss-120b` en Groq y `gemma3:4b` en Ollama (con 16 GB, `qwen3:8b`) como alternativas | Gemini responde en segundos y usa bien las tablas; Ollama queda para datos que no deben salir de la PC |
| Modelo para las pruebas | `gemini-3.5-flash-lite` | Su cupo gratuito alcanzó para correr las 28 pruebas seguidas |
| Framework RAG | Código propio en `rag.py` | Para aprender cómo funciona cada paso; un framework queda para más adelante |
| Embeddings | `intfloat/multilingual-e5-base` | Lee unas 300 palabras por fragmento; MiniLM solo leía unas 80 |
| Base vectorial | ChromaDB 1.5.9, guardada en disco | Evita recalcular los vectores en cada ejecución |
| Lectura de PDFs | pypdf (texto) y pdfplumber (tablas por filas y categorías) | pypdf convierte las tablas en listas sin título que la búsqueda no encuentra |
| Indexación | Local, en Google Colab con GPU o en WSL con GPU | En CPU tarda decenas de minutos; en esta máquina, WSL con GPU tardó 11,2 min |
| Pruebas | `probar_rag.py` y la planilla `casos_de_prueba_NeuroClerk.xlsx`; `test_rag.py` con pytest para las funciones puras | Medir cada cambio con los mismos casos y guardar el historial; comprobar la lógica en menos de un segundo, sin modelo ni base |
| Evaluación | Ragas 0.4.3 en `evaluar_ragas.py`, con su propio entorno (`.venv-ragas`) | Mide fidelidad y relevancia; aparte, porque exige LangChain y `openai` 1.x, y así la aplicación sigue sin framework |
| Interfaz | Terminal; Streamlit en la fase 4 | Para probar sin depender de una interfaz |
| Control de versiones | Git y GitHub (repositorio público), una rama por función | Para volver a una versión que funciona si algo se rompe |
| Entorno | Windows + VS Code Remote-WSL; ejecución en Ubuntu 26.04 (WSL2) | La edición queda en Windows y la ejecución pesada en Linux; ver `docs/ENTORNOS.md` |

## Fases

### Fase 1: Entorno y fundamentos de RAG — completada

El entorno de desarrollo y la base de conocimiento, con documentos reales de referencia.

- VS Code, entorno virtual con Python 3.12, Git y GitHub.
- Base de conocimiento de 61 PDFs (~3.300 páginas, ~13.700 fragmentos): 51 fichas técnicas de CIMA, el libro de interacciones de la SEFH, la tabla CYP450 de Flockhart, el DSM-5-TR, la guía de referencia de la CIE-11, la guía mhGAP, el Formulario Terapéutico del MSP y las escalas PHQ-9, GAD-7, YMRS y PANSS.
- Herramientas para mantenerla: `descargar_fichas.py` (descarga automática desde CIMA), `revisar_datos.py` (control de la carpeta antes de indexar) y `fuentes.csv` (registro de cada documento).

### Fase 2: Consulta farmacológica con RAG — casi completa

Es la base del resto del proyecto. Responde preguntas cruzando varias fuentes y cita el archivo y la página de cada dato.

Hecho:

- Búsqueda por archivo, con un cupo de candidatos proporcional al tamaño de cada documento (de 12 a 15).
- Filtros sobre los candidatos:
  - Descarta los fragmentos que quedan a más de 0.03 del mejor.
  - Hasta 2 fragmentos por página, para que una sola tabla no desplace a las otras fuentes.
  - Descarta los casi duplicados de una misma página, como un recuadro leído como texto y como tabla.
  - Hasta 12 fragmentos por pregunta.
- Prompt con reglas: citar después de cada afirmación, no agregar nada fuera del contexto e incluir todas las fuentes relevantes; temperatura 0.1.
- Continuaciones: hasta 2 fragmentos de la página siguiente a los tres mejores, para no perder tablas o frases partidas.
- Aviso destacado de combinación cuando la pregunta menciona dos fármacos del corpus, con la regla de no afirmar que la combinación es segura sin cita.
- Tablas extraídas con pdfplumber: un fragmento por fila, uno por categoría (*Sustratos*, *Inhibidores*, *Inductores*) y título heredado en las continuaciones.
- Limpieza del texto escaneado (palabras cortadas con guion).
- Modelo en la nube (Gemini o Groq) sin streaming, porque el de Gemini a veces se cierra a mitad de respuesta y sin indicar el motivo, con reintentos automáticos ante errores pasajeros, límites de uso y respuestas incompletas. Una respuesta sin confirmación de que terminó no se muestra.
- Indexación en Colab con GPU, con huella por contenido para reutilizar la base en la PC.
- Pruebas automáticas con `probar_rag.py`: 28 casos sobre tablas de interacciones, fichas técnicas, criterios del DSM-5-TR, la CIE-11, la guía mhGAP, el Formulario, las escalas, un caso clínico, dos preguntas en las que debe abstenerse y 9 casos de dosis.
  - Antes de medir, `--verificar` comprueba que cada palabra clave esté en su fuente.
  - Para diagnosticar un fallo, `--buscar` y `--ranking` muestran qué fragmentos existen y cuál de los filtros los deja afuera.

Evolución de las pruebas:

| Cambio | Tabla | Fuente | Respuesta | Abstención |
| --- | --- | --- | --- | --- |
| Tablas por filas y categorías, cupo proporcional | 7/7 | 16/17 | 12/17 | 2/2 |
| Límite de 2 fragmentos por página | 7/7 | 16/17 | 14/17 | 2/2 |
| Filtro de casi duplicados y caso de la CIE-11 rehecho | 7/7 | 17/17 | 13/17 | 2/2 |
| Tope de 12 fragmentos, caso de la CIE-11 reformulado, claves ampliadas en el caso clínico y 2 fichas más | 7/7 | 17/17 | 14/17 | 2/2 |
| Migración a WSL; tablas partidas y banco de pruebas | 7/7 | 17/17 | 14/17 | 2/2 |
| Regla de dosis en el prompt | 7/7 | 17/17 | 14/17 | 2/2 |
| Cupo mínimo 12 y regla de dosis máxima en el prompt | 7/7 | 17/17 | 14/17 | 2/2 |
| Continuaciones de página y regla de puntaje máximo | 7/7 | 17/17 | 17/17 | 2/2 |

El caso que se sumó en la fila del tope de 12 fragmentos es el clínico, por las claves ampliadas de la prueba; los otros cambios no resolvieron ningún caso que fallaba. La migración a WSL no cambió los totales; el cupo 12 y la regla de máximo llevaron las dosis a 9/9 y el respaldo a 9/9. Las continuaciones de página y la regla de puntaje máximo cerraron los tres casos que fallaban: 17/17.

Falta:

- Documentos en inglés: con preguntas en español casi no llegan al contexto. Dos documentos sobre zolpidem que se probaron y se quitaron no aparecieron en ninguno de los 28 casos, y es posible que a la tabla de Flockhart le pase lo mismo.
- Revisar si el límite por página corta listas largas: en la tabla de inhibidores del CYP2D6, la continuación queda afuera.

### Fase 3: Módulo de documentación clínica — completada

Estructura una nota de evolución en formato SOAP a partir de texto libre, con el Examen del Estado Mental separado y sin inventar síntomas.

Hecho:
- 5 notas clínicas ficticias en `pruebas/`, fuera de `datos/`.
- `soap.py`: prompt SOAP + Examen del Estado Mental, parser de secciones y uso de Ollama por defecto.
- `probar_soap.py`: mide secciones, datos clave y examen mental.
- `test_soap.py`: pruebas del parser y del rechazo a la nube.
- Resultado con `gemma3:4b`: 5/5 secciones, 5/5 datos, 5/5 exámenes mentales y 5/5 análisis.

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
| Cero alucinaciones en dosis | Parcial | Responde solo con el contexto, cita cada afirmación, temperatura 0.1; una prueba comprueba que no invente la dosis de un fármaco que no está en los documentos; 9 casos de dosis y un chequeo de que cada dosis de la respuesta esté en los fragmentos. Desde el 07/11/2026 el prompt exige que la dosis esté textual y para ese uso | Sin pendientes: 9/9 en dosis y 9/9 de respaldo (07/11/2026) |
| Humano en el bucle | Parcial | Muestra los fragmentos usados para verificar cada dato | La revisión y firma de notas llega con la fase 3 |
| Datos sintéticos | Pendiente | Todavía no se usan datos de pacientes | Escribir los casos ficticios para las fases 2 y 3 |
| Privacidad | Parcial | La búsqueda es local; los PDFs, la base vectorial y las claves no se suben a Git, lo que importa porque el repositorio es público; Ollama permite trabajar sin enviar nada fuera | Con Gemini o Groq, la pregunta y los fragmentos salen a la nube: datos de pacientes, solo con Ollama |
| Derechos de autor | Parcial | Los documentos con licencia (DSM-5-TR, PANSS) quedan solo en la PC | Confirmar la licencia de la YMRS antes de cualquier uso compartido |
| Aviso de uso | Parcial | Está en el README | Mostrarlo en la interfaz (fase 4) |

## Próximos pasos

Primero se cierra la fase 2 con los casos que fallan y las reglas de seguridad, y después se empieza la documentación clínica.

- [x] Un fragmento por fila en las tablas con columnas.
- [x] Pruebas de referencia sobre todos los tipos de documento: 19 casos en `probar_rag.py`, con la planilla de resultados.
- [x] Límite de fragmentos por página y filtro de casi duplicados.
- [x] Medir el tope de 12 fragmentos y la pregunta nueva de la CIE-11.
- [x] Resolver los casos de la CIE-11, el PHQ-9 y la mhGAP (07/11/2026).
- [ ] Corregir `_parecido`: devuelve 0.0 con dos textos idénticos, así que no los descarta como duplicados. Hay una prueba marcada como `xfail` en `test_rag.py`; al corregirlo, quitar la marca y volver a medir.
- [x] Casos de prueba de dosis y línea de base: 7/9, respaldo 7/7.
- [x] Evaluación con Ragas (fidelidad y relevancia) en un entorno aparte.
- [x] Agregar al prompt la regla de no dar dosis que no estén textuales en un fragmento citado, y medirla (07/11/2026: 7/9, respaldo 7/7).
- [x] Flujo de advertencias para consultas de combinación de fármacos (07/11/2026).
- [x] Escribir los casos clínicos ficticios: pacientes con su medicación, para la consulta farmacológica, y notas en texto libre, para el SOAP.
- [x] Fase 3: prompt y módulo de notas SOAP con Examen del Estado Mental.
- [ ] Fase 4: interfaz en Streamlit con las dos pestañas y el aviso de uso.
- [ ] Más adelante: OCR para PDFs escaneados, guías de GuíaSalud y NICE, y comparar el código propio con LlamaIndex o LangChain.
