# descargar_fichas.py — descarga de CIMA (AEMPS) las fichas técnicas de DATOS.md
#
# Uso:
#   python descargar_fichas.py            -> descarga las que falten en datos/
#   python descargar_fichas.py --todas    -> vuelve a descargarlas todas
#
# Por cada principio activo elige UN medicamento comercializado (sin combinaciones),
# guarda su ficha como datos/FT_<Nombre>.pdf y actualiza fuentes.csv.

import csv
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

API = "https://cima.aemps.es/cima/rest/medicamentos"
CARPETA = Path("datos")
REGISTRO = Path("fuentes.csv")

# (término de búsqueda en CIMA, nombre del archivo)
FARMACOS = [
    # Antidepresivos ISRS
    ("fluoxetina", "Fluoxetina"), ("sertralina", "Sertralina"), ("paroxetina", "Paroxetina"),
    ("citalopram", "Citalopram"), ("escitalopram", "Escitalopram"), ("fluvoxamina", "Fluvoxamina"),
    # Otros antidepresivos
    ("venlafaxina", "Venlafaxina"), ("duloxetina", "Duloxetina"), ("mirtazapina", "Mirtazapina"),
    ("bupropion", "Bupropion"), ("trazodona", "Trazodona"), ("vortioxetina", "Vortioxetina"),
    ("agomelatina", "Agomelatina"),
    # Tricíclicos e IMAO
    ("amitriptilina", "Amitriptilina"), ("clomipramina", "Clomipramina"), ("moclobemida", "Moclobemida"),
    # Antipsicóticos
    ("haloperidol", "Haloperidol"), ("risperidona", "Risperidona"), ("paliperidona", "Paliperidona"),
    ("olanzapina", "Olanzapina"), ("quetiapina", "Quetiapina"), ("aripiprazol", "Aripiprazol"),
    ("clozapina", "Clozapina"), ("ziprasidona", "Ziprasidona"), ("amisulprida", "Amisulprida"),
    ("lurasidona", "Lurasidona"), ("cariprazina", "Cariprazina"),
    # Estabilizadores del ánimo
    ("litio", "Litio"), ("valproico", "Valproato"), ("carbamazepina", "Carbamazepina"),
    ("oxcarbazepina", "Oxcarbazepina"), ("lamotrigina", "Lamotrigina"),
    # Ansiolíticos e hipnóticos
    ("alprazolam", "Alprazolam"), ("lorazepam", "Lorazepam"), ("clonazepam", "Clonazepam"),
    ("diazepam", "Diazepam"), ("zolpidem", "Zolpidem"),
    # TDAH
    ("metilfenidato", "Metilfenidato"), ("atomoxetina", "Atomoxetina"),
    ("lisdexanfetamina", "Lisdexanfetamina"),
    # Adicciones
    ("naltrexona", "Naltrexona"), ("disulfiram", "Disulfiram"), ("buprenorfina", "Buprenorfina"),
    ("metadona", "Metadona"),
    # No psiquiátricos que interaccionan a menudo
    ("tramadol", "Tramadol"), ("warfarina", "Warfarina"), ("enalapril", "Enalapril"),
    ("ibuprofeno", "Ibuprofeno"), ("claritromicina", "Claritromicina"), ("linezolid", "Linezolid"),
    ("ciprofloxacino", "Ciprofloxacino"),
]

COLUMNAS = ["archivo", "titulo", "tipo", "editor", "url", "edicion_o_version",
            "fecha_descarga", "acceso", "notas"]


def sin_tildes(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def pedir_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def ficha_tecnica(medicamento):
    for doc in medicamento.get("docs") or []:
        if doc.get("tipo") == 1 and doc.get("url"):
            return doc
    return None


def puntaje(medicamento, termino):
    """Más alto = mejor candidato. Prefiere monofármacos, vía oral y el original."""
    vtm = medicamento.get("vtm") or ""
    if isinstance(vtm, dict):          # CIMA lo devuelve como {"id": ..., "nombre": "litio"}
        vtm = vtm.get("nombre") or ""
    vtm = sin_tildes(vtm)
    # Palabra completa: "citalopram" no debe coincidir con "escitalopram"
    if not re.search(rf"\b{re.escape(termino)}\b", vtm) or "+" in vtm or " y " in vtm:
        return None   # combinación u otro principio activo
    if not ficha_tecnica(medicamento):
        return None
    vias = sin_tildes(json.dumps(medicamento.get("viasAdministracion") or "", ensure_ascii=False))
    p = 0
    if "oral" in vias or "sublingual" in vias:
        p += 2
    if not medicamento.get("generico"):
        p += 1
    return p


def elegir(termino):
    url = f"{API}?{urllib.parse.urlencode({'practiv1': termino, 'comerc': 1})}"
    resultados = pedir_json(url).get("resultados") or []
    candidatos = [(puntaje(m, termino), m) for m in resultados]
    candidatos = [(p, m) for p, m in candidatos if p is not None]
    if not candidatos:
        return None
    return max(candidatos, key=lambda x: x[0])[1]


def leer_registro():
    if not REGISTRO.exists():
        return {}
    with open(REGISTRO, encoding="utf-8", newline="") as f:
        return {fila["archivo"]: fila for fila in csv.DictReader(f)}


def guardar_registro(filas):
    with open(REGISTRO, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        for fila in filas.values():
            escritor.writerow({c: fila.get(c, "") for c in COLUMNAS})


def main():
    todas = "--todas" in sys.argv
    CARPETA.mkdir(exist_ok=True)
    registro = leer_registro()
    hoy = date.today().isoformat()
    bajadas, saltadas, fallos = 0, 0, []

    for termino, nombre in FARMACOS:
        archivo = f"FT_{nombre}.pdf"
        destino = CARPETA / archivo
        if destino.exists() and not todas:
            saltadas += 1
            continue
        try:
            med = elegir(termino)
            if not med:
                fallos.append(f"{nombre}: no encontré un medicamento comercializado con ficha")
                continue
            doc = ficha_tecnica(med)
            urllib.request.urlretrieve(doc["url"], destino)
            revision = ""
            if doc.get("fecha"):
                revision = datetime.fromtimestamp(doc["fecha"] / 1000).date().isoformat()
            registro[archivo] = {
                "archivo": archivo,
                "titulo": f"Ficha técnica de {nombre.lower()} ({med.get('nombre', '')})",
                "tipo": "ficha",
                "editor": "AEMPS (CIMA)",
                "url": doc["url"],
                "edicion_o_version": f"nregistro {med.get('nregistro')}; revisión {revision}",
                "fecha_descarga": hoy,
                "acceso": "público",
                "notas": "",
            }
            bajadas += 1
            print(f"OK    {archivo:<28} {med.get('nombre', '')}")
        except Exception as e:
            fallos.append(f"{nombre}: {e}")
        time.sleep(0.5)   # no saturar el servidor de CIMA

    guardar_registro(registro)
    print(f"\nDescargadas: {bajadas} · Ya estaban: {saltadas} · Fallos: {len(fallos)}")
    for f in fallos:
        print(f"  FALLO {f}")
    if fallos:
        print("Para los fallos, prueba otro término de búsqueda en la lista FARMACOS "
              "o descarga la ficha a mano desde https://cima.aemps.es")


if __name__ == "__main__":
    main()