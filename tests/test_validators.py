"""Testes automatizados para o módulo src/validators.py."""

import math
from datetime import date
from decimal import Decimal
import pytest

from src.validators import (
    ErroValidacao,
    formatar_data_br,
    formatar_moeda_br,
    para_decimal,
    validar_data,
    validar_lancamento,
    validar_meta,
    validar_valor_nao_negativo,
    validar_valor_positivo,
)


def test_para_decimal_precisao_monetaria():
    """Garante que valores monetários não sofram erro de ponto flutuante (0.1 + 0.2 == 0.30)."""
    v1 = para_decimal("0.10")
    v2 = para_decimal(0.2)
    assert v1 + v2 == Decimal("0.30")
    assert para_decimal("R$ 1.234,56") == Decimal("1234.56")
    assert para_decimal("1234,50") == Decimal("1234.50")


@pytest.mark.parametrize("valor_invalido", [0, -10, "-0.01", "0,00"])
def test_validar_valor_positivo_rejeita_zero_e_negativos(valor_invalido):
    with pytest.raises(ErroValidacao):
        validar_valor_positivo(valor_invalido)


@pytest.mark.parametrize("valor_invalido", [None, "", "   ", "abc", True, False, math.nan, math.inf, -math.inf])
def test_validar_valor_rejeita_nulos_booleanos_infinitos_e_nan(valor_invalido):
    with pytest.raises(ErroValidacao):
        validar_valor_positivo(valor_invalido)


def test_validar_valor_nao_negativo_aceita_zero():
    assert validar_valor_nao_negativo(0) == Decimal("0.00")
    with pytest.raises(ErroValidacao):
        validar_valor_nao_negativo(-0.01)


def test_validar_data_formatos_br_e_iso():
    assert validar_data("15/10/2026") == "2026-10-15"
    assert validar_data("2026-10-15") == "2026-10-15"
    assert validar_data(date(2026, 10, 15)) == "2026-10-15"
    assert formatar_data_br("2026-10-15") == "15/10/2026"


@pytest.mark.parametrize("data_invalida", [None, "", "31/02/2026", "2026-13-01", "15-10-2026", "texto"])
def test_validar_data_rejeita_datas_invalidas(data_invalida):
    with pytest.raises(ErroValidacao):
        validar_data(data_invalida)


def test_validar_lancamento_bloqueia_categoria_incompativel():
    """Impede registrar Despesa com categoria de Receita ('Salário') e vice-versa."""
    with pytest.raises(ErroValidacao, match="não é compatível"):
        validar_lancamento(
            descricao="Teste inválido",
            valor=100.0,
            data_lancamento="15/10/2026",
            categoria="Salário",
            tipo="Despesa",
        )

    with pytest.raises(ErroValidacao, match="não é compatível"):
        validar_lancamento(
            descricao="Teste inválido 2",
            valor=100.0,
            data_lancamento="15/10/2026",
            categoria="Alimentação",
            tipo="Receita",
        )


def test_validar_lancamento_campos_obrigatorios():
    with pytest.raises(ErroValidacao, match="descrição"):
        validar_lancamento("", 50.0, "2026-10-15", "Alimentação", "Despesa")

    with pytest.raises(ErroValidacao, match="tipo"):
        validar_lancamento("Almoço", 50.0, "2026-10-15", "Alimentação", "Investimento")


def test_validar_meta_e_formatar_moeda():
    meta = validar_meta("Reserva de Emergência", "5.000,00", "31/12/2027", "500,00")
    assert meta["valor_alvo"] == 5000.0
    assert meta["valor_inicial"] == 500.0
    assert meta["prazo"] == "2027-12-31"
    assert formatar_moeda_br(1234.56) == "R$ 1.234,56"
