"""
Módulo de Lançamentos Financeiros, Importação/Exportação CSV e Dados de Demonstração.
Inclui CRUD completo, armazenamento em centavos (precisão exata), detecção de duplicatas
e separação estrita entre dados reais do usuário e dados fictícios de demonstração.
"""

import csv
from decimal import Decimal
import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.database import conectar, inicializar_banco, listar_categorias
from src.validators import (
    ErroValidacao,
    formatar_data_br,
    para_decimal,
    validar_data,
    validar_lancamento,
)


def _gerar_assinatura(data_iso: str, tipo: str, categoria: str, descricao: str, valor_centavos: int) -> str:
    """Gera um identificador determinístico para detectar lançamentos duplicados em importações."""
    chave = f"{data_iso}|{tipo.strip().lower()}|{categoria.strip().lower()}|{descricao.strip().lower()}|{valor_centavos}"
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:32]


def _centavos_para_decimal(centavos: int) -> Decimal:
    return (Decimal(int(centavos)) / Decimal("100")).quantize(Decimal("0.01"))


def _linha_para_dict(row: Any) -> Dict[str, Any]:
    dec = _centavos_para_decimal(row["valor_centavos"])
    return {
        "id": int(row["id"]),
        "descricao": row["descricao"],
        "valor": float(dec),
        "valor_decimal": dec,
        "valor_centavos": int(row["valor_centavos"]),
        "data": row["data"],
        "data_br": formatar_data_br(row["data"]),
        "categoria": row["categoria"],
        "tipo": row["tipo"],
        "is_demo": bool(row["is_demo"]),
        "origem": "Demonstração" if row["is_demo"] else "Usuário",
    }


