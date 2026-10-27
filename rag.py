# rag.py — RAG básico con PDFs y ChromaDB
# Lee los PDFs de la carpeta "datos", los parte en fragmentos y guarda sus vectores
# en ChromaDB (carpeta "chroma_db"). La próxima vez solo procesa los PDFs nuevos.
# Luego busca los fragmentos más parecidos a tu pregunta y se los pasa al modelo de lenguaje,
# que puede ser local (Ollama) o en la nube (Gemini o Groq).

import os
# Usa el modelo ya descargado. Para descargarlo (primera vez, o en Colab): HF_HUB_OFFLINE=0
os.environ.setdefault("HF_HUB_OFFLINE", "1")
# SOLO_INDEXAR=1: indexa los PDFs y termina (útil en Colab; no pide clave del modelo)
SOLO_INDEXAR = os.environ.get("SOLO_INDEXAR") == "1"

import re
import hashlib
from pathlib import Path

import numpy as np
import chromadb
import pdfplumber
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------
# 0) CONFIGURACIÓN: cambia aquí los valores para experimentar
# ---------------------------------------------------------------
# Modelo de lenguaje: "gemini" o "groq" (nube, gratis, más rápidos) u "ollama" (local).
# Los de la nube necesitan una clave en una variable de entorno (ver README).
# En su plan gratuito, Google puede usar lo que envías para mejorar sus productos:
# no mandes datos de pacientes por ahí.
PROVEEDOR = "gemini"
MODELOS = {
    "gemini": "gemini-3.5-flash-lite",
    "groq": "openai/gpt-oss-120b",
    "ollama": "qwen3:8b",
}
MODELO_LLM = MODELOS[PROVEEDOR]
_VARIABLES = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY"}
if not SOLO_INDEXAR and PROVEEDOR in _VARIABLES and not os.environ.get(_VARIABLES[PROVEEDOR]):
    raise SystemExit(f"Falta la clave de {PROVEEDOR}: define la variable de entorno "
                     f"{_VARIABLES[PROVEEDOR]} (ver README), o pon PROVEEDOR = \"ollama\".")
MAX_TOKENS_RESPUESTA = 700 if PROVEEDOR == "ollama" else 2000   # los de la nube cuentan su razonamiento

MODELO_EMBEDDINGS = "intfloat/multilingual-e5-base"   # lee hasta ~300 palabras
TAM_CHUNK = 200                # palabras por fragmento
SOLAPE = 40                    # palabras repetidas entre fragmentos
K_POR_ARCHIVO = 3              # candidatos que se buscan en cada PDF
MARGEN = 0.03                  # se descarta lo que esté a más de esto del mejor fragmento
MAX_FRAGMENTOS = 8             # tope de fragmentos que llegan al modelo
VERSION_TEXTO = 2              # súbela cada vez que cambies cómo se extrae o divide el texto

CARPETA_DATOS = "datos"
CARPETA_DB = "chroma_db"       # aquí ChromaDB guarda los vectores en disco

# e5 necesita estos prefijos para distinguir documentos de preguntas
PREFIJO_DOC = "passage: "
PREFIJO_PREGUNTA = "query: "


# ---------------------------------------------------------------
# 1) CARGAR: leer el texto de un PDF, página por página
# ---------------------------------------------------------------
def cargar_pdf(ruta):
    lector = PdfReader(ruta)
    paginas = []
    for numero, pagina in enumerate(lector.pages, start=1):
        texto = pagina.extract_text() or ""            # algunas páginas devuelven None
        texto = " ".join(texto.split())                 # limpia saltos y espacios extra
        texto = re.sub(r"(\w)- (\w)", r"\1\2", texto)   # "dificul- tad" -> "dificultad"
        if texto:
            paginas.append({"pagina": numero, "texto": texto})
    return paginas


# ---------------------------------------------------------------
# 1b) TABLAS: extraerlas con pdfplumber y convertirlas en texto legible
# ---------------------------------------------------------------
def limpiar(celda):
    return " ".join((celda or "").split())


