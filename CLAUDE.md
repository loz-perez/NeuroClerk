# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

NeuroClerk es un asistente de psiquiatría con RAG: responde solo con documentos de referencia (`datos/`) y cita archivo y página de cada dato. El RAG está escrito a mano y sin framework a propósito, para entender cada pieza: no introducir LangChain ni LlamaIndex sin que se pida. El código, los comentarios, la documentación y los mensajes de commit están en español.

El estado de cada fase y los próximos pasos están en `HOJA_DE_RUTA.md`; el registro corto de pendientes, en `TODO.md`; qué documentos usar, en `DATOS.md`.

## Comandos

El repositorio canónico vive en WSL (`~/neuroclerk`); la copia de Windows es un respaldo congelado. Desde la terminal de VS Code Remote-WSL, sin activar el entorno, usar `.venv/bin/python` en lugar de `python`.

```bash
.venv/bin/python rag.py                 # indexa lo que falte y abre la consulta interactiva
.venv/bin/python revisar_datos.py       # revisa datos/ antes de indexar
.venv/bin/python descargar_fichas.py    # descarga de CIMA las fichas que falten

.venv/bin/python -m pytest              # tests unitarios + arquitectura
uvx ruff check .                       # estilo, imports y bugs simples
.venv/bin/python -m pytest test_rag.py::test_parecido_es_la_proporcion_de_palabras_compartidas

.venv/bin/python probar_rag.py --verificar
.venv/bin/python probar_rag.py
.venv/bin/python probar_rag.py --llm
.venv/bin/python probar_rag.py --llm --modelo NOMBRE --pausa 15
.venv/bin/python probar_rag.py --buscar PALABRA [ARCHIVO]
.venv/bin/python probar_rag.py --ranking "PREGUNTA" ARCHIVO
.venv/bin/python banco.py correr
.venv/bin/python panel.py               # http://localhost:8765
.venv/bin/python soap.py pruebas/nota_depresion.txt
.venv/bin/python probar_soap.py

.venv-ragas/bin/python evaluar_ragas.py [--limite N] [--modelo NOMBRE] [--resumen]
```

`evaluar_ragas.py` corre siempre en `.venv-ragas` (`requirements-ragas.txt`): Ragas arrastra LangChain y su propio stack de `openai`, distinto del de `rag.py`. No instalarlo en `.venv`, no importarlo desde `rag.py` ni importar `rag.py` desde `evaluar_ragas.py`; se comunican por el JSON. `test_rag.py` importa sus funciones puras, así que Ragas debe seguir importándose solo dentro de `evaluar()`. Cada evaluador guarda sus puntajes por separado: el de por defecto en `evaluaciones/ragas.json` y los demás en `evaluaciones/ragas_MODELO.json`.

`test_rag.py`, `test_banco.py`, `test_soap.py` y `test_arquitectura.py` corren sin el modelo, la base, los PDFs ni claves. `probar_rag.py` mide la búsqueda y las respuestas, necesita `datos/` y `chroma_db/`, que no están en Git, y no tiene una opción para correr un solo caso: para investigar uno, usar `--ranking` y `--buscar`. Ruff revisa estilo e imports; no hay CI todavía.

Variables de entorno: `GEMINI_API_KEY` / `GROQ_API_KEY`, `NEUROCLERK_MODELO` (cambia el modelo sin editar el código), `SOLO_INDEXAR=1` (indexa y termina), `HF_HUB_OFFLINE=0` (permite descargar el modelo de embeddings; por defecto `rag.py` trabaja sin conexión).

## Arquitectura

`soap.py` estructura notas clínicas ficticias en SOAP y Examen del Estado Mental. Importarlo no tiene efectos; `estructurar()` exige `PROVEEDOR = "ollama"` salvo que se pase `permitir_nube=True` (solo para las notas de `pruebas/`). Las notas nunca van a `datos/`.

Para leer una página puntual de un PDF del corpus, usar `read_document`; para recuperar una decisión anterior, `session_search`. Los plugins de DSH viven en el perfil `~/.dsh/profiles/desktop`, no en el repositorio; ver `docs/PLUGINS.md`.

Las reglas de capas, dependencias y código limpio están en `docs/ARQUITECTURA.md`; `test_arquitectura.py` las comprueba.

`rag.py` es el programa completo y está organizado en bloques numerados: 0 configuración, 1 carga de PDF (`pypdf`) y tablas (`pdfplumber`), 2 división, 3 indexación en ChromaDB, 4 `recuperar()`, 5 `responder()` y `generar()`, 6 bucle interactivo. Los parámetros se cambian en el bloque 0.

**Importar `rag.py` no tiene efectos.** Solo define funciones y valores, y mantenerlo así permite probarlo sin el modelo ni la base. Quien lo use llama explícitamente a:

