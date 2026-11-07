# soap.py — estructura una nota clínica en formato SOAP
#
# Uso:
#   python soap.py pruebas/nota_depresion.txt
#   python soap.py --todas
#   python soap.py --todas --salida evaluaciones/soap
#   python soap.py --todas --nube        # solo con notas ficticias
#
# Importar este archivo no tiene efectos: solo define funciones.
# Por defecto exige PROVEEDOR = "ollama": una nota clínica no debe salir de la computadora.
# --nube solo se justifica con las notas ficticias de pruebas/.

import argparse
import re
import unicodedata
from pathlib import Path

import rag

CARPETA_NOTAS = Path("pruebas")
SECCIONES = ("subjetivo", "objetivo", "analisis", "plan", "examen_mental")
TITULOS = {
    "subjetivo": "S — Subjetivo",
    "objetivo": "O — Objetivo",
    "analisis": "A — Análisis",
    "plan": "P — Plan",
    "examen_mental": "Examen del Estado Mental",
}

_REGLAS = """Eres un asistente clínico que ordena una nota de evolución en formato SOAP.

Reglas:
- Usa SOLO la información escrita en la nota. No agregues síntomas, signos, antecedentes, medicación, resultados de estudios ni datos sociales que no estén en el texto.
- Si un dato no está, escribe "no consta". No lo completes por lógica ni por lo que suele acompañar al cuadro.
- No cambies el sentido de la nota ni interpretes: separa lo que la persona refiere (Subjetivo) de lo que se observa (Objetivo) y de lo que se concluye (Análisis).
- El Examen del Estado Mental resume los hallazgos del examen que la nota describe (apariencia, conducta, lenguaje, ánimo, afecto, pensamiento, percepción, cognición, juicio, introspección). Si están en la nota, no escribas "no consta": cópialos ahí aunque también aparezcan en Objetivo. Solo escribe "no consta" para un elemento que la nota no menciona.
- En el Análisis, usa el diagnóstico o la impresión diagnóstica que la nota ya menciona; no agregues uno nuevo. Si la nota no lo menciona, escribe "no consta".
- El Plan solo puede contener lo que la nota indica o propone. No agregues tratamientos, estudios ni dosis nuevas.
- Ignora la línea "NOTA FICTICIA" y cualquier aclaración de que el texto es inventado.

Devuelve exactamente estas secciones, cada una en su propia línea, en español:
S — Subjetivo
O — Objetivo
A — Análisis
P — Plan
Examen del Estado Mental
"""

# Encabezados posibles: "S — Subjetivo", "Subjetivo:", "**O — Objetivo**", etc.
_PATRONES = (
    ("subjetivo", re.compile(r"^(?:s\s*[—–\-:]\s*(?:subjetivo\s*:?\s*)?|subjetivo\s*:?)\s*(.*)$", re.I)),
    ("objetivo", re.compile(r"^(?:o\s*[—–\-:]\s*(?:objetivo\s*:?\s*)?|objetivo\s*:?)\s*(.*)$", re.I)),
    ("analisis", re.compile(r"^(?:a\s*[—–\-:]\s*(?:an[aá]lisis\s*:?\s*)?|an[aá]lisis\s*:?)\s*(.*)$", re.I)),
    ("plan", re.compile(r"^(?:p\s*[—–\-:]\s*(?:plan\s*:?\s*)?|plan\s*:?)\s*(.*)$", re.I)),
    ("examen_mental", re.compile(r"^examen(?:\s+del\s+estado)?\s+mental\s*:?\s*(.*)$", re.I)),
)


