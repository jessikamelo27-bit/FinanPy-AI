/**
 * FinanPy AI PRO — Front-End Application Logic (Dark Fintech Edition)
 * Conecta-se à API Flask/SQLite/Pandas, gerencia CRUD com edição, importação CSV validada,
 * metas de economia e o FinanPy AI Assistant.
 */

let estado = {
    modo: "usuario",
    ano: "Todos",
    mes: "Todos",
    categoria: "Todas",
    categoriasPorTipo: {
        "Receita": ["Salário", "Renda extra", "Outros"],
        "Despesa": ["Alimentação", "Moradia", "Transporte", "Saúde", "Educação", "Lazer", "Contas e serviços", "Compras", "Outros"]
    },
    lancamentos: [],
    metas: [],
    validosCsvPendentes: []
};

const formatadorBRL = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
});

function formatarMoeda(valor) {
    return formatadorBRL.format(Number(valor || 0));
}

function mostrarToast(mensagem) {
    const toast = document.getElementById("toast");
    toast.textContent = mensagem;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3200);
}

// ============================================================
// 1. NAVEGAÇÃO ENTRE SEÇÕES E MODAIS
// ============================================================
function configurarNavegacao() {
    const botoes = document.querySelectorAll(".nav-item");
    const secoes = document.querySelectorAll(".view-section");

    botoes.forEach(btn => {
        btn.addEventListener("click", () => {
            botoes.forEach(b => b.classList.remove("active"));
            secoes.forEach(s => s.classList.remove("active"));
            btn.classList.add("active");
            const alvo = document.getElementById(btn.dataset.target);
            if (alvo) alvo.classList.add("active");
            window.dispatchEvent(new Event("resize"));
        });
    });

    document.querySelectorAll("[data-close]").forEach(btn => {
        btn.addEventListener("click", () => {
            document.getElementById(btn.dataset.close).classList.remove("open");
        });
    });

    document.getElementById("btn-abrir-modal-novo").addEventListener("click", abrirModalNovoLancamento);
    document.getElementById("btn-abrir-modal-meta").addEventListener("click", () => {
        document.getElementById("modal-meta").classList.add("open");
    });
}

function atualizarOpcoesCategoriaModal(categoriaSelecionada = null) {
    const tipo = document.getElementById("lanc-tipo").value;
    const selectCat = document.getElementById("lanc-categoria");
    const lista = estado.categoriasPorTipo[tipo] || ["Outros"];
    selectCat.innerHTML = lista.map(c => `<option value="${c}">${c}</option>`).join("");
    if (categoriaSelecionada && lista.includes(categoriaSelecionada)) {
        selectCat.value = categoriaSelecionada;
    }
}

function abrirModalNovoLancamento() {
    document.getElementById("modal-lancamento-titulo").textContent = "➕ Novo Lançamento";
    document.getElementById("lanc-id").value = "";
    document.getElementById("lanc-tipo").value = "Despesa";
    atualizarOpcoesCategoriaModal();
    document.getElementById("lanc-descricao").value = "";
    document.getElementById("lanc-valor").value = "";
    document.getElementById("lanc-data").value = new Date().toISOString().split("T")[0];
    document.getElementById("erro-form-lancamento").style.display = "none";
    document.getElementById("modal-lancamento").classList.add("open");
}

function abrirModalEdicao(id) {
    const item = estado.lancamentos.find(x => x.id === id);
    if (!item) return;

    document.getElementById("modal-lancamento-titulo").textContent = `✏️ Editar Lançamento #${item.id}`;
    document.getElementById("lanc-id").value = String(item.id);
    document.getElementById("lanc-tipo").value = item.tipo;
    atualizarOpcoesCategoriaModal(item.categoria);
    document.getElementById("lanc-descricao").value = item.descricao;
    document.getElementById("lanc-valor").value = Number(item.valor).toFixed(2);
    document.getElementById("lanc-data").value = item.data;
    document.getElementById("erro-form-lancamento").style.display = "none";
    document.getElementById("modal-lancamento").classList.add("open");
}

