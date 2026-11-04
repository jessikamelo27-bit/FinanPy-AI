"""
Módulo de Persistência SQLite do FinanPy AI.
Gerencia conexões parametrizadas, criação de tabelas (lançamentos, categorias editáveis e metas)
e isolamento entre dados reais do usuário e dados de demonstração (is_demo).
"""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional, Iterator

from src.validators import CATEGORIAS_INICIAIS

DIRETORIO_BASE = Path(__file__).resolve().parent.parent
DIRETORIO_DADOS = DIRETORIO_BASE / "data"
CAMINHO_BANCO_PADRAO = DIRETORIO_DADOS / "finanpy_ai.db"


def obter_caminho_banco(caminho_customizado: Optional[Path] = None) -> Path:
    """Retorna o caminho do banco SQLite, garantindo que a pasta 'data/' exista."""
    caminho = Path(caminho_customizado) if caminho_customizado else CAMINHO_BANCO_PADRAO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


@contextmanager
def conectar(caminho_banco: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """
    Gerenciador de contexto para conexão SQLite com transações seguras,
    chaves estrangeiras ativas e acesso às colunas por nome.
    """
    caminho = obter_caminho_banco(caminho_banco)
    conn = sqlite3.connect(str(caminho))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_banco(caminho_banco: Optional[Path] = None) -> None:
    """
    Cria as tabelas de lançamentos, categorias e metas caso não existam,
    e popula as categorias iniciais padrão de Receita e Despesa.
    """
    with conectar(caminho_banco) as conn:
        cursor = conn.cursor()

        # 1. Tabela de Categorias Editáveis (diferenciadas por Receita e Despesa)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('Receita', 'Despesa')),
                UNIQUE(nome, tipo)
            )
        """)

        # 2. Tabela de Lançamentos Financeiros (valor armazenado em centavos para precisão exata)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lancamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                valor_centavos INTEGER NOT NULL CHECK(valor_centavos > 0),
                data TEXT NOT NULL,
                categoria TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('Receita', 'Despesa')),
                is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1)),
                assinatura_duplicata TEXT,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_lancamentos_data
            ON lancamentos(data DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_lancamentos_demo
            ON lancamentos(is_demo)
        """)

        # 3. Tabela de Metas de Economia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                valor_alvo_centavos INTEGER NOT NULL CHECK(valor_alvo_centavos > 0),
                valor_inicial_centavos INTEGER NOT NULL DEFAULT 0 CHECK(valor_inicial_centavos >= 0),
                prazo TEXT NOT NULL,
                is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1)),
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Popula categorias iniciais caso a tabela esteja vazia
        total_cat = cursor.execute("SELECT COUNT(*) AS qtd FROM categorias").fetchone()["qtd"]
        if total_cat == 0:
            for tipo, nomes in CATEGORIAS_INICIAIS.items():
                for nome in nomes:
                    cursor.execute(
                        "INSERT OR IGNORE INTO categorias (nome, tipo) VALUES (?, ?)",
                        (nome, tipo),
                    )


def listar_categorias(caminho_banco: Optional[Path] = None) -> Dict[str, List[str]]:
    """Retorna um dicionário {'Receita': [...], 'Despesa': [...]} com as categorias cadastradas."""
    inicializar_banco(caminho_banco)
    resultado: Dict[str, List[str]] = {"Receita": [], "Despesa": []}
    with conectar(caminho_banco) as conn:
        linhas = conn.execute(
            "SELECT nome, tipo FROM categorias ORDER BY tipo, nome ASC"
        ).fetchall()
        for row in linhas:
            resultado[row["tipo"]].append(row["nome"])
    return resultado


def adicionar_categoria(
    nome: str,
    tipo: str,
    caminho_banco: Optional[Path] = None,
) -> None:
    """Adiciona uma nova categoria personalizada ao tipo ('Receita' ou 'Despesa')."""
    if tipo not in ("Receita", "Despesa"):
        raise ValueError("O tipo da categoria deve ser 'Receita' ou 'Despesa'.")
    nome_limpo = " ".join(str(nome).strip().split())
    if not nome_limpo or len(nome_limpo) > 60:
        raise ValueError("Informe um nome de categoria válido (até 60 caracteres).")

    inicializar_banco(caminho_banco)
    with conectar(caminho_banco) as conn:
        existe = conn.execute(
            "SELECT 1 FROM categorias WHERE LOWER(nome) = LOWER(?) AND tipo = ?",
            (nome_limpo, tipo),
        ).fetchone()
        if existe:
            raise ValueError(f"A categoria '{nome_limpo}' já existe para {tipo}.")
        conn.execute(
            "INSERT INTO categorias (nome, tipo) VALUES (?, ?)",
            (nome_limpo, tipo),
        )


def remover_categoria(
    nome: str,
    tipo: str,
    caminho_banco: Optional[Path] = None,
) -> None:
    """Remove uma categoria caso não seja a categoria padrão 'Outros' e não esteja em uso."""
    if nome.strip() == "Outros":
        raise ValueError("A categoria padrão 'Outros' não pode ser removida.")

    with conectar(caminho_banco) as conn:
        em_uso = conn.execute(
            "SELECT COUNT(*) AS qtd FROM lancamentos WHERE categoria = ? AND tipo = ?",
            (nome.strip(), tipo),
        ).fetchone()["qtd"]
        if em_uso > 0:
            raise ValueError(
                f"Não é possível remover '{nome}' pois existem {em_uso} lançamento(s) vinculado(s) a ela."
            )
        conn.execute(
            "DELETE FROM categorias WHERE nome = ? AND tipo = ?",
            (nome.strip(), tipo),
        )
