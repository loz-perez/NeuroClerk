# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

NeuroClerk es un asistente de psiquiatría con RAG: responde solo con documentos de referencia (`datos/`) y cita archivo y página de cada dato. El RAG está escrito a mano y sin framework a propósito, para entender cada pieza: no introducir LangChain ni LlamaIndex sin que se pida. El código, los comentarios, la documentación y los mensajes de commit están en español.

El estado de cada fase y los próximos pasos están en `HOJA_DE_RUTA.md`; qué documentos usar, en `DATOS.md`.

## Comandos

Python 3.12, en Windows con PowerShell. Sin activar el entorno, usar `.venv\Scripts\python.exe` en lugar de `python`.

```powershell
python .\rag.py                  # indexa lo que falte y abre la consulta interactiva ("salir" para terminar)
python .\revisar_datos.py        # revisa datos/ antes de indexar (escaneados, fuentes.csv, duplicados)
python .\descargar_fichas.py     # descarga de CIMA las fichas que falten y actualiza fuentes.csv

python -m pytest                                      # pruebas unitarias de las funciones puras (test_rag.py)
python -m pytest test_rag.py::test_parecido_es_la_proporcion_de_palabras_compartidas   # una sola prueba

python .\probar_rag.py --verificar                    # revisa que los casos estén bien armados
python .\probar_rag.py                                # los 28 casos, solo búsqueda (no llama al modelo)
python .\probar_rag.py --llm                          # además pide las respuestas (28 peticiones, gasta cupo)
python .\probar_rag.py --llm --modelo NOMBRE --pausa 15
python .\probar_rag.py --buscar PALABRA [ARCHIVO]     # qué fragmentos contienen una palabra
python .\probar_rag.py --ranking "PREGUNTA" ARCHIVO   # qué filtro deja afuera a un fragmento

.venv\Scripts\python.exe probar_rag.py --llm --exportar   # guarda las respuestas en evaluaciones/respuestas.json
.venv-ragas\Scripts\python.exe evaluar_ragas.py [--limite N] [--pausa S] [--resumen]   # fidelidad y relevancia con Ragas
```

`evaluar_ragas.py` corre siempre en `.venv-ragas` (`requirements-ragas.txt`): Ragas arrastra LangChain y baja `openai` a 1.x, y `rag.py` usa 3.x. No instalarlo en `.venv`, no importarlo desde `rag.py` ni importar `rag.py` desde `evaluar_ragas.py`; se comunican por el JSON. `test_rag.py` importa sus funciones puras, así que Ragas debe seguir importándose solo dentro de `evaluar()`.

`test_rag.py` corre sin el modelo, la base, los PDFs ni claves. `probar_rag.py` mide la búsqueda y las respuestas, necesita `datos/` y `chroma_db/`, que no están en Git, y no tiene una opción para correr un solo caso: para investigar uno, usar `--ranking` y `--buscar`. No hay linter ni CI.

Variables de entorno: `GEMINI_API_KEY` / `GROQ_API_KEY`, `NEUROCLERK_MODELO` (cambia el modelo sin editar el código), `SOLO_INDEXAR=1` (indexa y termina), `HF_HUB_OFFLINE=0` (permite descargar el modelo de embeddings; por defecto `rag.py` trabaja sin conexión).

## Arquitectura

`rag.py` es el programa completo y está organizado en bloques numerados: 0 configuración, 1 carga de PDF (`pypdf`) y tablas (`pdfplumber`), 2 división, 3 indexación en ChromaDB, 4 `recuperar()`, 5 `responder()` y `generar()`, 6 bucle interactivo. Los parámetros se cambian en el bloque 0.

**Importar `rag.py` no tiene efectos.** Solo define funciones y valores, y mantenerlo así permite probarlo sin el modelo ni la base. Quien lo use llama explícitamente a:

- `rag.comprobar_clave()`: sale con error si falta la clave del proveedor. Solo hace falta cuando se va a llamar al modelo.
- `rag.preparar()`: carga el modelo de embeddings, abre ChromaDB e indexa los PDFs nuevos o modificados. **También borra de la base los vectores de cualquier PDF que ya no esté en `datos/`.** `modelo_emb`, `coleccion`, `archivos` y `CUPO` quedan vacíos hasta llamarla, y `recuperar()` y `responder()` la necesitan.