// ============================================================
// 2. CARREGAMENTO CENTRAL (/api/dashboard)
// ============================================================
async function carregarDados() {
    const params = new URLSearchParams({
        modo: estado.modo,
        ano: estado.ano,
        mes: estado.mes,
        categoria: estado.categoria
    });

    const resp = await fetch(`/api/dashboard?${params.toString()}`);
    const dados = await resp.json();

    estado.categoriasPorTipo = dados.categorias_por_tipo || estado.categoriasPorTipo;
    estado.lancamentos = dados.lancamentos || [];
    estado.metas = dados.metas || [];

    // Atualiza banner e seletor de modo
    document.getElementById("select-modo-dados").value = dados.modo_atual;
    document.getElementById("sidebar-modo-label").textContent =
        dados.modo_atual === "demo" ? "🧪 Dados de Demonstração" : "👤 Meus Dados Reais";
    document.getElementById("banner-demo").style.display =
        dados.modo_atual === "demo" ? "block" : "none";

    atualizarFiltrosGlobais(dados.anos_disponiveis || []);
    renderizarKPIs(dados.indicadores);

    const semDados = estado.lancamentos.length === 0;
    document.getElementById("dashboard-vazio").style.display = semDados ? "block" : "none";
    document.getElementById("dashboard-graficos").style.display = semDados ? "none" : "block";

    if (!semDados) {
        renderizarGraficoMensal(dados.comparativo_mensal || []);
        renderizarGraficoCategorias(dados.gastos_categoria || []);
        renderizarGraficoEvolucaoSaldo(dados.evolucao_saldo || []);
        renderizarGraficoSankey(dados.sankey || {});
    }

    renderizarTabelaLancamentos();
    renderizarMetas();
    renderizarAssistenteIA(dados.diagnostico_ia, dados.status_ia);
    renderizarCategoriasConfig();
}

function atualizarFiltrosGlobais(anos) {
    const selAno = document.getElementById("filtro-ano");
    const opcoesAno = [`<option value="Todos">Todos</option>`];
    anos.forEach(a => {
        const sel = String(a) === String(estado.ano) ? "selected" : "";
        opcoesAno.push(`<option value="${a}" ${sel}>${a}</option>`);
    });
    selAno.innerHTML = opcoesAno.join("");

    const selCat = document.getElementById("filtro-categoria-global");
    const todasCats = Array.from(new Set([
        ...(estado.categoriasPorTipo.Receita || []),
        ...(estado.categoriasPorTipo.Despesa || [])
    ])).sort();
    const opcoesCat = [`<option value="Todas">Todas</option>`];
    todasCats.forEach(c => {
        const sel = c === estado.categoria ? "selected" : "";
        opcoesCat.push(`<option value="${c}" ${sel}>${c}</option>`);
    });
    selCat.innerHTML = opcoesCat.join("");
}

function renderizarKPIs(ind) {
    document.getElementById("kpi-receitas").textContent = formatarMoeda(ind.total_receitas);
    document.getElementById("kpi-receitas-sub").textContent = `${ind.quantidade_receitas} receita(s) no período`;

    document.getElementById("kpi-despesas").textContent = formatarMoeda(ind.total_despesas);
    document.getElementById("kpi-despesas-sub").textContent = `${ind.quantidade_despesas} despesa(s) no período`;

    document.getElementById("kpi-saldo").textContent = formatarMoeda(ind.saldo);
    document.getElementById("kpi-saldo-sub").textContent =
        ind.saldo >= 0 ? "✅ Superávit no período" : "⚠️ Déficit no período";

    if (ind.comprometimento_calculavel) {
        document.getElementById("kpi-comprometido").textContent = `${ind.percentual_comprometido.toFixed(1)}%`;
        document.getElementById("kpi-comprometido-sub").textContent = `Taxa de economia: ${ind.taxa_economia.toFixed(1)}%`;
    } else {
        document.getElementById("kpi-comprometido").textContent = "N/D";
        document.getElementById("kpi-comprometido-sub").textContent = "Sem receitas registradas no período";
    }
}

