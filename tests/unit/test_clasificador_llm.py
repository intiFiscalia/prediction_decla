import json

import pytest

from decla.fenomenos.clasificador_llm import (
    ResultadoClasificacionLLM,
    clasificar_relato,
    construir_prompt,
    parsear_respuesta_llm,
)

CODIGOS = ["organizacion_criminal", "incautacion_y_conteo_de_efectivo", "no_clasificado"]


class _ClienteFalso:
    def __init__(self, respuesta: str) -> None:
        self.respuesta = respuesta
        self.llamadas: list[dict[str, object]] = []

    def generar(self, prompt: str, temperatura: float, semilla: int) -> str:
        self.llamadas.append(
            {"prompt": prompt, "temperatura": temperatura, "semilla": semilla}
        )
        return self.respuesta


def test_construir_prompt_incluye_criterios_y_relato() -> None:
    prompt = construir_prompt("SE HALLÓ DINERO EN UN VEHÍCULO.", CODIGOS)
    assert "organizacion_criminal" in prompt
    assert "SE HALLÓ DINERO EN UN VEHÍCULO." in prompt
    assert "Caso límite" in prompt
    assert "organizacion_mencionada" in prompt


def test_parsear_respuesta_llm_extrae_organizacion_mencionada() -> None:
    texto = json.dumps(
        {
            "codigos": [],
            "evidencia": "",
            "confianza": 0.7,
            "organizacion_mencionada": "grupo de liberación nacional ELF",
        }
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.organizacion_mencionada == "grupo de liberación nacional ELF"


def test_parsear_respuesta_llm_organizacion_null_queda_none() -> None:
    texto = json.dumps(
        {"codigos": [], "evidencia": "", "confianza": 0.7, "organizacion_mencionada": None}
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.organizacion_mencionada is None


def test_parsear_respuesta_llm_organizacion_vacia_queda_none() -> None:
    texto = json.dumps(
        {"codigos": [], "evidencia": "", "confianza": 0.7, "organizacion_mencionada": "   "}
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.organizacion_mencionada is None


def test_parsear_respuesta_llm_quita_texto_narrativo_despues_del_json() -> None:
    texto = (
        '{"codigos": ["incautacion_y_conteo_de_efectivo"], "evidencia": "x", "confianza": 0.8}\n'
        "\nNota: razonamiento adicional que el modelo no debía escribir."
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.codigos == ["incautacion_y_conteo_de_efectivo"]


def test_parsear_respuesta_llm_confianza_ausente_usa_cero_sin_descartar_codigos() -> None:
    """Fallo real observado: el modelo escribió 'confida' en vez de 'confianza'. No se debe
    perder el 'codigos' que sí se parseó bien por un nombre de llave mal escrito."""
    texto = json.dumps(
        {"codigos": ["organizacion_criminal"], "evidencia": "roles y alias", "confida": 0.0}
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.codigos == ["organizacion_criminal"]
    assert resultado.confianza == 0.0


def test_parsear_respuesta_llm_extrae_fenomeno_no_listado() -> None:
    texto = json.dumps(
        {
            "codigos": [],
            "evidencia": "",
            "confianza": 0.0,
            "fenomeno_no_listado": "hallazgo de esmeraldas sin documentación de legalidad",
        }
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.fenomeno_no_listado == "hallazgo de esmeraldas sin documentación de legalidad"
    assert resultado.codigos == []


def test_parsear_respuesta_llm_fenomeno_no_listado_null_queda_none() -> None:
    texto = json.dumps(
        {"codigos": [], "evidencia": "", "confianza": 0.0, "fenomeno_no_listado": None}
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.fenomeno_no_listado is None


def test_parsear_respuesta_llm_valida() -> None:
    texto = json.dumps(
        {
            "codigos": ["organizacion_criminal"],
            "evidencia": "roles diferenciados descritos",
            "confianza": 0.9,
        }
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado == ResultadoClasificacionLLM(
        codigos=["organizacion_criminal"], evidencia="roles diferenciados descritos", confianza=0.9
    )


def test_parsear_respuesta_llm_sin_codigos_es_valido() -> None:
    texto = json.dumps({"codigos": [], "evidencia": "", "confianza": 0.4})
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.codigos == []


def test_parsear_respuesta_llm_quita_valla_markdown() -> None:
    texto = (
        '```json\n{"codigos": ["incautacion_y_conteo_de_efectivo"], "evidencia": "x", '
        '"confianza": 1.0}\n```'
    )
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.codigos == ["incautacion_y_conteo_de_efectivo"]


def test_parsear_respuesta_llm_quita_valla_markdown_sin_lenguaje() -> None:
    texto = '```\n{"codigos": [], "evidencia": "", "confianza": 0.3}\n```'
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.codigos == []


def test_parsear_respuesta_llm_rechaza_json_invalido() -> None:
    with pytest.raises(ValueError, match="JSON válido"):
        parsear_respuesta_llm("esto no es json", CODIGOS)


def test_parsear_respuesta_llm_normaliza_tildes_a_forma_canonica() -> None:
    """Fallo real observado: el modelo escribió 'organización_criminal' (con tilde) cuando el
    código exacto de la taxonomía es sin tilde. Debe aceptarse y guardarse con la forma
    canónica, nunca la variante del modelo."""
    texto = json.dumps({"codigos": ["organización_criminal"], "evidencia": "", "confianza": 0.7})
    resultado = parsear_respuesta_llm(texto, CODIGOS)
    assert resultado.codigos == ["organizacion_criminal"]


def test_parsear_respuesta_llm_rechaza_codigo_desconocido() -> None:
    texto = json.dumps({"codigos": ["fenomeno_inventado"], "evidencia": "", "confianza": 0.5})
    with pytest.raises(ValueError, match="fuera de la taxonomía"):
        parsear_respuesta_llm(texto, CODIGOS)


def test_parsear_respuesta_llm_rechaza_confianza_fuera_de_rango() -> None:
    texto = json.dumps({"codigos": [], "evidencia": "", "confianza": 1.5})
    with pytest.raises(ValueError, match="rango"):
        parsear_respuesta_llm(texto, CODIGOS)


def test_clasificar_relato_usa_el_cliente_con_parametros_deterministas() -> None:
    texto = json.dumps({"codigos": ["no_clasificado"], "evidencia": "", "confianza": 0.5})
    cliente = _ClienteFalso(texto)

    resultado = clasificar_relato(cliente, "UN RELATO CUALQUIERA.", CODIGOS)

    assert resultado.codigos == ["no_clasificado"]
    assert cliente.llamadas == [
        {
            "prompt": cliente.llamadas[0]["prompt"],
            "temperatura": 0.0,
            "semilla": 20260101,
        }
    ]
    assert "UN RELATO CUALQUIERA." in str(cliente.llamadas[0]["prompt"])
