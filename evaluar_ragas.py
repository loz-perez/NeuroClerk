# evaluar_ragas.py — mide con Ragas las respuestas exportadas por probar_rag.py
#
# Corre en su propio entorno (.venv-ragas), porque Ragas exige LangChain y una versión de openai
# más vieja que la de rag.py. Por eso no importa rag.py: solo lee el JSON exportado.
#
# Uso:
#   .venv\Scripts\python.exe probar_rag.py --llm --exportar      -> genera las respuestas
#   .venv-ragas\Scripts\python.exe evaluar_ragas.py              -> las evalúa
#   .venv-ragas\Scripts\python.exe evaluar_ragas.py --limite 5   -> solo 5 evaluaciones nuevas
#   .venv-ragas\Scripts\python.exe evaluar_ragas.py --modelo gemini-3.1-flash-lite
#                                                                -> otro evaluador: cada modelo tiene su cupo
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
import re
import sys
from pathlib import Path

ARCHIVO_RESPUESTAS = Path("evaluaciones/respuestas.json")
ARCHIVO_RESULTADOS = Path("evaluaciones/ragas.json")

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODELO_EVALUADOR = "gemini-3.5-flash-lite"
MODELO_EMBEDDINGS = "gemini-embedding-001"
MAX_TOKENS_EVALUADOR = 4000   # la lista de afirmaciones de una respuesta larga no debe cortarse
PREGUNTAS_RELEVANCIA = 1      # Ragas usa 3 por defecto: con 1 se gasta menos cupo, pero varía más
PETICIONES_POR_MINUTO = 12    # el plan gratuito permite 15: se deja margen
INTENTOS = 3                  # por evaluación, ante límites por minuto y servidor saturado
ESPERA_SERVIDOR = 30          # segundos, cuando el servidor está saturado (503)

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


class Ritmo:
    """Separa las peticiones al modelo, para no pasar del límite por minuto.

    Actúa en cada petición HTTP porque una evaluación hace varias, y Ragas puede sumar reintentos.
    Los embeddings no cuentan: tienen un límite propio mucho más alto."""

    def __init__(self, por_minuto, reloj=None):
        self.intervalo = 60 / por_minuto
        self.reloj = reloj
        self.proxima = 0.0

    async def esperar(self, peticion):
        if not peticion.url.path.endswith("/chat/completions"):
            return
        ahora = (self.reloj or asyncio.get_running_loop().time)()
        turno = max(ahora, self.proxima)
        self.proxima = turno + self.intervalo
        if turno > ahora:
            await asyncio.sleep(turno - ahora)


def espera_por_limite(mensaje):
    """Segundos a esperar tras un error 429, o None si es el cupo diario: esperar no sirve."""
    if "PerDay" in mensaje:
        return None
    pedido = re.search(r"retryDelay\W+(\d+)s", mensaje)
    return int(pedido.group(1)) + 1 if pedido else 60


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


async def evaluar(casos, resultados, limite, modelo):
    # Se importa acá para que las funciones de arriba se puedan probar sin Ragas instalado
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient, InternalServerError, RateLimitError
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, Faithfulness

    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise SystemExit("Falta la clave: define la variable de entorno GEMINI_API_KEY (ver README).")
    ritmo = Ritmo(PETICIONES_POR_MINUTO)
    # max_retries=0: los reintentos los decide el bucle de abajo, según qué límite se alcanzó
    cliente = AsyncOpenAI(base_url=URL_GEMINI, api_key=clave, max_retries=0,
                          http_client=DefaultAsyncHttpxClient(event_hooks={"request": [ritmo.esperar]}))
    llm = llm_factory(modelo, client=cliente, max_tokens=MAX_TOKENS_EVALUADOR)
    fidelidad = Faithfulness(llm=llm)
    relevancia = AnswerRelevancy(llm=llm, embeddings=OpenAIEmbeddings(client=cliente, model=MODELO_EMBEDDINGS),
                                 strictness=PREGUNTAS_RELEVANCIA)

    async def medir(caso, metrica):
        if metrica == "fidelidad":
            return await fidelidad.ascore(user_input=caso["pregunta"], response=caso["respuesta"],
                                          retrieved_contexts=contextos_de(caso))
        return await relevancia.ascore(user_input=caso["pregunta"], response=caso["respuesta"])

    faltan = pendientes(casos, resultados)
    print(f"{len(faltan)} evaluaciones pendientes (evaluador: {modelo}).")
    errores_seguidos = 0
    for n, (caso, metrica) in enumerate(faltan[:limite] if limite else faltan, start=1):
        print(f"[{n}] {metrica}: {caso['pregunta'][:70]}", flush=True)
        r = None
        for intento in range(INTENTOS):
            try:
                r = await medir(caso, metrica)
                break
            except RateLimitError as e:
                espera = espera_por_limite(str(e))
                if espera is None:
                    print(f"Se agotó el cupo diario de {modelo}. Vuelve a correrlo cuando se renueve, "
                          "o usa otro modelo con --modelo: sigue donde quedó.")
                    return
                print(f"    límite por minuto; espero {espera} s", flush=True)
            except InternalServerError:
                espera = ESPERA_SERVIDOR
                print(f"    servidor saturado; espero {espera} s", flush=True)
            except Exception as e:   # un error inesperado no debe perder lo ya evaluado
                print(f"    ERROR {type(e).__name__}: {str(e)[:500]}")
                break
            if intento < INTENTOS - 1:
                await asyncio.sleep(espera)
        if r is None:
            errores_seguidos += 1
            if errores_seguidos == 2:
                print("Dos evaluaciones seguidas sin resultado: lo detengo. "
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
        modelo = sys.argv[sys.argv.index("--modelo") + 1] if "--modelo" in sys.argv else MODELO_EVALUADOR
        asyncio.run(evaluar(casos, resultados, limite, modelo))
    mostrar_resumen(casos, resultados)


if __name__ == "__main__":
    main()