// ============================================================
// 3. GRÁFICOS INTERATIVOS (PLOTLY DARK)
// ============================================================
const layoutDark = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, sans-serif", color: "#cbd5e1", size: 12 },
    margin: { l: 45, r: 20, t: 20, b: 40 }
};

function renderizarGraficoMensal(dados) {
    const el = document.getElementById("chart-mensal");
    const meses = dados.map(d => d.ano_mes);
    Plotly.newPlot(el, [
        {
            x: meses,
            y: dados.map(d => d.Receita),
            name: "Receitas",
            type: "bar",
            marker: { color: "#10b981" }
        },
        {
            x: meses,
            y: dados.map(d => d.Despesa),
            name: "Despesas",
            type: "bar",
            marker: { color: "#ef4444" }
        },
        {
            x: meses,
            y: dados.map(d => d.Saldo),
            name: "Saldo Mensal",
            type: "scatter",
            mode: "lines+markers",
            line: { color: "#60a5fa", width: 3 }
        }
    ], {
        ...layoutDark,
        barmode: "group",
        legend: { orientation: "h", y: 1.12 },
        xaxis: { gridcolor: "rgba(255,255,255,0.05)" },
        yaxis: { gridcolor: "rgba(255,255,255,0.06)" }
    }, { responsive: true, displayModeBar: false });
}

