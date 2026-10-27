# probar_rag.py — pruebas de NeuroClerk sobre todos los tipos de documento
#
# Uso:
#   python probar_rag.py               -> solo la búsqueda (rápido, no usa el modelo)
#   python probar_rag.py --llm         -> además pide la respuesta al modelo (~19 peticiones)
#   python probar_rag.py --verificar   -> revisa que los casos estén bien armados:
#                                         que cada palabra clave exista en su fuente,
#                                         que no esté en la pregunta, y que lo que debe
#                                         faltar en los documentos de verdad falte
#
# Usa la misma base de ChromaDB que rag.py: si los PDFs ya están indexados, arranca rápido.

import re
import sys
import unicodedata

import rag   # al importarlo se abre ChromaDB y se indexa lo que falte

LIBRO = "Interacciones_Farmacologicas_SEFH.pdf"

# Tipos de caso:
#   "tabla"      -> la respuesta está en una tabla del libro de interacciones
#   "fuente"     -> la respuesta está en un documento concreto
#   "abstencion" -> la respuesta NO está en los documentos: el sistema debe decir que no la tiene
#
# Campos:
#   fuentes    archivos que se aceptan como fuente correcta (cualquier página)
#   tabla      (página, comienzo del título) de la tabla esperada en el libro
#   claves     palabras que deben aparecer en la respuesta (basta una); no deben estar en la pregunta
#   ausente    palabra que no debe existir en ningún documento (solo en abstención)
#   prohibido  lo que la respuesta NO debe contener (solo en abstención)
CASOS = [
    # --- Tablas del libro de interacciones (los 7 casos de probar_tablas.py) ---
    {"tipo": "tabla", "grupo": "Interacciones (tabla)",
     "pregunta": "¿Qué fármacos pueden causar síndrome neuroléptico maligno?",
     "tabla": (9, "Tabla 1. Fármacos que pueden causar Síndrome Neuroléptico Maligno"),
     "fuentes": [LIBRO], "claves": ["pergolida", "tiopropenazina", "tolcapona"]},
    {"tipo": "tabla", "grupo": "Interacciones (tabla)",
     "pregunta": "¿Qué fármacos pueden causar síndrome serotoninérgico?",
     "tabla": (10, "Tabla 2. Fármacos que pueden causar Síndrome Serotoninérgico"),
     "fuentes": [LIBRO], "claves": ["dapoxetina", "metiltionina", "tapentadol"]},
    {"tipo": "tabla", "grupo": "Interacciones (tabla)",
     "pregunta": "¿Qué fármacos pueden prolongar el segmento QT?",
     "tabla": (11, "Tabla 3. Fármacos que pueden prolongar el segmento QT"),
     "fuentes": [LIBRO], "claves": ["ebastina", "retigabina", "piperaquina", "eribulina"]},
    {"tipo": "tabla", "grupo": "Interacciones (tabla)",
     "pregunta": "¿Qué interacción tienen los IECA con el litio?",
     "tabla": (177, "Tabla 5. Interacciones farmacocinéticas de IECA"),
     "fuentes": [LIBRO, "FT_Litio.pdf", "FT_Enalapril.pdf"], "claves": ["toxicidad", "concentraci", "nivel"]},
    {"tipo": "tabla", "grupo": "Interacciones (tabla)",
     "pregunta": "¿Qué isoenzimas del citocromo P450 metabolizan la clozapina?",
     "tabla": (265, "Tabla 7. Isoformas del citocromo P450"),
     "fuentes": [LIBRO, "FT_Clozapina.pdf"], "claves": ["cyp1a2", "1a2"]},
    {"tipo": "tabla", "grupo": "Interacciones (tabla)",
     "pregunta": "¿Cómo se metaboliza el alprazolam?",
     "tabla": (268, "Tabla 9. Metabolismo de las benzodiazepinas"),
     "fuentes": [LIBRO, "FT_Alprazolam.pdf"], "claves": ["cyp3a4", "3a4"]},
    {"tipo": "tabla", "grupo": "Interacciones (tabla)",
     "pregunta": "¿Qué fármacos son inhibidores del CYP2D6?",
     "tabla": (20, "Tabla 6. Sustratos e inhibidores del CYP2D6"),
     "fuentes": [LIBRO], "claves": ["imatinib", "pazopanib", "cinacalcet"]},

    # --- Fichas técnicas ---
    {"tipo": "fuente", "grupo": "Ficha: dosis",
     "pregunta": "¿Cuál es la dosis inicial de sertralina en el tratamiento de la depresión?",
     "fuentes": ["FT_Sertralina.pdf"], "claves": ["50 mg"]},
    {"tipo": "fuente", "grupo": "Ficha: seguridad",
     "pregunta": "¿Qué controles de sangre requiere el tratamiento con clozapina?",
     "fuentes": ["FT_Clozapina.pdf"], "claves": ["neutrofilos", "leucocitos"]},
    {"tipo": "fuente", "grupo": "Ficha: niveles",
     "pregunta": "¿Qué concentraciones de litio en sangre se consideran terapéuticas?",
     "fuentes": ["FT_Litio.pdf"], "claves": ["meq", "mmol"]},

    # --- Diagnóstico ---
    {"tipo": "fuente", "grupo": "Diagnóstico (DSM)",
     "pregunta": "¿Cuánto tiempo deben durar los síntomas para diagnosticar un episodio de depresión mayor?",
     "fuentes": ["DSM-5-TR.pdf"], "claves": ["dos semanas", "2 semanas"]},
    {"tipo": "fuente", "grupo": "Diagnóstico (CIE-11)",
     "pregunta": "¿Qué código tiene la esquizofrenia en la clasificación internacional de enfermedades?",
     "fuentes": ["CIE-11.pdf"], "claves": ["6a20"]},

    # --- Guías, formulario, CYP y escalas ---
    {"tipo": "fuente", "grupo": "Guía (mhGAP)",
     "pregunta": "¿Qué antidepresivos se recomiendan para tratar la depresión en atención primaria?",
     "fuentes": ["Guia_mhGAP.pdf"], "claves": ["fluoxetina", "amitriptilina"]},
    {"tipo": "fuente", "grupo": "Formulario (MSP)",
     "pregunta": "¿Qué antipsicóticos están disponibles en el formulario terapéutico de Uruguay?",
     "fuentes": ["Formulario_Terapeutico_de_Medicamentos.pdf"], "claves": ["haloperidol", "risperidona"]},
    {"tipo": "fuente", "grupo": "CYP (Flockhart)",
     "pregunta": "¿Qué fármacos son inductores del CYP3A4?",
     "fuentes": ["Tabla_de_enzimas_CYP450_Flockhart_Table.pdf", LIBRO],
     "claves": ["rifampicina", "rifampin", "carbamazepina", "carbamazepine"]},
    {"tipo": "fuente", "grupo": "Escala",
     "pregunta": "¿Cómo se puntúa el PHQ-9 y cuál es el puntaje máximo?",
     "fuentes": ["PHQ-9_Spanish.pdf"], "claves": ["27"]},

    # --- Caso clínico que cruza fuentes ---
    {"tipo": "fuente", "grupo": "Caso clínico",
     "pregunta": "Un paciente con esquizofrenia tratado con clozapina deja de fumar. ¿Qué puede pasar?",
     "fuentes": ["FT_Clozapina.pdf", LIBRO], "claves": ["1a2", "aument"]},

    # --- Abstención: la respuesta no está en los documentos ---
    {"tipo": "abstencion", "grupo": "Sin respuesta",
     "pregunta": "¿Cuál es la dosis de esketamina para la depresión resistente?",
     "ausente": "esketamina", "prohibido": "dosis"},
    {"tipo": "abstencion", "grupo": "Fuera de tema",
     "pregunta": "¿Cuál es la capital de Uruguay?",
     "ausente": "montevideo", "prohibido": "montevideo"},
]