- `rag.comprobar_clave()`: sale con error si falta la clave del proveedor. Solo hace falta cuando se va a llamar al modelo.
- `rag.preparar()`: carga el modelo de embeddings, abre ChromaDB e indexa los PDFs nuevos o modificados. **También borra de la base los vectores de cualquier PDF que ya no esté en `datos/`.** `modelo_emb`, `coleccion`, `archivos` y `CUPO` quedan vacíos hasta llamarla, y `recuperar()` y `responder()` la necesitan.

**Identidad del índice.** El nombre de la colección es un hash de `MODELO_EMBEDDINGS|TAM_CHUNK|SOLAPE|VERSION_TEXTO`:

- Cambiar cualquiera de esos valores crea una colección nueva y reindexa todo, lo que en CPU tarda horas (ver "Indexar en la nube" en el README). Las colecciones viejas quedan en disco.
- Cualquier cambio en cómo se extrae o se divide el texto exige subir `VERSION_TEXTO`; si no, la base sigue con el texto anterior.
- Cada PDF se reconoce por una huella MD5 de su contenido, lo que permite indexar en Colab y reutilizar la base en la PC, siempre que `rag.py` sea el mismo en ambos lados.

**Recuperación.** Se buscan candidatos por separado en cada archivo, para que el DSM-5-TR no acapare los resultados, con un cupo proporcional al tamaño (`CUPO`, de 12 a 15). Luego se aplican, en orden: margen de similitud respecto al mejor, máximo por página, descarte de casi duplicados de la misma página (Jaccard, sin contar el prefijo común, porque las filas de una tabla repiten el título) y tope total. Al final se suman hasta 2 fragmentos de la página siguiente a los tres mejores (`MAX_CONTINUACIONES`, `MARGEN_CONTINUACION`), para no perder tablas o frases partidas. Los embeddings e5 requieren los prefijos `passage:` y `query:`.

**Tablas.** `tabla_a_unidades()` distingue tres formas: por categorías, por filas y tipo lista. Cada fragmento lleva el título delante, y las continuaciones lo heredan. Las filas de sección acompañan a las filas siguientes como etiqueta. `unir_tablas_partidas()` da el encabezado de la página anterior a las tablas que siguen sin repetirlo; se reconocen por su posición en la página (`es_continuacion()`).

**Relación entre `rag.py` y `probar_rag.py`.** Cambiar uno de estos puntos puede romper las pruebas sin que se note a simple vista:

- `probar_rag.py` usa `rag.preparar`, `rag.comprobar_clave`, `rag.coleccion`, `rag.recuperar`, `rag.responder`, `rag.archivos`, `rag.CUPO`, `rag.modelo_emb`, `rag.MARGEN`, `rag.K_MIN` y `rag.PREFIJO_PREGUNTA`.
- Los avisos del proveedor (límite alcanzado, servidor caído, respuesta incompleta) se devuelven como texto que empieza con `[`, y las pruebas los detectan así para contarlos como errores y no como fallos.
- Los casos de tabla comparan la página y el comienzo del texto del fragmento con el título esperado, así que cambiar el formato de los fragmentos de tabla afecta esos casos.
- `probar_rag.py` fija `NEUROCLERK_MODELO` antes de importar `rag` y usa por defecto `gemini-3.5-flash-lite`, aunque `PROVEEDOR` sea otro. Con Groq u Ollama hay que pasar `--modelo`.

`probar_tablas.py` es la prueba anterior: sus 7 casos ya están dentro de `probar_rag.py`, que es la que se usa.

## Reglas del proyecto

- **Después de cambiar la extracción o la búsqueda:** volver a correr las pruebas y anotar el resultado en la hoja *Historial* de `casos_de_prueba_NeuroClerk.xlsx` y en el mensaje del commit.
- **Respuestas:** el modelo responde solo con el contexto y cita cada afirmación, con temperatura 0.1. Lo más delicado son las dosis, que no deben inventarse nunca: desde el 07/11/2026 el prompt exige que estén textuales en un fragmento citado, para ese fármaco y ese uso. Si la pregunta menciona dos fármacos del corpus, `responder()` muestra una advertencia de combinación y el prompt pide no afirmar que es segura sin cita. Los casos de abstención de las pruebas cubren parte de esto.
- **Datos de pacientes:** nunca por Gemini ni Groq, solo con `PROVEEDOR = "ollama"`.
- **`evaluaciones/`:** contiene texto de los PDFs, así que no se sube a Git.
- **`datos/`:** es la fuente de verdad y todo lo que contiene puede citarse como bibliografía. Las notas y los casos ficticios van en `pruebas/`. No subir los PDFs a Git, por derechos de autor.
- **Nombres de PDF:** claros y sin tildes ni eñes (`FT_Litio.pdf`), porque el modelo los cita y las tildes se desconfiguran entre Windows y Colab. Cada documento nuevo se registra en `fuentes.csv`.
- **Dependencias:** al instalar una librería, regenerar `requirements-lock.txt` con `pip freeze` y volver a poner al principio la línea `--extra-index-url https://download.pytorch.org/whl/cpu`; sin ella falla la instalación de `torch==...+cpu`.