def tabla_a_texto(filas):
    """Convierte una tabla (lista de filas) en (título, líneas de texto)."""
    # Cada celda puede tener varios renglones (p. ej. una columna de fármacos)
    filas = [[(c or "").strip() for c in f] for f in filas]
    filas = [f for f in filas if any(f)]
    if not filas:
        return "", []

    # Si la primera fila tiene una sola celda con texto, es el título de la tabla
    titulo = ""
    if sum(1 for c in filas[0] if c) == 1:
        titulo = limpiar(next(c for c in filas[0] if c))
        filas = filas[1:]

    lineas = []
    encabezado = filas[0] if len(filas) >= 3 and sum(1 for c in filas[0] if c) >= 2 else None
    if encabezado:
        # Tabla con encabezado: cada fila se escribe como "columna: valor; columna: valor"
        nombres = [limpiar(c) for c in encabezado]
        for f in filas[1:]:
            partes = [f"{n}: {limpiar(v)}" if n else limpiar(v)
                      for n, v in zip(nombres, f) if limpiar(v)]
            if partes:
                lineas.append("; ".join(partes))
    else:
        # Tabla tipo lista: todos los elementos separados por comas
        elementos = [limpiar(x) for f in filas for c in f for x in c.split("\n") if limpiar(x)]
        if elementos:
            lineas.append(", ".join(elementos))
    return titulo, lineas


def cargar_tablas(ruta, tam=TAM_CHUNK):
    """Devuelve fragmentos de tablas; cada uno lleva el título delante."""
    fragmentos = []
    with pdfplumber.open(ruta) as pdf:
        for numero, pagina in enumerate(pdf.pages, start=1):
            try:
                tablas = pagina.extract_tables()
            except Exception:
                continue   # alguna página rara no debe frenar todo
            for filas in tablas:
                titulo, lineas = tabla_a_texto(filas)
                texto = " ".join(lineas)
                if len(texto.split()) < 5:
                    continue   # tablas vacías o casi vacías
                prefijo = f"{titulo}: " if titulo else "Tabla: "
                palabras = texto.split()
                # Tablas largas: se parten, pero cada trozo repite el título
                for i in range(0, len(palabras), tam):
                    trozo = " ".join(palabras[i:i + tam])
                    fragmentos.append({"pagina": numero, "texto": prefijo + trozo})
    return fragmentos


# ---------------------------------------------------------------
# 2) DIVIDIR: partir el texto en fragmentos (chunks) con solapamiento
# ---------------------------------------------------------------
def dividir_en_chunks(paginas, tam=TAM_CHUNK, solape=SOLAPE):
    chunks = []
    paso = tam - solape
    for p in paginas:
        palabras = p["texto"].split()
        for inicio in range(0, len(palabras), paso):
            trozo = " ".join(palabras[inicio:inicio + tam])
            chunks.append({"pagina": p["pagina"], "texto": trozo})
            if inicio + tam >= len(palabras):
                break
    return chunks


# ---------------------------------------------------------------
# 3) PREPARAR: abrir ChromaDB y procesar solo los PDFs que falten
# ---------------------------------------------------------------
modelo_emb = SentenceTransformer(MODELO_EMBEDDINGS)

# Si cambias el modelo de embeddings o el tamaño de los chunks, los vectores viejos
# ya no sirven. Por eso el nombre de la colección depende de esa configuración:
# al cambiarla se crea una colección nueva y se recalcula todo automáticamente.
config = f"{MODELO_EMBEDDINGS}|{TAM_CHUNK}|{SOLAPE}|{VERSION_TEXTO}"
nombre_coleccion = "rag_" + hashlib.md5(config.encode()).hexdigest()[:10]

cliente = chromadb.PersistentClient(path=CARPETA_DB)
coleccion = cliente.get_or_create_collection(nombre_coleccion)


