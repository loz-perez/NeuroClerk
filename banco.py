# banco.py — compara configuraciones de la búsqueda con los casos de probar_rag.py
#
# Uso:
#   python banco.py correr                                   -> mide la configuración de rag.py
#   python banco.py correr --set margen=0.03,0.05,0.08 --set max_fragmentos=12,20
#                                                            -> mide todas las combinaciones (6)
#   python banco.py correr --nombre tope20 --set max_fragmentos=20
#   python banco.py correr --llm --modelo NOMBRE --pausa 15  -> además pide las respuestas (gasta cupo)
#   python banco.py listar                                   -> las corridas guardadas
#   python banco.py comparar 1 4                             -> qué casos mejoraron o empeoraron
#
# Sin --llm no llama a ningún modelo: mide qué llega al contexto, gratis y en segundos. Además de las
# medidas de probar_rag.py (Tabla y Fuente), mide Contexto: si alguna palabra clave del caso está en
# los fragmentos. Fuente aprueba con cualquier página del documento; Contexto detecta cuándo llega el
# documento correcto, pero no la página con el dato. Una clave corta ("27", "ran") puede aprobar por
# casualidad: un acierto de Contexto no garantiza que el fragmento sea el correcto.
#
# Los parámetros de indexación (TAM_CHUNK, SOLAPE, modelo de embeddings) no se pueden variar con --set,
# porque cambian la colección: se cambian en rag.py y se mide con "correr", que no indexa sin --indexar.
#
# Guarda los resultados en evaluaciones/banco.sqlite, fuera de Git, sin el texto de los fragmentos.

import argparse
import functools
import hashlib
import itertools
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
ARCHIVO_BD = CARPETA / "evaluaciones" / "banco.sqlite"
ARCHIVO_COMMIT = CARPETA / ".commit_desplegado"   # lo escribe desplegar_wsl.sh: en WSL no hay .git

# Nombre en --set -> (variable de rag.py, tipo)
PARAMETROS = {
    "margen": ("MARGEN", float),
    "max_fragmentos": ("MAX_FRAGMENTOS", int),
    "max_por_pagina": ("MAX_POR_PAGINA", int),
    "similitud_duplicado": ("SIMILITUD_DUPLICADO", float),
    "k_min": ("K_MIN", int),
    "k_max": ("K_MAX", int),
    "fragmentos_por_candidato": ("FRAGMENTOS_POR_CANDIDATO", int),
}

