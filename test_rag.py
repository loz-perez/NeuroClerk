# test_rag.py — pruebas unitarias de las funciones puras de rag.py
#
# Uso:  python -m pytest
#
# No necesitan el modelo de embeddings, ChromaDB, los PDFs de datos/ ni claves, y tardan
# menos de un segundo. La calidad de la búsqueda y de las respuestas se mide con probar_rag.py.

import sys
import time
from types import SimpleNamespace

import pytest

import rag
from probar_rag import dosis_sin_respaldo, extraer_dosis, respuesta_ok
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


# ---------------------------------------------------------------
# extraer_dosis y dosis_sin_respaldo (probar_rag.py)
# ---------------------------------------------------------------
@pytest.mark.parametrize("texto, esperado", [
    ("50 mg una vez al día", {"50 mg"}),
    ("50mg/día", {"50 mg"}),
    ("12,5 MG", {"12.5 mg"}),
    ("12.5 mg", {"12.5 mg"}),
    ("de 50 a 200 mg", {"50 mg", "200 mg"}),
    ("50-200 mg", {"50 mg", "200 mg"}),
    ("1.000 mg", {"1000 mg"}),
    ("100 microgramos", {"100 mcg"}),
    ("100 µg", {"100 mcg"}),
    ("0,6 mEq/l", {"0.6 meq"}),
    ("1 g", {"1 g"}),
])
def test_extraer_dosis_reconoce_las_formas_de_escribirla(texto, esperado):
    assert extraer_dosis(texto) == esperado


@pytest.mark.parametrize("texto", [
    "", "dos semanas", "CYP2D6", "50 pacientes", "página 12", "12 gotas", "27 puntos",
])
def test_extraer_dosis_ignora_lo_que_no_es_dosis(texto):
    assert extraer_dosis(texto) == set()


def test_extraer_dosis_no_confunde_un_numero_de_dia_con_una_dosis():
    assert extraer_dosis("200 mg el Día 3 y 300 mg el Día 4") == {"200 mg", "300 mg"}


CASO_CON_AVISO = {"tipo": "dosis_ausente", "aviso": ["no se recomienda", "no recomendado"]}


def test_aviso_acepta_la_dosis_de_un_estudio_si_aclara_que_no_se_recomienda():
    respuesta = "No se recomienda en niños. Un estudio con 0,25 mg/kg/día no demostró eficacia."
    assert respuesta_ok(respuesta, CASO_CON_AVISO)[0]


@pytest.mark.parametrize("respuesta", ["El contexto no alcanza para responder.", "Se dan 10 mg al día."])
def test_aviso_falla_si_no_aclara_que_no_se_recomienda(respuesta):
    assert not respuesta_ok(respuesta, CASO_CON_AVISO)[0]


def test_dosis_ausente_sin_aviso_sigue_sin_aceptar_ninguna_dosis():
    caso = {"tipo": "dosis_ausente", "prohibido": "dosis"}
    assert respuesta_ok("El contexto no alcanza.", caso)[0]
    assert not respuesta_ok("No se recomienda, pero se usan 10 mg.", caso)[0]


def test_dosis_sin_respaldo_avisa_de_la_que_no_esta_en_los_fragmentos():
    fragmentos = [{"texto": "La dosis máxima es de 200 mg/día."}]
    assert dosis_sin_respaldo("Máximo 200 mg; algunos usan 300 mg.", fragmentos) == {"300 mg"}


def test_dosis_sin_respaldo_acepta_otra_forma_de_escribir_la_misma_dosis():
    assert dosis_sin_respaldo("Empieza con 12.5 mg.", [{"texto": "12,5 mg el primer día"}]) == set()


def test_dosis_sin_respaldo_acepta_la_cifra_que_ya_estaba_en_la_pregunta():
    fragmentos = [{"texto": "La dosis máxima es de 200 mg/día."}]
    respuesta = "No: el máximo es 200 mg, no 500 mg."
    assert dosis_sin_respaldo(respuesta, fragmentos, "¿Es de 500 mg?") == set()
    assert dosis_sin_respaldo(respuesta, fragmentos) == {"500 mg"}


# ---------------------------------------------------------------
# generar: una respuesta sin confirmación de que terminó no se entrega
# ---------------------------------------------------------------
class ClienteFalso:
    """Imita al cliente de OpenAI: devuelve las respuestas indicadas, una por llamada."""

    def __init__(self, *respuestas):
        self.pendientes = list(respuestas)
        self.llamadas = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.crear))

    def crear(self, **parametros):
        assert "stream" not in parametros
        self.llamadas += 1
        texto, motivo = self.pendientes.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=motivo,
                                                        message=SimpleNamespace(content=texto))])


@pytest.fixture
def nube(monkeypatch):
    monkeypatch.setattr(rag, "PROVEEDOR", "gemini")
    monkeypatch.setattr(time, "sleep", lambda segundos: None)

    def usar(*respuestas):
        cliente = ClienteFalso(*respuestas)
        monkeypatch.setattr(rag, "_cliente", cliente)
        return cliente
    return usar


def test_generar_entrega_la_respuesta_que_termino_bien(nube):
    cliente = nube(("Completa", "stop"))
    assert "".join(rag.generar("p")) == "Completa"
    assert cliente.llamadas == 1


def test_generar_reintenta_si_no_se_indica_el_motivo_de_cierre(nube):
    cliente = nube(("Según los", None), ("Completa", "stop"))
    assert "".join(rag.generar("p")) == "Completa"
    assert cliente.llamadas == 2


def test_generar_avisa_y_no_entrega_el_trozo_si_nunca_termina(nube):
    cliente = nube(*[("Según los", None)] * 4)
    respuesta = "".join(rag.generar("p"))
    assert respuesta.startswith("[")   # así las pruebas lo cuentan como error y no como fallo
    assert "Según los" not in respuesta
    assert cliente.llamadas == 4


def test_generar_no_reintenta_si_se_alcanzo_el_limite_de_tokens(nube):
    cliente = nube(("Lista larga", "length"))
    respuesta = "".join(rag.generar("p"))
    assert respuesta.startswith("[") and "length" in respuesta
    assert "Lista larga" not in respuesta
    assert cliente.llamadas == 1


def test_generar_reintenta_si_termina_sin_texto(nube):
    cliente = nube((None, "stop"), ("Completa", "stop"))
    assert "".join(rag.generar("p")) == "Completa"
    assert cliente.llamadas == 2


@pytest.mark.parametrize("motivo, esperado", [
    ("stop", "Hola mundo"),
    ("length", "["),
    (None, "["),
])
def test_generar_con_ollama_revisa_el_motivo_de_cierre(monkeypatch, motivo, esperado):
    ChatResponse = pytest.importorskip("ollama").ChatResponse   # no está en requirements.txt
    # Tipos reales de la librería: en los trozos intermedios, leer ["done_reason"] lanza KeyError
    final = {"done_reason": motivo} if motivo else {}
    trozos = [ChatResponse(message={"role": "assistant", "content": "Hola "}),
              ChatResponse(message={"role": "assistant", "content": "mundo"}, **final)]
    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(chat=lambda **parametros: iter(trozos)))
    monkeypatch.setattr(rag, "PROVEEDOR", "ollama")
    assert "".join(rag.generar("p")).startswith(esperado)
