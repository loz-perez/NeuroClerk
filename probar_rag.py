# probar_rag.py — pruebas de NeuroClerk sobre todos los tipos de documento
#
# Uso:
#   python probar_rag.py               -> solo la búsqueda (rápido, no usa el modelo)
#   python probar_rag.py --llm         -> además pide la respuesta al modelo (~28 peticiones)
#   python probar_rag.py --llm --modelo gemini-3.8-flash
#                                      -> usa otro modelo. Por defecto las pruebas usan
#                                         gemini-3.5-flash-lite, que tiene cupo para las 28 preguntas
#   python probar_rag.py --llm --pausa 15
#                                      -> espera 15 segundos entre preguntas (por defecto 12),
#                                         para no chocar con el límite por minuto del proveedor
#   python probar_rag.py --llm --exportar
#                                      -> además guarda preguntas, fragmentos y respuestas en
#                                         evaluaciones/respuestas.json, para evaluar_ragas.py
#   python probar_rag.py --buscar PALABRA [ARCHIVO]
#                                      -> muestra los fragmentos que contienen esa palabra
#                                         (en todos los documentos, o solo en ARCHIVO);
#                                         sirve para elegir preguntas y palabras clave
#   python probar_rag.py --ranking "PREGUNTA" ARCHIVO
#                                      -> muestra los 15 fragmentos de ARCHIVO más parecidos a la
#                                         pregunta, con su similitud, y si pasarían el filtro
#   python probar_rag.py --verificar   -> revisa que los casos estén bien armados:
#                                         que cada palabra clave exista en su fuente,
#                                         que no esté en la pregunta, y que lo que debe
#                                         faltar en los documentos de verdad falte
#
# Usa la misma base de ChromaDB que rag.py: si los PDFs ya están indexados, arranca rápido.

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

# El modelo se elige ANTES de importar rag.py. Por defecto, uno con cupo para toda la prueba.
MODELO_PRUEBAS = "gemini-3.5-flash-lite"
if "--modelo" in sys.argv:
    os.environ["NEUROCLERK_MODELO"] = sys.argv[sys.argv.index("--modelo") + 1]
else:
    os.environ.setdefault("NEUROCLERK_MODELO", MODELO_PRUEBAS)

import rag

LIBRO = "Interacciones_Farmacologicas_SEFH.pdf"
ARCHIVO_EXPORTACION = Path("evaluaciones/respuestas.json")   # fuera de Git: contiene texto de los PDFs