def criar_lancamento(
    descricao: str,
    valor: Union[float, int, str, Decimal],
    data: Union[str, Any],
    categoria: str,
    tipo: str,
    is_demo: bool = False,
    caminho_banco: Optional[Path] = None,
) -> int:
    """Valida e insere um novo lançamento financeiro no banco SQLite. Retorna o ID criado."""
    inicializar_banco(caminho_banco)
    categorias_atuais = listar_categorias(caminho_banco)
    dados = validar_lancamento(
        descricao=descricao,
        valor=valor,
        data_lancamento=data,
        categoria=categoria,
        tipo=tipo,
        categorias_por_tipo=categorias_atuais,
    )
    valor_centavos = int((dados["valor_decimal"] * 100).to_integral_value())
    assinatura = _gerar_assinatura(
        dados["data"], dados["tipo"], dados["categoria"], dados["descricao"], valor_centavos
    )

    with conectar(caminho_banco) as conn:
        cursor = conn.execute(
            """
            INSERT INTO lancamentos
                (descricao, valor_centavos, data, categoria, tipo, is_demo, assinatura_duplicata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dados["descricao"],
                valor_centavos,
                dados["data"],
                dados["categoria"],
                dados["tipo"],
                1 if is_demo else 0,
                assinatura,
            ),
        )
        return int(cursor.lastrowid)


def editar_lancamento(
    lancamento_id: int,
    descricao: str,
    valor: Union[float, int, str, Decimal],
    data: Union[str, Any],
    categoria: str,
    tipo: str,
    caminho_banco: Optional[Path] = None,
) -> None:
    """Valida e atualiza um lançamento existente pelo ID."""
    inicializar_banco(caminho_banco)
    categorias_atuais = listar_categorias(caminho_banco)
    dados = validar_lancamento(
        descricao=descricao,
        valor=valor,
        data_lancamento=data,
        categoria=categoria,
        tipo=tipo,
        categorias_por_tipo=categorias_atuais,
    )
    valor_centavos = int((dados["valor_decimal"] * 100).to_integral_value())
    assinatura = _gerar_assinatura(
        dados["data"], dados["tipo"], dados["categoria"], dados["descricao"], valor_centavos
    )

    with conectar(caminho_banco) as conn:
        existe = conn.execute(
            "SELECT id FROM lancamentos WHERE id = ?", (int(lancamento_id),)
        ).fetchone()
        if not existe:
            raise ErroValidacao(f"Lançamento #{lancamento_id} não encontrado.")

        conn.execute(
            """
            UPDATE lancamentos
               SET descricao = ?,
                   valor_centavos = ?,
                   data = ?,
                   categoria = ?,
                   tipo = ?,
                   assinatura_duplicata = ?
             WHERE id = ?
            """,
            (
                dados["descricao"],
                valor_centavos,
                dados["data"],
                dados["categoria"],
                dados["tipo"],
                assinatura,
                int(lancamento_id),
            ),
        )


def excluir_lancamento(lancamento_id: int, caminho_banco: Optional[Path] = None) -> None:
    """Remove um lançamento financeiro pelo ID."""
    inicializar_banco(caminho_banco)
    with conectar(caminho_banco) as conn:
        cursor = conn.execute("DELETE FROM lancamentos WHERE id = ?", (int(lancamento_id),))
        if cursor.rowcount == 0:
            raise ErroValidacao(f"Lançamento #{lancamento_id} não encontrado para exclusão.")


def obter_lancamento(
    lancamento_id: int, caminho_banco: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Busca um único lançamento pelo seu ID."""
    inicializar_banco(caminho_banco)
    with conectar(caminho_banco) as conn:
        row = conn.execute(
            "SELECT * FROM lancamentos WHERE id = ?", (int(lancamento_id),)
        ).fetchone()
        return _linha_para_dict(row) if row else None


def listar_lancamentos(
    modo_dados: str = "usuario",
    ano: Optional[int] = None,
    mes: Optional[int] = None,
    categoria: Optional[str] = None,
    tipo: Optional[str] = None,
    busca: Optional[str] = None,
    caminho_banco: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Lista lançamentos com filtros opcionais e isolamento entre dados reais e de demonstração:
    - modo_dados='usuario': retorna apenas lançamentos reais do usuário (is_demo = 0).
    - modo_dados='demo': retorna apenas lançamentos fictícios de demonstração (is_demo = 1).
    - modo_dados='todos': retorna ambos (apenas se explicitamente solicitado).
    """
    inicializar_banco(caminho_banco)
    clausulas: List[str] = []
    parametros: List[Any] = []

    if modo_dados == "usuario":
        clausulas.append("is_demo = 0")
    elif modo_dados == "demo":
        clausulas.append("is_demo = 1")

    if ano is not None:
        clausulas.append(" substr(data, 1, 4) = ? ")
        parametros.append(f"{int(ano):04d}")

    if mes is not None:
        clausulas.append(" substr(data, 6, 2) = ? ")
        parametros.append(f"{int(mes):02d}")

    if categoria and categoria != "Todas":
        clausulas.append(" categoria = ? ")
        parametros.append(categoria)

    if tipo and tipo != "Todos":
        clausulas.append(" tipo = ? ")
        parametros.append(tipo)

    if busca and busca.strip():
        clausulas.append(" LOWER(descricao) LIKE ? ")
        parametros.append(f"%{busca.strip().lower()}%")

    where_sql = f"WHERE {' AND '.join(clausulas)}" if clausulas else ""
    sql = f"SELECT * FROM lancamentos {where_sql} ORDER BY data DESC, id DESC"

    with conectar(caminho_banco) as conn:
        linhas = conn.execute(sql, parametros).fetchall()
        return [_linha_para_dict(r) for r in linhas]


# ==========================================
# Importação e Exportação CSV (Seção 4.4)
# ==========================================

COLUNAS_CSV_OBRIGATORIAS = {"data", "descricao", "valor", "categoria", "tipo"}


def validar_e_analisar_csv(
    conteudo_csv: Union[str, bytes],
    modo_dados: str = "usuario",
    caminho_banco: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Analisa e valida um arquivo CSV sem gravar no banco de dados.
    Retorna:
      - 'validos': lista de dicionários prontos para inserção
      - 'erros': lista de {'linha': int, 'motivo': str, 'dados': dict}
      - 'duplicados': lista de {'linha': int, 'motivo': str, 'dados': dict}
      - 'erro_estrutural': str ou None (ex.: arquivo vazio ou colunas ausentes)
    """
    inicializar_banco(caminho_banco)
    if isinstance(conteudo_csv, bytes):
        try:
            texto = conteudo_csv.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = conteudo_csv.decode("latin-1", errors="replace")
    else:
        texto = str(conteudo_csv)

    if not texto or not texto.strip():
        return {
            "validos": [],
            "erros": [],
            "duplicados": [],
            "erro_estrutural": "O arquivo CSV está vazio.",
        }

    # Detecta delimitador (vírgula ou ponto-e-vírgula, comum no Excel em português)
    primeira_linha = texto.strip().splitlines()[0]
    delimitador = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","

    leitor = csv.DictReader(io.StringIO(texto.strip()), delimiter=delimitador)
    if not leitor.fieldnames:
        return {
            "validos": [],
            "erros": [],
            "duplicados": [],
            "erro_estrutural": "Não foi possível identificar o cabeçalho do arquivo CSV.",
        }

    mapa_colunas = {col.strip().lower(): col for col in leitor.fieldnames if col}
    faltantes = COLUNAS_CSV_OBRIGATORIAS - set(mapa_colunas.keys())
    if faltantes:
        return {
            "validos": [],
            "erros": [],
            "duplicados": [],
            "erro_estrutural": (
                f"Colunas obrigatórias ausentes no CSV: {', '.join(sorted(faltantes))}. "
                f"Esperado: data, descricao, valor, categoria, tipo."
            ),
        }

    categorias_permitidas = listar_categorias(caminho_banco)
    flag_demo = 1 if modo_dados == "demo" else 0

    with conectar(caminho_banco) as conn:
        assinaturas_existentes = {
            row["assinatura_duplicata"]
            for row in conn.execute(
                "SELECT assinatura_duplicata FROM lancamentos WHERE is_demo = ? AND assinatura_duplicata IS NOT NULL",
                (flag_demo,),
            ).fetchall()
        }

    assinaturas_no_arquivo = set()
    validos: List[Dict[str, Any]] = []
    erros: List[Dict[str, Any]] = []
    duplicados: List[Dict[str, Any]] = []

    for indice, linha_bruta in enumerate(leitor, start=2):  # Linha 1 é o cabeçalho
        dados_linha = {
            chave: (linha_bruta.get(col_original) or "").strip()
            for chave, col_original in mapa_colunas.items()
        }
        try:
            validado = validar_lancamento(
                descricao=dados_linha.get("descricao"),
                valor=dados_linha.get("valor"),
                data_lancamento=dados_linha.get("data"),
                categoria=dados_linha.get("categoria"),
                tipo=dados_linha.get("tipo"),
                categorias_por_tipo=categorias_permitidas,
            )
            centavos = int((validado["valor_decimal"] * 100).to_integral_value())
            assinatura = _gerar_assinatura(
                validado["data"],
                validado["tipo"],
                validado["categoria"],
                validado["descricao"],
                centavos,
            )

            if assinatura in assinaturas_existentes:
                duplicados.append({
                    "linha": indice,
                    "motivo": "Lançamento idêntico já existe no banco de dados.",
                    "dados": dados_linha,
                })
                continue

            if assinatura in assinaturas_no_arquivo:
                duplicados.append({
                    "linha": indice,
                    "motivo": "Lançamento repetido dentro do próprio arquivo CSV.",
                    "dados": dados_linha,
                })
                continue

            assinaturas_no_arquivo.add(assinatura)
            validos.append({
                "linha": indice,
                "descricao": validado["descricao"],
                "valor": validado["valor"],
                "valor_centavos": centavos,
                "data": validado["data"],
                "data_br": formatar_data_br(validado["data"]),
                "categoria": validado["categoria"],
                "tipo": validado["tipo"],
                "assinatura_duplicata": assinatura,
            })
        except ErroValidacao as exc:
            erros.append({
                "linha": indice,
                "motivo": str(exc),
                "dados": dados_linha,
            })

    return {
        "validos": validos,
        "erros": erros,
        "duplicados": duplicados,
        "erro_estrutural": None,
    }


def confirmar_importacao_csv(
    lancamentos_validados: List[Dict[str, Any]],
    is_demo: bool = False,
    caminho_banco: Optional[Path] = None,
) -> int:
    """
    Grava uma lista de lançamentos previamente validados em uma única transação atômica.
    Se qualquer item falhar, nenhuma alteração parcial é persistida.
    """
    if not lancamentos_validados:
        return 0

    inicializar_banco(caminho_banco)
    inseridos = 0
    flag_demo = 1 if is_demo else 0

    with conectar(caminho_banco) as conn:
        for item in lancamentos_validados:
            # Revalida cada item para segurança contra adulteração
            validado = validar_lancamento(
                descricao=item["descricao"],
                valor=item["valor"],
                data_lancamento=item["data"],
                categoria=item["categoria"],
                tipo=item["tipo"],
                categorias_por_tipo=listar_categorias(caminho_banco),
            )
            centavos = int((validado["valor_decimal"] * 100).to_integral_value())
            assinatura = _gerar_assinatura(
                validado["data"],
                validado["tipo"],
                validado["categoria"],
                validado["descricao"],
                centavos,
            )
            existe = conn.execute(
                "SELECT 1 FROM lancamentos WHERE assinatura_duplicata = ? AND is_demo = ?",
                (assinatura, flag_demo),
            ).fetchone()
            if existe:
                continue

            conn.execute(
                """
                INSERT INTO lancamentos
                    (descricao, valor_centavos, data, categoria, tipo, is_demo, assinatura_duplicata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validado["descricao"],
                    centavos,
                    validado["data"],
                    validado["categoria"],
                    validado["tipo"],
                    flag_demo,
                    assinatura,
                ),
            )
            inseridos += 1

    return inseridos


def exportar_lancamentos_csv(lancamentos: List[Dict[str, Any]]) -> str:
    """Gera o conteúdo CSV (UTF-8) dos lançamentos informados."""
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(["data", "tipo", "categoria", "descricao", "valor"])
    for item in lancamentos:
        valor_dec = para_decimal(item["valor"])
        escritor.writerow([
            item["data"],
            item["tipo"],
            item["categoria"],
            item["descricao"],
            f"{valor_dec:.2f}",
        ])
    return saida.getvalue()


# ==========================================
# Dados Fictícios de Demonstração (Seção 4.7)
# ==========================================

DADOS_FICTICIOS_DEMO = [
    # Agosto / 2026
    ("2026-08-05", "Receita", "Salário", "[DEMO] Salário Mensal CLT", "5800.00"),
    ("2026-08-08", "Despesa", "Moradia", "[DEMO] Aluguel e Condomínio", "1850.00"),
    ("2026-08-10", "Despesa", "Contas e serviços", "[DEMO] Energia, Água e Internet Fibra", "340.00"),
    ("2026-08-12", "Despesa", "Alimentação", "[DEMO] Compras Supermercado Mensal", "980.00"),
    ("2026-08-15", "Despesa", "Transporte", "[DEMO] Combustível e Transporte App", "410.00"),
    ("2026-08-18", "Despesa", "Saúde", "[DEMO] Plano de Saúde e Farmácia", "390.00"),
    ("2026-08-22", "Despesa", "Lazer", "[DEMO] Cinema e Jantar de Fim de Semana", "280.00"),
    ("2026-08-25", "Despesa", "Educação", "[DEMO] Curso de Python e IA", "190.00"),
    # Setembro / 2026
    ("2026-09-05", "Receita", "Salário", "[DEMO] Salário Mensal CLT", "5800.00"),
    ("2026-09-12", "Receita", "Renda extra", "[DEMO] Projeto Freelance de Automação", "950.00"),
    ("2026-09-08", "Despesa", "Moradia", "[DEMO] Aluguel e Condomínio", "1850.00"),
    ("2026-09-10", "Despesa", "Contas e serviços", "[DEMO] Energia, Água e Internet Fibra", "355.00"),
    ("2026-09-14", "Despesa", "Alimentação", "[DEMO] Supermercado e Delivery", "1190.00"),
    ("2026-09-16", "Despesa", "Transporte", "[DEMO] Combustível e Manutenção", "460.00"),
    ("2026-09-19", "Despesa", "Saúde", "[DEMO] Plano de Saúde e Academia", "420.00"),
    ("2026-09-21", "Despesa", "Lazer", "[DEMO] Passeio e Restaurantes", "450.00"),
    ("2026-09-25", "Despesa", "Compras", "[DEMO] Fone de Ouvido e Acessórios", "320.00"),
    # Outubro / 2026
    ("2026-10-05", "Receita", "Salário", "[DEMO] Salário Mensal CLT", "5800.00"),
    ("2026-10-15", "Receita", "Renda extra", "[DEMO] Consultoria de Dados", "600.00"),
    ("2026-10-08", "Despesa", "Moradia", "[DEMO] Aluguel e Condomínio", "1850.00"),
    ("2026-10-10", "Despesa", "Contas e serviços", "[DEMO] Energia, Água e Internet Fibra", "360.00"),
    ("2026-10-13", "Despesa", "Alimentação", "[DEMO] Supermercado, Feira e Delivery", "1480.00"),
    ("2026-10-17", "Despesa", "Transporte", "[DEMO] Combustível e Pedágio", "490.00"),
    ("2026-10-20", "Despesa", "Saúde", "[DEMO] Plano de Saúde", "350.00"),
    ("2026-10-24", "Despesa", "Lazer", "[DEMO] Shows, Streaming e Restaurantes", "620.00"),
    ("2026-10-27", "Despesa", "Educação", "[DEMO] Livros Técnicos", "160.00"),
]


def carregar_dados_demonstracao(caminho_banco: Optional[Path] = None) -> int:
    """
    Carrega o conjunto de dados inteiramente fictícios marcados com is_demo=1,
    sem misturar nem alterar os lançamentos reais do usuário (is_demo=0).
    """
    inicializar_banco(caminho_banco)
    existentes = listar_lancamentos(modo_dados="demo", caminho_banco=caminho_banco)
    if existentes:
        return 0

    inseridos = 0
    for data_iso, tipo, categoria, descricao, valor in DADOS_FICTICIOS_DEMO:
        criar_lancamento(
            descricao=descricao,
            valor=valor,
            data=data_iso,
            categoria=categoria,
            tipo=tipo,
            is_demo=True,
            caminho_banco=caminho_banco,
        )
        inseridos += 1

    # Adiciona metas fictícias de demonstração se não houver metas demo
    with conectar(caminho_banco) as conn:
        qtd_metas_demo = conn.execute(
            "SELECT COUNT(*) AS qtd FROM metas WHERE is_demo = 1"
        ).fetchone()["qtd"]
        if qtd_metas_demo == 0:
            conn.execute(
                """
                INSERT INTO metas (titulo, valor_alvo_centavos, valor_inicial_centavos, prazo, is_demo)
                VALUES (?, ?, ?, ?, 1)
                """,
                ("[DEMO] Reserva de Emergência (6 meses)", 1200000, 150000, "2027-06-30"),
            )
            conn.execute(
                """
                INSERT INTO metas (titulo, valor_alvo_centavos, valor_inicial_centavos, prazo, is_demo)
                VALUES (?, ?, ?, ?, 1)
                """,
                ("[DEMO] Notebook Novo para Estudos de IA", 650000, 50000, "2027-03-31"),
            )

    return inseridos


def remover_dados_demonstracao(caminho_banco: Optional[Path] = None) -> int:
    """
    Remove exclusivamente os lançamentos e metas fictícios (is_demo = 1),
    preservando intactos todos os dados reais do usuário (is_demo = 0).
    """
    inicializar_banco(caminho_banco)
    with conectar(caminho_banco) as conn:
        cursor = conn.execute("DELETE FROM lancamentos WHERE is_demo = 1")
        conn.execute("DELETE FROM metas WHERE is_demo = 1")
        return int(cursor.rowcount)


def excluir_dados_usuario(caminho_banco: Optional[Path] = None) -> int:
    """Remove todos os lançamentos e metas reais do usuário (is_demo = 0)."""
    inicializar_banco(caminho_banco)
    with conectar(caminho_banco) as conn:
        cursor = conn.execute("DELETE FROM lancamentos WHERE is_demo = 0")
        conn.execute("DELETE FROM metas WHERE is_demo = 0")
        return int(cursor.rowcount)
