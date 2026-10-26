# probar_tablas.py — comprueba que las tablas extraídas con pdfplumber se encuentran
#
# Uso:
#   python probar_tablas.py          -> solo la búsqueda (rápido, no usa Ollama)
#   python probar_tablas.py --llm    -> además pide la respuesta al modelo y revisa
#                                       que mencione datos que solo están en la tabla
#
# Usa la misma base de ChromaDB que rag.py: si los PDFs ya están indexados, arranca rápido.

import sys

import rag   # al importarlo se abre ChromaDB y se indexa lo que falte

ARCHIVO = "InteraccionesFarmacoloigicas_pr.pdf"

# Cada caso: una pregunta, la tabla que debería aparecer entre los fragmentos usados
# y palabras que están en esa tabla pero no en el texto normal de alrededor.
CASOS = [
    {
        "pregunta": "¿Qué fármacos pueden causar síndrome neuroléptico maligno?",
        "pagina": 9,
        "titulo": "Tabla 1. Fármacos que pueden causar Síndrome Neuroléptico Maligno",
        "claves": ["amantadina", "tolcapona", "metilfenidato"],
    },
    {
        "pregunta": "¿Qué fármacos pueden causar síndrome serotoninérgico?",
        "pagina": 10,
        "titulo": "Tabla 2. Fármacos que pueden causar Síndrome Serotoninérgico",
        "claves": ["tramadol", "linezolid", "dextrometorfano"],
    },
    {
        "pregunta": "¿Qué fármacos pueden prolongar el segmento QT?",
        "pagina": 11,
        "titulo": "Tabla 3. Fármacos que pueden prolongar el segmento QT",
        "claves": ["metadona", "quetiapina", "citalopram"],
    },
    {
        "pregunta": "¿Qué interacción tienen los IECA con el litio?",
        "pagina": 177,
        "titulo": "Tabla 5. Interacciones farmacocinéticas de IECA",
        "claves": ["litio", "excreción"],
    },
    {
        "pregunta": "¿Qué isoenzimas del citocromo P450 metabolizan la clozapina?",
        "pagina": 265,
        "titulo": "Tabla 7. Isoformas del citocromo P450",
        "claves": ["cyp1a2"],
    },
    {
        "pregunta": "¿Cómo se metaboliza el alprazolam?",
        "pagina": 268,
        "titulo": "Tabla 9. Metabolismo de las benzodiazepinas",
        "claves": ["cyp3a4"],
    },
    {
        # Caso difícil a propósito: esta tabla tiene dos columnas (Sustratos / Inhibidores)
        # y la extracción actual las junta en una sola lista. Puede fallar la respuesta.
        "pregunta": "¿Qué fármacos son inhibidores del CYP2D6?",
        "pagina": 20,
        "titulo": "Tabla 6. Sustratos e inhibidores del CYP2D6",
        "claves": ["paroxetina", "bupropi"],
        "dificil": True,
    },
]


def es_la_tabla(fragmento, caso):
    return (
        fragmento["archivo"] == ARCHIVO
        and fragmento["pagina"] == caso["pagina"]
        and fragmento["texto"].startswith(caso["titulo"])
    )


def main():
    usar_llm = "--llm" in sys.argv
    ok_busqueda = ok_respuesta = 0

    for n, caso in enumerate(CASOS, start=1):
        etiqueta = " (difícil)" if caso.get("dificil") else ""
        print(f"\n[{n}] {caso['pregunta']}{etiqueta}")

        fragmentos = rag.recuperar(caso["pregunta"])
        posicion = next((i for i, f in enumerate(fragmentos, 1) if es_la_tabla(f, caso)), None)

        if posicion:
            ok_busqueda += 1
            sim = fragmentos[posicion - 1]["similitud"]
            print(f"  BÚSQUEDA  OK    tabla en el puesto {posicion} de {len(fragmentos)} (similitud {sim:.3f})")
        else:
            print(f"  BÚSQUEDA  FALLA no apareció '{caso['titulo']}' (pág. {caso['pagina']})")
            for f in fragmentos[:3]:
                print(f"            vino: [{f['similitud']:.3f}] {f['archivo']} pág. {f['pagina']}: {f['texto'][:60]}...")

        if usar_llm:
            respuesta = rag.responder(caso["pregunta"]).lower()
            encontradas = [c for c in caso["claves"] if c in respuesta]
            if encontradas:
                ok_respuesta += 1
                print(f"  RESPUESTA OK    menciona: {', '.join(encontradas)}")
            else:
                print(f"  RESPUESTA FALLA no menciona ninguna de: {', '.join(caso['claves'])}")

    total = len(CASOS)
    print("\n" + "=" * 60)
    print(f"Búsqueda:  {ok_busqueda}/{total} tablas encontradas")
    if usar_llm:
        print(f"Respuesta: {ok_respuesta}/{total} respuestas usan datos de la tabla")


if __name__ == "__main__":
    main()