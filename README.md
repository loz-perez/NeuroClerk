# NeuroClerk

NeuroClerk es un asistente para psiquiatría que responde consultas sobre interacciones farmacológicas y, en una próxima versión, ayudará a estructurar notas de evolución. Usa RAG: responde solo con la información de documentos de referencia, como el DSM-5-TR o fichas técnicas, y cita el archivo y la página de cada dato, para que cualquier respuesta se pueda verificar en la fuente. La búsqueda funciona siempre en equipos propios; la respuesta la puede redactar un modelo local o uno gratuito en la nube.

El estado de cada fase y los próximos pasos están en [HOJA_DE_RUTA.md](HOJA_DE_RUTA.md).

Qué documentos usar y dónde conseguirlos, en [DATOS.md](DATOS.md).

> **Aviso:** es una herramienta de apoyo y un proyecto en desarrollo. No reemplaza el juicio clínico ni la consulta de las fuentes originales.

## Cómo funciona

```mermaid
flowchart LR
    A["PDFs en datos/"] --> B["Extraer texto<br/>pypdf"]
    A --> C["Extraer tablas<br/>pdfplumber"]
    B --> D["Dividir en fragmentos<br/>200 palabras, solape 40"]
    C --> D
    D --> E["Embeddings<br/>multilingual-e5-base"]
    E --> F[("ChromaDB<br/>chroma_db/")]
    P["Pregunta"] --> G["Buscar candidatos<br/>3 a 15 por archivo"]
    F --> G
    G --> H["Filtrar por similitud<br/>margen 0.03, máx. 12"]
    H --> I["Prompt con reglas<br/>y citas"]
    I --> J["Modelo de lenguaje<br/>Gemini, Groq u Ollama"]
    J --> R["Respuesta citada"]
```

1. **Cargar:** lee el texto de cada página con `pypdf` y une las palabras cortadas con guion ("dificul- tad" → "dificultad").
2. **Tablas:** `pdfplumber` detecta las tablas y las guarda con su título delante: un fragmento por fila en las tablas con columnas, y uno por categoría (por ejemplo *Sustratos* e *Inhibidores*) en las listas agrupadas. Las tablas que siguen en otra columna de la página heredan el título.
3. **Dividir:** parte el texto en fragmentos de 200 palabras que se solapan 40, para no cortar una idea a la mitad.
4. **Indexar:** convierte cada fragmento en un vector y lo guarda en ChromaDB. Solo se hace la primera vez, o cuando un PDF es nuevo o cambió. Cada PDF se reconoce por una huella de su contenido, así que la base se puede indexar en otra computadora (por ejemplo, en Colab).
5. **Recuperar:** busca los fragmentos más parecidos de **cada** archivo (12 en una ficha corta, hasta 15 en un libro) y descarta los que quedan muy por debajo del mejor. Además suma hasta dos fragmentos de la página siguiente a los tres mejores, para no perder tablas o frases partidas.
6. **Generar:** le pasa esos fragmentos al modelo con instrucciones de responder solo con el contexto y citar cada afirmación. La respuesta se muestra solo si el modelo confirma que terminó, y los errores pasajeros del proveedor se reintentan solos. No da ninguna dosis que no esté escrita textualmente en un fragmento que cite.

## Estructura del proyecto

```text
NeuroClerk/
├── .venv/                 # entorno Linux (Python 3.12), no se sube a Git
├── .venv-ragas/           # entorno de Ragas, no se sube a Git
├── datos/                 # PDFs, no se suben a Git
├── chroma_db/             # vectores guardados, no se sube a Git
├── evaluaciones/          # respuestas, Ragas y banco.sqlite, no se sube a Git
├── pruebas/               # notas clínicas ficticias, no se indexan
├── docs/ENTORNOS.md       # cómo está montado Windows + WSL
├── .vscode/               # intérprete y tareas para Remote-WSL
├── rag.py                 # el programa completo
├── probar_rag.py          # pruebas de búsqueda y respuesta
├── probar_tablas.py       # prueba anterior; sus 7 casos están en probar_rag.py
├── test_rag.py            # pruebas unitarias de las funciones puras (pytest)
├── test_banco.py          # pruebas de banco.py (pytest)
├── test_soap.py           # pruebas de soap.py (pytest)
├── probar_soap.py         # mide las cinco notas ficticias con Ollama
├── banco.py               # compara configuraciones de la búsqueda
├── panel.py               # panel web de las corridas del banco
├── soap.py                # estructura notas clínicas en SOAP + examen mental
├── evaluar_ragas.py       # fidelidad y relevancia con Ragas (entorno aparte)
├── descargar_fichas.py    # descarga las fichas técnicas de CIMA
├── revisar_datos.py       # revisa la carpeta datos/ antes de indexar
├── fuentes.csv            # registro de los documentos de datos/
├── casos_de_prueba_NeuroClerk.xlsx  # casos de prueba y resultados
├── requirements.txt       # librerías principales
├── requirements-lock.txt  # versiones exactas del entorno
├── requirements-ragas.txt # librerías de .venv-ragas
├── BANCO.md               # cómo medir y comparar configuraciones
├── DATOS.md               # qué documentos poner en datos/ y dónde conseguirlos
├── HOJA_DE_RUTA.md
├── README.md
└── CLAUDE.md              # guía para trabajar en el proyecto con Claude Code
```