function renderizarGraficoCategorias(cats) {
    const el = document.getElementById("chart-categorias");
    if (!cats.length) {
        el.innerHTML = `<p style="color:#64748b;padding:40px;text-align:center;">Não há despesas no período selecionado.</p>`;
        return;
    }
    Plotly.newPlot(el, [{
        labels: cats.map(c => c.categoria),
        values: cats.map(c => c.valor),
        type: "pie",
        hole: 0.5,
        textinfo: "label+percent",
        marker: { colors: ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#14b8a6", "#f43f5e"] }
    }], {
        ...layoutDark,
        showlegend: true,
        legend: { orientation: "h", y: -0.1 }
    }, { responsive: true, displayModeBar: false });
}

function renderizarGraficoEvolucaoSaldo(evol) {
    const el = document.getElementById("chart-evolucao-saldo");
    Plotly.newPlot(el, [{
        x: evol.map(e => e.data_br),
        y: evol.map(e => e.saldo_acumulado),
        name: "Saldo Acumulado",
        type: "scatter",
        mode: "lines+markers",
        fill: "tozeroy",
        line: { color: "#3b82f6", width: 3 }
    }], {
        ...layoutDark,
        xaxis: { gridcolor: "rgba(255,255,255,0.05)" },
        yaxis: { gridcolor: "rgba(255,255,255,0.06)" }
    }, { responsive: true, displayModeBar: false });
}

function renderizarGraficoSankey(sankey) {
    const el = document.getElementById("chart-sankey");
    if (!sankey.labels || sankey.labels.length < 2) {
        el.innerHTML = `<p style="color:#64748b;padding:40px;text-align:center;">Adicione receitas e despesas para visualizar o fluxo Sankey.</p>`;
        return;
    }
    Plotly.newPlot(el, [{
        type: "sankey",
        orientation: "h",
        node: {
            pad: 16,
            thickness: 18,
            line: { color: "#090d16", width: 1 },
            label: sankey.labels,
            color: sankey.colors
        },
        link: {
            source: sankey.sources,
            target: sankey.targets,
            value: sankey.values,
            color: "rgba(148, 163, 184, 0.22)"
        }
    }], {
        ...layoutDark,
        margin: { l: 15, r: 15, t: 15, b: 15 }
    }, { responsive: true, displayModeBar: false });
}

// ============================================================
// 4. TABELA DE LANÇAMENTOS (CRUD COM EDIÇÃO E CONFIRMAÇÃO)
// ============================================================
function renderizarTabelaLancamentos() {
    const busca = document.getElementById("input-busca").value.toLowerCase();
    const tipoFiltro = document.getElementById("filtro-tipo-tabela").value;

    const filtrados = estado.lancamentos.filter(item => {
        const bateBusca = item.descricao.toLowerCase().includes(busca) || item.categoria.toLowerCase().includes(busca);
        const bateTipo = tipoFiltro === "Todos" || item.tipo === tipoFiltro;
        return bateBusca && bateTipo;
    });

    const tbody = document.getElementById("tabela-lancamentos-body");
    if (!filtrados.length) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#64748b;padding:28px;">Nenhum lançamento encontrado para os filtros aplicados.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtrados.map(item => `
        <tr>
            <td>#${item.id}</td>
            <td>${item.data_br}</td>
            <td><span class="badge badge-${item.tipo}">${item.tipo}</span></td>
            <td>${item.categoria}</td>
            <td><strong>${item.descricao}</strong></td>
            <td><span class="conta-chip">${item.is_demo ? "🧪 Demo" : "👤 Real"}</span></td>
            <td style="font-family:'JetBrains Mono',monospace;font-weight:600;">${formatarMoeda(item.valor)}</td>
            <td class="text-right">
                <button class="btn-mini" onclick="abrirModalEdicao(${item.id})">✏️ Editar</button>
                <button class="btn-icon-danger" onclick="confirmarExclusaoLancamento(${item.id}, '${item.descricao.replace(/'/g, "")}')">🗑️ Excluir</button>
            </td>
        </tr>
    `).join("");
}

async function confirmarExclusaoLancamento(id, descricao) {
    if (!confirm(`Confirma a exclusão permanente do lançamento #${id} ("${descricao}")?`)) return;
    const resp = await fetch(`/api/lancamentos/${id}`, { method: "DELETE" });
    const dados = await resp.json();
    if (resp.ok) {
        mostrarToast(dados.mensagem);
        carregarDados();
    } else {
        mostrarToast(`Erro: ${dados.erro}`);
    }
}

// ============================================================
// 5. IMPORTAÇÃO CSV COM VALIDAÇÃO PRÉVIA
// ============================================================
async function validarArquivoCSV() {
    const input = document.getElementById("input-arquivo-csv");
    const container = document.getElementById("resultado-previa-csv");
    const btnConfirmar = document.getElementById("btn-confirmar-csv");

    if (!input.files || !input.files.length) {
        mostrarToast("Selecione um arquivo .csv primeiro.");
        return;
    }

    const texto = await input.files[0].text();
    const resp = await fetch("/api/csv/validar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conteudo_csv: texto, modo: estado.modo })
    });
    const analise = await resp.json();

    if (analise.erro_estrutural) {
        btnConfirmar.style.display = "none";
        container.innerHTML = `<div class="suggestion-item alerta"><strong>Erro Estrutural no CSV</strong><p>${analise.erro_estrutural}</p></div>`;
        return;
    }

    estado.validosCsvPendentes = analise.validos || [];
    btnConfirmar.style.display = estado.validosCsvPendentes.length > 0 ? "inline-block" : "none";

    let html = `
        <div class="suggestion-item info" style="margin-bottom:12px;">
            <strong>Resultado da Análise Prévia do CSV</strong>
            <p>✅ <strong>${analise.validos.length}</strong> linha(s) válida(s) pronta(s) para importar |
               ⚠️ <strong>${analise.duplicados.length}</strong> duplicada(s) ignorada(s) |
               ❌ <strong>${analise.erros.length}</strong> linha(s) com erro</p>
        </div>
    `;

    if (analise.erros.length) {
        html += `<div class="suggestion-item alerta" style="margin-bottom:12px;"><strong>Linhas com Erro (bloqueadas):</strong><ul style="margin-left:18px;font-size:12.5px;">` +
            analise.erros.map(e => `<li>Linha ${e.linha}: ${e.motivo}</li>`).join("") +
            `</ul></div>`;
    }

    if (analise.duplicados.length) {
        html += `<div class="suggestion-item aviso" style="margin-bottom:12px;"><strong>Duplicatas detectadas (ignoradas):</strong><ul style="margin-left:18px;font-size:12.5px;">` +
            analise.duplicados.map(d => `<li>Linha ${d.linha}: ${d.motivo}</li>`).join("") +
            `</ul></div>`;
    }

    container.innerHTML = html;
}