def huella(ruta):
    """Huella del contenido: igual en cualquier computadora; cambia solo si cambia el PDF."""
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def indexar_pdf(ruta):
    chunks = dividir_en_chunks(cargar_pdf(ruta))
    tablas = cargar_tablas(ruta)
    if tablas:
        print(f"  {len(tablas)} fragmentos de tablas encontrados")
    chunks += tablas
    if not chunks:
        print(f"  (sin texto: {ruta.name} puede ser un PDF escaneado)")
        return
    textos = [c["texto"] for c in chunks]
    vectores = modelo_emb.encode(
        [PREFIJO_DOC + t for t in textos], normalize_embeddings=True, show_progress_bar=True
    )
    marca = huella(ruta)
    # ChromaDB acepta lotes de tamaño limitado, así que se guardan de a 1000
    for i in range(0, len(chunks), 1000):
        lote = range(i, min(i + 1000, len(chunks)))
        coleccion.add(
            ids=[f"{ruta.name}-{j}" for j in lote],
            embeddings=[vectores[j].tolist() for j in lote],
            documents=[textos[j] for j in lote],
            metadatas=[{"archivo": ruta.name, "pagina": chunks[j]["pagina"], "huella": marca}
                       for j in lote],
        )
    print(f"  {len(chunks)} fragmentos guardados")


pdfs = sorted(Path(CARPETA_DATOS).glob("*.pdf"))
if not pdfs:
    raise SystemExit(f"No encontré PDFs dentro de la carpeta '{CARPETA_DATOS}'.")

for ruta in pdfs:
    guardado = coleccion.get(where={"archivo": ruta.name}, limit=1, include=["metadatas"])
    if guardado["ids"] and guardado["metadatas"][0].get("huella") == huella(ruta):
        print(f"Ya indexado: {ruta.name}")
        continue
    if guardado["ids"]:
        print(f"{ruta.name} cambió: borrando sus vectores viejos...")
        coleccion.delete(where={"archivo": ruta.name})
    print(f"Indexando {ruta.name} (solo esta vez)...")
    indexar_pdf(ruta)

# Los PDFs que quitaste de la carpeta "datos" también se quitan de la base
nombres_actuales = {r.name for r in pdfs}
todos = coleccion.get(include=["metadatas"])
for archivo in {m["archivo"] for m in todos["metadatas"]} - nombres_actuales:
    print(f"Quitando {archivo} (ya no está en '{CARPETA_DATOS}')")
    coleccion.delete(where={"archivo": archivo})

archivos = sorted(nombres_actuales)
print(f"Base lista: {coleccion.count()} fragmentos de {len(archivos)} archivos.")
if SOLO_INDEXAR:
    raise SystemExit("Indexación terminada (SOLO_INDEXAR=1).")


# ---------------------------------------------------------------
# 4) RECUPERAR: los fragmentos más parecidos, de CADA archivo,
#    descartando los que se parecen mucho menos que el mejor
# ---------------------------------------------------------------
def recuperar(pregunta, k_por_archivo=K_POR_ARCHIVO, margen=MARGEN, max_total=MAX_FRAGMENTOS):
    v = modelo_emb.encode([PREFIJO_PREGUNTA + pregunta], normalize_embeddings=True)[0]

    # Paso 1: candidatos, los k mejores de cada archivo (ChromaDB hace la búsqueda)
    candidatos = []
    for archivo in archivos:
        r = coleccion.query(
            query_embeddings=[v.tolist()],
            n_results=k_por_archivo,
            where={"archivo": archivo},
            include=["documents", "metadatas", "embeddings"],
        )
        for texto, meta, emb in zip(r["documents"][0], r["metadatas"][0], r["embeddings"][0]):
            candidatos.append({
                "archivo": meta["archivo"],
                "pagina": meta["pagina"],
                "texto": texto,
                "similitud": float(np.dot(emb, v)),   # similitud coseno (vectores normalizados)
            })
    if not candidatos:
        return []

    # Paso 2: filtro, solo los que están cerca del mejor candidato
    mejor = max(c["similitud"] for c in candidatos)
    aceptados = [c for c in candidatos if c["similitud"] >= mejor - margen]

    # Paso 3: ordenar de más a menos parecido y aplicar el tope
    aceptados.sort(key=lambda c: c["similitud"], reverse=True)
    return aceptados[:max_total]


