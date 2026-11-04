"""Testes automatizados de importação e exportação CSV (Seção 4.4 e Seção 8)."""

from src.transactions import (
    confirmar_importacao_csv,
    exportar_lancamentos_csv,
    listar_lancamentos,
    validar_e_analisar_csv,
)


def test_importacao_csv_valido_e_deteccao_duplicatas(tmp_path):
    banco = tmp_path / "teste_csv.db"
    csv_conteudo = (
        "data,descricao,valor,categoria,tipo\n"
        "05/10/2026,Salário Outubro,5000.00,Salário,Receita\n"
        "10/10/2026,Supermercado Central,450.25,Alimentação,Despesa\n"
        "10/10/2026,Supermercado Central,450.25,Alimentação,Despesa\n"  # Duplicata no próprio CSV
    )

    analise = validar_e_analisar_csv(csv_conteudo, caminho_banco=banco)
    assert analise["erro_estrutural"] is None
    assert len(analise["validos"]) == 2
    assert len(analise["duplicados"]) == 1
    assert len(analise["erros"]) == 0

    inseridos = confirmar_importacao_csv(analise["validos"], caminho_banco=banco)
    assert inseridos == 2

    # Tentar importar novamente o mesmo arquivo deve detectar todas como duplicadas no banco
    segunda_analise = validar_e_analisar_csv(csv_conteudo, caminho_banco=banco)
    assert len(segunda_analise["validos"]) == 0
    assert len(segunda_analise["duplicados"]) == 3


def test_importacao_csv_invalido_nao_corrompe_banco(tmp_path):
    banco = tmp_path / "teste_csv_invalido.db"
    csv_com_erros = (
        "data,descricao,valor,categoria,tipo\n"
        "12/10/2026,Almoço Executivo,45.00,Alimentação,Despesa\n"
        "31/02/2026,Data Impossível,100.00,Lazer,Despesa\n"
        "15/10/2026,Valor Negativo,-50.00,Transporte,Despesa\n"
        "16/10/2026,Categoria Errada,200.00,Salário,Despesa\n"
    )

    analise = validar_e_analisar_csv(csv_com_erros, caminho_banco=banco)
    assert analise["erro_estrutural"] is None
    assert len(analise["validos"]) == 1
    assert len(analise["erros"]) == 3
    linhas_com_erro = [e["linha"] for e in analise["erros"]]
    assert linhas_com_erro == [3, 4, 5]

    # Antes da confirmação, o banco permanece vazio
    assert len(listar_lancamentos(caminho_banco=banco)) == 0


def test_importacao_csv_colunas_ausentes(tmp_path):
    banco = tmp_path / "teste_colunas.db"
    csv_sem_colunas = "data,descricao,valor\n2026-10-10,Teste,100\n"
    analise = validar_e_analisar_csv(csv_sem_colunas, caminho_banco=banco)
    assert analise["erro_estrutural"] is not None
    assert "categoria" in analise["erro_estrutural"]


def test_exportacao_csv(tmp_path):
    banco = tmp_path / "teste_export.db"
    csv_entrada = (
        "data;descricao;valor;categoria;tipo\n"
        "2026-10-05;Salário;4000,00;Salário;Receita\n"
        "2026-10-08;Internet;120,50;Contas e serviços;Despesa\n"
    )
    analise = validar_e_analisar_csv(csv_entrada, caminho_banco=banco)
    confirmar_importacao_csv(analise["validos"], caminho_banco=banco)

    lancamentos = listar_lancamentos(caminho_banco=banco)
    csv_exportado = exportar_lancamentos_csv(lancamentos)
    linhas = csv_exportado.strip().splitlines()
    assert linhas[0] == "data,tipo,categoria,descricao,valor"
    assert len(linhas) == 3
    assert "120.50" in csv_exportado
