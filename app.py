"""
FinanPy AI PRO — Servidor Web Full-Stack (Flask + REST API JSON)
Interface Dark Fintech sem protótipos fictícios de bancos, conectada 100% aos módulos reais em src/:
- Persistência SQLite com precisão de centavos (src/database.py, src/transactions.py)
- Validações com Decimal e datas BR/ISO (src/validators.py)
- Motor analítico Pandas/Decimal (src/analytics.py, src/goals.py)
- Assistente de IA determinístico local + LLM opcional (src/ai_assistant.py)
"""

from pathlib import Path
from typing import Any, Dict, Optional
from flask import Flask, Response, jsonify, render_template, request

from src.ai_assistant import (
    gerar_diagnostico_deterministico,
    responder_pergunta,
    status_integracao_ia,
)
from src.analytics import (
    calcular_indicadores,
    comparativo_mensal,
    evolucao_saldo,
    gastos_por_categoria,
    gerar_dados_sankey,
    para_dataframe,
)
from src.database import (
    adicionar_categoria,
    inicializar_banco,
    listar_categorias,
    remover_categoria,
)
from src.goals import (
    atualizar_valor_inicial_meta,
    avaliar_progresso_meta,
    criar_meta,
    excluir_meta,
    listar_metas,
)
from src.transactions import (
    carregar_dados_demonstracao,
    confirmar_importacao_csv,
    criar_lancamento,
    editar_lancamento,
    excluir_dados_usuario,
    excluir_lancamento,
    exportar_lancamentos_csv,
    listar_lancamentos,
    remover_dados_demonstracao,
    validar_e_analisar_csv,
)
from src.validators import ErroValidacao

app = Flask(__name__)
app.config["DATABASE_PATH"] = None  # Permite injeção de banco temporário nos testes automatizados

inicializar_banco()


def _caminho_db() -> Optional[Path]:
    caminho = app.config.get("DATABASE_PATH")
    return Path(caminho) if caminho else None


def _serializar_lancamento(item: Dict[str, Any]) -> Dict[str, Any]:
    """Remove objetos Decimal internos para serialização limpa em JSON."""
    copia = dict(item)
    copia.pop("valor_decimal", None)
    return copia


@app.errorhandler(ErroValidacao)
def tratar_erro_validacao(exc: ErroValidacao):
    return jsonify({"erro": str(exc)}), 400


@app.errorhandler(ValueError)
def tratar_value_error(exc: ValueError):
    return jsonify({"erro": str(exc)}), 400


@app.route("/")
def index():
    """Renderiza a interface web Dark Fintech PRO."""
    return render_template("index.html")


@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    """
    Retorna todos os indicadores, séries para gráficos Plotly, diagnóstico do FinanPy AI Assistant,
    lançamentos filtrados, categorias editáveis e metas avaliadas.
    """
    db_path = _caminho_db()
    modo = request.args.get("modo", "usuario")
    if modo not in ("usuario", "demo"):
        modo = "usuario"

    ano_str = request.args.get("ano", "Todos")
    mes_str = request.args.get("mes", "Todos")
    categoria = request.args.get("categoria", "Todas")

    ano = int(ano_str) if ano_str and ano_str != "Todos" and ano_str.isdigit() else None
    mes = int(mes_str) if mes_str and mes_str != "Todos" and mes_str.isdigit() else None
    cat_filtro = categoria if categoria and categoria != "Todas" else None

    todos_do_modo = listar_lancamentos(modo_dados=modo, caminho_banco=db_path)
    df_modo = para_dataframe(todos_do_modo)
    anos_disponiveis = (
        sorted(df_modo["ano"].dropna().astype(int).unique().tolist(), reverse=True)
        if not df_modo.empty
        else []
    )

    lancamentos_filtrados = listar_lancamentos(
        modo_dados=modo,
        ano=ano,
        mes=mes,
        categoria=cat_filtro,
        caminho_banco=db_path,
    )

    metas_brutas = listar_metas(modo_dados=modo, caminho_banco=db_path)
    metas_avaliadas = [avaliar_progresso_meta(m, todos_do_modo) for m in metas_brutas]

    indicadores = calcular_indicadores(lancamentos_filtrados)
    df_mensal = comparativo_mensal(lancamentos_filtrados)
    df_cat = gastos_por_categoria(lancamentos_filtrados)
    df_evol = evolucao_saldo(lancamentos_filtrados)
    sankey = gerar_dados_sankey(lancamentos_filtrados)
    diagnostico = gerar_diagnostico_deterministico(lancamentos_filtrados, metas_brutas)

    tem_demo = len(listar_lancamentos(modo_dados="demo", caminho_banco=db_path)) > 0

    return jsonify({
        "modo_atual": modo,
        "tem_dados_demo": tem_demo,
        "anos_disponiveis": anos_disponiveis,
        "categorias_por_tipo": listar_categorias(db_path),
        "indicadores": indicadores,
        "comparativo_mensal": df_mensal.to_dict(orient="records"),
        "gastos_categoria": df_cat.to_dict(orient="records"),
        "evolucao_saldo": df_evol.to_dict(orient="records"),
        "sankey": sankey,
        "diagnostico_ia": diagnostico,
        "status_ia": status_integracao_ia(),
        "lancamentos": [_serializar_lancamento(x) for x in lancamentos_filtrados],
        "metas": metas_avaliadas,
    })