# ---------------------------------------------------------------
# 5) GENERAR: pedirle al modelo que responda usando ese contexto
# ---------------------------------------------------------------
def responder(pregunta):
    encontrados = recuperar(pregunta)

    print("\nFragmentos usados:")
    for c in encontrados:
        print(f"  -> [{c['similitud']:.3f}] {c['archivo']}, página {c['pagina']}: {c['texto'][:70]}...")

    contexto = "\n\n".join(
        f"[{c['archivo']}, página {c['pagina']}] {c['texto']}" for c in encontrados
    )
    prompt = (
        "Eres un asistente que responde SOLO con la información del contexto.\n"
        "Reglas:\n"
        "- No agregues nada que no esté escrito en los fragmentos.\n"
        "- Después de cada afirmación, indica entre corchetes el archivo y la página.\n"
        "- Ignora los fragmentos que no tengan relación con la pregunta.\n"
        "- Si varios fragmentos aportan datos distintos sobre el tema, inclúyelos todos.\n"
        "- Si el contexto no alcanza para responder, dilo.\n\n"
        f"Contexto:\n{contexto}\n\nPregunta: {pregunta}\n\nRespuesta en español:"
    )

    print("\nGenerando respuesta...", flush=True)
    partes = []
    for trozo in generar(prompt):        # la respuesta llega de a poco (streaming)
        partes.append(trozo)
        print(".", end="", flush=True)   # un punto por trozo: se ve que avanza
    print()

    texto = "".join(partes)
    if "</think>" in texto:
        texto = texto.split("</think>")[-1]   # por si el modelo razona en voz alta
    return texto.strip()


# Direcciones de los proveedores en la nube (ambos aceptan el formato de OpenAI)
NUBE = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
}
_cliente = None


def generar(prompt):
    """Devuelve la respuesta del modelo en trozos de texto, sea local o en la nube."""
    mensajes = [{"role": "user", "content": prompt}]

    if PROVEEDOR == "ollama":
        import ollama
        extra = {"think": False} if MODELO_LLM.startswith("qwen3") else {}
        for trozo in ollama.chat(
            model=MODELO_LLM,
            messages=mensajes,
            options={"num_ctx": 8192, "temperature": 0.1, "num_predict": MAX_TOKENS_RESPUESTA},
            stream=True,
            **extra,
        ):
            yield trozo["message"]["content"]
        return

    global _cliente
    import time
    from openai import OpenAI, RateLimitError, InternalServerError, APIConnectionError, APITimeoutError
    if _cliente is None:
        url, variable = NUBE[PROVEEDOR]
        clave = os.environ.get(variable)
        if not clave:
            raise SystemExit(f"Falta la clave: define la variable de entorno {variable} (ver README).")
        _cliente = OpenAI(base_url=url, api_key=clave)

    extra = {"reasoning_effort": "low"} if PROVEEDOR == "groq" else {}
    # Errores pasajeros (servidor saturado, 503, cortes de red): se reintenta hasta 3 veces
    for intento in range(4):
        try:
            respuesta = _cliente.chat.completions.create(
                model=MODELO_LLM,
                messages=mensajes,
                temperature=0.1,
                max_tokens=MAX_TOKENS_RESPUESTA,
                stream=True,
                **extra,
            )
            for trozo in respuesta:
                if trozo.choices and trozo.choices[0].delta.content:
                    yield trozo.choices[0].delta.content
            return
        except RateLimitError:
            yield ("[Se alcanzó el límite gratuito del proveedor. Espera un minuto y vuelve a "
                   "preguntar, o cambia PROVEEDOR en el bloque 0.]")
            return
        except (InternalServerError, APIConnectionError, APITimeoutError) as e:
            if intento == 3:
                yield (f"[El proveedor no responde ({type(e).__name__}). Prueba en unos minutos "
                       "o cambia PROVEEDOR en el bloque 0.]")
                return
            espera = 2 ** (intento + 1)   # 2, 4 y 8 segundos
            print(f"\n  (el servidor no respondió; reintento en {espera} s)", flush=True)
            time.sleep(espera)


# ---------------------------------------------------------------
# 6) PROGRAMA PRINCIPAL: hacer preguntas hasta escribir "salir"
# ---------------------------------------------------------------
if __name__ == "__main__":
    print(f"Listo (modelo: {MODELO_LLM} en {PROVEEDOR}). Escribe tu pregunta (o 'salir' para terminar).")
    while True:
        pregunta = input("\nPregunta: ").strip()
        if pregunta.lower() in ("salir", "exit", "q"):
            break
        if pregunta:
            respuesta = responder(pregunta)
            print("\nRespuesta:")
            print(respuesta)