# Una dosis escrita como número + unidad: "50 mg", "0,5 mg", "100 mcg"...
PATRON_DOSIS = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|microgramos|g)\b")


def normalizar(texto):
    """Minúsculas, sin tildes y sin espacios: ignora diferencias invisibles."""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return "".join(texto.split())


def es_la_tabla(fragmento, caso):
    pagina, titulo = caso["tabla"]
    return (normalizar(fragmento["archivo"]) == normalizar(LIBRO)
            and int(fragmento["pagina"]) == pagina
            and normalizar(fragmento["texto"]).startswith(normalizar(titulo)))


def es_fuente(fragmento, caso):
    return normalizar(fragmento["archivo"]) in {normalizar(f) for f in caso.get("fuentes", [])}


def respuesta_ok(respuesta, caso):
    """Devuelve (aprobada, detalle)."""
    if caso["tipo"] == "abstencion":
        if caso["prohibido"] == "dosis":
            dosis = PATRON_DOSIS.findall(respuesta.lower())
            return (not dosis, "no da ninguna dosis" if not dosis else f"da una dosis: {dosis[:3]}")
        dijo = normalizar(caso["prohibido"]) in normalizar(respuesta)
        return (not dijo, "no responde con conocimiento propio" if not dijo
                else f"menciona '{caso['prohibido']}' sin que esté en los documentos")
    encontradas = [c for c in caso["claves"] if normalizar(c) in normalizar(respuesta)]
    if encontradas:
        return True, f"menciona: {', '.join(encontradas)}"
    return False, f"no menciona ninguna de: {', '.join(caso['claves'])}"


def textos_de(archivos):
    """Todos los fragmentos indexados de esos archivos, normalizados."""
    r = rag.coleccion.get(where={"archivo": {"$in": list(archivos)}}, include=["documents"])
    return [normalizar(d) for d in r["documents"]]


