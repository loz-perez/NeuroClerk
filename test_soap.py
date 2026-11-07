# test_soap.py — pruebas de las funciones puras de soap.py
#
# Uso: python -m pytest test_soap.py
# No necesitan el modelo, la base, los PDFs ni claves.

from pathlib import Path

import pytest

import rag
import soap

TEXTO = """S — Subjetivo
Refiere ánimo bajo.
O — Objetivo
No consta peso.
A — Análisis
Episodio depresivo.
P — Plan
Continuar sertralina.
Examen del Estado Mental
Ánimo deprimido, sin ideación suicida.
"""


def test_cargar_notas_encuentra_las_cinco():
    notas = soap.cargar_notas()
    assert len(notas) == 5
    assert all(nota["archivo"].startswith("nota_") for nota in notas)
    assert all("NOTA FICTICIA" in nota["texto"] for nota in notas)


def test_las_notas_no_estan_en_datos():
    assert not list(Path("datos").glob("nota_*.txt"))


def test_prompt_incluye_la_nota_y_las_reglas():
    prompt = soap.prompt_soap("texto de prueba")
    assert "texto de prueba" in prompt
    assert "no consta" in prompt.lower()
    assert "S — Subjetivo" in prompt


def test_dividir_secciones_reconoce_los_encabezados():
    secciones = soap.dividir_secciones(TEXTO)
    assert set(secciones) == set(soap.SECCIONES)
    assert "ánimo bajo" in secciones["subjetivo"]
    assert "no consta peso" in secciones["objetivo"].lower()
    assert "episodio depresivo" in secciones["analisis"].lower()
    assert "sertralina" in secciones["plan"]
    assert "sin ideación suicida" in secciones["examen_mental"]


def test_dividir_secciones_acepta_markdown_y_puntos():
    texto = "**S — Subjetivo**\nRefiere insomnio.\n**O — Objetivo:**\nNo consta.\n"
    secciones = soap.dividir_secciones(texto)
    assert secciones["subjetivo"] == "Refiere insomnio."
    assert secciones["objetivo"] == "No consta."


def test_dividir_secciones_acepta_letras_solas():
    texto = "S — Refiere insomnio.\nO — No consta.\nA — Episodio depresivo.\nP — Control en 2 semanas.\n"
    secciones = soap.dividir_secciones(texto)
    assert set(secciones) == {"subjetivo", "objetivo", "analisis", "plan"}
    assert secciones["subjetivo"] == "Refiere insomnio."
    assert secciones["plan"] == "Control en 2 semanas."


def test_dividir_secciones_sin_encabezados_devuelve_vacio():
    assert soap.dividir_secciones("Solo texto sin secciones.") == {}


def test_estructurar_rechaza_la_nube_sin_permiso(monkeypatch):
    monkeypatch.setattr(rag, "PROVEEDOR", "gemini")
    with pytest.raises(SystemExit):
        soap.estructurar("nota", permitir_nube=False)


def test_estructurar_usa_el_generador_y_separa(monkeypatch):
    monkeypatch.setattr(rag, "PROVEEDOR", "ollama")
    monkeypatch.setattr(rag, "generar", lambda prompt: iter([TEXTO]))
    texto, secciones = soap.estructurar("nota")
    assert texto == TEXTO.strip()
    assert set(secciones) == set(soap.SECCIONES)


def test_formatear_respeta_el_orden_soap():
    texto = soap.formatear(soap.dividir_secciones(TEXTO))
    assert texto.startswith("S — Subjetivo")
    assert texto.index("O — Objetivo") < texto.index("A — Análisis") < texto.index("P — Plan")
    assert texto.index("P — Plan") < texto.index("Examen del Estado Mental")