## Entorno híbrido (WSL)

En este equipo el repositorio canónico vive en WSL (`~/neuroclerk`) y se edita con VS Code desde Windows mediante *Remote - WSL*; `C:\Users\loren\dev\NeuroClerk` queda como respaldo congelado. La indexación, las pruebas, el banco, el panel, Ragas y Ollama corren en WSL. Los comandos para abrir las dos ventanas y dónde van las claves están en [docs/ENTORNOS.md](docs/ENTORNOS.md).

## Requisitos

- Windows 10/11 (también funciona en macOS y Linux cambiando los comandos de activación).
- **Python 3.12.** Las versiones más nuevas pueden no tener todavía PyTorch disponible.
- Una clave gratuita de Gemini o Groq, o bien [Ollama](https://ollama.com) instalado para usar un modelo local.
- Para el modelo local, `gemma3:4b` funciona con unos 8 GB de RAM; `qwen3:8b` necesita unos 16 GB.
- VS Code con la extensión Python (opcional, pero recomendado).

## Instalación

```powershell
# 1. Crear y activar el entorno virtual con Python 3.12
py -3.12 -m venv .venv
.venv\Scripts\activate

# 2. Instalar las versiones exactas que funcionan (torch CPU incluido)
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-lock.txt

# 3. Solo si vas a usar el modelo local
ollama pull qwen3:8b
```

Si `requirements-lock.txt` falla, instala desde las librerías principales:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

La primera vez, el modelo de embeddings se tiene que descargar. Ejecuta con la variable `HF_HUB_OFFLINE=0`:

```powershell
$env:HF_HUB_OFFLINE = "0"; python .\rag.py
```

Las siguientes veces no hace falta: `rag.py` usa el modelo ya descargado sin conectarse a Hugging Face.

En VS Code: `Ctrl+Shift+P` → **Python: Select Interpreter** → el que dice `.venv`.

### Mantener las dependencias

- `requirements.txt` tiene solo las librerías principales; `requirements-lock.txt`, las versiones exactas de todo el entorno.
- **Cada vez que instales una librería nueva**, regenera el lock en ese momento:

  ```powershell
  pip freeze > requirements-lock.txt
  ```

- `pip freeze` no escribe la dirección de PyTorch CPU. Después de regenerarlo, agrega esta línea **al principio** del archivo; si no, falla la instalación de `torch==...+cpu`:

  ```text
  --extra-index-url https://download.pytorch.org/whl/cpu
  ```

### Por qué PyTorch CPU

PyTorch solo calcula los embeddings, y gracias a ChromaDB eso pesa únicamente al indexar. La respuesta la genera el modelo de lenguaje, que no depende de PyTorch. La versión CPU pesa ~200 MB frente a más de 2 GB, y no depende de tener una tarjeta NVIDIA. Para indexar rápido, usa Colab (ver [Indexar en la nube](#indexar-en-la-nube-colab)).

## Modelo de lenguaje: local o en la nube

En el bloque 0 de `rag.py`, `PROVEEDOR` elige quién redacta la respuesta:

| `PROVEEDOR` | Modelo | Costo | Velocidad | A tener en cuenta |
| --- | --- | --- | --- | --- |
| `"gemini"` (por defecto) | `gemini-3.5-flash-lite` | Plan gratuito | Rápido | Límite de peticiones por día; en el plan gratuito, Google puede usar lo enviado para mejorar sus productos |
| `"groq"` | `openai/gpt-oss-120b` | Plan gratuito | Muy rápido | Límite de 8.000 tokens por minuto: alcanza para 1 o 2 preguntas por minuto |
| `"ollama"` | `gemma3:4b` | Gratis | Lento en CPU | Nada sale de la computadora |

Los proveedores en la nube solo reciben la pregunta y los fragmentos encontrados, nunca los PDFs completos. Aun así, **no los uses con datos de pacientes**: para eso está `"ollama"`.

En el plan gratuito de Gemini, cada modelo tiene su propio límite diario. Si se agota, o si un modelo sigue devolviendo el error 503 (servidor saturado), cambia el modelo en `MODELOS`, por ejemplo a `"gemini-3.8-flash"`, o pasa a `PROVEEDOR = "groq"`.

### Configurar la clave

1. Crea una clave gratuita:
   - Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   - Groq: [console.groq.com/keys](https://console.groq.com/keys)
2. Guárdala como variable de entorno (no dentro de `rag.py`, para que no termine en Git):

   ```powershell
   setx GEMINI_API_KEY "tu_clave"
   setx GROQ_API_KEY "tu_clave"
   ```

3. Cierra **todas** las ventanas de VS Code y vuelve a abrirlo. Comprueba con `echo $env:GEMINI_API_KEY`.

Nunca pegues la clave completa en un chat, un archivo del proyecto ni un commit. Si eso pasa, bórrala en la consola del proveedor y crea otra.

Si falta la clave, el programa avisa al arrancar. Si se alcanza el límite gratuito, la respuesta lo dice. Los errores pasajeros (servidor saturado, código 503) se reintentan hasta 3 veces. Los límites actuales se ven en [AI Studio](https://aistudio.google.com/rate-limit) y en la [consola de Groq](https://console.groq.com/settings/limits).

## Uso

1. Pon tus PDFs en `datos/`. Las fichas técnicas de [DATOS.md](DATOS.md) se descargan solas:

   ```powershell
   python .\descargar_fichas.py
   ```

2. Revisa la carpeta antes de indexar:

   ```powershell
   python .\revisar_datos.py
   ```

   Avisa de PDFs escaneados sin texto, archivos que faltan en `fuentes.csv`, nombres poco claros y posibles duplicados.
3. Ejecuta:

   ```powershell
   python .\rag.py
   ```

4. Escribe tus preguntas. Para terminar, escribe `salir`.

**Nombres de archivo:** usa nombres claros y **sin tildes ni eñes** (`Guia_mhGAP.pdf`, no `Guía_mhGAP-spa.pdf`). El modelo cita el nombre del archivo, y las tildes se desconfiguran al pasar los archivos entre Windows y Colab.

Para cada pregunta, el programa muestra los fragmentos usados con su puntaje de similitud. Mientras el modelo escribe aparecen puntos, y al final la respuesta:

```text
Fragmentos usados:
  -> [0.909] Interacciones_Farmacologicas_SEFH.pdf, página 9: Tabla 1. Fármacos que pueden causar...
  -> [0.894] Interacciones_Farmacologicas_SEFH.pdf, página 9: de receptores), en los procesos...

Generando respuesta...
..........................................

Respuesta:
...
```

## Consultas de combinación

Si la pregunta menciona dos fármacos del corpus (`FT_*.pdf`), el programa muestra un aviso antes de la respuesta:

```text
================================================================
 ADVERTENCIA - CONSULTA DE COMBINACIÓN
 Fármacos detectados: fluoxetina, tramadol
 Revisa la interacción en las fuentes citadas antes de indicar.
 Que el contexto no la mencione no significa que la combinación sea segura.
================================================================
```

El aviso no reemplaza la respuesta: el prompt pide describir el riesgo y el mecanismo, y decir expresamente si los fragmentos no mencionan la interacción. Se detectan por el nombre del archivo (`FT_Fluoxetina.pdf`); las clases (por ejemplo, IECA) y las marcas no se reconocen.

## Notas clínicas (SOAP)

`soap.py` ordena una nota de evolución en Subjetivo, Objetivo, Análisis, Plan y Examen del Estado Mental. Las cinco notas ficticias están en `pruebas/` (no en `datos/`), así que el RAG no las cita como bibliografía.

```bash
.venv/bin/python soap.py pruebas/nota_depresion.txt
.venv/bin/python soap.py --todas --salida evaluaciones/soap
.venv/bin/python probar_soap.py
```

Por defecto usa Ollama (`gemma3:4b`): una nota clínica no se envía a Gemini ni Groq. `--nube` existe solo para las notas ficticias. El prompt prohíbe agregar síntomas, medicación o resultados que no estén en la nota; si falta un dato, el modelo escribe “no consta”.

## Indexar en la nube (Colab)

Indexar las ~3.300 páginas en una computadora sin GPU tarda mucho. En Google Colab, con una GPU gratuita, es mucho más rápido.

1. En tu PC, comprime lo necesario:

   ```powershell
   Compress-Archive -Path rag.py, datos -DestinationPath NeuroClerk.zip -Force
   ```

2. En [Colab](https://colab.research.google.com), crea un cuaderno, elige **Entorno de ejecución → Cambiar tipo de entorno → GPU T4** y sube `NeuroClerk.zip`.
3. Ejecuta estas tres celdas:

   ```python
   !unzip -q -o NeuroClerk.zip -d /content/NeuroClerk
   %cd /content/NeuroClerk
   !pip install -q pdfplumber==0.11.10 chromadb==1.5.9 "cryptography>=50.0,<51" pypdf
   ```

   ```python
   !HF_HUB_OFFLINE=0 SOLO_INDEXAR=1 python rag.py
   ```

   ```python
   !zip -qr chroma_db.zip chroma_db
   from google.colab import files
   files.download("chroma_db.zip")
   ```

4. En tu PC, borra la carpeta `chroma_db` vieja y descomprime `chroma_db.zip` en la raíz del proyecto. Al ejecutar `rag.py` deberías ver *"Ya indexado"* en todos los PDFs.

El aviso de conflictos de dependencias que muestra `pip` en Colab se puede ignorar. El `rag.py` de tu PC tiene que ser el mismo que usaste en Colab.

## Configuración

Todo se ajusta en el bloque 0 de `rag.py`:

| Variable | Valor actual | Para qué sirve |
| --- | --- | --- |
| `PROVEEDOR` | `"gemini"` | Quién redacta la respuesta: `"gemini"`, `"groq"` u `"ollama"` |
| `MODELOS` | ver `rag.py` | Qué modelo usa cada proveedor |
| `MODELO_EMBEDDINGS` | `intfloat/multilingual-e5-base` | Modelo que convierte texto en vectores |
| `TAM_CHUNK` | `200` | Palabras por fragmento |
| `SOLAPE` | `40` | Palabras repetidas entre fragmentos seguidos |
| `K_MIN`, `K_MAX` | `12`, `15` | Candidatos que se buscan en cada PDF: 12 en una ficha corta, hasta 15 en un libro |
| `FRAGMENTOS_POR_CANDIDATO` | `100` | 12 candidatos como mínimo; uno más por cada 100 fragmentos, hasta 15 |
| `MARGEN` | `0.03` | Se descartan los fragmentos que quedan más de esto por debajo del mejor |
| `MAX_FRAGMENTOS` | `12` | Tope de fragmentos elegidos; se suman hasta 2 continuaciones de la página siguiente |
| `MAX_POR_PAGINA` | `2` | Tope de fragmentos de una misma página, para que una tabla con muchas filas no ocupe todo el contexto |
| `MAX_CONTINUACIONES` | `2` | Fragmentos extra de la página siguiente a los tres mejores |
| `MARGEN_CONTINUACION` | `0.05` | Cuánto puede caer una continuación respecto del mejor fragmento |
| `SIMILITUD_DUPLICADO` | `0.5` | Dos fragmentos de una misma página que comparten más de esta proporción de palabras se consideran el mismo texto, y se usa solo uno (pasa cuando un cuadro se lee como texto y también como tabla) |
| `VERSION_TEXTO` | `4` | Súbela cada vez que cambies cómo se extrae o se divide el texto |

El modelo trabaja con `temperature` 0.1, para que se apegue al texto. El tope de la respuesta es de 700 tokens con Ollama y de 2.000 con los proveedores en la nube, que cuentan su razonamiento dentro de ese tope.

Si cambias `MODELO_EMBEDDINGS`, `TAM_CHUNK`, `SOLAPE` o `VERSION_TEXTO`, el programa crea una colección nueva y vuelve a indexar todo automáticamente. Para empezar de cero, borra la carpeta `chroma_db/`.

Variables de entorno opcionales: `SOLO_INDEXAR=1` indexa y termina, sin pedir la clave del modelo; `HF_HUB_OFFLINE=0` permite descargar el modelo de embeddings; `NEUROCLERK_MODELO` usa otro modelo del proveedor elegido, sin editar `MODELOS`.

## Pruebas

`test_rag.py` comprueba con pytest las funciones puras: `dividir_en_chunks`, `tabla_a_unidades` y `_parecido`. No necesita el modelo, la base, los PDFs ni claves, y tarda menos de un segundo:

```powershell
python -m pytest
```

`probar_rag.py` comprueba con 28 preguntas, de todos los tipos de documento, que la búsqueda encuentra las fuentes correctas y que el modelo las usa. Los casos también están en `casos_de_prueba_NeuroClerk.xlsx`, donde se anotan los resultados de cada ejecución.

```powershell
python .\probar_rag.py --verificar             # revisa que los casos estén bien armados
python .\probar_rag.py                         # solo la búsqueda: rápido, no usa el modelo
python .\probar_rag.py --llm                   # además pide la respuesta al modelo (28 peticiones)
python .\probar_rag.py --buscar litemia FT_Litio.pdf   # busca una palabra en los documentos
python .\probar_rag.py --ranking "PREGUNTA" ARCHIVO     # por qué un fragmento llega o no al modelo
```

Todos estos comandos indexan lo que falte. Solo `--llm` pide la clave del proveedor, porque es el único que llama al modelo.

Opciones de `--llm`:

- `--modelo NOMBRE`: modelo para la prueba. Por defecto usa `gemini-3.5-flash-lite`, porque el plan gratuito de `gemini-3.8-flash` no alcanza para todas las preguntas. Ese valor no depende de `PROVEEDOR`: con `"groq"` u `"ollama"` hay que indicar el modelo con esta opción. El programa normal (`rag.py`) sigue usando el modelo del bloque 0.
- `--pausa SEGUNDOS`: espera entre preguntas (por defecto 12), para no chocar con el límite de peticiones por minuto.

Si el proveedor falla dos veces seguidas, la prueba deja de pedir respuestas y sigue solo con la búsqueda.

Para cada pregunta mide:

- **Tabla:** si aparece la tabla del libro de interacciones que contiene la respuesta (casos 1 a 7).
- **Fuente:** si aparece alguna fuente válida: la tabla, la ficha técnica, el DSM, la CIE-11, la guía o la escala que corresponda.
- **Respuesta:** si la respuesta nombra las palabras clave. En los casos 1, 2, 3 y 7 son fármacos que figuran **solo en la tabla** y en ninguna de las fichas, así que nombrarlos prueba que el modelo usó la tabla.
- **Abstención:** en dos preguntas cuya respuesta no está en los documentos (la dosis de esketamina y la capital de Uruguay), si el sistema se niega a responder en lugar de inventar.
- **Dosis:** en 9 casos aparte, si da la dosis que está en los documentos, o ninguna cuando el fármaco está pero no hay dosis para ese uso (niños, indicación no autorizada). En el caso del zolpidem en niños puede citar la dosis de un estudio, siempre que deje claro que el uso no se recomienda. Desde el 07/11/2026 el prompt prohíbe dar dosis que no estén textuales en un fragmento citado; la regla no cambió los totales.
- **Respaldo:** en cualquier respuesta, si todas sus dosis aparecen en los fragmentos usados. No detecta una dosis que está en los fragmentos, pero corresponde a otro fármaco o a otro uso: las respuestas de los casos de dosis se muestran para revisarlas a mano.

Los avisos del proveedor (límite alcanzado, servidor caído, respuesta incompleta) se cuentan como errores y no como fallos.

Resultados:

| Medida | Línea de base (27/10/2026, 59 documentos) | Medición anterior (05/11/2026, 61 documentos) | Última medición (07/11/2026, WSL, 61 documentos) |
| --- | --- | --- | --- |
| Tabla | 7/7 | 7/7 | 7/7 |
| Fuente | 16/17 | 17/17 | 17/17 |
| Respuesta | 12/17 | 14/17 | 17/17 |
| Abstención | 2/2 | 2/2 | 2/2 |
| Dosis | — | 7/9 | 9/9 |
| Respaldo de dosis | — | 7/7 | 9/9 |

La medición anterior a la última dio 13/17 en respuesta. El caso que se sumó es el 17, porque se agregaron palabras clave a la prueba, no porque mejorara el sistema. En esa medición fallaban los casos 12 (CIE-11), 13 (mhGAP) y 16 (PHQ-9).

La corrida del 07/11/2026, ya en WSL, repitió 14/17 y 2/2. Con el cupo mínimo de 12 candidatos y la regla de dosis máxima, los 9 casos de dosis pasaron a 9/9 y el respaldo a 9/9. Con las continuaciones de página y la regla de puntaje máximo, la corrida oficial del 07/11/2026 pasó a 17/17: no queda ningún caso fallando.

El detalle de cada caso y la evolución entre versiones están en la hoja de cálculo. Después de cada cambio en la extracción o la búsqueda, vuelve a correr las pruebas, anota el resultado en la hoja *Historial* y en el mensaje del commit.

### Notas clínicas (SOAP)

`test_soap.py` comprueba el parser y que el módulo rechace la nube sin permiso. `probar_soap.py` procesa las cinco notas ficticias con Ollama y mide cuatro cosas: que aparezcan las cinco secciones, que estén los datos clave de cada nota, que el Examen del Estado Mental tenga contenido y que el Análisis recoja el diagnóstico que la nota ya menciona.

### Banco de pruebas

`banco.py` compara configuraciones de la búsqueda sobre los mismos 28 casos, guarda cada corrida en `evaluaciones/banco.sqlite` y muestra qué casos mejoran o empeoran; `panel.py` lo publica en `http://localhost:8765`. Sin `--llm` no llama al modelo. El detalle está en [BANCO.md](BANCO.md).

### Evaluación con Ragas

`evaluar_ragas.py` complementa a `probar_rag.py` con dos medidas de [Ragas](https://docs.ragas.io/) que no necesitan una respuesta de referencia:

- **Fidelidad:** qué proporción de lo que afirma la respuesta está respaldada por los fragmentos.
- **Relevancia:** cuánto contesta la respuesta lo que se preguntó. Sirve para comparar casos y versiones, no como valor absoluto: en una prueba, una respuesta sin ninguna relación con la pregunta sacó 0.49. No se mide en los casos en los que lo correcto es no responder.

Ragas corre en un entorno aparte, porque exige LangChain y su propio stack de `openai`, distinto del que usa `rag.py`. La aplicación no lo usa ni lo importa.

```powershell
py -3.12 -m venv .venv-ragas
.venv-ragas\Scripts\python.exe -m pip install -r requirements-ragas.txt

.venv\Scripts\python.exe probar_rag.py --llm --exportar   # guarda las respuestas en evaluaciones/ (28 peticiones)
.venv-ragas\Scripts\python.exe evaluar_ragas.py           # las evalúa (gasta cupo)
.venv-ragas\Scripts\python.exe evaluar_ragas.py --limite 5   # solo 5 evaluaciones nuevas
.venv-ragas\Scripts\python.exe evaluar_ragas.py --resumen    # muestra lo ya evaluado, sin pedir nada
.venv-ragas\Scripts\python.exe evaluar_ragas.py --modelo gemini-3.1-flash-lite   # otro evaluador
.venv-ragas\Scripts\python.exe evaluar_ragas.py --modelo gemini-3.1-flash-lite --resumen   # lo evaluado por él
```

El programa envía como máximo 12 peticiones por minuto al modelo, y ante un límite por minuto espera lo que pide el proveedor. Si se agota el cupo diario, se detiene: cada modelo tiene su propio cupo.

Cada evaluador guarda sus puntajes por separado, porque los de evaluadores distintos no son del todo comparables: el de por defecto en `evaluaciones/ragas.json` y los demás en `evaluaciones/ragas_MODELO.json`. Por eso `--modelo` empieza desde cero con un evaluador nuevo y no sirve para completar lo que otro dejó pendiente.

La fidelidad no se mide cuando la respuesta solo se abstiene (dice que no puede responder y no cita nada), porque no hay afirmaciones que verificar y el puntaje depende de cómo lo interprete cada evaluador. La relevancia sí se mide en esas respuestas, salvo en los casos donde abstenerse es lo correcto, y sirve para señalar abstenciones que no deberían haber ocurrido.

Cada resultado se guarda al obtenerlo: si se agota el cupo, volver a correrlo sigue donde quedó. Una respuesta que cambió se vuelve a evaluar. `evaluaciones/` no se sube a Git porque contiene texto de los PDFs.

Ragas usa un modelo para juzgar, así que sus puntajes pueden variar entre ejecuciones y equivocarse: un puntaje bajo es una señal para revisar la respuesta a mano. No reemplaza el chequeo de dosis de `probar_rag.py`, que es exacto. Como envía preguntas, fragmentos y respuestas a Gemini, no debe usarse con datos de pacientes.

## Documentos de prueba

61 PDFs, unas 3.300 páginas. El detalle de cada uno está en `fuentes.csv`, y cómo conseguirlos, en [DATOS.md](DATOS.md).

| Tipo | Documentos |
| --- | --- |
| Fichas técnicas | 51 psicofármacos y fármacos que interaccionan a menudo, descargados de [CIMA](https://cima.aemps.es) con `descargar_fichas.py` |
| Interacciones | *Introducción a las interacciones farmacológicas* (SEFH) y la tabla de enzimas CYP450 de Flockhart |
| Diagnóstico | DSM-5-TR y la guía de referencia de la CIE-11 (OMS) |
| Guías y formularios | Guía mhGAP (OMS/OPS) y Formulario Terapéutico de Medicamentos (MSP Uruguay) |
| Escalas | PHQ-9, GAD-7, YMRS y PANSS |

Los PDFs no se suben al repositorio por su tamaño y por derechos de autor.

## Problemas encontrados y cómo se resolvieron

### Instalación y entorno

| Problema | Causa | Solución |
| --- | --- | --- |
| "La ejecución de scripts está deshabilitada" | PowerShell bloquea `activate` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Muchos errores de dependencias | PyTorch todavía no estaba disponible para la versión más nueva de Python | Usar Python 3.12 e instalar PyTorch CPU primero |
| `No suitable Python runtime found` | Python 3.12 no estaba instalado | Instalarlo; puede convivir con otras versiones |
| `cryptography>=3.1 is required for AES` | El PDF de interacciones está cifrado | `pip install cryptography` |
| `NameError: name 'paso' is not defined` | Se borró una línea al editar | Usar el archivo completo en lugar de pegar trozos |
| `model 'qwen3:4b' not found` | El modelo no estaba descargado | `ollama pull <modelo>`; verificar con `ollama list` |
| Aviso "unauthenticated requests to the HF Hub" | Se consultaba Hugging Face en cada arranque | Modo offline con el modelo ya descargado |
| El entorno dejó de funcionar al renombrar la carpeta a `NeuroClerk` | En Windows, `.venv` guarda la ruta completa de la carpeta | Borrar `.venv`, recrearlo e instalar desde el lock; volver a elegir el intérprete en VS Code |
| `ModuleNotFoundError: No module named 'pdfplumber'` | El lock se generó antes de instalar pdfplumber | `pip install -r requirements.txt` y regenerar el lock |
| Los PDFs quedaron públicos en GitHub | Se subieron antes de agregar `datos/` al `.gitignore`, que no deja de seguir archivos ya subidos | Repositorio privado, `git filter-repo` para borrarlos del historial y repositorio nuevo para eliminar los commits huérfanos |
| Indexar tardaba horas | Embeddings en CPU sobre miles de páginas | Indexar en Colab con GPU; huella por contenido para reutilizar la base en la PC |
| "Quitando Gu├нa_mhGAP-spa.pdf" al volver de Colab | La tilde se desconfiguró al comprimir en Windows y descomprimir en Linux | Nombres de archivo sin tildes ni eñes |

### Calidad de la búsqueda

| Problema | Causa | Solución |
| --- | --- | --- |
| El DSM-5-TR acaparaba todos los resultados | Es casi tres veces más grande que el resto | Traer candidatos de cada archivo por separado |
| Se ignoraba el final de cada fragmento | `MiniLM-L12` lee solo ~128 tokens (~80 palabras) | Cambiar a `multilingual-e5-base` (~300 palabras), con los prefijos `passage:` y `query:` |
| Fragmentos sin relación con la pregunta | Siempre se traía la misma cantidad de cada archivo | Filtro por margen de similitud respecto al mejor |
| Nombrar la fuente en la pregunta empeoraba la búsqueda | "según el DSM-5" atraía páginas que repiten "DSM-5" | Preguntar sin nombrar las fuentes |
| Palabras cortadas ("tem- poral") | OCR del DSM-5-TR | Expresión regular que une las palabras al cargar |
| Las tablas nunca se encontraban | pypdf las aplana en una lista de nombres sin título, partida en varios fragmentos | Extraerlas con `pdfplumber` como fragmentos propios con el título delante |
| Las tablas largas con columnas no se encontraban | Se partían en trozos que mezclaban filas, y se juntaban columnas como *Sustratos* e *Inhibidores* | Un fragmento por fila, uno por categoría, y título heredado en las continuaciones |
| Los libros grandes perdían frente a las fichas | Cada archivo aportaba 3 candidatos, tuviera 10 páginas o 367 | Cupo proporcional al tamaño: de 3 a 15 candidatos |
| El dato estaba en la página siguiente | Las tablas y frases se cortan al cambiar de página y la siguiente no entraba al contexto | Se suman hasta 2 fragmentos de la página siguiente a los tres mejores |

### Calidad de la respuesta

| Problema | Causa | Solución |
| --- | --- | --- |
| `llama3.2` fallaba la mayoría de las preguntas | Modelo de 3B, débil en español | Cambiar a `qwen3:8b` |
| Respuestas lentas con texto en inglés antes de `</think>` | `qwen3:4b` es la variante que siempre razona | Usar `qwen3:8b` con `think=False` y recortar lo anterior a `</think>` |
| Datos inventados o mezclados (por ejemplo, "hiperkinesia") | Prompt poco estricto y temperatura por defecto | Reglas explícitas, cita después de cada afirmación y `temperature=0.1` |
| Usaba una sola fuente aunque recibía varias | El modelo copiaba el fragmento más fácil | Regla "si varios fragmentos aportan datos distintos, inclúyelos todos" |
| Parecía colgado en algunas preguntas | Copiaba listas de más de 100 fármacos y no mostraba nada hasta terminar | Streaming con un punto por trozo y tope de tokens |
| Respuestas lentas con el modelo local | `qwen3:8b` en CPU | Modelo en la nube (Gemini o Groq) |
| `Error code: 503` | Servidores de Gemini saturados | Reintentos automáticos con espera de 2, 4 y 8 segundos |
| Las pruebas se quedaban sin cupo de Gemini | `gemini-3.8-flash` no alcanza para 19 preguntas seguidas en el plan gratuito, y hay límite por minuto | Las pruebas usan `gemini-3.5-flash-lite` por defecto, con pausa entre preguntas y reintentos ante el error 429 |
| Recalcular los embeddings en cada ejecución | Los vectores vivían solo en memoria | ChromaDB guardado en disco |

## Resultados de las pruebas

Pregunta de referencia: *"¿Qué es el síndrome neuroléptico maligno, cuáles son sus síntomas y qué fármacos pueden causarlo?"*

| Etapa | Búsqueda | Respuesta |
| --- | --- | --- |
| `llama3.2` + MiniLM | No encontraba la descripción del DSM-5-TR | La mayoría de las preguntas, mal |
| `qwen3:8b` + e5 | Encontraba DSM-5-TR págs. 759–760 | 5 errores (síntomas invertidos, fármacos mal clasificados) |
| + prompt con citas y temperatura baja | Igual | 1 error (mezclaba dos síndromes) |
| + filtro por similitud | 6–7 fragmentos, todos relevantes | Sin errores, pero sin usar el DSM-5-TR |
| + regla "inclúyelos todos" | Igual | Combina 3 fuentes; 1 cita con la página equivocada |
| + tablas con pdfplumber | La Tabla 1 aparece primera (0.909) | Incluye fármacos que solo están en la tabla |
| + 59 documentos y Gemini | Tabla 1 primera, más DSM-5-TR y fichas | Lista completa de la tabla, DSM-5-TR y una ficha, sin errores y en segundos |

## Limitaciones conocidas

- **Hay que revisar las fuentes:** aunque los resultados son buenos, el modelo puede citar una página equivocada o mezclar conceptos parecidos.
- **Límites del plan gratuito:** los proveedores en la nube limitan las peticiones por día o por minuto.
- **PDFs escaneados sin texto:** si `extract_text()` devuelve vacío, hace falta OCR, que todavía no está implementado.
- **Documentos en inglés:** con preguntas en español, sus fragmentos suelen quedar bajo el umbral de similitud y no llegan al modelo.
- **Números de página:** son los del PDF, no los impresos en el libro.
- **Preguntas comparativas** ("¿cuáles de estos cuatro fármacos...?") son difíciles para un RAG simple, porque la búsqueda trae fragmentos parecidos a la pregunta y no necesariamente el dato de cada documento.
