"""Testes automatizados para CRUD de lançamentos, categorias editáveis e isolamento de dados demo."""

import pytest

from src.database import adicionar_categoria, listar_categorias, remover_categoria
from src.transactions import (
    carregar_dados_demonstracao,
    criar_lancamento,
    editar_lancamento,
    excluir_lancamento,
    listar_lancamentos,
    obter_lancamento,
    remover_dados_demonstracao,
)
from src.validators import ErroValidacao


def test_crud_completo_lancamento(tmp_path):
    banco = tmp_path / "teste_crud.db"

    # 1. Criação
    novo_id = criar_lancamento(
        descricao="Salário Mensal",
        valor="4500.50",
        data="05/10/2026",
        categoria="Salário",
        tipo="Receita",
        caminho_banco=banco,
    )
    obtido = obter_lancamento(novo_id, caminho_banco=banco)
    assert obtido is not None
    assert obtido["descricao"] == "Salário Mensal"
    assert obtido["valor"] == 4500.50
    assert obtido["data"] == "2026-10-05"
    assert obtido["data_br"] == "05/10/2026"
    assert obtido["is_demo"] is False

    # 2. Edição
    editar_lancamento(
        lancamento_id=novo_id,
        descricao="Salário + Bônus",
        valor="4800.75",
        data="06/10/2026",
        categoria="Salário",
        tipo="Receita",
        caminho_banco=banco,
    )
    atualizado = obter_lancamento(novo_id, caminho_banco=banco)
    assert atualizado["descricao"] == "Salário + Bônus"
    assert atualizado["valor"] == 4800.75
    assert atualizado["data"] == "2026-10-06"

    # 3. Exclusão
    excluir_lancamento(novo_id, caminho_banco=banco)
    assert obter_lancamento(novo_id, caminho_banco=banco) is None


def test_filtros_por_periodo_e_categoria(tmp_path):
    banco = tmp_path / "teste_filtros.db"
    criar_lancamento("Aluguel Setembro", 1500, "2026-09-10", "Moradia", "Despesa", caminho_banco=banco)
    criar_lancamento("Mercado Outubro", 600, "2026-10-12", "Alimentação", "Despesa", caminho_banco=banco)
    criar_lancamento("Salário Outubro", 5000, "2026-10-05", "Salário", "Receita", caminho_banco=banco)

    outubro = listar_lancamentos(ano=2026, mes=10, caminho_banco=banco)
    assert len(outubro) == 2

    moradia = listar_lancamentos(categoria="Moradia", caminho_banco=banco)
    assert len(moradia) == 1
    assert moradia[0]["descricao"] == "Aluguel Setembro"

    apenas_receitas = listar_lancamentos(tipo="Receita", caminho_banco=banco)
    assert len(apenas_receitas) == 1
    assert apenas_receitas[0]["categoria"] == "Salário"


def test_isolamento_dados_demonstracao_e_usuario(tmp_path):
    """
    Garante que carregar e remover os dados de demonstração nunca afete
    nem se misture aos lançamentos reais do usuário.
    """
    banco = tmp_path / "teste_demo.db"

    criar_lancamento("Meu Salário Real", 3200, "2026-10-05", "Salário", "Receita", caminho_banco=banco)
    qtd_demo = carregar_dados_demonstracao(caminho_banco=banco)
    assert qtd_demo > 0

    dados_usuario = listar_lancamentos(modo_dados="usuario", caminho_banco=banco)
    dados_demo = listar_lancamentos(modo_dados="demo", caminho_banco=banco)

    assert len(dados_usuario) == 1
    assert dados_usuario[0]["descricao"] == "Meu Salário Real"
    assert len(dados_demo) == qtd_demo

    # Remove dados demo e verifica se o lançamento real continua intacto
    removidos = remover_dados_demonstracao(caminho_banco=banco)
    assert removidos == qtd_demo
    assert len(listar_lancamentos(modo_dados="demo", caminho_banco=banco)) == 0
    assert len(listar_lancamentos(modo_dados="usuario", caminho_banco=banco)) == 1


def test_categorias_editaveis(tmp_path):
    banco = tmp_path / "teste_cat.db"
    adicionar_categoria("Pet Shop", "Despesa", caminho_banco=banco)
    cats = listar_categorias(caminho_banco=banco)
    assert "Pet Shop" in cats["Despesa"]

    # Não permite remover categoria em uso
    criar_lancamento("Ração", 120, "2026-10-10", "Pet Shop", "Despesa", caminho_banco=banco)
    with pytest.raises(ValueError, match="vinculado"):
        remover_categoria("Pet Shop", "Despesa", caminho_banco=banco)

    # Não permite remover 'Outros'
    with pytest.raises(ValueError, match="Outros"):
        remover_categoria("Outros", "Despesa", caminho_banco=banco)



def test_api_flask_endpoints_completos(tmp_path):
    """Testa as rotas REST da aplicação Flask Dark Fintech PRO (app.py)."""
    from app import app as flask_app

    banco = tmp_path / "teste_flask_api.db"
    flask_app.config["TESTING"] = True
    flask_app.config["DATABASE_PATH"] = str(banco)
    cliente = flask_app.test_client()

    # 1. Página inicial HTML Dark Fintech
    r_home = cliente.get("/")
    assert r_home.status_code == 200
    assert "FinanPy AI" in r_home.get_data(as_text=True)

    # 2. Criar lançamento via POST /api/lancamentos
    r_post = cliente.post(
        "/api/lancamentos",
        json={
            "descricao": "Salário API",
            "valor": "5200.00",
            "data": "2026-10-05",
            "categoria": "Salário",
            "tipo": "Receita",
            "modo": "usuario",
        },
    )
    assert r_post.status_code == 201
    lanc_id = r_post.get_json()["id"]

    # 3. Editar lançamento via PUT /api/lancamentos/<id>
    r_put = cliente.put(
        f"/api/lancamentos/{lanc_id}",
        json={
            "descricao": "Salário API Atualizado",
            "valor": "5500.00",
            "data": "2026-10-05",
            "categoria": "Salário",
            "tipo": "Receita",
        },
    )
    assert r_put.status_code == 200

    # 4. Consultar dashboard via GET /api/dashboard
    r_dash = cliente.get("/api/dashboard?modo=usuario")
    assert r_dash.status_code == 200
    dados = r_dash.get_json()
    assert dados["indicadores"]["total_receitas"] == 5500.0
    assert dados["lancamentos"][0]["descricao"] == "Salário API Atualizado"

    # 5. Perguntar ao FinanPy AI Assistant via POST /api/ia/perguntar
    r_ia = cliente.post(
        "/api/ia/perguntar",
        json={"pergunta": "Qual o resumo das minhas finanças?", "modo": "usuario", "usar_llm": False},
    )
    assert r_ia.status_code == 200
    assert "5.500,00" in r_ia.get_json()["resposta"]

    # 6. Excluir lançamento via DELETE /api/lancamentos/<id>
    r_del = cliente.delete(f"/api/lancamentos/{lanc_id}")
    assert r_del.status_code == 200
