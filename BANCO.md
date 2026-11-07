# Banco de pruebas

Compara configuraciones de la búsqueda con los 28 casos de `probar_rag.py`, guarda cada corrida y muestra qué casos mejoran o empeoran. Corre en la misma copia canónica del proyecto en WSL (`~/neuroclerk`) y solo escribe en `evaluaciones/`; ya no hay una copia aparte ni un paso de despliegue.

## Medir

Desde la terminal de VS Code Remote-WSL:

```bash
cd ~/neuroclerk
.venv/bin/python banco.py correr                                    # la configuración de rag.py
.venv/bin/python banco.py correr --set margen=0.03,0.05 --set max_fragmentos=12,20   # combinaciones
.venv/bin/python banco.py correr --llm --pausa 15                   # además pide las respuestas (gasta cupo)
.venv/bin/python banco.py listar
.venv/bin/python banco.py comparar 1 4
```

Se pueden variar `margen`, `max_fragmentos`, `max_por_pagina`, `similitud_duplicado`, `k_min`, `k_max` y `fragmentos_por_candidato`. El chunking y los embeddings se cambian en `rag.py`: eso crea otra colección, y `correr` no la indexa sin `--indexar`, porque en CPU tarda mucho.

`--llm` solo acepta una configuración y necesita la clave del proveedor en WSL. Envía preguntas y fragmentos a la nube: nunca usarlo con datos de pacientes.

## Panel

`http://localhost:8765`, con la tarea *Panel* de VS Code o `.venv/bin/python panel.py`. Solo escucha en `127.0.0.1`, lee `evaluaciones/banco.sqlite` y no necesita el modelo ni la base vectorial. Si WSL está apagado, no responde.

## Qué mide

| Medida | Pregunta | Límite |
| --- | --- | --- |
| Tabla | ¿Llegó la tabla esperada? | La misma medida de `probar_rag.py` |
| Fuente | ¿Llegó algún fragmento del documento correcto? | Aprueba con cualquier página |
| Contexto | ¿Alguna palabra clave del caso está en los fragmentos? | Una clave corta puede aprobar por casualidad: el "27" del PHQ-9 aprueba aunque la página 2 no llegue |
| Respuesta, Abstención, Dosis, Respaldo | Los criterios de `probar_rag.py` | Solo con `--llm` |

Contexto no reemplaza las respuestas: que el dato llegue no garantiza que el modelo lo use. Sirve para descartar configuraciones sin gastar cupo.

Los resultados quedan en `evaluaciones/banco.sqlite`, fuera de Git y sin el texto de los fragmentos. Con `--llm` también guarda las respuestas del modelo. La planilla *Historial* sigue siendo el registro oficial: el banco no la actualiza.
