# 🧪 Relatório de Testes e Verificação — FinanPy AI

## 1. Ambiente de Execução dos Testes

- **Sistema Operacional:** Windows (win32)
- **Interpretador Python:** Python 3.11.9 (`.venv\Scripts\python.exe`)
- **Framework de Testes:** `pytest 9.2.0`
- **Comando Executado:**
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -v
  ```

---

## 2. Resultado Real da Suíte Automatizada

- **Total de casos de teste executados:** `38`
- **Testes aprovados (`PASSED`):** `38`
- **Testes reprovados (`FAILED`):** `0`
- **Tempo de execução:** `11.39s`

### Detalhamento por Módulo de Teste

| Arquivo de Teste | Casos Executados | Cobertura Funcional Verificada | Status |
| :--- | :---: | :--- | :---: |
| `tests/test_validators.py` | 25 | Precisão decimal (`0.10 + 0.20 == 0.30`), rejeição de zeros/negativos, `NaN`, `inf`, booleanos, datas inválidas (`31/02/2026`), bloqueio de categorias incompatíveis com o tipo (`Receita` vs `Despesa`). | ✅ 25/25 |
| `tests/test_transactions.py` | 5 | Criação, leitura, edição e exclusão (CRUD), filtros por mês/ano/categoria/tipo, categorias editáveis, rotas REST da API Flask (`app.py`) e isolamento estrito entre dados fictícios (`is_demo=1`) e dados reais (`is_demo=0`). | ✅ 5/5 |
| `tests/test_import_export.py` | 4 | Importação de CSV válido (`,` e `;`), detecção de duplicatas no arquivo e no banco, rejeição de linhas com erro sem corromper o banco, validação de colunas ausentes e exportação CSV. | ✅ 4/4 |
| `tests/test_analytics.py` | 4 | Cálculos com banco vazio, caso-limite sem receitas (`percentual_comprometido = None`), comparativo mensal, evolução de saldo, metas de economia e assistente de IA (modo sem chave de API, anonimização de descrições e fallback em falha de API externa). | ✅ 4/4 |

---

## 3. Verificações Manuais e de Integração Realizadas

1. **Inicialização do Banco SQLite (`data/finanpy_ai.db`)**: Verificada a criação automática do diretório `data/` e das tabelas `categorias`, `lancamentos` e `metas`.
2. **Isolamento de Dados de Demonstração**: Verificado que o carregamento de 26 lançamentos fictícios de 3 meses (`2026-08`, `2026-09` e `2026-10`) e 2 metas de demonstração ocorre com `is_demo = 1`, podendo ser removido integralmente sem afetar os lançamentos reais (`is_demo = 0`).
3. **Execução do Servidor Streamlit (`app.py`)**: Servidor iniciado na porta `8501` e verificado via requisição HTTP (`StatusCode 200`).
