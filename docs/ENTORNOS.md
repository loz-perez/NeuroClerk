# Entorno híbrido: Windows para editar, WSL para ejecutar

*Actualizado el 7 de noviembre de 2026.*

Este documento explica cómo está montado el proyecto después de la migración: el código vive en WSL, VS Code se usa desde Windows con *Remote - WSL*, y la copia de `C:\Users\loren\dev\NeuroClerk` queda como respaldo congelado.

## Dónde está cada cosa

| Pieza | Ubicación |
| --- | --- |
| Repositorio canónico | `~/neuroclerk` en WSL (ext4) |
| Respaldo congelado | `C:\Users\loren\dev\NeuroClerk` (no se edita) |
| Entorno principal | `~/neuroclerk/.venv` (Python 3.12) |
| Entorno de Ragas | `~/neuroclerk/.venv-ragas` |
| PDFs | `~/neuroclerk/datos` (61 archivos) |
| Base vectorial | `~/neuroclerk/chroma_db` (13.864 fragmentos) |
| Claves | `~/.config/neuroclerk/env` (fuera del repositorio) |
| Ollama | `~/.local/bin/ollama`, servicio de usuario, modelo `gemma3:4b` |
| Panel del banco | `~/neuroclerk/panel.py`, en `http://localhost:8765` |

## Abrir VS Code

La ventana diaria se abre **desde WSL**, para que el servidor de VS Code y el intérprete sean Linux:

```powershell
# Desde Windows
code --remote wsl+Ubuntu /home/justperez/neuroclerk
```

o, dentro de WSL:

```bash
cd ~/neuroclerk && code .
```

La primera vez, VS Code instala el servidor en `~/.vscode-server`. El intérprete queda en `${workspaceFolder}/.venv/bin/python` por `.vscode/settings.json`; si no se selecciona solo, usar **Python: Select Interpreter** y elegir `.venv/bin/python`.

Las tareas de `.vscode/tasks.json` ya están armadas: *Indexar PDFs*, *Consultar*, *Pytest*, *Verificar casos*, *Probar búsqueda*, *Probar respuestas*, *Banco*, *Panel* y *Ragas*.

### La segunda ventana (Windows)

Una ventana de VS Code corre en un solo entorno: no se puede mezclar una carpeta local con una de WSL. Para tareas de Windows (Excel, Word, extensiones que no existen en Linux) hay dos opciones:

1. Abrir el respaldo `C:\Users\loren\dev\NeuroClerk` en una ventana local. Es una copia congelada: no editar ahí para no bifurcar Git.
2. Abrir `\\wsl.localhost\Ubuntu\home\justperez\neuroclerk` en una ventana local. Sirve para mirar, pero el Python sería el de Windows y el acceso a archivos va por 9p, mucho más lento.

Regla práctica: **una sola copia editable, la de WSL**. La planilla se abre desde Excel con `\\wsl.localhost\Ubuntu\home\justperez\neuroclerk\casos_de_prueba_NeuroClerk.xlsx`.

## Plugins de DSH

Los plugins del entorno están documentados en [PLUGINS.md](PLUGINS.md): Market, Session Search, `dsh-files` y el hub. Viven en `~/.dsh/profiles/desktop`, no en este repositorio.

Los que se usan a diario:

- **`read_document`**: leer páginas puntuales de `datos/` sin escribir scripts. Probado con `CIE-11.pdf`, página 504.
- **`session_search`**: recuperar decisiones de sesiones anteriores del proyecto.
- **`attachment_list` / `export_attachment`**: traer un archivo subido al workspace.

## Claves y variables

Ya están en `~/.config/neuroclerk/env` (permisos 600) y `~/.bashrc` las carga en cada terminal. Para cambiarlas, editar ese archivo:

```bash
nano ~/.config/neuroclerk/env
```

No van al repositorio. WSL no hereda las variables de Windows, así que si se regeneran las claves hay que actualizar ese archivo.

## Ollama

Se instaló a nivel de usuario porque la cuenta no tiene `sudo` sin contraseña. El servicio de systemd de usuario queda en `~/.config/systemd/user/ollama.service` y escucha solo en `127.0.0.1:11434`.

```bash
systemctl --user status ollama
ollama list
ollama ps          # muestra si corre en GPU o CPU
```

Con 4 GB de VRAM y 7,6 GB de RAM, el modelo elegido es `gemma3:4b` (unos 3,3 GB). `qwen3:8b` no entra completo: se repartiría con la CPU y sería muy lento. Para usar otro modelo sin editar el código:

```bash
export NEUROCLERK_MODELO="gemma3:4b"
```

`PROVEEDOR = "ollama"` sigue siendo la única opción para datos de pacientes. Gemini y Groq reciben la pregunta y los fragmentos.

## Comandos del día a día

Todo se corre desde la terminal de WSL (la que abre VS Code Remote-WSL):

