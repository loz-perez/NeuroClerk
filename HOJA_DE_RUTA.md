# Hoja de ruta de NeuroClerk

Oct 26, 2026 · @Lorenzo Pérez

NeuroClerk ya ofrece consultas farmacológicas con RAG sobre documentos reales y citas verificables. El siguiente paso es cerrar la base de conocimiento y avanzar hacia el módulo de documentación clínica (notas SOAP) y la interfaz web.

## Resumen ejecutivo

La prioridad actual es consolidar la fase de consulta farmacológica, porque sirve como base técnica y de validación para el resto del producto. El proyecto ya funciona de forma local, con salida en terminal y un pipeline transparente de recuperación y generación.

## Estado actual

- Estado general: en desarrollo activo
- Fase de RAG farmacológico: avanzada
- Módulo de notas clínicas: pendiente
- Interfaz web: pendiente
- Privacidad y ejecución local: cumplida

## Stack tecnológico

Todo corre en local para que no salgan datos del equipo. El sistema está implementado a mano en Python, sin framework de RAG, para comprender cada pieza del flujo.

| Componente | Elección | Motivo |
| --- | --- | --- |
| Lenguaje | Python 3.12 | La versión más reciente todavía no tiene PyTorch disponible en todas las combinaciones |
| Modelo local | `qwen3:8b` en Ollama | Tiene mejor rendimiento en español y se ajusta mejor al contexto que modelos más pequeños |
| Framework RAG | Código propio en `rag.py` | Permite entender cada paso del flujo y ajustar reglas sin ocultar la lógica |
| Embeddings | `intfloat/multilingual-e5-base` | Maneja mejor fragmentos largos; `MiniLM` quedaba demasiado corto para textos médicos |
| Base vectorial | ChromaDB guardada en disco | Evita recalcular embeddings en cada ejecución |
| Lectura de PDFs | `pypdf` + `pdfplumber` | `pypdf` extrae texto y `pdfplumber` resuelve tablas y contenido estructurado |
| Interfaz | Terminal por ahora; Streamlit en la fase 4 | Permite probar rápidamente sin bloquear la validación funcional |
| Control de versiones | Git + GitHub | Facilita regresiones y recuperación de versiones estables |

## Fases del proyecto

### Fase 1: Entorno y fundamentos de RAG — completada

Se consolidó la base técnica del proyecto con documentos reales y un entorno de trabajo listo para iterar.

Hecho:

- Configuración del entorno en VS Code con Python 3.12.
- Uso de Ollama con `qwen3:8b`.
- Base documental compuesta por:
  - DSM-5 (1000 páginas)
  - *Introducción a las interacciones farmacológicas* (SEFH)
  - Fichas técnicas de la AEMPS para sertralina, litio, quetiapina y clozapina
- Renombrado y organización del repositorio como NeuroClerk.

### Fase 2: Consulta farmacológica con RAG — avanzada

Esta es la base del producto y ya permite consultar documentos reales con recuperación contextual y referencias verificables.

Hecho:

- Búsqueda por archivo para evitar que el DSM-5 domine todos los resultados.
- Filtro de similitud: descarta fragmentos que caen muy por debajo del mejor candidato.
- Prompt con reglas estrictas: citación por afirmación, no añadir información ajena al contexto y mantener la temperatura baja.
- Extracción de tablas con `pdfplumber` como fragmentos propios con título.
- Limpieza de texto escaneado para corregir palabras cortadas por OCR.

Resultado observado:

- La calidad de la respuesta mejoró significativamente.
- Se redujeron errores de inventar conceptos o mezclar fuentes.
- Ya se combinan varias fuentes cuando aportan información distinta.
- Queda una mejora pendiente en la precisión de la página citada en algunos casos.

Pendiente:

