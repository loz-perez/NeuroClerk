# TODO — NeuroClerk

*Actualizado el 7 de noviembre de 2026.*

Registro corto de tareas pendientes. El contexto de cada fase está en `HOJA_DE_RUTA.md`; este archivo solo lleva el seguimiento.

## Prioridad alta

- [ ] **Estabilizar el caso 13 (mhGAP).** La tabla de antidepresivos de la pág. 37 está en el contexto, pero `gemini-3.5-flash-lite` a veces responde que no hay fármacos. Criterio: 17/17 en dos corridas seguidas.
- [ ] **Recalcular Ragas.** Exportar respuestas nuevas con `probar_rag.py --llm --exportar` y correr `.venv-ragas/bin/python evaluar_ragas.py`. Criterio: `ragas.json` actualizado y resumen anotado.
- [ ] **Fase 4: interfaz Streamlit.** Dos pestañas (nota SOAP y consulta farmacológica), fragmentos visibles, selector de proveedor y aviso de uso obligatorio. Criterio: flujo completo con Ollama y con Gemini.

## Calidad y fase 2

- [ ] **Revisar documentos en inglés.** Con preguntas en español casi no llegan al contexto; decidir si se traducen, se descartan o se indexan aparte.
- [ ] **Vigilar la abstención ocasional del caso 12.** La pág. 504 está en el contexto y el caso pasó 5/5 al repetirlo; en una corrida el modelo dijo que no alcanzaba. No reproducido.
- [ ] **Revisar el límite por página.** En la tabla de inhibidores del CYP2D6, la continuación queda afuera; evaluar si `MAX_POR_PAGINA=2` corta listas largas.
- [ ] **Decidir qué hacer con `probar_tablas.py`.** Sus 7 casos ya están en `probar_rag.py`; si se elimina, actualizar README y CLAUDE.
- [ ] **Mantener el Historial.** Cada corrida con `--llm` debe quedar en la hoja *Historial* y en el mensaje del commit.

## Entorno e infraestructura

- [ ] **Resolver el desfase de dependencias.** `requirements-lock.txt` fija `torch+cpu`, pero el `.venv` de WSL tiene `torch+cu126` para reindexar. Decidir si se crea un `requirements-gpu.txt` o se documenta como ajuste local.
- [ ] **Decidir el respaldo CPU de 300 MB.** `~/chroma_db_cpu_backup_20261107` ya no es la base activa; conservarlo solo si se van a comparar tiempos.
- [ ] **Revisar `.claude/`.** Solo contiene `scheduled_tasks.lock`; borrarlo si no se usan tareas programadas de Claude Code.
- [ ] **Revisar el worktree de prueba.** `/home/justperez/neuroclerk-otra-rama` se puede eliminar con `git worktree remove` si ya no se usa.
- [ ] **Mantener `AGENTS.md` y `CLAUDE.md` sincronizados.** Si cambia el entorno o el estado, actualizar ambos; `AGENTS.md` es la guía de DSH y `CLAUDE.md` la de Claude Code.
- [ ] **Evaluar un proveedor local para DSH.** `dsh-llm-ollama` no declara compatibilidad con DSH 0.2.2; probarlo solo en una copia del perfil, nunca en el principal.

## Largo plazo

- [ ] **OCR** para PDFs escaneados, cuando se agregue ese tipo de documento.
- [ ] **Guías de GuíaSalud y NICE**, si aportan respuestas que hoy no están cubiertas.
- [ ] **Comparar el RAG propio con un framework** (LlamaIndex o LangChain), solo como evaluación, sin reemplazar el código actual.
- [ ] **Revisar licencias** de YMRS y PANSS antes de cualquier uso compartido.
- [ ] **Evaluar CI** para correr `pytest` y `ruff check` en cada push; hoy no hay CI.

## Estado de partida

- 134 tests pasan, 0 xfail.
- Búsqueda: 7/7 tablas, 17/17 fuentes, 9/9 fuentes de dosis.
- Respuestas: 16/17; el único fallo es el caso 13.
- Dosis: 9/9; respaldo 9/9.
- SOAP: 5/5.
- Base: 13.864 fragmentos de 61 PDFs; reindexación GPU en ~11,4 min.
