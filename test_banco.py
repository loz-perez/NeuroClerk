# test_banco.py — pruebas de las funciones de banco.py: sin el modelo, la base, los PDFs ni claves

import pytest

import banco


class ProbarRagFalso:
    """Lo que banco.py usa de probar_rag.py, sin importar rag.py."""

    normalizar = staticmethod(lambda texto: "".join(texto.lower().split()))
    es_la_tabla = staticmethod(lambda f, caso: f["pagina"] == caso["tabla"][0])
    es_fuente = staticmethod(lambda f, caso: f["archivo"] in caso["fuentes"])
    respuesta_ok = staticmethod(lambda respuesta, caso: ("bien" in respuesta, "detalle"))
    dosis_sin_respaldo = staticmethod(lambda respuesta, fragmentos, pregunta: {"99 mg"} if "99 mg" in respuesta else set())
    extraer_dosis = staticmethod(lambda respuesta: {"99 mg"} if "mg" in respuesta else set())


def fila(pregunta="p", tipo="fuente", **medidas):
    return {"grupo": "g", "tipo": tipo, "pregunta": pregunta, "n_fragmentos": 4, "fragmentos": [],
            "tabla_ok": None, "fuente_ok": None, "contexto_ok": None, "respuesta_ok": None,
            "sin_respaldo": [], **medidas}


def test_expandir_ajustes_arma_todas_las_combinaciones():
    configuraciones = banco.expandir_ajustes(["margen=0.03,0.05", "max_fragmentos=12,20"])
    assert len(configuraciones) == 4
    assert {"margen": 0.05, "max_fragmentos": 20} in configuraciones


def test_expandir_ajustes_sin_ajustes_mide_la_configuracion_base():
    assert banco.expandir_ajustes(None) == [{}]


@pytest.mark.parametrize("ajuste", ["margen", "margen=", "desconocido=1", "max_fragmentos=muchos"])
def test_expandir_ajustes_rechaza_lo_mal_escrito(ajuste):
    with pytest.raises(ValueError):
        banco.expandir_ajustes([ajuste])


def test_nombre_de():
    assert banco.nombre_de({}) == "base"
    assert banco.nombre_de({"margen": 0.05}) == "margen=0.05"
    assert banco.nombre_de({"margen": 0.05}, "prueba") == "prueba margen=0.05"
    assert banco.nombre_de({}, "prueba") == "prueba"


def test_calcular_cupos_respeta_los_limites():
    cupos = banco.calcular_cupos({"chico": 10, "medio": 700, "enorme": 90000}, 3, 15, 100)
    assert cupos == {"chico": 3, "medio": 7, "enorme": 15}


def test_contexto_detecta_la_fuente_correcta_sin_el_dato():
    """El motivo de esta medida: el documento llega, pero no la página que tiene la respuesta."""
    caso = {"fuentes": ["PHQ-9.pdf"], "claves": ["27"]}
    fragmentos = [{"archivo": "PHQ-9.pdf", "pagina": 1, "texto": "Durante las últimas dos semanas"}]
    medida = banco.medir_busqueda(caso, fragmentos, ProbarRagFalso)
    assert medida == {"tabla_ok": None, "fuente_ok": True, "contexto_ok": False}


def test_contexto_ignora_espacios_y_mayusculas():
    caso = {"claves": ["12,5 mg"]}
    fragmentos = [{"archivo": "a.pdf", "pagina": 1, "texto": "Iniciar con 12,5  MG al día"}]
    assert banco.medir_busqueda(caso, fragmentos, ProbarRagFalso)["contexto_ok"] is True


def test_medidas_que_no_aplican_quedan_vacias():
    medida = banco.medir_busqueda({"tipo": "abstencion"}, [], ProbarRagFalso)
    assert medida == {"tabla_ok": None, "fuente_ok": None, "contexto_ok": None}


def test_tabla_se_mide_solo_si_el_caso_tiene_tabla():
    caso = {"tabla": (9, "Tabla 1")}
    assert banco.medir_busqueda(caso, [{"archivo": "a", "pagina": 9, "texto": ""}], ProbarRagFalso)["tabla_ok"] is True
    assert banco.medir_busqueda(caso, [{"archivo": "a", "pagina": 8, "texto": ""}], ProbarRagFalso)["tabla_ok"] is False


