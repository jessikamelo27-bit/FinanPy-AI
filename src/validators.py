"""
Módulo de Validações e Regras de Integridade do FinanPy AI.
Garante precisão monetária com Decimal, validação de datas (DD/MM/AAAA e AAAA-MM-DD),
campos obrigatórios e compatibilidade entre tipo de lançamento e categoria.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
from typing import Dict, List, Optional, Tuple, Any, Union

TIPOS_VALIDOS = ("Receita", "Despesa")

CATEGORIAS_INICIAIS: Dict[str, List[str]] = {
    "Receita": [
        "Salário",
        "Renda extra",
        "Outros",
    ],
    "Despesa": [
        "Alimentação",
        "Moradia",
        "Transporte",
        "Saúde",
        "Educação",
        "Lazer",
        "Contas e serviços",
        "Compras",
        "Outros",
    ],
}

VALOR_MAXIMO = Decimal("999999999.99")


class ErroValidacao(ValueError):
    """Exceção controlada para erros de validação de dados financeiros."""


def para_decimal(valor: Any) -> Decimal:
    """
    Converte um valor numérico ou string monetária em Decimal com 2 casas decimais,
    evitando erros de arredondamento de ponto flutuante (IEEE 754).
    """
    if valor is None or isinstance(valor, bool):
        raise ErroValidacao("O valor monetário é obrigatório e deve ser numérico.")

    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            raise ErroValidacao("O valor informado não pode ser infinito ou inválido (NaN).")
        valor_str = f"{valor:.6f}"
    elif isinstance(valor, (int, Decimal)):
        valor_str = str(valor)
    elif isinstance(valor, str):
        limpo = valor.strip().replace("R$", "").strip()
        if not limpo:
            raise ErroValidacao("O valor monetário não pode estar vazio.")
        # Suporta formato brasileiro "1.234,56" e formato padrão "1234.56"
        if "," in limpo and "." in limpo:
            if limpo.rfind(",") > limpo.rfind("."):
                limpo = limpo.replace(".", "").replace(",", ".")
            else:
                limpo = limpo.replace(",", "")
        elif "," in limpo:
            limpo = limpo.replace(",", ".")
        valor_str = limpo
    else:
        raise ErroValidacao("Tipo de dado inválido para valor monetário.")

    try:
        dec = Decimal(valor_str)
    except InvalidOperation as exc:
        raise ErroValidacao(f"Valor monetário inválido: '{valor}'.") from exc

    if dec.is_nan() or dec.is_infinite():
        raise ErroValidacao("O valor informado não pode ser infinito ou NaN.")

    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validar_valor_positivo(valor: Any, nome_campo: str = "valor") -> Decimal:
    """Valida que o valor é estritamente maior que zero e dentro do limite seguro."""
    dec = para_decimal(valor)
    if dec <= Decimal("0.00"):
        raise ErroValidacao(f"O campo '{nome_campo}' deve ser maior que zero.")
    if dec > VALOR_MAXIMO:
        raise ErroValidacao(f"O campo '{nome_campo}' excede o limite máximo permitido.")
    return dec


def validar_valor_nao_negativo(valor: Any, nome_campo: str = "valor") -> Decimal:
    """Valida que o valor é zero ou positivo (>= 0)."""
    dec = para_decimal(valor)
    if dec < Decimal("0.00"):
        raise ErroValidacao(f"O campo '{nome_campo}' não pode ser negativo.")
    if dec > VALOR_MAXIMO:
        raise ErroValidacao(f"O campo '{nome_campo}' excede o limite máximo permitido.")
    return dec


def validar_data(data_entrada: Union[str, date, datetime, None], nome_campo: str = "data") -> str:
    """
    Valida uma data recebida como date, datetime, 'DD/MM/AAAA' ou 'AAAA-MM-DD'
    e retorna sempre no padrão ISO 'AAAA-MM-DD'.
    """
    if data_entrada is None:
        raise ErroValidacao(f"O campo '{nome_campo}' é obrigatório.")

    if isinstance(data_entrada, datetime):
        return data_entrada.date().isoformat()
    if isinstance(data_entrada, date):
        return data_entrada.isoformat()

    if not isinstance(data_entrada, str) or not data_entrada.strip():
        raise ErroValidacao(f"O campo '{nome_campo}' não pode estar vazio.")

    texto = data_entrada.strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(texto, formato).date()
            if dt.year < 1900 or dt.year > 2100:
                raise ErroValidacao(f"O ano da '{nome_campo}' deve estar entre 1900 e 2100.")
            return dt.isoformat()
        except ValueError:
            continue

    raise ErroValidacao(
        f"Data inválida em '{nome_campo}': '{texto}'. Use o formato DD/MM/AAAA ou AAAA-MM-DD."
    )


def formatar_data_br(data_iso: str) -> str:
    """Converte 'AAAA-MM-DD' para o formato brasileiro 'DD/MM/AAAA'."""
    try:
        dt = datetime.strptime(str(data_iso).strip()[:10], "%Y-%m-%d").date()
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return str(data_iso)


def formatar_moeda_br(valor: Union[Decimal, float, int]) -> str:
    """Formata um número ou Decimal no padrão brasileiro R$ 1.234,56."""
    dec = para_decimal(valor)
    sinal = "-" if dec < 0 else ""
    abs_dec = abs(dec)
    texto = f"{abs_dec:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {texto}"


def validar_lancamento(
    descricao: Any,
    valor: Any,
    data_lancamento: Any,
    categoria: Any,
    tipo: Any,
    categorias_por_tipo: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Valida todos os campos de um lançamento financeiro (receita ou despesa).
    Garante que a categoria seja compatível com o tipo selecionado.
    """
    if not isinstance(tipo, str) or tipo.strip() not in TIPOS_VALIDOS:
        raise ErroValidacao("O tipo de lançamento deve ser 'Receita' ou 'Despesa'.")
    tipo_limpo = tipo.strip()

    if not isinstance(descricao, str) or not descricao.strip():
        raise ErroValidacao("A descrição do lançamento é obrigatória.")
    descricao_limpa = " ".join(descricao.strip().split())
    if len(descricao_limpa) > 200:
        raise ErroValidacao("A descrição deve ter no máximo 200 caracteres.")

    if not isinstance(categoria, str) or not categoria.strip():
        raise ErroValidacao("A categoria do lançamento é obrigatória.")
    categoria_limpa = categoria.strip()

    mapa_categorias = categorias_por_tipo or CATEGORIAS_INICIAIS
    permitidas = mapa_categorias.get(tipo_limpo, [])
    if permitidas and categoria_limpa not in permitidas:
        raise ErroValidacao(
            f"A categoria '{categoria_limpa}' não é compatível com o tipo '{tipo_limpo}'. "
            f"Categorias permitidas para {tipo_limpo}: {', '.join(permitidas)}."
        )

    valor_dec = validar_valor_positivo(valor, "valor")
    data_iso = validar_data(data_lancamento, "data")

    return {
        "descricao": descricao_limpa,
        "valor": float(valor_dec),
        "valor_decimal": valor_dec,
        "data": data_iso,
        "categoria": categoria_limpa,
        "tipo": tipo_limpo,
    }


def validar_meta(
    titulo: Any,
    valor_alvo: Any,
    prazo: Any,
    valor_inicial: Any = 0,
) -> Dict[str, Any]:
    """Valida os dados de uma meta de economia."""
    if not isinstance(titulo, str) or not titulo.strip():
        raise ErroValidacao("O título da meta é obrigatório.")
    titulo_limpo = " ".join(titulo.strip().split())
    if len(titulo_limpo) > 150:
        raise ErroValidacao("O título da meta deve ter no máximo 150 caracteres.")

    alvo_dec = validar_valor_positivo(valor_alvo, "valor desejado")
    inicial_dec = validar_valor_nao_negativo(valor_inicial, "valor inicial")
    prazo_iso = validar_data(prazo, "prazo")

    return {
        "titulo": titulo_limpo,
        "valor_alvo": float(alvo_dec),
        "valor_inicial": float(inicial_dec),
        "prazo": prazo_iso,
    }
