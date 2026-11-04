"""
Módulo de Processamento e Análise Financeira (Pandas + Decimal) do FinanPy AI.
Calcula indicadores com precisão de centavos, comparativos mensais, distribuição por categoria,
evolução acumulada do saldo e detecção determinística de variações de gastos.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
import pandas as pd

from src.validators import formatar_data_br


def para_dataframe(lancamentos: List[Dict[str, Any]]) -> pd.DataFrame:
    """Converte a lista de lançamentos em um DataFrame enriquecido com colunas temporais."""
    colunas = [
        "id",
        "data",
        "data_br",
        "ano",
        "mes",
        "ano_mes",
        "tipo",
        "categoria",
        "descricao",
        "valor",
        "valor_centavos",
    ]
    if not lancamentos:
        return pd.DataFrame(columns=colunas)

    df = pd.DataFrame(lancamentos)
    if "valor_centavos" not in df.columns:
        df["valor_centavos"] = (pd.to_numeric(df["valor"]) * 100).round().astype(int)
    else:
        df["valor_centavos"] = df["valor_centavos"].astype(int)

    df["valor"] = df["valor_centavos"] / 100.0
    if "data_br" not in df.columns:
        df["data_br"] = df["data"].apply(formatar_data_br)

    datas_dt = pd.to_datetime(df["data"], errors="coerce")
    df["ano"] = datas_dt.dt.year
    df["mes"] = datas_dt.dt.month
    df["ano_mes"] = datas_dt.dt.strftime("%Y-%m")
    return df[colunas]


def calcular_indicadores(lancamentos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula o resumo financeiro do período usando aritmética exata em centavos (Decimal):
    - total_receitas, total_despesas, saldo
    - percentual_comprometido (None se receitas == 0 e houver despesas, ou 0.0 se tudo zero)
    - taxa_economia
    """
    if not lancamentos:
        return {
            "total_receitas": 0.0,
            "total_despesas": 0.0,
            "saldo": 0.0,
            "percentual_comprometido": 0.0,
            "comprometimento_calculavel": False,
            "taxa_economia": 0.0,
            "quantidade_lancamentos": 0,
            "quantidade_receitas": 0,
            "quantidade_despesas": 0,
        }

    rec_centavos = sum(
        int(round(float(item.get("valor", 0)) * 100))
        if "valor_centavos" not in item
        else int(item["valor_centavos"])
        for item in lancamentos
        if item.get("tipo") == "Receita"
    )
    desp_centavos = sum(
        int(round(float(item.get("valor", 0)) * 100))
        if "valor_centavos" not in item
        else int(item["valor_centavos"])
        for item in lancamentos
        if item.get("tipo") == "Despesa"
    )
    saldo_centavos = rec_centavos - desp_centavos

    receitas_dec = (Decimal(rec_centavos) / Decimal(100)).quantize(Decimal("0.01"))
    despesas_dec = (Decimal(desp_centavos) / Decimal(100)).quantize(Decimal("0.01"))
    saldo_dec = (Decimal(saldo_centavos) / Decimal(100)).quantize(Decimal("0.01"))

    if rec_centavos > 0:
        pct_comp = (
            (Decimal(desp_centavos) / Decimal(rec_centavos)) * Decimal(100)
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        pct_econ = (
            (Decimal(saldo_centavos) / Decimal(rec_centavos)) * Decimal(100)
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        calculavel = True
        percentual_comprometido: Optional[float] = float(pct_comp)
        taxa_economia: Optional[float] = float(pct_econ)
    else:
        calculavel = False
        percentual_comprometido = None if desp_centavos > 0 else 0.0
        taxa_economia = None if desp_centavos > 0 else 0.0

    qtd_rec = sum(1 for item in lancamentos if item.get("tipo") == "Receita")
    qtd_desp = sum(1 for item in lancamentos if item.get("tipo") == "Despesa")

    return {
        "total_receitas": float(receitas_dec),
        "total_despesas": float(despesas_dec),
        "saldo": float(saldo_dec),
        "percentual_comprometido": percentual_comprometido,
        "comprometimento_calculavel": calculavel,
        "taxa_economia": taxa_economia,
        "quantidade_lancamentos": len(lancamentos),
        "quantidade_receitas": qtd_rec,
        "quantidade_despesas": qtd_desp,
    }


def gastos_por_categoria(lancamentos: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Agrupa as despesas por categoria, retornando um DataFrame ordenado do maior para o menor gasto,
    com valor em R$, percentual sobre o total de despesas e quantidade de lançamentos.
    """
    colunas = ["categoria", "valor", "percentual", "quantidade"]
    df = para_dataframe(lancamentos)
    if df.empty:
        return pd.DataFrame(columns=colunas)

    df_desp = df[df["tipo"] == "Despesa"]
    if df_desp.empty:
        return pd.DataFrame(columns=colunas)

    agrupado = (
        df_desp.groupby("categoria", as_index=False)
        .agg(
            valor_centavos=("valor_centavos", "sum"),
            quantidade=("id", "count"),
        )
        .sort_values(by="valor_centavos", ascending=False)
        .reset_index(drop=True)
    )

    total_centavos = int(agrupado["valor_centavos"].sum())
    agrupado["valor"] = (agrupado["valor_centavos"] / 100.0).round(2)
    agrupado["percentual"] = (
        (agrupado["valor_centavos"] / total_centavos * 100.0).round(1)
        if total_centavos > 0
        else 0.0
    )
    return agrupado[colunas]


def comparativo_mensal(lancamentos: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Consolida Receitas, Despesas, Saldo do Mês e Saldo Acumulado por mês ('AAAA-MM').
    """
    colunas = ["ano_mes", "Receita", "Despesa", "Saldo", "Saldo_Acumulado"]
    df = para_dataframe(lancamentos)
    if df.empty:
        return pd.DataFrame(columns=colunas)

    piv = (
        df.pivot_table(
            index="ano_mes",
            columns="tipo",
            values="valor_centavos",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .sort_values("ano_mes")
    )

    for col in ("Receita", "Despesa"):
        if col not in piv.columns:
            piv[col] = 0

    piv["Saldo_centavos"] = piv["Receita"] - piv["Despesa"]
    piv["Acumulado_centavos"] = piv["Saldo_centavos"].cumsum()

    piv["Receita"] = (piv["Receita"] / 100.0).round(2)
    piv["Despesa"] = (piv["Despesa"] / 100.0).round(2)
    piv["Saldo"] = (piv["Saldo_centavos"] / 100.0).round(2)
    piv["Saldo_Acumulado"] = (piv["Acumulado_centavos"] / 100.0).round(2)

    return piv[colunas].reset_index(drop=True)


def evolucao_saldo(lancamentos: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Calcula a evolução cronológica diária do saldo ao longo do tempo.
    """
    colunas = ["data", "data_br", "fluxo_dia", "saldo_acumulado"]
    df = para_dataframe(lancamentos)
    if df.empty:
        return pd.DataFrame(columns=colunas)

    df["fluxo_centavos"] = df.apply(
        lambda r: r["valor_centavos"] if r["tipo"] == "Receita" else -r["valor_centavos"],
        axis=1,
    )
    diario = (
        df.groupby("data", as_index=False)["fluxo_centavos"]
        .sum()
        .sort_values("data")
        .reset_index(drop=True)
    )
    diario["acumulado_centavos"] = diario["fluxo_centavos"].cumsum()
    diario["data_br"] = diario["data"].apply(formatar_data_br)
    diario["fluxo_dia"] = (diario["fluxo_centavos"] / 100.0).round(2)
    diario["saldo_acumulado"] = (diario["acumulado_centavos"] / 100.0).round(2)
    return diario[colunas]


def detectar_variacoes_mensais(lancamentos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compara os dois meses mais recentes registrados para identificar variações relevantes
    no total de despesas e em cada categoria.
    Informa explicitamente quando não há meses suficientes (< 2 meses).
    """
    df = para_dataframe(lancamentos)
    if df.empty:
        return {
            "dados_suficientes": False,
            "motivo": "Não há lançamentos registrados para comparar períodos.",
            "variacoes_categorias": [],
        }

    meses = sorted(df["ano_mes"].dropna().unique().tolist())
    if len(meses) < 2:
        return {
            "dados_suficientes": False,
            "motivo": (
                f"Apenas 1 mês com dados ({meses[0] if meses else 'nenhum'}). "
                "São necessários pelo menos 2 meses diferentes para comparar a evolução de gastos."
            ),
            "variacoes_categorias": [],
        }

    mes_anterior, mes_atual = meses[-2], meses[-1]
    df_ant = df[(df["ano_mes"] == mes_anterior) & (df["tipo"] == "Despesa")]
    df_atu = df[(df["ano_mes"] == mes_atual) & (df["tipo"] == "Despesa")]

    desp_ant = round(float(df_ant["valor_centavos"].sum()) / 100.0, 2)
    desp_atu = round(float(df_atu["valor_centavos"].sum()) / 100.0, 2)
    dif_total = round(desp_atu - desp_ant, 2)
    pct_total = round((dif_total / desp_ant) * 100.0, 1) if desp_ant > 0 else None

    cat_ant = df_ant.groupby("categoria")["valor_centavos"].sum().to_dict()
    cat_atu = df_atu.groupby("categoria")["valor_centavos"].sum().to_dict()
    todas_cats = sorted(set(cat_ant.keys()) | set(cat_atu.keys()))

    variacoes: List[Dict[str, Any]] = []
    for cat in todas_cats:
        v_ant = round(cat_ant.get(cat, 0) / 100.0, 2)
        v_atu = round(cat_atu.get(cat, 0) / 100.0, 2)
        diferenca = round(v_atu - v_ant, 2)
        pct = round((diferenca / v_ant) * 100.0, 1) if v_ant > 0 else None
        if abs(diferenca) > 0:
            variacoes.append({
                "categoria": cat,
                "valor_anterior": v_ant,
                "valor_atual": v_atu,
                "diferenca": diferenca,
                "percentual": pct,
            })

    variacoes.sort(key=lambda x: abs(x["diferenca"]), reverse=True)

    return {
        "dados_suficientes": True,
        "mes_anterior": mes_anterior,
        "mes_atual": mes_atual,
        "despesa_anterior": desp_ant,
        "despesa_atual": desp_atu,
        "diferenca_total": dif_total,
        "percentual_total": pct_total,
        "variacoes_categorias": variacoes,
    }


# ==========================================
# Visualizações Extras para o Tema Dark PRO (Sankey & Matplotlib)
# ==========================================

def gerar_dados_sankey(lancamentos: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    """
    Estrutura os nós e fluxos para o Diagrama de Sankey (Fluxo de Caixa):
    Categorias de Receita -> Orçamento do Período -> Categorias de Despesa e Saldo Positivo.
    """
    if not lancamentos:
        return {"labels": [], "sources": [], "targets": [], "values": [], "colors": []}

    df = para_dataframe(lancamentos)
    if df.empty:
        return {"labels": [], "sources": [], "targets": [], "values": [], "colors": []}

    labels: List[str] = ["Orçamento do Período"]
    colors: List[str] = ["#6366f1"]
    sources: List[int] = []
    targets: List[int] = []
    values: List[float] = []

    def obter_no(nome: str, cor: str) -> int:
        if nome not in labels:
            labels.append(nome)
            colors.append(cor)
        return labels.index(nome)

    idx_central = 0

    df_rec = df[df["tipo"] == "Receita"]
    if not df_rec.empty:
        for cat, centavos in df_rec.groupby("categoria")["valor_centavos"].sum().items():
            if centavos > 0:
                idx_orig = obter_no(f"🟢 {cat}", "#10b981")
                sources.append(idx_orig)
                targets.append(idx_central)
                values.append(round(centavos / 100.0, 2))

    df_desp = df[df["tipo"] == "Despesa"]
    if not df_desp.empty:
        for cat, centavos in df_desp.groupby("categoria")["valor_centavos"].sum().items():
            if centavos > 0:
                idx_dest = obter_no(f"🔴 {cat}", "#ef4444")
                sources.append(idx_central)
                targets.append(idx_dest)
                values.append(round(centavos / 100.0, 2))

    ind = calcular_indicadores(lancamentos)
    if ind["saldo"] > 0:
        idx_saldo = obter_no("🏦 Saldo Economizado", "#3b82f6")
        sources.append(idx_central)
        targets.append(idx_saldo)
        values.append(round(ind["saldo"], 2))

    return {
        "labels": labels,
        "sources": sources,
        "targets": targets,
        "values": values,
        "colors": colors,
    }
