"""
Módulo de Metas de Economia e Planejamento Financeiro do FinanPy AI.
Calcula o progresso real a partir dos lançamentos registrados, estima o esforço mensal
necessário até o prazo e emite alertas baseados na capacidade real de poupança do usuário.
"""

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.analytics import calcular_indicadores, comparativo_mensal
from src.database import conectar, inicializar_banco
from src.validators import (
    ErroValidacao,
    formatar_data_br,
    formatar_moeda_br,
    validar_meta,
)


def criar_meta(
    titulo: str,
    valor_alvo: Union[float, int, str, Decimal],
    prazo: Union[str, date],
    valor_inicial: Union[float, int, str, Decimal] = 0,
    is_demo: bool = False,
    caminho_banco: Optional[Path] = None,
) -> int:
    """Valida e cadastra uma nova meta de economia no banco SQLite."""
    inicializar_banco(caminho_banco)
    dados = validar_meta(titulo, valor_alvo, prazo, valor_inicial)
    alvo_centavos = int(round(dados["valor_alvo"] * 100))
    inicial_centavos = int(round(dados["valor_inicial"] * 100))

    with conectar(caminho_banco) as conn:
        cursor = conn.execute(
            """
            INSERT INTO metas (titulo, valor_alvo_centavos, valor_inicial_centavos, prazo, is_demo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                dados["titulo"],
                alvo_centavos,
                inicial_centavos,
                dados["prazo"],
                1 if is_demo else 0,
            ),
        )
        return int(cursor.lastrowid)


def atualizar_valor_inicial_meta(
    meta_id: int,
    novo_valor_inicial: Union[float, int, str, Decimal],
    caminho_banco: Optional[Path] = None,
) -> None:
    """Atualiza a reserva inicial já alocada para uma meta existente."""
    inicializar_banco(caminho_banco)
    from src.validators import validar_valor_nao_negativo
    dec = validar_valor_nao_negativo(novo_valor_inicial, "valor inicial")
    centavos = int((dec * 100).to_integral_value())

    with conectar(caminho_banco) as conn:
        cursor = conn.execute(
            "UPDATE metas SET valor_inicial_centavos = ? WHERE id = ?",
            (centavos, int(meta_id)),
        )
        if cursor.rowcount == 0:
            raise ErroValidacao(f"Meta #{meta_id} não encontrada.")


def excluir_meta(meta_id: int, caminho_banco: Optional[Path] = None) -> None:
    """Remove uma meta de economia pelo ID."""
    inicializar_banco(caminho_banco)
    with conectar(caminho_banco) as conn:
        cursor = conn.execute("DELETE FROM metas WHERE id = ?", (int(meta_id),))
        if cursor.rowcount == 0:
            raise ErroValidacao(f"Meta #{meta_id} não encontrada.")


def listar_metas(
    modo_dados: str = "usuario",
    caminho_banco: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Lista as metas de acordo com o modo de dados ('usuario' ou 'demo')."""
    inicializar_banco(caminho_banco)
    flag_demo = 1 if modo_dados == "demo" else 0
    with conectar(caminho_banco) as conn:
        linhas = conn.execute(
            "SELECT * FROM metas WHERE is_demo = ? ORDER BY prazo ASC, id ASC",
            (flag_demo,),
        ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "titulo": r["titulo"],
                "valor_alvo": round(int(r["valor_alvo_centavos"]) / 100.0, 2),
                "valor_inicial": round(int(r["valor_inicial_centavos"]) / 100.0, 2),
                "prazo": r["prazo"],
                "prazo_br": formatar_data_br(r["prazo"]),
                "is_demo": bool(r["is_demo"]),
            }
            for r in linhas
        ]


def calcular_meses_restantes(prazo_iso: str, referencia: Optional[date] = None) -> int:
    """Calcula o número de meses restantes entre a data de referência e o prazo da meta."""
    hoje = referencia or date.today()
    dt_prazo = datetime.strptime(str(prazo_iso)[:10], "%Y-%m-%d").date()
    if dt_prazo <= hoje:
        return 0
    meses = (dt_prazo.year - hoje.year) * 12 + (dt_prazo.month - hoje.month)
    if dt_prazo.day > hoje.day and meses == 0:
        return 1
    return max(1, meses)


