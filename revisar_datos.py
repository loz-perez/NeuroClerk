# revisar_datos.py — revisa la carpeta datos/ antes de indexar
#
# Uso:  python revisar_datos.py
#
# Para cada PDF muestra páginas, si tiene texto legible, si está cifrado y si figura
# en fuentes.csv. Al final avisa de posibles problemas.

import csv
import re
from pathlib import Path

from pypdf import PdfReader

CARPETA = Path("datos")
REGISTRO = Path("fuentes.csv")


def revisar(ruta):
    info = {"archivo": ruta.name, "mb": ruta.stat().st_size / 1e6,
            "paginas": 0, "texto": False, "cifrado": False, "error": ""}
    try:
        lector = PdfReader(ruta)
        info["cifrado"] = lector.is_encrypted
        info["paginas"] = len(lector.pages)
        # Muestra de hasta 5 páginas repartidas por el documento
        n = info["paginas"]
        muestra = sorted({0, n // 4, n // 2, 3 * n // 4, n - 1}) if n else []
        texto = "".join((lector.pages[i].extract_text() or "") for i in muestra)
        info["texto"] = len(texto.strip()) > 100 * max(1, len(muestra))
    except Exception as e:
        info["error"] = str(e)[:60]
    return info


def main():
    pdfs = sorted(CARPETA.glob("*.pdf"))
    otros = sorted(p for p in CARPETA.iterdir() if p.is_file() and p.suffix.lower() != ".pdf")
    registrados = set()
    if REGISTRO.exists():
        with open(REGISTRO, encoding="utf-8", newline="") as f:
            registrados = {fila["archivo"] for fila in csv.DictReader(f)}

    print(f"{'Archivo':<45} {'MB':>6} {'Págs':>5}  Texto  En fuentes.csv")
    print("-" * 80)
    filas = [revisar(p) for p in pdfs]
    for r in filas:
        texto = "error" if r["error"] else ("sí" if r["texto"] else "NO")
        reg = "sí" if r["archivo"] in registrados else "NO"
        print(f"{r['archivo'][:45]:<45} {r['mb']:>6.1f} {r['paginas']:>5}  {texto:<5}  {reg}")

    total_pags = sum(r["paginas"] for r in filas)
    print("-" * 80)
    print(f"{len(filas)} PDFs · {total_pags} páginas · {sum(r['mb'] for r in filas):.0f} MB")

    problemas = []
    for r in filas:
        if r["error"]:
            problemas.append(f"{r['archivo']}: no se pudo abrir ({r['error']})")
        elif not r["texto"]:
            problemas.append(f"{r['archivo']}: casi sin texto; puede ser escaneado y rag.py no lo leerá")
        if r["archivo"] not in registrados:
            problemas.append(f"{r['archivo']}: falta en fuentes.csv")
        if re.search(r"\d{4,}", Path(r["archivo"]).stem) or " " in r["archivo"]:
            problemas.append(f"{r['archivo']}: nombre poco claro o con espacios; el modelo cita este nombre")
    for nombre in sorted(registrados - {r["archivo"] for r in filas}):
        problemas.append(f"{nombre}: figura en fuentes.csv pero no está en datos/")

    # Posibles duplicados: mismo nombre base ignorando mayúsculas, números y sufijos
    base = {}
    for r in filas:
        clave = re.sub(r"[^a-z]", "", Path(r["archivo"]).stem.lower().replace("ft_", ""))
        base.setdefault(clave, []).append(r["archivo"])
    for archivos in base.values():
        if len(archivos) > 1:
            problemas.append(f"posible duplicado: {', '.join(archivos)}")
    for p in otros:
        problemas.append(f"{p.name}: no es PDF; rag.py lo ignora")

    print("\nPROBLEMAS:" if problemas else "\nSin problemas: la carpeta está lista para indexar.")
    for p in problemas:
        print(f"  - {p}")


if __name__ == "__main__":
    main()
