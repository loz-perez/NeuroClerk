# probar_soap.py — mide el módulo SOAP con las cinco notas ficticias
#
# Uso:
#   python probar_soap.py              -> usa Ollama (gemma3:4b), local
#   python probar_soap.py --nube       -> usa el proveedor configurado en rag.py; solo notas ficticias
#   python probar_soap.py --modelo gemma3:4b --pausa 5
#
# No usa RAG ni ChromaDB: solo el modelo configurado en rag.py.

import sys
import time

import rag
import soap

CASOS = [
    {"archivo": "nota_depresion.txt",
     "claves": ["sertralina", "phq-9", "animo deprimido"]},
    {"archivo": "nota_esquizofrenia.txt",
     "claves": ["clozapina", "alucinaciones auditivas", "hemograma"]},
    {"archivo": "nota_bipolar.txt",
     "claves": ["litio", "litemia", "fuga de ideas"]},
    {"archivo": "nota_ansiedad.txt",
     "claves": ["escitalopram", "palpitaciones", "tension muscular"]},
    {"archivo": "nota_tdah.txt",
     "claves": ["metilfenidato", "tension arterial", "apetito"]},
]


def main():
    permitir_nube = "--nube" in sys.argv
    if not permitir_nube:
        rag.PROVEEDOR = "ollama"
        rag.MODELO_LLM = rag.MODELOS["ollama"]
    if "--modelo" in sys.argv:
        rag.MODELO_LLM = sys.argv[sys.argv.index("--modelo") + 1]
    pausa = float(sys.argv[sys.argv.index("--pausa") + 1]) if "--pausa" in sys.argv else 5
    if permitir_nube:
        rag.comprobar_clave()

    notas = {nota["archivo"]: nota["texto"] for nota in soap.cargar_notas()}
    secciones_ok = datos_ok = examen_ok = analisis_ok = 0
    for n, caso in enumerate(CASOS, start=1):
        print(f"\n[{n}] {caso['archivo']}")
        if caso["archivo"] not in notas:
            print("  FALLA no está en pruebas/")
            continue
        texto, secciones = soap.estructurar(notas[caso["archivo"]], permitir_nube=permitir_nube)
        if texto.startswith("["):
            print(f"  ERROR DEL PROVEEDOR: {texto[:120]}")
            continue
        faltan = [nombre for nombre in soap.SECCIONES if not secciones.get(nombre)]
        if faltan:
            print(f"  SECCIONES FALLA faltan: {', '.join(faltan)}")
        else:
            secciones_ok += 1
            print("  SECCIONES OK")
        examen = soap.normalizar(secciones.get("examen_mental", ""))
        if examen and examen != "no consta":
            examen_ok += 1
            print("  EXAMEN    OK")
        else:
            print("  EXAMEN    FALLA vacío o 'no consta'")
        analisis = soap.normalizar(secciones.get("analisis", ""))
        if analisis and analisis != "no consta":
            analisis_ok += 1
            print("  ANALISIS  OK")
        else:
            print("  ANALISIS  FALLA vacío o 'no consta'")
        plano = soap.normalizar(texto)
        halladas = [clave for clave in caso["claves"] if soap.normalizar(clave) in plano]
        if len(halladas) == len(caso["claves"]):
            datos_ok += 1
            print(f"  DATOS     OK    {', '.join(halladas)}")
        else:
            faltan_claves = [c for c in caso["claves"] if c not in halladas]
            print(f"  DATOS     FALLA faltan: {', '.join(faltan_claves)}")
        time.sleep(pausa)

    print("\n" + "=" * 60)
    print(f"Secciones: {secciones_ok}/{len(CASOS)} notas con las cinco secciones")
    print(f"Datos:     {datos_ok}/{len(CASOS)} notas con sus datos clave")
    print(f"Examen:    {examen_ok}/{len(CASOS)} notas con examen mental descrito")
    print(f"Análisis:  {analisis_ok}/{len(CASOS)} notas con análisis diagnóstico")
    if not permitir_nube:
        print(f"Modelo:    {rag.MODELO_LLM} (ollama)")


if __name__ == "__main__":
    main()