async function confirmarGravacaoCSV() {
    if (!estado.validosCsvPendentes.length) return;
    const resp = await fetch("/api/csv/confirmar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ validos: estado.validosCsvPendentes, modo: estado.modo })
    });
    const dados = await resp.json();
    if (resp.ok) {
        estado.validosCsvPendentes = [];
        document.getElementById("btn-confirmar-csv").style.display = "none";
        document.getElementById("resultado-previa-csv").innerHTML = "";
        document.getElementById("input-arquivo-csv").value = "";
        mostrarToast(dados.mensagem);
        carregarDados();
    }
}

// ============================================================
// 6. METAS E PLANEJAMENTO
// ============================================================
function renderizarMetas() {
    const grid = document.getElementById("grid-metas");
    if (!estado.metas.length) {
        grid.innerHTML = `<div class="glass-card"><p style="color:#94a3b8;">Nenhuma meta cadastrada neste modo. Clique em <strong>+ Definir Nova Meta</strong>.</p></div>`;
        return;
    }

    grid.innerHTML = estado.metas.map(m => `
        <div class="meta-card">
            <div class="meta-top">
                <div>
                    <h4>🏆 ${m.titulo}</h4>
                    <small>Prazo: <strong>${m.prazo_br}</strong> (${m.meses_restantes} mês(es) restante(s))</small>
                </div>
                <button class="btn-icon-danger" onclick="excluirMeta(${m.id})">🗑️</button>
            </div>

            <div class="progress-track">
                <div class="progress-fill" style="width:${m.percentual_concluido}%;"></div>
            </div>

            <div class="meta-numbers">
                <span>Acumulado: <strong>${formatarMoeda(m.valor_acumulado)}</strong> (${m.percentual_concluido.toFixed(1)}%)</span>
                <span>Meta: <strong>${formatarMoeda(m.valor_alvo)}</strong></span>
            </div>

            <div class="panel-row" style="margin-bottom:6px;">
                <span>Valor faltante:</span>
                <strong>${formatarMoeda(m.valor_faltante)}</strong>
            </div>
            <div class="panel-row" style="margin-bottom:12px;">
                <span>Economia mensal necessária:</span>
                <strong style="color:#60a5fa;">${formatarMoeda(m.economia_mensal_necessaria)}/mês</strong>
            </div>

            <div class="suggestion-item ${m.nivel_alerta}" style="margin-bottom:12px;">
                <strong>${m.status_texto}</strong>
                <p>${m.mensagem_alerta}</p>
            </div>
        </div>
    `).join("");
}

async function excluirMeta(id) {
    if (!confirm("Deseja remover esta meta de economia?")) return;
    await fetch(`/api/metas/${id}`, { method: "DELETE" });
    mostrarToast("Meta removida!");
    carregarDados();
}

// ============================================================
// 7. FINANPY AI ASSISTANT
// ============================================================
function renderizarAssistenteIA(diag, statusIa) {
    document.getElementById("ia-status-banner").textContent = statusIa.modo_padrao;
    const labelLlm = document.getElementById("label-check-llm");
    labelLlm.style.display = statusIa.llm_disponivel ? "inline-block" : "none";

    document.getElementById("ia-resumo-executivo").innerHTML = `
        <strong>Resumo Executivo do Período</strong>
        <p>${diag.resumo_executivo}</p>
    `;

    const divMaiores = document.getElementById("ia-maiores-gastos");
    const itensMaiores = (diag.maiores_gastos || []).map(g => `<div class="suggestion-item info"><p>${g}</p></div>`);
    itensMaiores.push(`<div class="suggestion-item info"><strong>Comparação entre Períodos</strong><p>${diag.comparacao_periodos}</p></div>`);
    divMaiores.innerHTML = itensMaiores.join("");

    const divOp = document.getElementById("ia-oportunidades");
    const itensOp = (diag.oportunidades_economia || []).map(o => `<div class="suggestion-item sucesso"><p>${o}</p></div>`);
    (diag.recomendacoes || []).forEach(r => {
        itensOp.push(`<div class="suggestion-item ${r.nivel}"><strong>${r.titulo}</strong><p>${r.texto}</p></div>`);
    });
    divOp.innerHTML = itensOp.join("") || `<p style="color:#94a3b8;font-size:13px;">Sem recomendações adicionais para o período.</p>`;

    document.getElementById("ia-explicacao").textContent = `📐 ${diag.explicacao_calculo} (${diag.aviso_modo})`;
}