def test_dosis_sin_respaldo_hace_fallar_un_caso_de_dosis():
    medida = banco.medir_respuesta({"tipo": "dosis", "pregunta": "p"}, [], "bien, 99 mg", ProbarRagFalso)
    assert medida["medida_respuesta"] == "dosis"
    assert medida["respuesta_ok"] is False
    assert medida["sin_respaldo"] == ["99 mg"]


def test_dosis_sin_respaldo_no_cambia_un_caso_de_otro_tipo():
    medida = banco.medir_respuesta({"tipo": "fuente", "pregunta": "p"}, [], "bien, 99 mg", ProbarRagFalso)
    assert medida["medida_respuesta"] == "respuesta"
    assert medida["respuesta_ok"] is True


def test_resumir_separa_la_fuente_de_los_casos_de_dosis():
    resumen = banco.resumir([
        fila(fuente_ok=True, contexto_ok=False),
        fila(fuente_ok=False, contexto_ok=True),
        fila(tipo="dosis", fuente_ok=True, contexto_ok=True),
        fila(tipo="dosis_ausente", fuente_ok=False),
    ])
    assert resumen["fuente"] == {"aciertos": 1, "casos": 2}
    assert resumen["fuente_dosis"] == {"aciertos": 1, "casos": 2}
    assert resumen["contexto"] == {"aciertos": 2, "casos": 3}
    assert "tabla" not in resumen
    assert resumen["fragmentos_promedio"] == 4


def test_resumir_cuenta_respuestas_respaldo_y_errores():
    resumen = banco.resumir([
        fila(medida_respuesta="dosis", respuesta_ok=False, tiene_dosis=True, sin_respaldo=["99 mg"]),
        fila(medida_respuesta="dosis", respuesta_ok=True, tiene_dosis=True),
        fila(medida_respuesta="respuesta", respuesta_ok=True),
        fila(error="[límite]"),
    ])
    assert resumen["dosis"] == {"aciertos": 1, "casos": 2}
    assert resumen["respuesta"] == {"aciertos": 1, "casos": 1}
    assert resumen["respaldo"] == {"aciertos": 1, "casos": 2}
    assert resumen["errores"] == 1


def test_comparar_casos_separa_mejoras_y_empeoramientos():
    a = [fila("uno", contexto_ok=False), fila("dos", fuente_ok=True), fila("tres", contexto_ok=True)]
    b = [fila("uno", contexto_ok=True), fila("dos", fuente_ok=False), fila("tres", contexto_ok=True)]
    cambios = banco.comparar_casos(a, b)
    assert [(c["pregunta"], c["medida"]) for c in cambios["mejoras"]] == [("uno", "contexto")]
    assert [(c["pregunta"], c["medida"]) for c in cambios["empeoran"]] == [("dos", "fuente")]


def test_comparar_casos_ignora_lo_que_no_se_midio_en_ambas():
    """Una corrida sin --llm no debe contarse como un empeoramiento de las respuestas."""
    cambios = banco.comparar_casos([fila("uno", respuesta_ok=True), fila("viejo", fuente_ok=True)],
                                   [fila("uno", respuesta_ok=None), fila("nuevo", fuente_ok=False)])
    assert cambios == {"mejoras": [], "empeoran": []}


def test_guardar_y_leer_una_corrida(tmp_path):
    conexion = banco.abrir(tmp_path / "evaluaciones" / "banco.sqlite")
    datos = {"fecha": "2026-11-05T10:00:00", "nombre": "base", "version": "abc1234", "huella_codigo": "f00",
             "coleccion": "rag_x", "modelo": None, "segundos": 1.5, "config": {"margen": 0.03}}
    filas = [fila("uno", fuente_ok=True, fragmentos=[{"archivo": "a.pdf", "pagina": 3, "similitud": 0.9}]),
             fila("dos", error="[límite]", sin_respaldo=["99 mg"])]
    corrida = banco.guardar_corrida(conexion, datos, filas)

    [leida] = banco.leer_corridas(conexion)
    assert leida["id"] == corrida
    assert leida["config"] == {"margen": 0.03}
    assert leida["resumen"]["fuente"] == {"aciertos": 1, "casos": 1}

    casos = banco.leer_casos(conexion, corrida)
    assert [c["n"] for c in casos] == [1, 2]
    assert casos[0]["fragmentos"] == [{"archivo": "a.pdf", "pagina": 3, "similitud": 0.9}]
    assert casos[1]["sin_respaldo"] == ["99 mg"]
    assert casos[1]["error"] == "[límite]"
    assert banco.comparar_casos(casos, casos) == {"mejoras": [], "empeoran": []}