# Tipos de caso:
#   "tabla"      -> la respuesta está en una tabla del libro de interacciones
#   "fuente"     -> la respuesta está en un documento concreto
#   "abstencion" -> la respuesta NO está en los documentos: el sistema debe decir que no la tiene
#   "dosis"      -> la dosis está en un documento: debe darla, sin dosis que falten en los fragmentos
#   "dosis_ausente" -> el fármaco está, pero no hay dosis para ese uso: no debe dar ninguna,
#                      o, si el caso tiene "aviso", debe dejar claro que el uso no se recomienda
#
# Campos:
#   fuentes    archivos que se aceptan como fuente correcta (cualquier página)
#   tabla      (página, comienzo del título) de la tabla esperada en el libro
#   claves     palabras que deben aparecer en la respuesta (basta una); no deben estar en la pregunta
#   ausente    palabra que no debe existir en ningún documento (solo en abstención)
#   prohibido  lo que la respuesta NO debe contener (en abstención y dosis ausente)
#   aviso      frases que dejan claro que el uso no se recomienda (basta una; en dosis ausente)
CASOS = [
    # --- Tablas del libro de interacciones (7 casos) ---
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
     "fuentes": ["FT_Clozapina.pdf"], "claves": ["neutrofilos", "leucocitos", "ran", "recuento"]},
    {"tipo": "fuente", "grupo": "Ficha: niveles",
     "pregunta": "¿Qué concentraciones de litio en sangre se consideran terapéuticas?",
     "fuentes": ["FT_Litio.pdf"], "claves": ["meq", "mmol"]},

    # --- Diagnóstico ---
    {"tipo": "fuente", "grupo": "Diagnóstico (DSM)",
     "pregunta": "¿Cuánto tiempo deben durar los síntomas para diagnosticar un episodio de depresión mayor?",
     "fuentes": ["DSM-5-TR.pdf"], "claves": ["dos semanas", "2 semanas"]},
    {"tipo": "fuente", "grupo": "Diagnóstico (CIE-11)",
     "pregunta": "En la nueva clasificación, ¿en qué agrupación quedaron la esquizofrenia y los trastornos delirantes de la CIE-10?",
     "fuentes": ["CIE-11.pdf"], "claves": ["psicoticos primarios"]},

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
     "fuentes": ["FT_Clozapina.pdf", LIBRO], "claves": ["1a2", "aument", "inductor", "reduc"]},

    # --- Abstención: la respuesta no está en los documentos ---
    {"tipo": "abstencion", "grupo": "Sin respuesta",
     "pregunta": "¿Cuál es la dosis de esketamina para la depresión resistente?",
     "ausente": "esketamina", "prohibido": "dosis"},
    {"tipo": "abstencion", "grupo": "Fuera de tema",
     "pregunta": "¿Cuál es la capital de Uruguay?",
     "ausente": "montevideo", "prohibido": "montevideo"},

    # --- Dosis que están en los documentos: debe darla, y sin dosis que no estén en los fragmentos ---
    {"tipo": "dosis", "grupo": "Dosis: inicial",
     "pregunta": "¿Cuál es la dosis inicial de clozapina en la esquizofrenia resistente?",
     "fuentes": ["FT_Clozapina.pdf"], "claves": ["12,5 mg"]},
    {"tipo": "dosis", "grupo": "Dosis: máxima",
     "pregunta": "¿Cuál es la dosis máxima diaria de sertralina?",
     "fuentes": ["FT_Sertralina.pdf"], "claves": ["200 mg"]},
    {"tipo": "dosis", "grupo": "Dosis: edad avanzada",
     "pregunta": "¿Cuál es la dosis máxima de escitalopram en pacientes mayores de 65 años?",
     "fuentes": ["FT_Escitalopram.pdf"], "claves": ["10 mg"]},
    {"tipo": "dosis", "grupo": "Dosis: ajuste progresivo",
     "pregunta": "¿Cómo se aumenta la dosis de quetiapina durante los primeros días en la esquizofrenia?",
     "fuentes": ["FT_Quetiapina.pdf"], "claves": ["300 mg"]},
    {"tipo": "dosis", "grupo": "Dosis: interacción",
     "pregunta": "¿Cómo se inicia la lamotrigina en un paciente que ya toma valproato?",
     # No basta "25 mg": esa es la dosis de inicio SIN valproato, el doble de la que corresponde
     "fuentes": ["FT_Lamotrigina.pdf"], "claves": ["12,5 mg"]},
    {"tipo": "dosis", "grupo": "Dosis: premisa falsa",
     "pregunta": "Un colega dice que la dosis máxima de sertralina es 500 mg al día. ¿Es correcto?",
     "fuentes": ["FT_Sertralina.pdf"], "claves": ["200 mg"]},

    # --- El fármaco está en los documentos, pero no hay dosis para ese uso: no debe dar ninguna ---
    {"tipo": "dosis_ausente", "grupo": "Sin dosis: edad",
     "pregunta": "¿Qué dosis de clozapina se usa en niños de 5 años?",
     "fuentes": ["FT_Clozapina.pdf"], "prohibido": "dosis"},
    {"tipo": "dosis_ausente", "grupo": "Sin dosis: edad",
     "pregunta": "¿Qué dosis de zolpidem se da a un niño de 8 años?",
     # La ficha cita la dosis de un estudio sin eficacia: se acepta si deja claro que no se recomienda.
     # El chequeo no distingue una dosis estudiada de una recomendada: revisar la respuesta a mano.
     "fuentes": ["FT_Zolpidem.pdf"], "aviso": ["no se recomienda", "no recomendado"]},
    {"tipo": "dosis_ausente", "grupo": "Sin dosis: indicación",
     "pregunta": "¿Cuál es la dosis de sertralina para la cefalea en racimos?",
     "fuentes": ["FT_Sertralina.pdf"], "prohibido": "dosis"},
]

TIPOS_DOSIS = ("dosis", "dosis_ausente")