# ==========================================
# Rotas REST de Lançamentos (CRUD)
# ==========================================

@app.route("/api/lancamentos", methods=["POST"])
def api_criar_lancamento():
    dados = request.get_json(force=True)
    modo = dados.get("modo", "usuario")
    novo_id = criar_lancamento(
        descricao=dados.get("descricao"),
        valor=dados.get("valor"),
        data=dados.get("data"),
        categoria=dados.get("categoria"),
        tipo=dados.get("tipo"),
        is_demo=(modo == "demo"),
        caminho_banco=_caminho_db(),
    )
    return jsonify({"id": novo_id, "mensagem": "Lançamento registrado com sucesso!"}), 201


@app.route("/api/lancamentos/<int:lancamento_id>", methods=["PUT"])
def api_editar_lancamento(lancamento_id: int):
    dados = request.get_json(force=True)
    editar_lancamento(
        lancamento_id=lancamento_id,
        descricao=dados.get("descricao"),
        valor=dados.get("valor"),
        data=dados.get("data"),
        categoria=dados.get("categoria"),
        tipo=dados.get("tipo"),
        caminho_banco=_caminho_db(),
    )
    return jsonify({"mensagem": f"Lançamento #{lancamento_id} atualizado com sucesso!"})


@app.route("/api/lancamentos/<int:lancamento_id>", methods=["DELETE"])
def api_excluir_lancamento(lancamento_id: int):
    excluir_lancamento(lancamento_id, caminho_banco=_caminho_db())
    return jsonify({"mensagem": f"Lançamento #{lancamento_id} excluído com sucesso!"})


# ==========================================
# Rotas REST de Importação e Exportação CSV
# ==========================================

@app.route("/api/csv/validar", methods=["POST"])
def api_validar_csv():
    dados = request.get_json(force=True)
    conteudo = dados.get("conteudo_csv", "")
    modo = dados.get("modo", "usuario")
    analise = validar_e_analisar_csv(conteudo, modo_dados=modo, caminho_banco=_caminho_db())
    return jsonify(analise)


@app.route("/api/csv/confirmar", methods=["POST"])
def api_confirmar_csv():
    dados = request.get_json(force=True)
    validos = dados.get("validos", [])
    modo = dados.get("modo", "usuario")
    inseridos = confirmar_importacao_csv(
        validos, is_demo=(modo == "demo"), caminho_banco=_caminho_db()
    )
    return jsonify({"inseridos": inseridos, "mensagem": f"{inseridos} lançamento(s) importado(s) com sucesso!"}), 201


