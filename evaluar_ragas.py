# evaluar_ragas.py — mide con Ragas las respuestas exportadas por probar_rag.py
#
# Corre en su propio entorno (.venv-ragas), porque Ragas exige LangChain y una versión de openai
# más vieja que la de rag.py. Por eso no importa rag.py: solo lee el JSON exportado.
#
# Uso:
#   .venv\Scripts\python.exe probar_rag.py --llm --exportar      -> genera las respuestas
#   .venv-ragas\Scripts\python.exe evaluar_ragas.py              -> las evalúa
#   .venv-ragas\Scripts\python.exe evaluar_ragas.py --limite 5   -> solo 5 evaluaciones nuevas
#   .venv-ragas\Scripts\python.exe evaluar_ragas.py --pausa 15   -> espera entre evaluaciones
#   .venv-ragas\Scripts\python.exe evaluar_ragas.py --resumen    -> muestra lo ya evaluado
#
# Cada resultado se guarda al obtenerlo: si se agota el cupo, volver a correrlo sigue donde quedó.
#
# Mide dos cosas, ninguna necesita una respuesta de referencia:
#   fidelidad    ¿lo que afirma la respuesta está respaldado por los fragmentos? (2 peticiones)
#   relevancia   ¿la respuesta contesta lo que se preguntó? (1 petición y embeddings)
# No reemplaza el chequeo de dosis de probar_rag.py, que es exacto y no depende de un modelo.
#
# Envía preguntas, fragmentos y respuestas a Gemini: nunca usarlo con datos de pacientes.

import asyncio
import json
import math
import os
import sys
from pathlib import Path

ARCHIVO_RESPUESTAS = Path("evaluaciones/respuestas.json")
ARCHIVO_RESULTADOS = Path("evaluaciones/ragas.json")

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODELO_EVALUADOR = "gemini-3.5-flash-lite"
MODELO_EMBEDDINGS = "gemini-embedding-001"
MAX_TOKENS_EVALUADOR = 4000   # la lista de afirmaciones de una respuesta larga no debe cortarse
PREGUNTAS_RELEVANCIA = 1      # Ragas usa 3 por defecto: con 1 se gasta menos cupo, pero varía más
PAUSA = 12                    # segundos entre evaluaciones, por el límite de peticiones por minuto

# En estos casos lo correcto es no responder, y la relevancia castiga justamente eso
TIPOS_SIN_RELEVANCIA = ("abstencion", "dosis_ausente")


def metricas_de(caso):
    """Las métricas que tienen sentido para un tipo de caso."""
    if caso["tipo"] in TIPOS_SIN_RELEVANCIA:
        return ["fidelidad"]
    return ["fidelidad", "relevancia"]


def contextos_de(caso):
    """Los fragmentos con el mismo formato que recibe el modelo, para que sus citas tengan respaldo."""
    return [f"[{f['archivo']}, página {f['pagina']}] {f['texto']}" for f in caso["fragmentos"]]


def pendientes(casos, resultados):
    """Las evaluaciones que faltan: una respuesta que cambió se vuelve a evaluar."""
    faltan = []
    for caso in casos:
        previo = resultados.get(caso["pregunta"], {})
        for metrica in metricas_de(caso):
            if previo.get("respuesta") != caso["respuesta"] or metrica not in previo.get("metricas", {}):
                faltan.append((caso, metrica))
    return faltan


def resumir(casos, resultados):
    """Promedio de cada métrica por tipo de caso. Solo cuenta las respuestas exportadas ahora."""
    grupos = {}
    for caso in casos:
        previo = resultados.get(caso["pregunta"], {})
        if previo.get("respuesta") != caso["respuesta"]:
            continue
        for metrica, valor in previo["metricas"].items():
            grupos.setdefault((caso["tipo"], metrica), []).append(valor)
    resumen = {}
    for clave, valores in grupos.items():
        validos = [v for v in valores if v is not None]
        resumen[clave] = {"promedio": sum(validos) / len(validos) if validos else None,
                          "casos": len(validos), "sin_valor": len(valores) - len(validos)}
    return resumen


def guardar(resultados):
    ARCHIVO_RESULTADOS.parent.mkdir(exist_ok=True)
    temporal = ARCHIVO_RESULTADOS.with_suffix(".tmp")
    temporal.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(ARCHIVO_RESULTADOS)   # si algo se corta al escribir, el archivo anterior sigue entero