async function enviarPerguntaIA(pergunta) {
    const usarLlm = document.getElementById("check-usar-llm").checked;
    const resp = await fetch("/api/ia/perguntar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pergunta, modo: estado.modo, usar_llm: usarLlm })
    });
    const dados = await resp.json();

    const hist = document.getElementById("historico-respostas-ia");
    const card = document.createElement("div");
    card.className = "suggestion-item info";
    card.innerHTML = `
        <strong>Você perguntou: "${pergunta}"</strong>
        <p style="white-space:pre-line; margin-top:6px;">${dados.resposta}</p>
        <small style="display:block; margin-top:8px; color:#64748b;">🔒 ${dados.aviso_modo}</small>
    `;
    hist.prepend(card);
}

function fazerPerguntaRapida(texto) {
    enviarPerguntaIA(texto);
}

// ============================================================
// 8. CONFIGURAÇÕES, CATEGORIAS EDITÁVEIS E DEMONSTRAÇÃO
// ============================================================
function renderizarCategoriasConfig() {
    const recContainer = document.getElementById("lista-cats-receita");
    const despContainer = document.getElementById("lista-cats-despesa");

    recContainer.innerHTML = (estado.categoriasPorTipo.Receita || []).map(c => `
        <span class="badge badge-Receita" style="display:inline-flex;align-items:center;gap:6px;">
            ${c}
            ${c !== "Outros" ? `<button onclick="removerCategoria('${c}', 'Receita')" style="background:none;border:none;color:#f87171;cursor:pointer;">&times;</button>` : ""}
        </span>
    `).join("");

    despContainer.innerHTML = (estado.categoriasPorTipo.Despesa || []).map(c => `
        <span class="badge badge-Despesa" style="display:inline-flex;align-items:center;gap:6px;">
            ${c}
            ${c !== "Outros" ? `<button onclick="removerCategoria('${c}', 'Despesa')" style="background:none;border:none;color:#f87171;cursor:pointer;">&times;</button>` : ""}
        </span>
    `).join("");
}

async function removerCategoria(nome, tipo) {
    const resp = await fetch("/api/categorias", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome, tipo })
    });
    const dados = await resp.json();
    mostrarToast(resp.ok ? dados.mensagem : `Aviso: ${dados.erro}`);
    if (resp.ok) carregarDados();
}

async function ativarDemonstracaoRapida() {
    await fetch("/api/demo/carregar", { method: "POST" });
    estado.modo = "demo";
    mostrarToast("Modo de Demonstração ativado com dados fictícios!");
    carregarDados();
}