@app.route("/api/csv/exportar", methods=["GET"])
def api_exportar_csv():
    db_path = _caminho_db()
    modo = request.args.get("modo", "usuario")
    ano_str = request.args.get("ano", "Todos")
    mes_str = request.args.get("mes", "Todos")
    categoria = request.args.get("categoria", "Todas")

    ano = int(ano_str) if ano_str and ano_str != "Todos" and ano_str.isdigit() else None
    mes = int(mes_str) if mes_str and mes_str != "Todos" and mes_str.isdigit() else None
    cat_filtro = categoria if categoria and categoria != "Todas" else None

    lancamentos = listar_lancamentos(
        modo_dados=modo, ano=ano, mes=mes, categoria=cat_filtro, caminho_banco=db_path
    )
    csv_str = exportar_lancamentos_csv(lancamentos)
    nome_arquivo = f"finanpy_ai_{modo}.csv"
    return Response(
        csv_str.encode("utf-8-sig"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


# ==========================================
# Rotas REST de Metas e Planejamento
# ==========================================

@app.route("/api/metas", methods=["POST"])
def api_criar_meta():
    dados = request.get_json(force=True)
    modo = dados.get("modo", "usuario")
    meta_id = criar_meta(
        titulo=dados.get("titulo"),
        valor_alvo=dados.get("valor_alvo"),
        prazo=dados.get("prazo"),
        valor_inicial=dados.get("valor_inicial", 0),
        is_demo=(modo == "demo"),
        caminho_banco=_caminho_db(),
    )
    return jsonify({"id": meta_id, "mensagem": "Meta cadastrada com sucesso!"}), 201


@app.route("/api/metas/<int:meta_id>", methods=["PATCH"])
def api_atualizar_meta(meta_id: int):
    dados = request.get_json(force=True)
    atualizar_valor_inicial_meta(
        meta_id=meta_id,
        novo_valor_inicial=dados.get("valor_inicial", 0),
        caminho_banco=_caminho_db(),
    )
    return jsonify({"mensagem": "Reserva inicial da meta atualizada!"})


@app.route("/api/metas/<int:meta_id>", methods=["DELETE"])
def api_excluir_meta(meta_id: int):
    excluir_meta(meta_id, caminho_banco=_caminho_db())
    return jsonify({"mensagem": "Meta removida com sucesso!"})


# ==========================================
# Rotas REST do FinanPy AI Assistant
# ==========================================

@app.route("/api/ia/perguntar", methods=["POST"])
def api_ia_perguntar():
    dados = request.get_json(force=True)
    pergunta = dados.get("pergunta", "")
    modo = dados.get("modo", "usuario")
    usar_llm = bool(dados.get("usar_llm", False))

    db_path = _caminho_db()
    lancamentos = listar_lancamentos(modo_dados=modo, caminho_banco=db_path)
    metas = listar_metas(modo_dados=modo, caminho_banco=db_path)

    resposta = responder_pergunta(
        pergunta=pergunta,
        lancamentos=lancamentos,
        metas=metas,
        usar_llm_externo=usar_llm,
    )
    return jsonify(resposta)


# ==========================================
# Rotas REST de Categorias e Dados de Demonstração
# ==========================================

@app.route("/api/categorias", methods=["POST"])
def api_adicionar_categoria():
    dados = request.get_json(force=True)
    adicionar_categoria(
        nome=dados.get("nome", ""),
        tipo=dados.get("tipo", ""),
        caminho_banco=_caminho_db(),
    )
    return jsonify({"mensagem": "Categoria adicionada com sucesso!"}), 201


@app.route("/api/categorias", methods=["DELETE"])
def api_remover_categoria():
    dados = request.get_json(force=True)
    remover_categoria(
        nome=dados.get("nome", ""),
        tipo=dados.get("tipo", ""),
        caminho_banco=_caminho_db(),
    )
    return jsonify({"mensagem": "Categoria removida com sucesso!"})


@app.route("/api/demo/carregar", methods=["POST"])
def api_carregar_demo():
    qtd = carregar_dados_demonstracao(caminho_banco=_caminho_db())
    return jsonify({"inseridos": qtd, "mensagem": f"{qtd} lançamentos fictícios de demonstração carregados!"})


@app.route("/api/demo/remover", methods=["POST"])
def api_remover_demo():
    rem = remover_dados_demonstracao(caminho_banco=_caminho_db())
    return jsonify({"removidos": rem, "mensagem": f"{rem} lançamentos de demonstração removidos!"})


@app.route("/api/dados-usuario/limpar", methods=["POST"])
def api_limpar_usuario():
    rem = excluir_dados_usuario(caminho_banco=_caminho_db())
    return jsonify({"removidos": rem, "mensagem": f"{rem} lançamentos reais excluídos do banco local."})


if __name__ == "__main__":
    import os
    import sys

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    print("[FinanPy AI PRO] Servidor Dark Fintech iniciado em http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