def verificar():
    """Revisa que los casos estén bien armados, contra los documentos reales."""
    print("Verificando los casos contra la base de ChromaDB...\n")
    problemas = 0
    presentes = {normalizar(a): a for a in rag.archivos}
    todos = None
    for n, caso in enumerate(CASOS, start=1):
        avisos = []
        faltan = [f for f in caso.get("fuentes", []) if normalizar(f) not in presentes]
        if faltan:
            avisos.append(f"no están en datos/: {', '.join(faltan)} (revisa el nombre del archivo)")
        if caso["tipo"] == "abstencion":
            if todos is None:
                todos = textos_de(rag.archivos)
            if any(normalizar(caso["ausente"]) in t for t in todos):
                avisos.append(f"'{caso['ausente']}' SÍ aparece en los documentos: el caso no sirve")
        else:
            en_pregunta = [c for c in caso["claves"] if normalizar(c) in normalizar(caso["pregunta"])]
            if en_pregunta:
                avisos.append(f"claves dentro de la pregunta: {', '.join(en_pregunta)}")
            fuentes_ok = [presentes[normalizar(f)] for f in caso["fuentes"] if normalizar(f) in presentes]
            if fuentes_ok:
                textos = textos_de(fuentes_ok)
                halladas = [c for c in caso["claves"] if any(normalizar(c) in t for t in textos)]
                if not halladas:
                    avisos.append("ninguna clave aparece en sus fuentes: cambia las claves")
                elif len(halladas) < len(caso["claves"]):
                    sobran = [c for c in caso["claves"] if c not in halladas]
                    avisos.append(f"claves que no están en las fuentes (se pueden quitar): {', '.join(sobran)}")
        estado = "OK   " if not avisos else "AVISO"
        print(f"[{n:2}] {estado} {caso['grupo']}: {caso['pregunta'][:60]}")
        for a in avisos:
            print(f"           - {a}")
        problemas += bool(avisos)
    print(f"\n{len(CASOS) - problemas}/{len(CASOS)} casos sin avisos.")


def main():
    if "--verificar" in sys.argv:
        verificar()
        return
    usar_llm = "--llm" in sys.argv
    tot = {"tabla": [0, 0], "fuente": [0, 0], "respuesta": [0, 0], "abstencion": [0, 0]}
    errores = 0

    for n, caso in enumerate(CASOS, start=1):
        print(f"\n[{n}] {caso['grupo']}: {caso['pregunta']}")
        fragmentos = rag.recuperar(caso["pregunta"])

        if "tabla" in caso:
            tot["tabla"][1] += 1
            p = next((i for i, f in enumerate(fragmentos, 1) if es_la_tabla(f, caso)), None)
            if p:
                tot["tabla"][0] += 1
                print(f"  TABLA     OK    puesto {p} de {len(fragmentos)} "
                      f"(similitud {fragmentos[p - 1]['similitud']:.3f})")
            else:
                print(f"  TABLA     FALLA no apareció '{caso['tabla'][1]}' (pág. {caso['tabla'][0]})")
        if caso.get("fuentes"):
            tot["fuente"][1] += 1
            p = next((i for i, f in enumerate(fragmentos, 1) if es_fuente(f, caso)), None)
            if p:
                tot["fuente"][0] += 1
                f = fragmentos[p - 1]
                print(f"  FUENTE    OK    {f['archivo']} pág. {f['pagina']} en el puesto {p}")
            else:
                print("  FUENTE    FALLA ninguna fuente válida; vinieron:")
                for f in fragmentos[:3]:
                    print(f"            [{f['similitud']:.3f}] {f['archivo']} pág. {f['pagina']}: {f['texto'][:60]!r}")

        if usar_llm:
            try:
                respuesta = rag.responder(caso["pregunta"])
            except Exception as e:   # un error del proveedor no debe cortar toda la prueba
                print(f"  RESPUESTA ERROR {type(e).__name__}: {str(e)[:80]}")
                errores += 1
                continue
            if respuesta.startswith("["):   # aviso de rag.py: límite alcanzado o proveedor caído
                print(f"  RESPUESTA ERROR {respuesta[:110]}")
                errores += 1
                continue
            clave = "abstencion" if caso["tipo"] == "abstencion" else "respuesta"
            ok, detalle = respuesta_ok(respuesta, caso)
            tot[clave][1] += 1
            tot[clave][0] += ok
            etiqueta = "ABSTENCIÓN" if clave == "abstencion" else "RESPUESTA "
            print(f"  {etiqueta} {'OK   ' if ok else 'FALLA'} {detalle}")
            if not ok:
                print(f"            empieza: {respuesta[:150]!r}")

    print("\n" + "=" * 60)
    print(f"Tabla:      {tot['tabla'][0]}/{tot['tabla'][1]} búsquedas encontraron la tabla")
    print(f"Fuente:     {tot['fuente'][0]}/{tot['fuente'][1]} búsquedas encontraron una fuente válida")
    if usar_llm:
        print(f"Respuesta:  {tot['respuesta'][0]}/{tot['respuesta'][1]} respuestas con las palabras clave")
        print(f"Abstención: {tot['abstencion'][0]}/{tot['abstencion'][1]} preguntas sin respuesta bien rechazadas")
        if errores:
            print(f"            ({errores} sin evaluar por errores del proveedor)")


if __name__ == "__main__":
    main()