- Validar la versión con tablas en todas las preguntas de referencia.
- Crear un conjunto de preguntas con respuestas correctas para medir la calidad del sistema tras cada cambio.
- Definir un flujo de consulta más útil para casos clínicos reales, por ejemplo: "Paciente toma fluoxetina, ¿puedo añadir tramadol?".

### Fase 3: Módulo de documentación clínica — pendiente

Objetivo: estructurar notas de evolución en formato SOAP a partir de texto libre, con foco en el Examen del Estado Mental sin inventar síntomas ni datos de paciente.

Trabajo previsto:

- Generar 5 notas clínicas ficticias para pruebas.
- Definir un prompt de sistema para SOAP y Examen del Estado Mental.
- Reutilizar la arquitectura del modelo local y la lógica de `rag.py`.
- Validar que la salida sea útil y no suponga una interpretación diagnóstica sin control humano.

### Fase 4: Interfaz y validación clínica — pendiente

Objetivo: transformar la herramienta de terminal en una experiencia usable para un clínico o investigador.

Funciones previstas:

- Interfaz en Streamlit con dos pestañas:
  - "Estructurar nota clínica"
  - "Consulta farmacológica"
- Mostrar los fragmentos usados junto a cada respuesta.
- Incluir un aviso visible: la herramienta es de apoyo a la decisión clínica y no reemplaza el criterio médico ni la revisión de las fuentes originales.
- Pruebas con colegas y validación de casos.

## Reglas éticas y técnicas

La prioridad técnica sigue siendo garantizar que el sistema no invente datos. La cita por afirmación ya cubre la mayor parte del objetivo, pero aún falta reforzar algunas reglas.

| Regla | Estado | Qué hay hoy | Qué falta |
| --- | --- | --- | --- |
| Cero alucinaciones en dosis | Parcial | Las respuestas se basan en contexto y cada afirmación va citada | Añadir una regla explícita: no ofrecer dosis que no aparezcan textualmente en un fragmento citado |
| Humano en el bucle | Parcial | Se muestran los fragmentos de apoyo | Incorporar revisión y firma de notas en la fase clínica |
| Datos sintéticos | Pendiente | No se usan casos ficticios todavía | Crear pacientes sintéticos para pruebas de farmacología y documentación |
| Privacidad | Cumplida | Todo corre localmente y los PDFs no se suben al repositorio | — |
| Aviso de uso | Parcial | Está en el README | Mostrarlo también en la interfaz final |

## Principales riesgos y desafíos

- El modelo más pequeño puede mezclar conceptos parecidos o citar páginas equivocadas.
- Los PDFs escaneados sin texto requieren OCR y no siempre tienen un contenido extraíble directo.
- Las preguntas comparativas pueden ser difíciles para un RAG simple si no se estructura bien la recuperación.
- El sistema no sustituye el criterio médico ni la revisión directa de las fuentes originales.

## Siguientes pasos prioritarios

1. Cerrar la fase 2 con validación formal de calidad.
2. Añadir la regla explícita de no inventar dosis ni cantidades que no aparezcan en un fragmento citado.
3. Crear 10 preguntas de referencia con respuesta correcta y un script para ejecutarlas automáticamente.
4. Preparar casos clínicos ficticios para pruebas de farmacología y SOAP.
5. Diseñar y construir el módulo de notas SOAP con Examen del Estado Mental.
6. Desarrollar la interfaz web en Streamlit con dos paneles y aviso obligatorio.
7. Evaluar OCR para PDFs escaneados y comparar el enfoque propio con LlamaIndex/LangChain más adelante.

## Criterio de éxito del proyecto

Se considerará que la base del proyecto está madura cuando:

- la respuesta farmacológica sea consistente, con citas verificables y sin inventar información;
- el flujo de notas clínicas pueda extraer datos útiles del texto libre sin añadir síntomas inventados;
- la interfaz sea clara para uso clínico y la advertencia de uso sea visible y obligatoria;
- el sistema se mantenga local, privado y reutilizable para futuras mejoras.