def normalizar(texto):
    """Minúsculas y sin tildes, para comparar y para tests."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def cargar_notas(carpeta=CARPETA_NOTAS):
    """Las notas ficticias de pruebas/, ordenadas por nombre."""
    return [{"archivo": ruta.name, "texto": ruta.read_text(encoding="utf-8")}
            for ruta in sorted(Path(carpeta).glob("nota_*.txt"))]


def prompt_soap(nota):
    """El prompt completo: reglas, secciones esperadas y la nota."""
    return (
        _REGLAS
        + f"\nNota:\n{nota.strip()}\n\n"
        + "Devuelve solo las secciones pedidas, sin explicaciones ni la nota repetida."
    )


def dividir_secciones(texto):
    """Separa el texto del modelo en las cinco secciones. Devuelve solo las que aparecen."""
    secciones, actual = {}, None
    for linea in texto.splitlines():
        limpia = linea.strip().strip("*# ").strip()
        if not limpia:
            if actual:
                secciones[actual].append("")
            continue
        for nombre, patron in _PATRONES:
            encontrado = patron.match(limpia)
            if encontrado:
                actual = nombre
                secciones.setdefault(nombre, [])
                resto = encontrado.group(1).strip()
                if resto:
                    secciones[nombre].append(resto)
                break
        else:
            if actual:
                secciones[actual].append(limpia)
    return {nombre: "\n".join(lineas).strip()
            for nombre, lineas in secciones.items() if "\n".join(lineas).strip()}


def comprobar_privacidad(permitir_nube=False):
    """Una nota clínica no sale de la computadora salvo que se pida explícitamente."""
    if rag.PROVEEDOR != "ollama" and not permitir_nube:
        raise SystemExit(
            'El módulo SOAP usa PROVEEDOR = "ollama" para no enviar notas clínicas a la nube. '
            'Cambia PROVEEDOR en rag.py o usa --nube solo con las notas ficticias de pruebas/.'
        )


def estructurar(nota, permitir_nube=False):
    """Devuelve (texto crudo, secciones). El texto lo genera el modelo configurado en rag.py."""
    comprobar_privacidad(permitir_nube)
    if rag.PROVEEDOR != "ollama":
        rag.comprobar_clave()
    texto = "".join(rag.generar(prompt_soap(nota))).strip()
    return texto, dividir_secciones(texto)


def formatear(secciones):
    """Las secciones en texto legible, en el orden SOAP + examen mental."""
    return "\n\n".join(f"{TITULOS[nombre]}\n{secciones[nombre]}"
                       for nombre in SECCIONES if secciones.get(nombre))


def main():
    parser = argparse.ArgumentParser(description="Estructura notas clínicas ficticias en SOAP.")
    parser.add_argument("archivo", nargs="?", help="una nota de pruebas/; si se omite, lista las notas")
    parser.add_argument("--todas", action="store_true", help="procesa las cinco notas de pruebas/")
    parser.add_argument("--nube", action="store_true",
                        help="permite Gemini o Groq; solo para notas ficticias")
    parser.add_argument("--salida", help="carpeta donde guardar un .md por nota")
    args = parser.parse_args()

    if not args.nube:
        rag.PROVEEDOR = "ollama"
        rag.MODELO_LLM = rag.MODELOS["ollama"]

    if args.archivo:
        ruta = Path(args.archivo)
        if not ruta.exists():
            raise SystemExit(f"No encontré {ruta}")
        notas = [{"archivo": ruta.name, "texto": ruta.read_text(encoding="utf-8")}]
    elif args.todas:
        notas = cargar_notas()
        if not notas:
            raise SystemExit(f"No hay notas nota_*.txt en {CARPETA_NOTAS}/")
    else:
        print("Notas disponibles:")
        for nota in cargar_notas():
            print(f"  {CARPETA_NOTAS / nota['archivo']}")
        print("\nUso: python soap.py pruebas/nota_depresion.txt  o  python soap.py --todas")
        return

    if args.nube:
        print("AVISO: --nube envía la nota al proveedor. Solo debe usarse con las notas ficticias de pruebas/.")

    salida = Path(args.salida) if args.salida else None
    if salida:
        salida.mkdir(parents=True, exist_ok=True)

    for nota in notas:
        print(f"\n{'=' * 60}\n{nota['archivo']}\n{'=' * 60}")
        texto, secciones = estructurar(nota["texto"], permitir_nube=args.nube)
        faltan = [nombre for nombre in SECCIONES if not secciones.get(nombre)]
        if faltan:
            print(f"No pude separar: {', '.join(faltan)}. Texto del modelo:")
            print(texto)
            continue
        print(formatear(secciones))
        if salida:
            destino = salida / f"{Path(nota['archivo']).stem}.md"
            destino.write_text(f"# {nota['archivo']}\n\n{formatear(secciones)}\n", encoding="utf-8")
            print(f"\nGuardado en {destino}")


if __name__ == "__main__":
    main()