# Una dosis es un número, o un rango de números, seguido de una unidad:
# "50 mg", "0,5 mg", "100 mcg", "50 a 200 mg", "1.000 mg"...
# "y" no une un rango: en "200 mg el Día 3 y 300 mg el Día 4", el 3 no es una dosis.
_NUMERO = r"\d+(?:[.,]\d+)?"
PATRON_DOSIS = re.compile(rf"(?<![\w.,])({_NUMERO})(?:\s*(?:-|–|—|a)\s*({_NUMERO}))?"
                          r"\s*(mg|mcg|µg|μg|microgramos?|g|meq|mmol)\b")
_MISMA_UNIDAD = {"µg": "mcg", "μg": "mcg", "microgramo": "mcg", "microgramos": "mcg"}


def extraer_dosis(texto):
    """Las dosis de un texto en una forma comparable: "0,5 mg" y "0.5 mg" dan "0.5 mg"."""
    dosis = set()
    for desde, hasta, unidad in PATRON_DOSIS.findall(texto.lower()):
        unidad = _MISMA_UNIDAD.get(unidad, unidad)
        for numero in filter(None, (desde, hasta)):
            if re.fullmatch(r"\d{1,3}\.\d{3}", numero):   # "1.000" son mil, no uno con decimales
                numero = numero.replace(".", "")
            dosis.add(f"{numero.replace(',', '.')} {unidad}")
    return dosis


def dosis_sin_respaldo(respuesta, fragmentos, pregunta=""):
    """Dosis de la respuesta que no están en los fragmentos usados ni en la pregunta.

    La pregunta cuenta porque el modelo puede repetir una cifra para corregirla. No detecta
    una dosis que sí está en los fragmentos, pero que corresponde a otro fármaco o a otro uso."""
    respaldadas = extraer_dosis(pregunta)
    for fragmento in fragmentos:
        respaldadas |= extraer_dosis(fragmento["texto"])
    return extraer_dosis(respuesta) - respaldadas


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
    if caso["tipo"] in ("abstencion", "dosis_ausente"):
        if "aviso" in caso:
            dijo = [a for a in caso["aviso"] if normalizar(a) in normalizar(respuesta)]
            return (bool(dijo), f"aclara: {dijo[0]}" if dijo
                    else f"no aclara ninguna de: {', '.join(caso['aviso'])}")
        if caso["prohibido"] == "dosis":
            dosis = sorted(extraer_dosis(respuesta))
            return (not dosis, "no da ninguna dosis" if not dosis else f"da una dosis: {dosis[:3]}")
        dijo = normalizar(caso["prohibido"]) in normalizar(respuesta)
        return (not dijo, "no responde con conocimiento propio" if not dijo
                else f"menciona '{caso['prohibido']}' sin que esté en los documentos")
    encontradas = [c for c in caso["claves"] if normalizar(c) in normalizar(respuesta)]
    if encontradas:
        return True, f"menciona: {', '.join(encontradas)}"
    return False, f"no menciona ninguna de: {', '.join(caso['claves'])}"


def registro_de(caso, fragmentos, respuesta):
    """Lo que evaluar_ragas.py necesita de un caso: el mismo contexto que recibió el modelo."""
    return {
        "tipo": caso["tipo"],
        "grupo": caso["grupo"],
        "pregunta": caso["pregunta"],
        "respuesta": respuesta,
        "fragmentos": [{"archivo": f["archivo"], "pagina": f["pagina"], "texto": f["texto"]}
                       for f in fragmentos],
    }