# Medidas por caso que se pueden comparar entre corridas
MEDIDAS = ("tabla_ok", "fuente_ok", "contexto_ok", "respuesta_ok")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS corridas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    nombre TEXT NOT NULL,
    version TEXT NOT NULL,
    huella_codigo TEXT NOT NULL,
    coleccion TEXT NOT NULL,
    modelo TEXT,
    segundos REAL NOT NULL,
    config TEXT NOT NULL,
    resumen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS casos (
    corrida_id INTEGER NOT NULL REFERENCES corridas(id) ON DELETE CASCADE,
    n INTEGER NOT NULL,
    grupo TEXT NOT NULL,
    tipo TEXT NOT NULL,
    pregunta TEXT NOT NULL,
    tabla_ok INTEGER,
    fuente_ok INTEGER,
    contexto_ok INTEGER,
    n_fragmentos INTEGER NOT NULL,
    fragmentos TEXT NOT NULL,
    medida_respuesta TEXT,
    respuesta_ok INTEGER,
    detalle TEXT,
    sin_respaldo TEXT,
    respuesta TEXT,
    error TEXT,
    PRIMARY KEY (corrida_id, n)
);
"""


# ---------------------------------------------------------------
# Funciones puras: no necesitan el modelo, la base ni los PDFs
# ---------------------------------------------------------------
def expandir_ajustes(ajustes):
    """De ["margen=0.03,0.05", "max_fragmentos=12"] a una configuración por cada combinación."""
    opciones = {}
    for ajuste in ajustes or []:
        nombre, separador, valores = ajuste.partition("=")
        if not separador or not valores:
            raise ValueError(f"'{ajuste}' no tiene la forma parametro=valor[,valor]")
        if nombre not in PARAMETROS:
            raise ValueError(f"Parámetro desconocido: '{nombre}'. Se puede usar: {', '.join(PARAMETROS)}")
        tipo = PARAMETROS[nombre][1]
        try:
            opciones[nombre] = [tipo(v) for v in valores.split(",")]
        except ValueError:
            raise ValueError(f"Valor no válido para {nombre}: '{valores}'") from None
    nombres = list(opciones)
    return [dict(zip(nombres, combinacion)) for combinacion in itertools.product(*opciones.values())]


def nombre_de(config, prefijo=None):
    """Un nombre legible para la corrida: "margen=0.05 max_fragmentos=20", o "base" si no cambia nada."""
    ajustes = " ".join(f"{k}={v}" for k, v in config.items())
    if prefijo:
        return f"{prefijo} {ajustes}".strip()
    return ajustes or "base"


def calcular_cupos(tamanos, k_min, k_max, fragmentos_por_candidato):
    """La misma fórmula que rag.preparar(): candidatos por archivo según su tamaño."""
    return {archivo: max(k_min, min(k_max, round(tamano / fragmentos_por_candidato)))
            for archivo, tamano in tamanos.items()}


def medir_busqueda(caso, fragmentos, pr):
    """Lo que se puede medir sin el modelo. Las medidas que no aplican al caso quedan en None."""
    medida = {"tabla_ok": None, "fuente_ok": None, "contexto_ok": None}
    if "tabla" in caso:
        medida["tabla_ok"] = any(pr.es_la_tabla(f, caso) for f in fragmentos)
    if caso.get("fuentes"):
        medida["fuente_ok"] = any(pr.es_fuente(f, caso) for f in fragmentos)
    if caso.get("claves"):
        contexto = [pr.normalizar(f["texto"]) for f in fragmentos]
        medida["contexto_ok"] = any(pr.normalizar(c) in texto for c in caso["claves"] for texto in contexto)
    return medida


def medir_respuesta(caso, fragmentos, respuesta, pr):
    """Los mismos criterios que probar_rag.py: una dosis sin respaldo hace fallar un caso de dosis."""
    medida = {"abstencion": "abstencion", "dosis": "dosis", "dosis_ausente": "dosis"}.get(caso["tipo"], "respuesta")
    ok, detalle = pr.respuesta_ok(respuesta, caso)
    sin_respaldo = sorted(pr.dosis_sin_respaldo(respuesta, fragmentos, caso["pregunta"]))
    if medida == "dosis" and sin_respaldo:
        ok = False
    return {"medida_respuesta": medida, "respuesta_ok": ok, "detalle": detalle,
            "sin_respaldo": sin_respaldo, "tiene_dosis": bool(pr.extraer_dosis(respuesta))}


def resumir(filas):
    """Los totales de una corrida. Fuente separa los casos de dosis, igual que probar_rag.py."""
    totales = {}

    def sumar(clave, valor):
        if valor is not None:
            aciertos, casos = totales.get(clave, (0, 0))
            totales[clave] = (aciertos + bool(valor), casos + 1)

    for fila in filas:
        sumar("tabla", fila["tabla_ok"])
        sumar("fuente_dosis" if fila["tipo"] in ("dosis", "dosis_ausente") else "fuente", fila["fuente_ok"])
        sumar("contexto", fila["contexto_ok"])
        if fila.get("medida_respuesta"):
            sumar(fila["medida_respuesta"], fila["respuesta_ok"])
        if fila.get("tiene_dosis"):
            sumar("respaldo", not fila["sin_respaldo"])
    resumen = {clave: {"aciertos": a, "casos": c} for clave, (a, c) in totales.items()}
    resumen["fragmentos_promedio"] = (round(sum(f["n_fragmentos"] for f in filas) / len(filas), 1) if filas else 0)
    resumen["errores"] = sum(1 for f in filas if f.get("error"))
    return resumen


def comparar_casos(casos_a, casos_b):
    """Qué cambió de A a B, caso por caso. Solo cuenta si la medida existe en ambas corridas."""
    por_pregunta = {c["pregunta"]: c for c in casos_a}
    mejoras, empeoran = [], []
    for caso in casos_b:
        previo = por_pregunta.get(caso["pregunta"])
        if previo is None:
            continue
        for medida in MEDIDAS:
            antes, ahora = previo[medida], caso[medida]
            if antes is None or ahora is None or bool(antes) == bool(ahora):
                continue
            cambio = {"grupo": caso["grupo"], "pregunta": caso["pregunta"], "medida": medida.removesuffix("_ok")}
            (mejoras if ahora else empeoran).append(cambio)
    return {"mejoras": mejoras, "empeoran": empeoran}


def texto_resumen(resumen):
    partes = [f"{clave} {resumen[clave]['aciertos']}/{resumen[clave]['casos']}"
              for clave in ("tabla", "fuente", "fuente_dosis", "contexto", "respuesta", "abstencion", "dosis", "respaldo")
              if clave in resumen]
    partes.append(f"{resumen['fragmentos_promedio']} frag.")
    if resumen.get("errores"):
        partes.append(f"{resumen['errores']} errores")
    return " | ".join(partes)


# ---------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------
def abrir(archivo=ARCHIVO_BD):
    archivo.parent.mkdir(exist_ok=True)
    conexion = sqlite3.connect(archivo)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(ESQUEMA)
    return conexion


def guardar_corrida(conexion, datos, filas):
    with conexion:
        cursor = conexion.execute(
            "INSERT INTO corridas (fecha, nombre, version, huella_codigo, coleccion, modelo, segundos, config, resumen) "
            "VALUES (:fecha, :nombre, :version, :huella_codigo, :coleccion, :modelo, :segundos, :config, :resumen)",
            {**datos, "config": json.dumps(datos["config"]), "resumen": json.dumps(resumir(filas))})
        corrida = cursor.lastrowid
        for n, fila in enumerate(filas, start=1):
            conexion.execute(
                "INSERT INTO casos VALUES (:corrida, :n, :grupo, :tipo, :pregunta, :tabla_ok, :fuente_ok, "
                ":contexto_ok, :n_fragmentos, :fragmentos, :medida_respuesta, :respuesta_ok, :detalle, "
                ":sin_respaldo, :respuesta, :error)",
                {"medida_respuesta": None, "respuesta_ok": None, "detalle": None, "respuesta": None, "error": None,
                 **fila, "corrida": corrida, "n": n, "fragmentos": json.dumps(fila["fragmentos"], ensure_ascii=False),
                 "sin_respaldo": json.dumps(fila.get("sin_respaldo", []), ensure_ascii=False)})
    return corrida


def leer_corridas(conexion):
    corridas = [dict(c) for c in conexion.execute("SELECT * FROM corridas ORDER BY id DESC")]
    for corrida in corridas:
        corrida["config"] = json.loads(corrida["config"])
        corrida["resumen"] = json.loads(corrida["resumen"])
    return corridas


def leer_casos(conexion, corrida):
    casos = [dict(c) for c in conexion.execute("SELECT * FROM casos WHERE corrida_id = ? ORDER BY n", (corrida,))]
    for caso in casos:
        caso["fragmentos"] = json.loads(caso["fragmentos"])
        caso["sin_respaldo"] = json.loads(caso["sin_respaldo"] or "[]")
    return casos


# ---------------------------------------------------------------
# Correr: acá sí se usan rag.py y probar_rag.py
# ---------------------------------------------------------------
def version_actual():
    """El commit medido, con una marca si había cambios sin guardar."""
    if ARCHIVO_COMMIT.exists():
        return ARCHIVO_COMMIT.read_text(encoding="utf-8").strip()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=CARPETA, capture_output=True,
                                text=True, check=True).stdout.strip()
        cambios = subprocess.run(["git", "status", "--porcelain"], cwd=CARPETA, capture_output=True,
                                 text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "sin versión"
    return f"{commit}+cambios" if cambios else commit


def huella_codigo():
    """Identifica el código medido aunque no esté en un commit: distingue dos "+cambios"."""
    h = hashlib.md5()
    for nombre in ("rag.py", "probar_rag.py"):
        h.update((CARPETA / nombre).read_bytes())
    return h.hexdigest()[:10]


def exigir_coleccion(rag, indexar):
    """rag.preparar() indexaría una colección que falta, lo que en CPU tarda horas: que sea a propósito."""
    if indexar:
        return
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    import chromadb
    colecciones = chromadb.PersistentClient(path=rag.CARPETA_DB).list_collections()
    if rag.nombre_coleccion not in {getattr(c, "name", c) for c in colecciones}:
        raise SystemExit(f"No existe la colección {rag.nombre_coleccion} (cambió el chunking o los embeddings "
                         "de rag.py). Indexarla puede tardar horas en CPU: si es lo que quieres, usa --indexar.")


def correr(args):
    try:
        configuraciones = expandir_ajustes(args.set)
    except ValueError as e:
        raise SystemExit(str(e)) from e
    if args.llm and len(configuraciones) > 1:
        raise SystemExit(f"--llm con {len(configuraciones)} combinaciones gastaría {len(configuraciones) * 28} "
                         "peticiones: mide la búsqueda primero y usa --llm con la mejor.")

    os.chdir(CARPETA)   # rag.py busca datos/ y chroma_db/ en la carpeta actual
    if args.modelo:
        os.environ["NEUROCLERK_MODELO"] = args.modelo
    sys.argv = sys.argv[:1]   # probar_rag.py lee sys.argv al importarse
    import probar_rag as pr
    import rag

    if args.llm:
        rag.comprobar_clave()
    exigir_coleccion(rag, args.indexar)
    rag.preparar()

    tamanos = {a: 0 for a in rag.archivos}
    for meta in rag.coleccion.get(include=["metadatas"])["metadatas"]:
        tamanos[meta["archivo"]] = tamanos.get(meta["archivo"], 0) + 1
    base = {nombre: getattr(rag, variable) for nombre, (variable, _) in PARAMETROS.items()}
    recuperar_original = rag.recuperar
    version, huella = version_actual(), huella_codigo()
    conexion = abrir()

    for ajustes in configuraciones:
        config = {**base, **ajustes}
        rag.MAX_POR_PAGINA = config["max_por_pagina"]
        rag.SIMILITUD_DUPLICADO = config["similitud_duplicado"]
        rag.CUPO = calcular_cupos(tamanos, config["k_min"], config["k_max"], config["fragmentos_por_candidato"])
        # responder() llama a recuperar() sin argumentos: así también usa estos valores
        rag.recuperar = functools.partial(recuperar_original, margen=config["margen"],
                                          max_total=config["max_fragmentos"])
        inicio = time.perf_counter()
        filas = medir_casos(pr, rag, args)
        datos = {"fecha": datetime.now().isoformat(timespec="seconds"), "nombre": nombre_de(ajustes, args.nombre),
                 "version": version, "huella_codigo": huella, "coleccion": rag.nombre_coleccion,
                 "modelo": rag.MODELO_LLM if args.llm else None,
                 "segundos": round(time.perf_counter() - inicio, 1), "config": config}
        corrida = guardar_corrida(conexion, datos, filas)
        print(f"#{corrida} {datos['nombre']}: {texto_resumen(resumir(filas))}", flush=True)


def medir_casos(pr, rag, args):
    filas, errores_seguidos = [], 0
    for n, caso in enumerate(pr.CASOS, start=1):
        fragmentos = rag.recuperar(caso["pregunta"])
        fila = {"grupo": caso["grupo"], "tipo": caso["tipo"], "pregunta": caso["pregunta"],
                "n_fragmentos": len(fragmentos), **medir_busqueda(caso, fragmentos, pr),
                "fragmentos": [{"archivo": f["archivo"], "pagina": int(f["pagina"]),
                                "similitud": round(f["similitud"], 3)} for f in fragmentos]}
        if args.llm:
            if errores_seguidos >= 2:
                fila["error"] = "sin evaluar: el proveedor falló dos veces seguidas"
            else:
                if n > 1 and args.pausa:
                    time.sleep(args.pausa)
                try:
                    respuesta = rag.responder(caso["pregunta"])
                except Exception as e:   # un error del proveedor no debe perder lo ya medido
                    respuesta = f"[{type(e).__name__}: {str(e)[:200]}]"
                if respuesta.startswith("["):   # aviso de rag.py: límite alcanzado o proveedor caído
                    fila["error"] = respuesta
                    errores_seguidos += 1
                else:
                    errores_seguidos = 0
                    fila["respuesta"] = respuesta
                    fila.update(medir_respuesta(caso, fragmentos, respuesta, pr))
        filas.append(fila)
    return filas


def listar(_args):
    conexion = abrir()
    corridas = leer_corridas(conexion)
    if not corridas:
        print("Todavía no hay corridas: usa 'python banco.py correr'.")
    for c in corridas:
        print(f"#{c['id']:<4} {c['fecha']}  {c['version']:<16} {c['nombre']}\n      {texto_resumen(c['resumen'])}")


def comparar(args):
    conexion = abrir()
    cambios = comparar_casos(leer_casos(conexion, args.a), leer_casos(conexion, args.b))
    for titulo, lista in (("Mejoran", cambios["mejoras"]), ("Empeoran", cambios["empeoran"])):
        print(f"\n{titulo} de #{args.a} a #{args.b}: {len(lista)}")
        for c in lista:
            print(f"  {c['medida']:<10} {c['grupo']}: {c['pregunta']}")


def main():
    parser = argparse.ArgumentParser(description="Compara configuraciones de la búsqueda de NeuroClerk.")
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("correr", help="mide una o varias configuraciones")
    p.add_argument("--set", action="append", metavar="PARAMETRO=VALOR[,VALOR]",
                   help=f"se puede repetir; parámetros: {', '.join(PARAMETROS)}")
    p.add_argument("--nombre", help="prefijo para reconocer la corrida")
    p.add_argument("--llm", action="store_true", help="además pide las respuestas (gasta cupo)")
    p.add_argument("--modelo", help="modelo para --llm")
    p.add_argument("--pausa", type=float, default=12, help="segundos entre preguntas con --llm")
    p.add_argument("--indexar", action="store_true", help="permite indexar si falta la colección")
    p.set_defaults(funcion=correr)
    p = sub.add_parser("listar", help="muestra las corridas guardadas")
    p.set_defaults(funcion=listar)
    p = sub.add_parser("comparar", help="qué casos cambiaron entre dos corridas")
    p.add_argument("a", type=int)
    p.add_argument("b", type=int)
    p.set_defaults(funcion=comparar)
    args = parser.parse_args()
    args.funcion(args)


if __name__ == "__main__":
    main()
