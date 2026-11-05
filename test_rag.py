# test_rag.py — pruebas unitarias de las funciones puras de rag.py
#
# Uso:  python -m pytest
#
# No necesitan el modelo de embeddings, ChromaDB, los PDFs de datos/ ni claves, y tardan
# menos de un segundo. La calidad de la búsqueda y de las respuestas se mide con probar_rag.py.

import pytest

from rag import _parecido, dividir_en_chunks, tabla_a_unidades


def pagina(texto, numero=1):
    return {"pagina": numero, "texto": texto}


def textos(chunks):
    return [c["texto"] for c in chunks]


# ---------------------------------------------------------------
# dividir_en_chunks
# ---------------------------------------------------------------
def test_chunks_se_solapan_y_cubren_todo_el_texto():
    chunks = dividir_en_chunks([pagina("a b c d e f g h i j")], tam=4, solape=1)
    assert textos(chunks) == ["a b c d", "d e f g", "g h i j"]


def test_chunks_texto_mas_corto_que_el_tamano_da_un_solo_fragmento():
    assert textos(dividir_en_chunks([pagina("a b c")], tam=4, solape=1)) == ["a b c"]


def test_chunks_texto_justo_del_tamano_no_deja_un_fragmento_sobrante():
    assert textos(dividir_en_chunks([pagina("a b c d")], tam=4, solape=1)) == ["a b c d"]


def test_chunks_ultimo_fragmento_puede_ser_mas_corto():
    chunks = dividir_en_chunks([pagina("a b c d e")], tam=4, solape=1)
    assert textos(chunks) == ["a b c d", "d e"]


def test_chunks_conservan_la_pagina_y_no_mezclan_paginas():
    chunks = dividir_en_chunks([pagina("a b", 3), pagina("c d", 7)], tam=4, solape=1)
    assert chunks == [{"pagina": 3, "texto": "a b"}, {"pagina": 7, "texto": "c d"}]


@pytest.mark.parametrize("paginas", [[], [pagina("")], [pagina("   ")]])
def test_chunks_sin_texto_no_dan_fragmentos(paginas):
    assert dividir_en_chunks(paginas, tam=4, solape=1) == []


# ---------------------------------------------------------------
# tabla_a_unidades
# ---------------------------------------------------------------
def test_tabla_por_filas_da_una_unidad_por_fila():
    filas = [["Fármaco", "Efecto"], ["litio", "toxicidad"], ["enalapril", "hipotensión"]]
    assert tabla_a_unidades(filas) == (
        "",
        ("Fármaco", "Efecto"),
        [("", "Fármaco: litio; Efecto: toxicidad"), ("", "Fármaco: enalapril; Efecto: hipotensión")],
    )


def test_tabla_por_filas_omite_las_celdas_vacias():
    _, _, unidades = tabla_a_unidades([["Fármaco", "Efecto"], ["litio", None], ["", "mareo"]])
    assert unidades == [("", "Fármaco: litio"), ("", "Efecto: mareo")]


def test_tabla_primera_fila_con_una_sola_celda_es_el_titulo():
    titulo, encabezado, unidades = tabla_a_unidades(
        [["Tabla 1. Riesgos", None], ["Fármaco", "Efecto"], ["litio", "toxicidad"]])
    assert titulo == "Tabla 1. Riesgos"
    assert encabezado == ("Fármaco", "Efecto")
    assert unidades == [("", "Fármaco: litio; Efecto: toxicidad")]


def test_tabla_por_categorias_da_una_unidad_por_categoria():
    # "Sustratos" abarca dos columnas: la celda vacía hereda la categoría de su izquierda
    filas = [["Sustratos", "", "Inhibidores"], ["a\nb\nc", "d\ne", "f\ng\nh\ni"]]
    assert tabla_a_unidades(filas) == (
        "",
        ("Sustratos", "Sustratos", "Inhibidores"),
        [("Sustratos", "a, b, c, d, e"), ("Inhibidores", "f, g, h, i")],
    )


def test_tabla_sin_encabezado_es_una_lista():
    assert tabla_a_unidades([["a\nb", "c"]]) == ("", None, [("", "a, b, c")])


def test_tabla_con_huecos_y_sin_listas_es_una_lista():
    filas = [["a", "", "b"], ["c", "", ""]]
    assert tabla_a_unidades(filas) == ("", None, [("", "a, b, c")])


def test_tabla_limpia_espacios_y_saltos_dentro_de_las_celdas():
    _, _, unidades = tabla_a_unidades([["Fármaco", "Efecto"], ["  litio ", "toxicidad\nrenal"]])
    assert unidades == [("", "Fármaco: litio; Efecto: toxicidad renal")]


@pytest.mark.parametrize("filas", [[], [[None, ""]], [["", " "], [None, None]]])
def test_tabla_vacia_no_da_unidades(filas):
    assert tabla_a_unidades(filas) == ("", None, [])


def test_tabla_con_solo_titulo_no_da_unidades():
    assert tabla_a_unidades([["Tabla 1. Riesgos", None]]) == ("Tabla 1. Riesgos", None, [])


# ---------------------------------------------------------------
# _parecido
# ---------------------------------------------------------------
def test_parecido_sin_palabras_en_comun_es_cero():
    assert _parecido("alfa beta", "gamma delta") == 0.0


def test_parecido_mismas_palabras_en_otro_orden_es_uno():
    assert _parecido("alfa beta gamma", "gamma beta alfa") == 1.0


def test_parecido_es_la_proporcion_de_palabras_compartidas():
    assert _parecido("alfa beta", "beta gamma") == pytest.approx(1 / 3)


def test_parecido_ignora_mayusculas_y_signos():
    assert _parecido("ALFA, beta.", "beta alfa") == 1.0


def test_parecido_ignora_palabras_de_tres_letras_o_menos():
    assert _parecido("de la alfa", "el un alfa") == 1.0


def test_parecido_sin_palabras_largas_es_cero():
    assert _parecido("de la", "el un") == 0.0


def test_parecido_filas_de_una_tabla_no_cuentan_el_titulo_que_repiten():
    titulo = "Tabla 1. Fármacos que pueden causar síndrome neuroléptico maligno: "
    assert _parecido(titulo + "sertralina", titulo + "fluoxetina") == 0.0


@pytest.mark.xfail(strict=True, reason="Error conocido: al quitar el comienzo común de dos textos "
                                       "iguales no queda nada que comparar y devuelve 0.0, no 1.0.")
def test_parecido_textos_identicos_es_uno():
    assert _parecido("alfa beta gamma", "alfa beta gamma") == 1.0
