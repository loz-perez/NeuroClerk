# probar_tablas.py — comprueba que las tablas extraídas con pdfplumber se encuentran
#
# Uso:
#   python probar_tablas.py          -> solo la búsqueda (rápido, no usa Ollama)
#   python probar_tablas.py --llm    -> además pide la respuesta al modelo y revisa
#                                       que mencione datos que solo están en la tabla
#
# Usa la misma base de ChromaDB que rag.py: si los PDFs ya están indexados, arranca rápido.

import sys
import unicodedata

import rag   # al importarlo se abre ChromaDB y se indexa lo que falte

ARCHIVO = "Interacciones_Farmacologicas_SEFH.pdf"   # nombre del libro de interacciones en datos/

# Cada caso: una pregunta, las fuentes que se aceptan como correctas y palabras clave.
# - "tabla": la tabla del libro de interacciones que contiene la respuesta.
# - "fichas": fichas técnicas que también la contienen (cualquier página cuenta).
# - "claves": palabras que deberían aparecer en la respuesta y NO están en la pregunta.
#   En los casos 1, 2, 3 y 7 son fármacos que figuran SOLO en la tabla, en ninguna de las
#   fichas: si la respuesta los nombra, el modelo usó la tabla.
CASOS = [
    {
        "pregunta": "¿Qué fármacos pueden causar síndrome neuroléptico maligno?",
        "tabla": (9, "Tabla 1. Fármacos que pueden causar Síndrome Neuroléptico Maligno"),
        "fichas": [],
        "claves": ["pergolida", "tiopropenazina", "tolcapona"],
    },
    {
        "pregunta": "¿Qué fármacos pueden causar síndrome serotoninérgico?",
        "tabla": (10, "Tabla 2. Fármacos que pueden causar Síndrome Serotoninérgico"),
        "fichas": [],
        "claves": ["dapoxetina", "metiltionina", "tapentadol"],
    },
    {
        "pregunta": "¿Qué fármacos pueden prolongar el segmento QT?",
        "tabla": (11, "Tabla 3. Fármacos que pueden prolongar el segmento QT"),
        "fichas": [],
        "claves": ["ebastina", "retigabina", "piperaquina", "eribulina"],
    },
    {
        "pregunta": "¿Qué interacción tienen los IECA con el litio?",
        "tabla": (177, "Tabla 5. Interacciones farmacocinéticas de IECA"),
        "fichas": ["FT_Litio.pdf", "FT_Enalapril.pdf"],
        "claves": ["toxicidad", "concentraci", "nivel"],
    },
    {
        "pregunta": "¿Qué isoenzimas del citocromo P450 metabolizan la clozapina?",
        "tabla": (265, "Tabla 7. Isoformas del citocromo P450"),
        "fichas": ["FT_Clozapina.pdf"],
        "claves": ["cyp1a2", "1a2"],
    },
    {
        "pregunta": "¿Cómo se metaboliza el alprazolam?",
        "tabla": (268, "Tabla 9. Metabolismo de las benzodiazepinas"),
        "fichas": ["FT_Alprazolam.pdf"],
        "claves": ["cyp3a4", "3a4"],
    },
    {
        # Caso difícil a propósito: la tabla tiene dos columnas (Sustratos / Inhibidores)
        # y la extracción actual las junta. Estas claves son inhibidores que solo están ahí.
        "pregunta": "¿Qué fármacos son inhibidores del CYP2D6?",
        "tabla": (20, "Tabla 6. Sustratos e inhibidores del CYP2D6"),
        "fichas": [],
        "claves": ["imatinib", "pazopanib", "cinacalcet"],
        "dificil": True,
    },
]


def normalizar(texto):
    """Ignora diferencias invisibles: forma de los acentos, espacios y mayúsculas."""
    texto = unicodedata.normalize("NFC", texto)
    return "".join(texto.split()).lower()


def es_la_tabla(fragmento, caso):
    pagina, titulo = caso["tabla"]
    return (
        normalizar(fragmento["archivo"]) == normalizar(ARCHIVO)
        and int(fragmento["pagina"]) == pagina
        and normalizar(fragmento["texto"]).startswith(normalizar(titulo))
    )


