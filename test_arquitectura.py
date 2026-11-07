"""Reglas de arquitectura ejecutables: imports permitidos entre módulos.

No necesita el modelo, la base, los PDFs ni claves. Si se agrega un import
cruzado, este test obliga a actualizar docs/ARQUITECTURA.md y esta tabla.
"""

import ast
from pathlib import Path

MODULOS = {"rag", "soap", "banco", "panel", "probar_rag", "probar_soap", "probar_tablas", "evaluar_ragas"}

PERMITIDOS = {
    "rag.py": set(),
    "soap.py": {"rag"},
    "probar_rag.py": {"rag"},
    "banco.py": {"rag", "probar_rag"},
    "panel.py": {"banco"},
    "probar_soap.py": {"rag", "soap"},
    "probar_tablas.py": {"rag"},
    "evaluar_ragas.py": set(),
    "descargar_fichas.py": set(),
    "revisar_datos.py": set(),
}


def imports_de(nombre):
    """Módulos del proyecto importados por un archivo, a nivel de módulo o dentro de funciones."""
    arbol = ast.parse(Path(nombre).read_text(encoding="utf-8"), filename=nombre)
    hallados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name in MODULOS:
                    hallados.add(alias.name)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module in MODULOS:
            hallados.add(nodo.module)
    return hallados


def test_las_dependencias_respetan_la_direccion():
    for archivo, permitidos in PERMITIDOS.items():
        hallados = imports_de(archivo)
        assert hallados <= permitidos, (
            f"{archivo} importa {sorted(hallados - permitidos)}; "
            f"permitidos: {sorted(permitidos)}. Si es a propósito, actualizar "
            "docs/ARQUITECTURA.md y esta tabla."
        )


def test_el_nucleo_no_importa_ningun_modulo_del_proyecto():
    assert imports_de("rag.py") == set()


def test_la_evaluacion_no_importa_el_rag():
    assert imports_de("evaluar_ragas.py") == set()


def test_no_hay_frameworks_en_el_nucleo():
    for archivo in ("rag.py", "soap.py", "probar_rag.py"):
        arbol = ast.parse(Path(archivo).read_text(encoding="utf-8"), filename=archivo)
        for nodo in ast.walk(arbol):
            nombres = []
            if isinstance(nodo, ast.Import):
                nombres = [alias.name for alias in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                nombres = [nodo.module]
            for nombre in nombres:
                assert not nombre.startswith(("langchain", "llama_index")), (
                    f"{archivo} importa {nombre}; el núcleo debe seguir sin framework"
                )
