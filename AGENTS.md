# AGENTS.md — guía para DeepSeek Harness (DSH)

*Actualizado el 7 de noviembre de 2026.*

Este archivo es para el agente DSH que trabaja en NeuroClerk. `CLAUDE.md` sigue siendo la guía de Claude Code; las reglas clínicas, de privacidad y de datos son las mismas. Si hay conflicto, mandan `CLAUDE.md` y `docs/ENTORNOS.md`.

## Entorno

- El repositorio canónico vive en **WSL**: `~/neuroclerk` (Ubuntu 26.04, Python 3.12).
- `C:\Users\loren\dev\NeuroClerk` es un **respaldo congelado**; no se edita ni se ejecuta desde ahí.
- Todo se ejecuta en WSL con `.venv/bin/python`; VS Code se usa desde Windows con *Remote - WSL*.
- La GPU es una RTX 3050 de 4 GB; `torch 2.14.1+cu126` está instalado en `.venv`.
- Las claves están en `~/.config/neuroclerk/env`; no van al repositorio.
- WSL **no tiene credenciales de GitHub**. Para publicar, generar un bundle en WSL, hacer `fetch` y `push` desde Windows, que sí tiene el credential manager.

## Comandos

```bash
cd ~/neuroclerk

.venv/bin/python rag.py                 # consulta interactiva; indexa lo que falte
.venv/bin/python -m pytest              # unitarias + arquitectura
uvx ruff check .                       # estilo, imports y bugs simples
.venv/bin/python probar_rag.py --verificar
.venv/bin/python probar_rag.py          # búsqueda, 28 casos
.venv/bin/python probar_rag.py --llm    # respuestas, gasta cupo
.venv/bin/python banco.py correr
.venv/bin/python panel.py               # http://localhost:8765
.venv/bin/python soap.py pruebas/nota_depresion.txt
.venv/bin/python probar_soap.py
.venv-ragas/bin/python evaluar_ragas.py --resumen
```

## Estado actual

- Rama canónica: `feature/entorno-wsl`.
- Base: 13.864 fragmentos de 61 PDFs; reindexación completa en GPU en ~11,4 min.
- `pytest`: 134 pasan, 0 xfail.
- Búsqueda: 7/7 tablas, 17/17 fuentes, 9/9 fuentes de dosis.
- Respuestas: 16/17 en la corrida de referencia; la última dio 15/17 porque el caso 12 se abstuvo una vez (pasó 5/5 al repetirlo). El caso 13 (mhGAP) sigue inestable con `gemini-3.5-flash-lite`.
- Dosis: 9/9; respaldo 9/9.
- SOAP: 5/5 notas con secciones, datos, examen mental y análisis.
- Fases: 1 ✅, 2 🔵 casi completa por el caso 13, 3 ✅, 4 ⚪ pendiente.
- Ragas: pendiente de recalcular con las respuestas nuevas.
- Ruff: `uvx ruff check .` pasa; reglas en `docs/ARQUITECTURA.md`.
- El registro corto de pendientes está en `TODO.md`.

## Arquitectura

- `rag.py`: bloques 0 configuración, 1 carga de PDFs/tablas, 2 división, 3 indexación en ChromaDB, 4 `recuperar()`, 5 `responder()`/`generar()`, 6 bucle interactivo.
- La búsqueda es por archivo, con cupo de 12 a 15 candidatos, margen de similitud, tope por página, descarte de duplicados y hasta 2 continuaciones de la página siguiente.
- `soap.py` es independiente del RAG: estructura notas ficticias de `pruebas/` en SOAP + Examen del Estado Mental y exige Ollama por defecto.
- `probar_rag.py` mide búsqueda y respuestas; `test_rag.py`, `test_banco.py` y `test_soap.py` son pruebas puras.
- El RAG es a mano: **no introducir LangChain ni LlamaIndex** salvo que se pida.

## Reglas de trabajo

1. Leer el archivo antes de editarlo. Usar `read`/`edit`/`write`, no `cat`.
2. Después de cambiar extracción o búsqueda: correr `pytest` y `probar_rag.py`, anotar el resultado en la hoja *Historial* de `casos_de_prueba_NeuroClerk.xlsx` y en el mensaje del commit.
3. No inventar dosis ni datos clínicos. Las notas de pacientes nunca van a Gemini/Groq: solo a Ollama.
4. `datos/` es la fuente de verdad y no se sube a Git. Las notas ficticias van en `pruebas/`.
5. `evaluaciones/` contiene texto de PDFs y está fuera de Git.
6. Mantener los commits en español y con el resultado de las pruebas.
7. Antes de borrar algo del proyecto, comprobar que no lo usan los tests, la documentación ni las tareas de VS Code.
8. **Modelo fijo de pruebas:** usar siempre `gemini-3.5-flash-lite` (`MODELO_PRUEBAS`). No mezclar modelos en una misma tanda. Si se agota el cupo, esperar el reinicio; si se evalúa Gemini 3.1, correr la tanda completa con ese modelo y dejarlo anotado.

## Herramientas de DSH

- **`read_document`**: leer páginas puntuales de `datos/*.pdf` sin scripts. Sirve para verificar CIE-11 p. 504, mhGAP p. 37 o PHQ-9 p. 2.
- **`session_search`**: recuperar decisiones de sesiones anteriores del proyecto.
- **`attachment_list` / `export_attachment`**: mover archivos subidos al workspace.
- **Jobs en segundo plano**: usarlos para reindexaciones y suites largas; no bloquear la sesión.
- Los plugins viven en `~/.dsh/profiles/desktop`, no en el repositorio. Ver `docs/PLUGINS.md`.

## Qué no tocar

- `datos/`, `chroma_db/`, `evaluaciones/` y las claves: son locales y no se suben.
- Los respaldos de base en `~/`: no borrar sin comprobar cuál es el actual.
- `CLAUDE.md`: es la guía de Claude Code; si se deja de usar esa herramienta, se puede archivar, pero no borrar a ciegas.