// ============================================================
// 9. INICIALIZAÇÃO DE EVENTOS
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
    configurarNavegacao();
    document.getElementById("lanc-tipo").addEventListener("change", () => atualizarOpcoesCategoriaModal());
    document.getElementById("meta-prazo").value = `${new Date().getFullYear() + 1}-12-31`;

    // Filtros globais e modo de dados
    document.getElementById("select-modo-dados").addEventListener("change", e => {
        estado.modo = e.target.value;
        carregarDados();
    });
    document.getElementById("filtro-ano").addEventListener("change", e => {
        estado.ano = e.target.value;
        carregarDados();
    });
    document.getElementById("filtro-mes").addEventListener("change", e => {
        estado.mes = e.target.value;
        carregarDados();
    });
    document.getElementById("filtro-categoria-global").addEventListener("change", e => {
        estado.categoria = e.target.value;
        carregarDados();
    });

    // Busca e filtro da tabela
    document.getElementById("input-busca").addEventListener("input", renderizarTabelaLancamentos);
    document.getElementById("filtro-tipo-tabela").addEventListener("change", renderizarTabelaLancamentos);

    // Salvar (Criar ou Editar) Lançamento
    document.getElementById("form-lancamento").addEventListener("submit", async e => {
        e.preventDefault();
        const idExistente = document.getElementById("lanc-id").value;
        const payload = {
            tipo: document.getElementById("lanc-tipo").value,
            categoria: document.getElementById("lanc-categoria").value,
            descricao: document.getElementById("lanc-descricao").value,
            valor: document.getElementById("lanc-valor").value,
            data: document.getElementById("lanc-data").value,
            modo: estado.modo
        };

        const url = idExistente ? `/api/lancamentos/${idExistente}` : "/api/lancamentos";
        const metodo = idExistente ? "PUT" : "POST";

        const resp = await fetch(url, {
            method: metodo,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const dados = await resp.json();

        if (resp.ok) {
            document.getElementById("modal-lancamento").classList.remove("open");
            mostrarToast(dados.mensagem);
            carregarDados();
        } else {
            const boxErro = document.getElementById("erro-form-lancamento");
            boxErro.textContent = dados.erro;
            boxErro.style.display = "block";
        }
    });

    // Salvar Meta
    document.getElementById("form-meta").addEventListener("submit", async e => {
        e.preventDefault();
        const payload = {
            titulo: document.getElementById("meta-titulo").value,
            valor_alvo: document.getElementById("meta-alvo").value,
            valor_inicial: document.getElementById("meta-inicial").value,
            prazo: document.getElementById("meta-prazo").value,
            modo: estado.modo
        };
        const resp = await fetch("/api/metas", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const dados = await resp.json();
        if (resp.ok) {
            document.getElementById("modal-meta").classList.remove("open");
            e.target.reset();
            mostrarToast(dados.mensagem);
            carregarDados();
        } else {
            mostrarToast(`Erro: ${dados.erro}`);
        }
    });

    // Importação e Exportação CSV
    document.getElementById("btn-validar-csv").addEventListener("click", validarArquivoCSV);
    document.getElementById("btn-confirmar-csv").addEventListener("click", confirmarGravacaoCSV);
    document.getElementById("btn-exportar-csv").addEventListener("click", () => {
        const params = new URLSearchParams({
            modo: estado.modo,
            ano: estado.ano,
            mes: estado.mes,
            categoria: estado.categoria
        });
        window.location.href = `/api/csv/exportar?${params.toString()}`;
    });

    // Pergunta ao Assistente de IA
    document.getElementById("form-pergunta-ia").addEventListener("submit", e => {
        e.preventDefault();
        const input = document.getElementById("input-pergunta-ia");
        if (input.value.trim()) {
            enviarPerguntaIA(input.value.trim());
            input.value = "";
        }
    });

    // Categorias Editáveis e Gestão de Dados Demo/Reais
    document.getElementById("form-nova-categoria").addEventListener("submit", async e => {
        e.preventDefault();
        const nome = document.getElementById("cat-novo-nome").value;
        const tipo = document.getElementById("cat-novo-tipo").value;
        const resp = await fetch("/api/categorias", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nome, tipo })
        });
        const dados = await resp.json();
        mostrarToast(resp.ok ? dados.mensagem : `Erro: ${dados.erro}`);
        if (resp.ok) {
            document.getElementById("cat-novo-nome").value = "";
            carregarDados();
        }
    });

    document.getElementById("btn-carregar-demo-rapido").addEventListener("click", ativarDemonstracaoRapida);
    document.getElementById("btn-config-carregar-demo").addEventListener("click", ativarDemonstracaoRapida);

    document.getElementById("btn-config-remover-demo").addEventListener("click", async () => {
        const resp = await fetch("/api/demo/remover", { method: "POST" });
        const dados = await resp.json();
        mostrarToast(dados.mensagem);
        carregarDados();
    });

    document.getElementById("btn-limpar-dados-reais").addEventListener("click", async () => {
        if (!confirm("Tem certeza absoluta? Isso apagará todos os seus lançamentos e metas reais salvos localmente.")) return;
        const resp = await fetch("/api/dados-usuario/limpar", { method: "POST" });
        const dados = await resp.json();
        mostrarToast(dados.mensagem);
        carregarDados();
    });

    carregarDados();
});