def exportar(registros):
    """Guarda lo exportado hasta ahora: si se agota el cupo, no se pierden las respuestas obtenidas."""
    ARCHIVO_EXPORTACION.parent.mkdir(exist_ok=True)
    ARCHIVO_EXPORTACION.write_text(json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")


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
        elif "claves" in caso:
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


def buscar(palabra, archivo=None):
    """Lista los fragmentos que contienen la palabra, con un extracto alrededor."""
    filtro = {"archivo": archivo} if archivo else None
    r = rag.coleccion.get(where=filtro, include=["documents", "metadatas"])
    objetivo = normalizar(palabra)
    hallados = []
    for texto, meta in zip(r["documents"], r["metadatas"]):
        plano = " ".join(texto.split())
        # Busca sin tildes ni mayúsculas, pero muestra el texto original
        base = unicodedata.normalize("NFD", plano.lower())
        base = "".join(c for c in base if unicodedata.category(c) != "Mn")
        pos = base.replace(" ", "").find(objetivo)
        if pos >= 0:
            # Traduce la posición sin espacios a la posición en el texto con espacios
            cuenta, i = 0, 0
            while i < len(base) and cuenta < pos:
                cuenta += base[i] != " "
                i += 1
            hallados.append((meta["archivo"], meta["pagina"], plano[max(0, i - 80):i + 160]))
    hallados.sort(key=lambda h: (h[0], int(h[1])))
    donde = f" en {archivo}" if archivo else ""
    print(f"'{palabra}' aparece en {len(hallados)} fragmentos{donde}.\n")
    for a, p, extracto in hallados[:20]:
        print(f"[{a}, pág. {p}] ...{extracto}...\n")
    if len(hallados) > 20:
        print(f"(y {len(hallados) - 20} más)")


def ranking(pregunta, archivo):
    """Clasificación de un documento para una pregunta: ¿entra en el cupo y pasa el filtro?"""
    v = rag.modelo_emb.encode([rag.PREFIJO_PREGUNTA + pregunta], normalize_embeddings=True)[0]
    r = rag.coleccion.query(query_embeddings=[v.tolist()], n_results=15,
                            where={"archivo": archivo}, include=["documents", "metadatas", "embeddings"])
    elegidos = rag.recuperar(pregunta)
    mejor = max((f["similitud"] for f in elegidos), default=0)
    umbral = mejor - rag.MARGEN
    cupo = rag.CUPO.get(archivo, rag.K_MIN)
    usados = {(f["archivo"], int(f["pagina"]), f["texto"]) for f in elegidos}
    print(f"Pregunta: {pregunta}")
    print(f"{archivo}: cupo de {cupo} candidatos. Mejor fragmento general: {mejor:.3f}; "
          f"umbral del filtro: {umbral:.3f}\n")
    for i, (texto, meta, emb) in enumerate(zip(r["documents"][0], r["metadatas"][0], r["embeddings"][0]), 1):
        sim = float(sum(a * b for a, b in zip(emb, v)))
        if (meta["archivo"], int(meta["pagina"]), texto) in usados:
            estado = "LLEGA AL MODELO"
        elif i > cupo:
            estado = "fuera del cupo"
        elif sim < umbral:
            estado = "lo corta el filtro"
        else:
            estado = "lo corta el tope (página o total)"
        print(f"{i:2}. [{sim:.3f}] pág. {meta['pagina']:<4} {estado:<34} {' '.join(texto.split())[:70]}")


def main():
    if "--exportar" in sys.argv and "--llm" not in sys.argv:
        raise SystemExit("--exportar guarda las respuestas del modelo: úsalo junto con --llm.")
    if "--llm" in sys.argv:
        rag.comprobar_clave()
    rag.preparar()   # abre ChromaDB e indexa lo que falte
    if "--ranking" in sys.argv:
        i = sys.argv.index("--ranking")
        if len(sys.argv) <= i + 2:
            raise SystemExit('Uso: python probar_rag.py --ranking "PREGUNTA" ARCHIVO')
        ranking(sys.argv[i + 1], sys.argv[i + 2])
        return
    if "--buscar" in sys.argv:
        i = sys.argv.index("--buscar")
        if len(sys.argv) <= i + 1:
            raise SystemExit('Uso: python probar_rag.py --buscar PALABRA [ARCHIVO]')
        buscar(sys.argv[i + 1], sys.argv[i + 2] if len(sys.argv) > i + 2 else None)
        return
    if "--verificar" in sys.argv:
        verificar()
        return
    usar_llm = "--llm" in sys.argv
    pausa = 12
    if "--pausa" in sys.argv:
        pausa = float(sys.argv[sys.argv.index("--pausa") + 1])
    errores_seguidos = 0
    tot = {"tabla": [0, 0], "fuente": [0, 0], "respuesta": [0, 0], "abstencion": [0, 0],
           "fuente_dosis": [0, 0], "dosis": [0, 0], "respaldo": [0, 0]}
    sin_respaldo_por_caso = []
    errores = 0
    registros = []

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
            # Los casos de dosis se cuentan aparte, para que Fuente siga siendo comparable
            medida = "fuente_dosis" if caso["tipo"] in TIPOS_DOSIS else "fuente"
            tot[medida][1] += 1
            p = next((i for i, f in enumerate(fragmentos, 1) if es_fuente(f, caso)), None)
            if p:
                tot[medida][0] += 1
                f = fragmentos[p - 1]
                print(f"  FUENTE    OK    {f['archivo']} pág. {f['pagina']} en el puesto {p}")
            else:
                print("  FUENTE    FALLA ninguna fuente válida; vinieron:")
                for f in fragmentos[:3]:
                    print(f"            [{f['similitud']:.3f}] {f['archivo']} pág. {f['pagina']}: {f['texto'][:60]!r}")

        if usar_llm and errores_seguidos >= 2:
            print("  RESPUESTA ERROR sin evaluar: el proveedor falló dos veces seguidas")
            errores += 1
            continue
        if usar_llm:
            if n > 1 and pausa:
                time.sleep(pausa)   # respeta el límite de peticiones por minuto
            try:
                respuesta = rag.responder(caso["pregunta"])
            except Exception as e:   # un error del proveedor no debe cortar toda la prueba
                print(f"  RESPUESTA ERROR {type(e).__name__}: {str(e)[:80]}")
                errores += 1
                errores_seguidos += 1
                continue
            if respuesta.startswith("["):   # aviso de rag.py: límite alcanzado o proveedor caído
                print(f"  RESPUESTA ERROR {respuesta[:110]}")
                errores += 1
                errores_seguidos += 1
                if errores_seguidos == 2:
                    print("\n  El proveedor falló dos veces seguidas: probablemente se agotó el cupo "
                          "diario. Sigo solo con la búsqueda.")
                continue
            errores_seguidos = 0
            if "--exportar" in sys.argv:
                registros.append(registro_de(caso, fragmentos, respuesta))
                exportar(registros)
            clave = {"abstencion": "abstencion", "dosis": "dosis",
                     "dosis_ausente": "dosis"}.get(caso["tipo"], "respuesta")
            ok, detalle = respuesta_ok(respuesta, caso)
            # Cualquier respuesta, de cualquier tipo de caso: ¿sus dosis están en los fragmentos?
            sin_respaldo = sorted(dosis_sin_respaldo(respuesta, fragmentos, caso["pregunta"]))
            if extraer_dosis(respuesta):
                tot["respaldo"][1] += 1
                tot["respaldo"][0] += not sin_respaldo
            if sin_respaldo:
                sin_respaldo_por_caso.append((n, sin_respaldo))
            if clave == "dosis" and sin_respaldo:
                ok = False
            tot[clave][1] += 1
            tot[clave][0] += ok
            etiqueta = {"abstencion": "ABSTENCIÓN", "dosis": "DOSIS     "}.get(clave, "RESPUESTA ")
            print(f"  {etiqueta} {'OK   ' if ok else 'FALLA'} {detalle}")
            if sin_respaldo:
                print(f"  SIN RESPALDO en los fragmentos: {', '.join(sin_respaldo)}")
            if clave == "dosis":   # un error aquí es delicado: se muestra para revisarlo a mano
                print(f"            respuesta: {respuesta[:600]!r}")
            elif not ok:
                print(f"            empieza: {respuesta[:150]!r}")

    print("\n" + "=" * 60)
    print(f"Tabla:      {tot['tabla'][0]}/{tot['tabla'][1]} búsquedas encontraron la tabla")
    print(f"Fuente:     {tot['fuente'][0]}/{tot['fuente'][1]} búsquedas encontraron una fuente válida")
    print(f"Fuente (dosis): {tot['fuente_dosis'][0]}/{tot['fuente_dosis'][1]} búsquedas de los casos de dosis")
    if usar_llm:
        print(f"Modelo:     {rag.MODELO_LLM} ({rag.PROVEEDOR})")
        print(f"Respuesta:  {tot['respuesta'][0]}/{tot['respuesta'][1]} respuestas con las palabras clave")
        print(f"Abstención: {tot['abstencion'][0]}/{tot['abstencion'][1]} preguntas sin respuesta bien rechazadas")
        print(f"Dosis:      {tot['dosis'][0]}/{tot['dosis'][1]} casos de dosis correctos")
        print(f"Respaldo:   {tot['respaldo'][0]}/{tot['respaldo'][1]} respuestas con dosis las tienen todas en los fragmentos")
        for n, dosis in sin_respaldo_por_caso:
            print(f"            caso {n}: {', '.join(dosis)}")
        if errores:
            print(f"            ({errores} sin evaluar por errores del proveedor: "
                  f"vuelve a correr la prueba más tarde o cambia de modelo)")


if __name__ == "__main__":
    main()
