"""Testes automatizados de análise financeira, metas e assistente de IA (Seção 8)."""

from datetime import date
from src.ai_assistant import (
    gerar_diagnostico_deterministico,
    gerar_resumo_anonimizado,
    responder_pergunta,
    status_integracao_ia,
)
from src.analytics import (
    calcular_indicadores,
    comparativo_mensal,
    detectar_variacoes_mensais,
    evolucao_saldo,
    gastos_por_categoria,
)
from src.goals import avaliar_progresso_meta, criar_meta, listar_metas
from src.transactions import criar_lancamento, listar_lancamentos


def test_calculo_indicadores_banco_vazio_e_sem_receita():
    # 1. Banco vazio
    vazio = calcular_indicadores([])
    assert vazio["total_receitas"] == 0.0
    assert vazio["total_despesas"] == 0.0
    assert vazio["saldo"] == 0.0
    assert vazio["comprometimento_calculavel"] is False

    # 2. Apenas despesas (receita == 0 -> percentual comprometido não calculável / None)
    apenas_despesa = [{"tipo": "Despesa", "valor": 250.0, "valor_centavos": 25000}]
    ind = calcular_indicadores(apenas_despesa)
    assert ind["total_receitas"] == 0.0
    assert ind["total_despesas"] == 250.0
    assert ind["saldo"] == -250.0
    assert ind["comprometimento_calculavel"] is False
    assert ind["percentual_comprometido"] is None


def test_calculo_exato_receitas_despesas_saldo_e_categorias(tmp_path):
    banco = tmp_path / "teste_analytics.db"
    criar_lancamento("Salário", "5000.00", "2026-09-05", "Salário", "Receita", caminho_banco=banco)
    criar_lancamento("Aluguel", "1500.00", "2026-09-10", "Moradia", "Despesa", caminho_banco=banco)
    criar_lancamento("Mercado", "500.00", "2026-09-15", "Alimentação", "Despesa", caminho_banco=banco)

    criar_lancamento("Salário", "5000.00", "2026-10-05", "Salário", "Receita", caminho_banco=banco)
    criar_lancamento("Aluguel", "1500.00", "2026-10-10", "Moradia", "Despesa", caminho_banco=banco)
    criar_lancamento("Mercado", "800.00", "2026-10-15", "Alimentação", "Despesa", caminho_banco=banco)

    lancamentos = listar_lancamentos(caminho_banco=banco)
    ind = calcular_indicadores(lancamentos)
    assert ind["total_receitas"] == 10000.0
    assert ind["total_despesas"] == 4300.0
    assert ind["saldo"] == 5700.0
    assert ind["percentual_comprometido"] == 43.0
    assert ind["taxa_economia"] == 57.0

    cats = gastos_por_categoria(lancamentos)
    assert len(cats) == 2
    assert cats.iloc[0]["categoria"] == "Moradia"
    assert cats.iloc[0]["valor"] == 3000.0

    mensal = comparativo_mensal(lancamentos)
    assert len(mensal) == 2
    assert list(mensal["Saldo"]) == [3000.0, 2700.0]

    evol = evolucao_saldo(lancamentos)
    assert evol.iloc[-1]["saldo_acumulado"] == 5700.0

    var = detectar_variacoes_mensais(lancamentos)
    assert var["dados_suficientes"] is True
    assert var["diferenca_total"] == 300.0


def test_metas_progresso_e_alertas(tmp_path):
    banco = tmp_path / "teste_metas.db"
    criar_meta("Reserva", 6000.0, "2027-04-15", valor_inicial=1000.0, caminho_banco=banco)
    metas = listar_metas(caminho_banco=banco)
    assert len(metas) == 1

    # Sem lançamentos -> avisa que faltam dados
    av_vazio = avaliar_progresso_meta(metas[0], [], referencia=date(2026, 10, 15))
    assert av_vazio["nivel_alerta"] == "info"
    assert av_vazio["meses_restantes"] == 6

    # Com saldo positivo mas abaixo da meta mensal
    lancs = [
        {"id": 1, "data": "2026-10-05", "tipo": "Receita", "categoria": "Salário", "descricao": "Sal", "valor": 3000.0, "valor_centavos": 300000},
        {"id": 2, "data": "2026-10-10", "tipo": "Despesa", "categoria": "Moradia", "descricao": "Alug", "valor": 2600.0, "valor_centavos": 260000},
    ]
    av_baixo = avaliar_progresso_meta(metas[0], lancs, referencia=date(2026, 10, 15))
    assert av_baixo["valor_acumulado"] == 1400.0
    assert av_baixo["nivel_alerta"] == "aviso"


def test_assistente_ia_sem_chave_dados_insuficientes_e_erro_llm(monkeypatch):
    # Remove chaves de API do ambiente
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    status = status_integracao_ia()
    assert status["llm_disponivel"] is False

    # 1. Ausência de dados suficientes
    diag_vazio = gerar_diagnostico_deterministico([])
    assert diag_vazio["dados_suficientes"] is False
    resp_vazia = responder_pergunta("Onde gasto mais?", [])
    assert "suficientes" in resp_vazia["resposta"].lower()

    # 2. Com dados locais e sem chave de API
    lancs = [
        {"id": 1, "data": "2026-10-05", "tipo": "Receita", "categoria": "Salário", "descricao": "Segredo Pessoal CPF 123", "valor": 5000.0, "valor_centavos": 500000},
        {"id": 2, "data": "2026-10-10", "tipo": "Despesa", "categoria": "Alimentação", "descricao": "Restaurante X", "valor": 1200.0, "valor_centavos": 120000},
    ]
    resumo_anon = gerar_resumo_anonimizado(lancs)
    # Garante que descrições pessoais nunca apareçam no payload anonimizado
    assert "Segredo Pessoal" not in str(resumo_anon)

    resp_local = responder_pergunta("Qual minha categoria de maior gasto?", lancs)
    assert resp_local["modo"] == "local_deterministico"
    assert "Alimentação" in resp_local["resposta"]

    # 3. Simula chave presente mas erro no provedor externo -> fallback gracioso
    monkeypatch.setenv("OPENAI_API_KEY", "chave-falsa-de-teste")
    import src.ai_assistant as ai_mod
    monkeypatch.setattr(
        ai_mod,
        "_consultar_llm_externo",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Falha de conexão simulada")),
    )
    resp_fallback = responder_pergunta("Resumo geral", lancs, usar_llm_externo=True)
    assert resp_fallback["modo"] == "local_deterministico"
    assert resp_fallback["erro_llm"] is not None
    assert "R$ 5.000,00" in resp_fallback["resposta"]