def avaliar_progresso_meta(
    meta: Dict[str, Any],
    lancamentos: List[Dict[str, Any]],
    referencia: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Avalia o progresso de uma meta com base nos lançamentos registrados:
    - Considera o valor_inicial da meta + o saldo acumulado positivo dos lançamentos.
    - Calcula quanto falta economizar e quanto seria necessário poupar por mês.
    - Compara com a economia média mensal real dos dados e gera alertas honestos.
    """
    hoje = referencia or date.today()
    indicadores = calcular_indicadores(lancamentos)
    saldo_registrado = indicadores["saldo"]

    valor_alvo = float(meta["valor_alvo"])
    valor_inicial = float(meta.get("valor_inicial", 0.0))

    # O saldo positivo registrado contribui para a meta; saldo negativo não reduz abaixo de 0 o progresso visual, mas gera alerta
    economia_dos_lancamentos = max(0.0, saldo_registrado)
    valor_acumulado_estimado = round(valor_inicial + economia_dos_lancamentos, 2)
    valor_faltante = round(max(0.0, valor_alvo - valor_acumulado_estimado), 2)

    percentual_concluido = (
        round(min(100.0, (valor_acumulado_estimado / valor_alvo) * 100.0), 1)
        if valor_alvo > 0
        else 0.0
    )

    dt_prazo = datetime.strptime(str(meta["prazo"])[:10], "%Y-%m-%d").date()
    prazo_vencido = dt_prazo < hoje
    meses_restantes = calcular_meses_restantes(meta["prazo"], hoje)

    if valor_faltante == 0:
        economia_mensal_necessaria = 0.0
    elif meses_restantes > 0:
        economia_mensal_necessaria = float(
            (Decimal(str(valor_faltante)) / Decimal(meses_restantes)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
    else:
        economia_mensal_necessaria = valor_faltante

    # Calcula média mensal histórica real a partir dos meses registrados
    df_mensal = comparativo_mensal(lancamentos)
    qtd_meses_historico = len(df_mensal)
    media_economia_mensal: Optional[float] = (
        round(float(df_mensal["Saldo"].mean()), 2) if qtd_meses_historico > 0 else None
    )

    # Diagnóstico e Alertas baseados estritamente nos dados disponíveis
    if valor_faltante <= 0:
        nivel_alerta = "sucesso"
        status_texto = "Meta atingida!"
        mensagem_alerta = (
            f"Parabéns! Somando o valor inicial ({formatar_moeda_br(valor_inicial)}) "
            f"ao saldo acumulado dos lançamentos ({formatar_moeda_br(economia_dos_lancamentos)}), "
            f"você já alcançou o objetivo de {formatar_moeda_br(valor_alvo)}."
        )
    elif not lancamentos:
        nivel_alerta = "info"
        status_texto = "Dados insuficientes para projeção"
        mensagem_alerta = (
            "Não há lançamentos financeiros registrados. Ainda não é possível avaliar se o seu "
            f"ritmo de economia permite guardar {formatar_moeda_br(economia_mensal_necessaria)}/mês."
        )
    elif prazo_vencido:
        nivel_alerta = "alerta"
        status_texto = "Prazo encerrado"
        mensagem_alerta = (
            f"O prazo da meta ({formatar_data_br(meta['prazo'])}) já passou e ainda faltam "
            f"{formatar_moeda_br(valor_faltante)}. Considere renegociar o prazo ou aumentar aportes."
        )
    elif saldo_registrado <= 0:
        nivel_alerta = "alerta"
        status_texto = "Risco alto: Saldo negativo ou zerado"
        mensagem_alerta = (
            f"Nos lançamentos registrados, suas despesas ({formatar_moeda_br(indicadores['total_despesas'])}) "
            f"consumiram toda a receita ({formatar_moeda_br(indicadores['total_receitas'])}). "
            f"Para cumprir esta meta até {formatar_data_br(meta['prazo'])}, você precisa reverter o déficit "
            f"e economizar {formatar_moeda_br(economia_mensal_necessaria)} por mês."
        )
    elif media_economia_mensal is not None and media_economia_mensal < economia_mensal_necessaria:
        diferenca_mensal = round(economia_mensal_necessaria - media_economia_mensal, 2)
        nivel_alerta = "aviso"
        status_texto = "Ritmo atual abaixo do necessário"
        mensagem_alerta = (
            f"Sua economia média nos dados registrados é de {formatar_moeda_br(media_economia_mensal)}/mês, "
            f"mas a meta exige {formatar_moeda_br(economia_mensal_necessaria)}/mês pelos próximos "
            f"{meses_restantes} mês(es). Seria necessário economizar mais {formatar_moeda_br(diferenca_mensal)}/mês."
        )
    else:
        nivel_alerta = "sucesso"
        status_texto = "Ritmo compatível com a meta"
        mensagem_alerta = (
            f"Sua economia média registrada ({formatar_moeda_br(media_economia_mensal or 0)}/mês) "
            f"é suficiente para cobrir os {formatar_moeda_br(economia_mensal_necessaria)}/mês necessários "
            f"pelos próximos {meses_restantes} mês(es)."
        )

    return {
        **meta,
        "saldo_registrado": saldo_registrado,
        "valor_acumulado": valor_acumulado_estimado,
        "valor_faltante": valor_faltante,
        "percentual_concluido": percentual_concluido,
        "meses_restantes": meses_restantes,
        "prazo_vencido": prazo_vencido,
        "economia_mensal_necessaria": economia_mensal_necessaria,
        "media_economia_mensal": media_economia_mensal,
        "nivel_alerta": nivel_alerta,
        "status_texto": status_texto,
        "mensagem_alerta": mensagem_alerta,
    }