```bash
cd ~/neuroclerk
.venv/bin/python rag.py
.venv/bin/python probar_rag.py
.venv/bin/python -m pytest
.venv/bin/python banco.py correr
.venv/bin/python panel.py
.venv-ragas/bin/python evaluar_ragas.py --resumen
```

`rag.py` indexa lo que falte. La primera indexación descarga el modelo de embeddings (~1,1 GB) y tarda; después arranca en segundos.

## Respaldos y Git

- Git vive en `~/neuroclerk/.git`; se usa `core.autocrlf=input` para que los archivos copiados desde Windows no aparezcan modificados.
- El respaldo de Windows es una foto del 7/11/2026. No se actualiza solo: si se quiere refrescar, se copia desde WSL hacia Windows, nunca al revés mientras WSL sea la copia canónica.
- `datos/` y `chroma_db/` no están en Git: el respaldo de los PDFs es la carpeta de Windows y la base se puede reconstruir indexando de nuevo.
- WSL apagado deja los archivos fuera de alcance desde Windows. No es un problema de datos: es que la máquina virtual está detenida.

## Validación del 7/11/2026

| Prueba | Resultado |
| --- | --- |
| `pytest` | 134 pasan, 0 xfail |
| `probar_rag.py` (búsqueda) | tabla 7/7, fuente 17/17, dosis 9/9 |
| `probar_rag.py --llm` (28 casos) | 16/17 respuestas (caso 13 inestable), 2/2 abstenciones, 9/9 dosis, 9/9 respaldo |
| Regla de dosis y cupo 12 | 9/9 dosis y 9/9 respaldo; 14/17 y 2/2 sin cambios |
| Reindexación GPU (61 PDFs) | 11,2 min y 13.864 fragmentos |
| Consulta de combinación (fluoxetina + tramadol) | aviso con los dos fármacos y respuesta con citas |
| SOAP (5 notas ficticias) | 5/5 secciones, datos, examen mental y análisis con `gemma3:4b` |
| `banco.py correr` | corrida #6: tabla 7/7, fuente 17/17, dosis 9/9, contexto 23/23 |
| Ruff | `uvx ruff check .` sin avisos |
| Ollama `gemma3:4b` | consulta de litio en 35 s, con citas; 45/55 % CPU/GPU |
| Gemini | la misma consulta en 17 s, con citas |

Las extensiones de Python, Pylance y debugpy ya están instaladas del lado de WSL.

## Reindexar con GPU en WSL

El 07/11/2026 se instaló `torch 2.14.1+cu126` en `.venv` y se reconstruyó `chroma_db` desde cero. La base CPU anterior quedó en `~/chroma_db_cpu_backup_20261107`.

```bash
cd ~/neuroclerk
mv chroma_db ~/chroma_db_cpu_backup_20261107   # solo la primera vez
HF_HUB_OFFLINE=1 SOLO_INDEXAR=1 .venv/bin/python rag.py
```

| Medición | Windows CPU | WSL CPU | WSL GPU |
| --- | --- | --- | --- |
| Muestra de 109 fragmentos | 15,05 s (7,24 frag/s) | 21,91 s (4,97 frag/s) | 2,39 s (45,7 frag/s) |
| Embeddings de 13.864 fragmentos | ~32-38 min (estimado) | ~55 min (estimado) | ~6 min |
| Parseo de los 61 PDFs | — | 4,9 min | 4,9 min |
| Reindexación completa | ~37-44 min (estimado) | ~60 min (estimado) | **669 s (11,2 min), medido** |

La muestra se armó con dos fragmentos por documento (texto y tabla) y se midió con el mismo lote en los tres entornos. El parseo es el mismo en CPU y GPU; por eso la ganancia de extremo a extremo (3,3-3,8×) es menor que la de los embeddings (6,3×).

El lock sigue con `torch==2.14.1+cpu`: esta máquina quedó con CUDA para reindexar. Para volver al entorno reproducible del lock, reinstalar desde `requirements-lock.txt`; para conservar GPU, anotar el índice `cu126` al reinstalar.

## Problemas frecuentes

| Síntoma | Causa | Solución |
| --- | --- | --- |
| `code` no abre la carpeta | Se ejecutó desde Windows sin `--remote` | `code --remote wsl+Ubuntu /home/justperez/neuroclerk` |
| No encuentra el intérprete | Se abrió la ventana local, no la de WSL | Abrir la ventana Remote-WSL y elegir `.venv/bin/python` |
| `localhost:8765` no responde | El panel no está corriendo o WSL está apagado | `systemctl --user status ollama` no aplica: el panel se lanza con la tarea *Panel* |
| Ollama no responde | Servicio caído | `systemctl --user restart ollama` |
| El modelo va lento | `gemma3:4b` se está repartiendo entre GPU y CPU | Revisar `ollama ps`; cerrar otras aplicaciones que usen VRAM |
| Los archivos se ven raros desde Windows | Se editaron por 9p en lugar de Remote-WSL | Editar solo desde la ventana Remote-WSL |