def mostrar_resumen(casos, resultados):
    print("\n" + "=" * 60)
    for (tipo, metrica), r in sorted(resumir(casos, resultados).items()):
        promedio = "sin datos" if r["promedio"] is None else f"{r['promedio']:.2f}"
        extra = f", {r['sin_valor']} sin valor" if r["sin_valor"] else ""
        print(f"{tipo:<14} {metrica:<11} {promedio:>9}  ({r['casos']} casos{extra})")

    valores = []
    for caso in casos:
        previo = resultados.get(caso["pregunta"], {})
        if previo.get("respuesta") == caso["respuesta"]:
            valor = previo["metricas"].get("fidelidad")
            if valor is not None:
                valores.append((valor, caso["pregunta"]))
    if valores:
        print("\nFidelidad más baja (para revisar a mano):")
        for valor, pregunta in sorted(valores, key=lambda v: v[0])[:5]:
            print(f"  {valor:.2f}  {pregunta[:80]}")


async def evaluar(casos, resultados, limite, pausa):
    # Se importa acá para que las funciones de arriba se puedan probar sin Ragas instalado
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, Faithfulness

    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise SystemExit("Falta la clave: define la variable de entorno GEMINI_API_KEY (ver README).")
    cliente = AsyncOpenAI(base_url=URL_GEMINI, api_key=clave)
    llm = llm_factory(MODELO_EVALUADOR, client=cliente, max_tokens=MAX_TOKENS_EVALUADOR)
    fidelidad = Faithfulness(llm=llm)
    relevancia = AnswerRelevancy(llm=llm, embeddings=OpenAIEmbeddings(client=cliente, model=MODELO_EMBEDDINGS),
                                 strictness=PREGUNTAS_RELEVANCIA)

    faltan = pendientes(casos, resultados)
    print(f"{len(faltan)} evaluaciones pendientes.")
    errores_seguidos = 0
    for n, (caso, metrica) in enumerate(faltan[:limite] if limite else faltan, start=1):
        if n > 1 and pausa:
            await asyncio.sleep(pausa)
        print(f"[{n}] {metrica}: {caso['pregunta'][:70]}", flush=True)
        try:
            if metrica == "fidelidad":
                r = await fidelidad.ascore(user_input=caso["pregunta"], response=caso["respuesta"],
                                           retrieved_contexts=contextos_de(caso))
            else:
                r = await relevancia.ascore(user_input=caso["pregunta"], response=caso["respuesta"])
        except Exception as e:   # un error del proveedor no debe perder lo ya evaluado
            print(f"    ERROR {type(e).__name__}: {str(e)[:150]}")
            errores_seguidos += 1
            if errores_seguidos == 2:
                print("El proveedor falló dos veces seguidas: probablemente se agotó el cupo. "
                      "Vuelve a correrlo más tarde: sigue donde quedó.")
                break
            continue
        errores_seguidos = 0
        valor = None if math.isnan(r.value) else float(r.value)   # sin afirmaciones no hay puntaje
        print(f"    {'sin valor' if valor is None else f'{valor:.2f}'}")
        previo = resultados.get(caso["pregunta"], {})
        if previo.get("respuesta") != caso["respuesta"]:
            previo = {"respuesta": caso["respuesta"], "metricas": {}}
        previo["metricas"][metrica] = valor
        resultados[caso["pregunta"]] = previo
        guardar(resultados)


def main():
    if not ARCHIVO_RESPUESTAS.exists():
        raise SystemExit(f"No existe {ARCHIVO_RESPUESTAS}: primero corre "
                         r"'.venv\Scripts\python.exe probar_rag.py --llm --exportar'.")
    casos = json.loads(ARCHIVO_RESPUESTAS.read_text(encoding="utf-8"))
    resultados = {}
    if ARCHIVO_RESULTADOS.exists():
        resultados = json.loads(ARCHIVO_RESULTADOS.read_text(encoding="utf-8"))

    if "--resumen" not in sys.argv:
        limite = int(sys.argv[sys.argv.index("--limite") + 1]) if "--limite" in sys.argv else None
        pausa = float(sys.argv[sys.argv.index("--pausa") + 1]) if "--pausa" in sys.argv else PAUSA
        asyncio.run(evaluar(casos, resultados, limite, pausa))
    mostrar_resumen(casos, resultados)


if __name__ == "__main__":
    main()
