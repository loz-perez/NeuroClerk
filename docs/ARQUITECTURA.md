# Arquitectura y reglas de código

*Actualizado el 7 de noviembre de 2026.*

Este documento fija las reglas para que el RAG siga siendo entendible y para que las pruebas sigan corriendo sin modelo, base ni PDFs.

## Capas

```text
                 rag.py  (núcleo: PDFs, Chroma, búsqueda, prompt)
                    ▲
        ┌───────────┼─────────────┐
   soap.py    probar_rag.py    banco.py
   (SOAP)     (medición)       (benchmark) ──► panel.py
                    │
              evaluar_ragas.py  (evaluación aparte, solo JSON)
```

- **Núcleo:** `rag.py`. No importa ningún otro módulo del proyecto.
- **Impulsores/CLI:** `soap.py`, `probar_rag.py`, `banco.py`, `panel.py`, `probar_soap.py`.
- **Evaluación aparte:** `evaluar_ragas.py`. No importa `rag.py`; lee y escribe JSON.
- **Pruebas:** `test_rag.py`, `test_banco.py`, `test_soap.py`, `test_arquitectura.py`.

## Dependencias permitidas

| Módulo | Puede importar del proyecto |
| --- | --- |
| `rag.py` | ninguno |
| `soap.py` | `rag` |
| `probar_rag.py` | `rag` |
| `banco.py` | `rag`, `probar_rag` |
| `panel.py` | `banco` |
| `probar_soap.py` | `rag`, `soap` |
| `probar_tablas.py` | `rag` |
| `evaluar_ragas.py` | ninguno |
| `descargar_fichas.py`, `revisar_datos.py` | ninguno |

Cualquier import nuevo entre módulos debe agregarse a esta tabla y a `test_arquitectura.py`. Si un módulo necesita otra dependencia, primero se discute la dirección; no se agrega un import cruzado sin actualizar las reglas.

## Reglas

1. **El núcleo no depende de la interfaz.** `rag.py` no importa `soap`, `banco`, `panel` ni `probar_rag`.
2. **La evaluación no contamina el RAG.** `evaluar_ragas.py` corre en `.venv-ragas`, no importa `rag.py` y se comunica solo por `evaluaciones/respuestas.json`.
3. **La base se toca solo desde `rag.py`.** Ningún otro módulo abre ChromaDB ni calcula embeddings; usan `rag.preparar()` y `rag.recuperar()`.
4. **La lógica pura no imprime.** `dividir_en_chunks`, `tabla_a_unidades`, `unir_tablas_partidas`, `_parecido`, `paginas_siguientes` y `farmacos_mencionados` devuelven datos; la salida queda en las funciones de borde.
5. **La configuración vive en el bloque 0 de `rag.py`.** No se agregan números mágicos ni rutas sueltas en medio de las funciones.
6. **El estado global solo lo cambia `preparar()`.** `modelo_emb`, `coleccion`, `archivos` y `CUPO` quedan vacíos hasta esa llamada; `recuperar()` y `responder()` no los reasignan.
7. **Los errores del proveedor se devuelven como texto que empieza con `[`.** Es el contrato que usan `probar_rag.py` y `banco.py` para contar errores en vez de fallos.
8. **Los datos clínicos no salen a la nube.** `soap.py` exige Ollama salvo `permitir_nube=True`; las notas de pacientes nunca van a Gemini ni Groq.
9. **Cada cambio de extracción o búsqueda se mide.** `pytest`, `probar_rag.py`, *Historial* y mensaje de commit.
10. **Sin frameworks.** No LangChain ni LlamaIndex en el núcleo; Ragas queda aislado en su entorno.
11. **Nombres y mensajes en español.** Las funciones y variables se nombran en español; los comentarios explican el porqué, no el qué.
12. **Sin `except Exception` nuevos sin justificación.** Se admiten en los bordes de PDFs, Chroma o proveedores, con un comentario de por qué no se puede ser más específico.

## Código limpio

- Funciones de una sola responsabilidad; si una función pasa de ~80 líneas, dividir antes de agregar lógica.
- Docstring en funciones públicas y en las que no son obvias.
- Sin estado global nuevo; si hace falta, encapsular en un objeto o pasarlo como parámetro.
- Sin duplicar la lógica de evaluación entre `probar_rag.py` y `banco.py`; si se toca una, revisar la otra.
- Los `print` de diagnóstico van en las CLIs (`probar_rag`, `banco`, `panel`, `soap`), no en las funciones puras.
- Las líneas largas se permiten en prompts y mensajes de una sola cadena; el resto se mantiene en 120 columnas.

## Deuda conocida

- `rag.py` usa estado global por diseño; hay que respetar el contrato de `preparar()`.
- `responder()` y `generar()` son largas porque contienen el prompt y los reintentos; no crecer más.
- `probar_rag.py` y `banco.py` comparten criterios de medición que hoy están duplicados.

## Cómo se verifica

```bash
cd ~/neuroclerk
uvx ruff check .                 # estilo, imports, bugs simples
.venv/bin/python -m pytest -q    # unitarias + arquitectura
```

`test_arquitectura.py` falla si `rag.py` importa un módulo del proyecto, si `evaluar_ragas.py` importa el RAG o si alguien introduce un framework en el núcleo.