**Identidad del índice.** El nombre de la colección es un hash de `MODELO_EMBEDDINGS|TAM_CHUNK|SOLAPE|VERSION_TEXTO`:

- Cambiar cualquiera de esos valores crea una colección nueva y reindexa todo, lo que en CPU tarda horas (ver "Indexar en la nube" en el README). Las colecciones viejas quedan en disco.
- Cualquier cambio en cómo se extrae o se divide el texto exige subir `VERSION_TEXTO`; si no, la base sigue con el texto anterior.
- Cada PDF se reconoce por una huella MD5 de su contenido, lo que permite indexar en Colab y reutilizar la base en la PC, siempre que `rag.py` sea el mismo en ambos lados.

**Recuperación.** Se buscan candidatos por separado en cada archivo, para que el DSM-5-TR no acapare los resultados, con un cupo proporcional al tamaño (`CUPO`, de 3 a 15). Luego se aplican, en orden: margen de similitud respecto al mejor, máximo por página, descarte de casi duplicados de la misma página (Jaccard, sin contar el prefijo común, porque las filas de una tabla repiten el título) y tope total. Los embeddings e5 requieren los prefijos `passage:` y `query:`.

**Tablas.** `tabla_a_unidades()` distingue tres formas: por categorías, por filas y tipo lista. Cada fragmento lleva el título delante, y las continuaciones lo heredan.

**Relación entre `rag.py` y `probar_rag.py`.** Cambiar uno de estos puntos puede romper las pruebas sin que se note a simple vista:

- `probar_rag.py` usa `rag.preparar`, `rag.comprobar_clave`, `rag.coleccion`, `rag.recuperar`, `rag.responder`, `rag.archivos`, `rag.CUPO`, `rag.modelo_emb`, `rag.MARGEN`, `rag.K_MIN` y `rag.PREFIJO_PREGUNTA`.
- Los avisos del proveedor (límite alcanzado, servidor caído) se devuelven como texto que empieza con `[`, y las pruebas los detectan así para contarlos como errores y no como fallos.
- Los casos de tabla comparan la página y el comienzo del texto del fragmento con el título esperado, así que cambiar el formato de los fragmentos de tabla afecta esos casos.
- `probar_rag.py` fija `NEUROCLERK_MODELO` antes de importar `rag` y usa por defecto `gemini-3.5-flash-lite`, aunque `PROVEEDOR` sea otro. Con Groq u Ollama hay que pasar `--modelo`.

`probar_tablas.py` es la prueba anterior: sus 7 casos ya están dentro de `probar_rag.py`, que es la que se usa.

## Reglas del proyecto

- **Después de cambiar la extracción o la búsqueda:** volver a correr las pruebas y anotar el resultado en la hoja *Historial* de `casos_de_prueba_NeuroClerk.xlsx` y en el mensaje del commit.
- **Respuestas:** el modelo responde solo con el contexto y cita cada afirmación, con temperatura 0.1. Lo más delicado son las dosis, que no deben inventarse nunca. Los casos de abstención de las pruebas cubren parte de esto.
- **Datos de pacientes:** nunca por Gemini ni Groq, solo con `PROVEEDOR = "ollama"`.
- **`evaluaciones/`:** contiene texto de los PDFs, así que no se sube a Git.
- **`datos/`:** es la fuente de verdad y todo lo que contiene puede citarse como bibliografía. Las notas y los casos ficticios van en `pruebas/`. No subir los PDFs a Git, por derechos de autor.
- **Nombres de PDF:** claros y sin tildes ni eñes (`FT_Litio.pdf`), porque el modelo los cita y las tildes se desconfiguran entre Windows y Colab. Cada documento nuevo se registra en `fuentes.csv`.
- **Dependencias:** al instalar una librería, regenerar `requirements-lock.txt` con `pip freeze` y volver a poner al principio la línea `--extra-index-url https://download.pytorch.org/whl/cpu`; sin ella falla la instalación de `torch==...+cpu`.