def es_ficha_valida(fragmento, caso):
    return normalizar(fragmento["archivo"]) in {normalizar(f) for f in caso["fichas"]}


def main():
    usar_llm = "--llm" in sys.argv
    ok_tabla = ok_fuente = ok_respuesta = errores = 0

    # Si el nombre del libro no coincide, todas las pruebas fallarían: mejor avisar ya
    if normalizar(ARCHIVO) not in {normalizar(a) for a in rag.archivos}:
        parecidos = [a for a in rag.archivos if "interac" in a.lower()]
        raise SystemExit(f"No encuentro '{ARCHIVO}' en datos/. Cambia la línea ARCHIVO "
                         f"al principio de este script. Archivos parecidos: {parecidos}")

    for caso in CASOS:
        for clave in caso["claves"]:
            if clave in normalizar(caso["pregunta"]):
                print(f"AVISO: la clave '{clave}' está en la pregunta: el caso es demasiado fácil")

    for n, caso in enumerate(CASOS, start=1):
        etiqueta = " (difícil)" if caso.get("dificil") else ""
        print(f"\n[{n}] {caso['pregunta']}{etiqueta}")

        fragmentos = rag.recuperar(caso["pregunta"])
        p_tabla = next((i for i, f in enumerate(fragmentos, 1) if es_la_tabla(f, caso)), None)
        p_ficha = next((i for i, f in enumerate(fragmentos, 1) if es_ficha_valida(f, caso)), None)

        if p_tabla:
            ok_tabla += 1
            sim = fragmentos[p_tabla - 1]["similitud"]
            print(f"  TABLA     OK    puesto {p_tabla} de {len(fragmentos)} (similitud {sim:.3f})")
        else:
            pagina, titulo = caso["tabla"]
            print(f"  TABLA     FALLA no apareció '{titulo}' (pág. {pagina})")
        if p_tabla or p_ficha:
            ok_fuente += 1
            if not p_tabla:
                f = fragmentos[p_ficha - 1]
                print(f"  FUENTE    OK    {f['archivo']} pág. {f['pagina']} en el puesto {p_ficha}")
        else:
            print("  FUENTE    FALLA ninguna fuente válida; vinieron:")
            for f in fragmentos[:3]:
                print(f"            [{f['similitud']:.3f}] {f['archivo']} pág. {f['pagina']}: {f['texto'][:60]!r}")

        if usar_llm:
            try:
                respuesta = rag.responder(caso["pregunta"]).lower()
            except Exception as e:   # un error del proveedor no debe cortar toda la prueba
                print(f"  RESPUESTA ERROR {type(e).__name__}: {str(e)[:80]}")
                errores += 1
                continue
            if respuesta.startswith("["):   # aviso de rag.py: límite alcanzado o proveedor caído
                print(f"  RESPUESTA ERROR {respuesta[:110]}")
                errores += 1
                continue
            encontradas = [c for c in caso["claves"] if c in respuesta]
            if encontradas:
                ok_respuesta += 1
                print(f"  RESPUESTA OK    menciona: {', '.join(encontradas)}")
            else:
                print(f"  RESPUESTA FALLA no menciona ninguna de: {', '.join(caso['claves'])}")
                print(f"            empieza: {respuesta[:150]!r}")

    total = len(CASOS)
    print("\n" + "=" * 60)
    print(f"Tabla:     {ok_tabla}/{total} búsquedas encontraron la tabla")
    print(f"Fuente:    {ok_fuente}/{total} búsquedas encontraron una fuente válida (tabla o ficha)")
    if usar_llm:
        validas = total - errores
        print(f"Respuesta: {ok_respuesta}/{validas} respuestas mencionan las palabras clave")
        if errores:
            print(f"           ({errores} sin evaluar por errores del proveedor; vuelve a "
                  f"correr la prueba más tarde o cambia de modelo)")


if __name__ == "__main__":
    main()
