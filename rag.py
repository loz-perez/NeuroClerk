# rag.py — RAG básico con PDFs
# Lee todos los PDFs de la carpeta "datos", los parte en fragmentos,
# busca los más parecidos a tu pregunta y se los pasa al modelo (Ollama).

from pathlib import Path

import numpy as np
import ollama
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------
# 0) CONFIGURACIÓN: cambia aquí los valores para experimentar
# ---------------------------------------------------------------
MODELO_LLM = "qwen3:8b"        # o "gemma3:4b", "gemma3:12b", "llama3.2"...
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-base"   # lee hasta ~300 palabras
TAM_CHUNK = 200                # palabras por fragmento
SOLAPE = 40                    # palabras repetidas entre fragmentos
K_POR_ARCHIVO = 2              # fragmentos que se traen de cada PDF

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
        texto = pagina.extract_text() or ""   # algunas páginas devuelven None
        texto = " ".join(texto.split())        # limpia saltos y espacios extra
        if texto:
            paginas.append({"pagina": numero, "texto": texto})
    return paginas


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
# 3) PREPARAR: cargar todos los PDFs y calcular sus vectores
# ---------------------------------------------------------------
chunks = []
for ruta in Path("datos").glob("*.pdf"):
    print(f"Leyendo {ruta.name}...")
    for c in dividir_en_chunks(cargar_pdf(ruta)):
        c["archivo"] = ruta.name
        chunks.append(c)

if not chunks:
    raise SystemExit("No encontré texto. ¿Hay algún PDF dentro de la carpeta 'datos'?")

print(f"Se cargaron {len(chunks)} fragmentos. Calculando embeddings (puede tardar)...")

modelo_emb = SentenceTransformer(MODELO_EMBEDDINGS)
textos = [c["texto"] for c in chunks]
vectores = modelo_emb.encode(
    [PREFIJO_DOC + t for t in textos], normalize_embeddings=True, show_progress_bar=True
)


# ---------------------------------------------------------------
# 4) RECUPERAR: los fragmentos más parecidos, de CADA archivo
# ---------------------------------------------------------------
def recuperar(pregunta, k_por_archivo=K_POR_ARCHIVO):
    v = modelo_emb.encode([PREFIJO_PREGUNTA + pregunta], normalize_embeddings=True)[0]
    similitudes = vectores @ v
    resultado = []
    for archivo in sorted({c["archivo"] for c in chunks}):
        indices = [i for i, c in enumerate(chunks) if c["archivo"] == archivo]
        mejores = sorted(indices, key=lambda i: similitudes[i], reverse=True)[:k_por_archivo]
        resultado += [chunks[i] for i in mejores]
    return resultado


# ---------------------------------------------------------------
# 5) GENERAR: pedirle al modelo que responda usando ese contexto
# ---------------------------------------------------------------
def responder(pregunta):
    encontrados = recuperar(pregunta)

    print("\nFragmentos usados:")
    for c in encontrados:
        print(f"  -> {c['archivo']}, página {c['pagina']}: {c['texto'][:80]}...")

    contexto = "\n\n".join(
        f"[{c['archivo']}, página {c['pagina']}] {c['texto']}" for c in encontrados
    )
    prompt = (
        "Eres un asistente que responde SOLO con la información del contexto.\n"
        "Reglas:\n"
        "- No agregues nada que no esté escrito en los fragmentos.\n"
        "- Después de cada afirmación, indica entre corchetes el archivo y la página.\n"
        "- Ignora los fragmentos que no tengan relación con la pregunta.\n"
        "- Si el contexto no alcanza para responder, dilo.\n\n"
        f"Contexto:\n{contexto}\n\nPregunta: {pregunta}\n\nRespuesta en español:"
    )

    opciones_extra = {}
    if MODELO_LLM.startswith("qwen3"):
        opciones_extra["think"] = False   # Qwen3: responder directo, sin "pensar en voz alta"

    r = ollama.chat(
        model=MODELO_LLM,
        messages=[{"role": "user", "content": prompt}],
        options={"num_ctx": 8192, "temperature": 0.1}, 
        **opciones_extra,
    )
    texto = r["message"]["content"]
    if "</think>" in texto:
        texto = texto.split("</think>")[-1]   # por si el modelo razona igual
    return texto.strip()


# ---------------------------------------------------------------
# 6) PROGRAMA PRINCIPAL: hacer preguntas hasta escribir "salir"
# ---------------------------------------------------------------
if __name__ == "__main__":
    print(f"Listo (modelo: {MODELO_LLM}). Escribe tu pregunta (o 'salir' para terminar).")
    while True:
        pregunta = input("\nPregunta: ").strip()
        if pregunta.lower() in ("salir", "exit", "q"):
            break
        if pregunta:
            respuesta = responder(pregunta)
            print("\nRespuesta:")
            print(respuesta)