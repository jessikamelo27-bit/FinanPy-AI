// ============================================================
// FINANPY — FRONTEND CONTROLLER (EDITORIAL WEALTH EDITION)
// Consumo da API REST real em Flask + SQLite + Plotly
// ============================================================

const estado = {
    modo: "usuario",
    ano: "Todos",
    mes: "Todos",
    categoria: "Todas",
    lancamentos: [],
    categoriasPorTipo: { Receita: [], Despesa: [] },
    metas: [],
    linhasCsvValidas: []
};

const TITULOS_PAGINAS = {
    "view-dashboard": [
        "Relatório Patrimonial",
        "Central de Inteligência Financeira",
        "Síntese de fluxo de caixa, alocação por categoria e análise consultiva"
    ],
    "view-lancamentos": [
        "Livro-Razão & Conciliação",
        "Movimentações e Importação CSV",
        "Registro contábil detalhado, filtros avançados e validação prévia de extratos"
    ],
    "view-metas": [
        "Planejamento de Longo Prazo",
        "Metas de Economia e Acumulação",
        "Acompanhamento de objetivos financeiros e esforço mensal necessário"
    ],
    "view-ia": [
        "Consultoria Analítica",
        "Diagnóstico Patrimonial e Assistente Financeiro",
        "Análises determinísticas e recomendações baseadas nos seus registros"
    ],
    "view-config": [
        "Governança & Plano de Contas",
        "Parâmetros, Categorias e Dados Locais",
        "Gestão do plano de categorias, base demonstrativa e privacidade SQLite"
    ]
};

function formatarMoeda(valor) {
    return Number(valor || 0).toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
        minimumFractionDigits: 2
    });
}

function mostrarToast(mensagem) {
    const t = document.getElementById("toast");
    t.textContent = mensagem;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 3400);
}

function formatarMarkdownIA(texto) {
    if (!texto) return "";
    return String(texto)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\*\*(.+?)\*\*/g, '<b style="color:#202923;font-weight:700;">$1</b>')
        .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function limparEmojisLegados(texto) {
    if (!texto) return "";
    return String(texto)
        .replace(/^[🟢🔴🏦🧪👤✨➕🎯🔎💡📊🔒📐]+\s*/g, "")
        .trim();
}

// ============================================================
// 1. NAVEGAÇÃO ENTRE TELAS E MODAIS
// ============================================================
function navegarParaSecao(targetId) {
    const botoes = document.querySelectorAll(".nav-item");
    const secoes = document.querySelectorAll(".view-section");

    botoes.forEach(b => {
        b.classList.toggle("active", b.getAttribute("data-target") === targetId);
    });
    secoes.forEach(s => {
        s.classList.toggle("active", s.id === targetId);
    });

    if (TITULOS_PAGINAS[targetId]) {
        const [eyebrow, titulo, subtitulo] = TITULOS_PAGINAS[targetId];
        const elEyebrow = document.getElementById("page-eyebrow");
        if (elEyebrow) elEyebrow.textContent = eyebrow;
        document.getElementById("page-title").textContent = titulo;
        document.getElementById("page-subtitle").textContent = subtitulo;
    }

    if (targetId === "view-dashboard") {
        window.dispatchEvent(new Event("resize"));
    }
}

function configurarNavegacao() {
    const botoes = document.querySelectorAll(".nav-item");
    botoes.forEach(btn => {
        btn.addEventListener("click", () => {
            const alvo = btn.getAttribute("data-target");
            navegarParaSecao(alvo);
        });
    });

    document.getElementById("btn-abrir-modal-novo").addEventListener("click", () => abrirModalNovoLancamento());
    document.getElementById("btn-abrir-modal-meta").addEventListener("click", () => {
        document.getElementById("modal-meta").classList.add("open");
    });

    document.querySelectorAll("[data-close]").forEach(btn => {
        btn.addEventListener("click", () => {
            const idModal = btn.getAttribute("data-close");
            document.getElementById(idModal).classList.remove("open");
        });
    });
}

function abrirModalNovoLancamento() {
    document.getElementById("modal-lancamento-titulo").textContent = "Novo Lançamento";
    document.getElementById("lanc-id").value = "";
    document.getElementById("lanc-tipo").value = "Despesa";
    atualizarOpcoesCategoriaModal("Despesa");
    document.getElementById("lanc-descricao").value = "";
    document.getElementById("lanc-valor").value = "";
    document.getElementById("lanc-data").value = new Date().toISOString().split("T")[0];
    document.getElementById("erro-form-lancamento").style.display = "none";
    document.getElementById("modal-lancamento").classList.add("open");
}

function abrirModalEdicao(id) {
    const item = estado.lancamentos.find(l => l.id === id);
    if (!item) return;

    document.getElementById("modal-lancamento-titulo").textContent = `Editar Lançamento #${item.id}`;
    document.getElementById("lanc-id").value = item.id;
    document.getElementById("lanc-tipo").value = item.tipo;
    atualizarOpcoesCategoriaModal(item.tipo, item.categoria);
    document.getElementById("lanc-descricao").value = item.descricao;
    document.getElementById("lanc-valor").value = item.valor.toFixed(2);
    document.getElementById("lanc-data").value = item.data;
    document.getElementById("erro-form-lancamento").style.display = "none";
    document.getElementById("modal-lancamento").classList.add("open");
}

function atualizarOpcoesCategoriaModal(tipoSelecionado, categoriaAtual = null) {
    const selectCat = document.getElementById("lanc-categoria");
    const lista = estado.categoriasPorTipo[tipoSelecionado] || ["Outros"];
    selectCat.innerHTML = lista.map(cat =>
        `<option value="${cat}" ${cat === categoriaAtual ? "selected" : ""}>${cat}</option>`
    ).join("");
}

// ============================================================
// 2. CARREGAMENTO E ATUALIZAÇÃO DO DASHBOARD
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

    estado.lancamentos = dados.lancamentos || [];
    estado.categoriasPorTipo = dados.categorias_por_tipo || { Receita: [], Despesa: [] };
    estado.metas = dados.metas || [];

    document.getElementById("select-modo-dados").value = dados.modo_atual;
    document.getElementById("sidebar-modo-label").textContent =
        dados.modo_atual === "demo" ? "Base de Demonstração" : "Carteira Pessoal";
    document.getElementById("banner-demo").style.display =
        dados.modo_atual === "demo" ? "flex" : "none";

    atualizarFiltrosGlobais(dados.anos_disponiveis || []);
    renderizarKPIs(dados.indicadores);

    const semDados = estado.lancamentos.length === 0;
    document.getElementById("dashboard-vazio").style.display = semDados ? "block" : "none";
    document.getElementById("dashboard-graficos").style.display = semDados ? "none" : "block";

    if (!semDados) {
        renderizarInsightsEditoriaisDashboard(dados.diagnostico_ia);
        renderizarGraficoEvolucaoSaldo(dados.evolucao_saldo || []);
        renderizarGraficoMensal(dados.comparativo_mensal || []);
        renderizarTopCategoriasDashboard(dados.gastos_categoria || []);
        renderizarGraficoCategorias(dados.gastos_categoria || []);
        renderizarGraficoSankey(dados.sankey || {});
        renderizarUltimasMovimentacoesDashboard(estado.lancamentos);
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
    document.getElementById("kpi-receitas-sub").textContent =
        `${ind.quantidade_receitas} receita(s) no período`;

    document.getElementById("kpi-despesas").textContent = formatarMoeda(ind.total_despesas);
    document.getElementById("kpi-despesas-sub").textContent =
        `${ind.quantidade_despesas} despesa(s) no período`;

    document.getElementById("kpi-saldo").textContent = formatarMoeda(ind.saldo);
    document.getElementById("kpi-saldo-sub").textContent =
        ind.saldo >= 0 ? "Superávit líquido no período" : "Déficit líquido no período";

    const badgeSaldo = document.getElementById("kpi-saldo-badge");
    if (badgeSaldo) {
        badgeSaldo.textContent = ind.saldo >= 0 ? "Superávit" : "Déficit";
    }

    if (ind.comprometimento_calculavel) {
        document.getElementById("kpi-comprometido").textContent = `${ind.taxa_economia.toFixed(1)}%`;
        document.getElementById("kpi-comprometido-sub").textContent =
            `Receita comprometida: ${ind.percentual_comprometido.toFixed(1)}%`;
    } else {
        document.getElementById("kpi-comprometido").textContent = "N/D";
        document.getElementById("kpi-comprometido-sub").textContent =
            "Sem receitas registradas no período";
    }
}

function renderizarInsightsEditoriaisDashboard(diag) {
    const container = document.getElementById("dashboard-editorial-insights");
    if (!container || !diag) return;

    const sintese = diag.resumo_executivo || "Sem dados suficientes para síntese no período.";
    const maiorGasto = (diag.maiores_gastos && diag.maiores_gastos.length > 0)
        ? diag.maiores_gastos[0]
        : (diag.comparacao_periodos || "Sem concentração de despesas identificada.");
    const oportunidade = (diag.oportunidades_economia && diag.oportunidades_economia.length > 0)
        ? diag.oportunidades_economia[0]
        : (diag.comparacao_periodos || "Mantenha o acompanhamento periódico das despesas.");

    container.innerHTML = `
        <div class="advisory-note">
            <span class="advisory-note-index">01 &middot; Balanço Patrimonial</span>
            <h4>Síntese do Período</h4>
            <p>${formatarMarkdownIA(sintese)}</p>
        </div>
        <div class="advisory-note">
            <span class="advisory-note-index">02 &middot; Principal Centro de Custo</span>
            <h4>Concentração de Saídas</h4>
            <p>${formatarMarkdownIA(maiorGasto)}</p>
        </div>
        <div class="advisory-note">
            <span class="advisory-note-index">03 &middot; Diretriz de Eficiência</span>
            <h4>Oportunidade de Economia</h4>
            <p>${formatarMarkdownIA(oportunidade)}</p>
        </div>
    `;
}

function renderizarTopCategoriasDashboard(cats) {
    const container = document.getElementById("dashboard-top-categorias");
    if (!container) return;

    if (!cats || !cats.length) {
        container.innerHTML = `<p style="color:#777E78;padding:24px 0;">Não há despesas registradas no período selecionado.</p>`;
        return;
    }

    const topCats = cats.slice(0, 6);
    container.innerHTML = topCats.map((c, idx) => {
        const corBarra = idx === 0 ? "#183D32" : (idx === 1 ? "#557A62" : "#7D9B87");
        return `
            <div class="cat-rank-item">
                <div class="cat-rank-header">
                    <span class="cat-rank-name">${c.categoria}</span>
                    <span class="cat-rank-meta tabular-nums">
                        <strong>${formatarMoeda(c.valor)}</strong>
                        (${c.percentual.toFixed(1)}% &middot; ${c.quantidade} lanç.)
                    </span>
                </div>
                <div class="cat-rank-track">
                    <div class="cat-rank-fill" style="width:${Math.min(100, Math.max(3, c.percentual))}%; background-color:${corBarra};"></div>
                </div>
            </div>
        `;
    }).join("");
}

function renderizarUltimasMovimentacoesDashboard(lancamentos) {
    const tbody = document.getElementById("dashboard-recent-body");
    if (!tbody) return;

    const recentes = (lancamentos || []).slice(0, 7);
    if (!recentes.length) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:#777E78;padding:20px;">Nenhuma movimentação no período.</td></tr>`;
        return;
    }

    tbody.innerHTML = recentes.map(item => {
        const sinal = item.tipo === "Receita" ? "+" : "-";
        const classeValor = item.tipo === "Receita" ? "val-positive" : "val-negative";
        return `
            <tr>
                <td class="tabular-nums">${item.data_br}</td>
                <td><strong>${item.descricao}</strong></td>
                <td><span class="badge badge-${item.tipo}">${item.categoria}</span></td>
                <td class="text-right tabular-nums ${classeValor}">${sinal} ${formatarMoeda(item.valor)}</td>
            </tr>
        `;
    }).join("");
}

// ============================================================
// 3. GRÁFICOS MINIMALISTAS E ELEGANTES (PLOTLY EDITORIAL)
// ============================================================
const layoutEditorial = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Manrope, sans-serif", color: "#202923", size: 12 },
    margin: { l: 52, r: 20, t: 24, b: 44 }
};

function renderizarGraficoMensal(dados) {
    const el = document.getElementById("chart-mensal");
    const meses = dados.map(d => {
        const partes = String(d.ano_mes).split("-");
        return partes.length === 2 ? `${partes[1]}/${partes[0]}` : d.ano_mes;
    });
    Plotly.newPlot(el, [
        {
            x: meses,
            y: dados.map(d => d.Receita),
            name: "Receitas",
            type: "bar",
            marker: { color: "#183D32" }
        },
        {
            x: meses,
            y: dados.map(d => d.Despesa),
            name: "Despesas",
            type: "bar",
            marker: { color: "#B75C52" }
        },
        {
            x: meses,
            y: dados.map(d => d.Saldo),
            name: "Saldo Líquido",
            type: "scatter",
            mode: "lines+markers",
            line: { color: "#557A62", width: 2.5 },
            marker: { size: 6, color: "#557A62" }
        }
    ], {
        ...layoutEditorial,
        barmode: "group",
        bargap: 0.28,
        legend: { orientation: "h", y: 1.14, font: { color: "#777E78", size: 11.5 } },
        xaxis: { type: "category", gridcolor: "#E8E9E2", linecolor: "#E8E9E2", tickfont: { color: "#777E78" } },
        yaxis: { gridcolor: "#E8E9E2", zerolinecolor: "#E8E9E2", tickfont: { color: "#777E78" } }
    }, { responsive: true, displayModeBar: false });
}

function renderizarGraficoCategorias(cats) {
    const el = document.getElementById("chart-categorias");
    if (!cats.length) {
        el.innerHTML = `<p style="color:#777E78;padding:40px;text-align:center;">Não há despesas no período selecionado.</p>`;
        return;
    }
    const paletaEditorial = [
        "#183D32",
        "#557A62",
        "#B75C52",
        "#7D9B87",
        "#A3B8A8",
        "#C58B83",
        "#777E78",
        "#D5DFD7"
    ];
    Plotly.newPlot(el, [{
        labels: cats.map(c => c.categoria),
        values: cats.map(c => c.valor),
        type: "pie",
        hole: 0.56,
        textinfo: "percent",
        textposition: "inside",
        insidetextfont: { color: "#FFFFFF", size: 11 },
        marker: {
            colors: paletaEditorial,
            line: { color: "#FFFFFF", width: 2 }
        }
    }], {
        ...layoutEditorial,
        margin: { l: 16, r: 135, t: 16, b: 16 },
        showlegend: true,
        legend: { orientation: "v", x: 1.02, y: 0.5, font: { color: "#202923", size: 11.5 } }
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
        fillcolor: "rgba(24, 61, 50, 0.08)",
        line: { color: "#183D32", width: 2.5 },
        marker: { color: "#183D32", size: 5 }
    }], {
        ...layoutEditorial,
        margin: { l: 54, r: 20, t: 20, b: 76 },
        xaxis: { type: "category", tickangle: -35, gridcolor: "#E8E9E2", linecolor: "#E8E9E2", tickfont: { color: "#777E78", size: 11 } },
        yaxis: { gridcolor: "#E8E9E2", zerolinecolor: "#E8E9E2", tickfont: { color: "#777E78" } }
    }, { responsive: true, displayModeBar: false });
}

function renderizarGraficoSankey(sankey) {
    const el = document.getElementById("chart-sankey");
    if (!sankey.labels || sankey.labels.length < 2) {
        el.innerHTML = `<p style="color:#777E78;padding:40px;text-align:center;">Registre receitas e despesas para visualizar o diagrama de alocação.</p>`;
        return;
    }

    const labelsLimpos = sankey.labels.map(l => limparEmojisLegados(l));
    const coresEditoriais = (sankey.colors || []).map(cor => {
        if (cor === "#10b981") return "#557A62"; // Receitas
        if (cor === "#ef4444") return "#B75C52"; // Despesas
        if (cor === "#3b82f6") return "#183D32"; // Saldo Economizado
        return "#183D32";                        // Orçamento Central
    });

    Plotly.newPlot(el, [{
        type: "sankey",
        orientation: "h",
        node: {
            pad: 16,
            thickness: 16,
            line: { color: "#E8E9E2", width: 1 },
            label: labelsLimpos,
            color: coresEditoriais
        },
        link: {
            source: sankey.sources,
            target: sankey.targets,
            value: sankey.values,
            color: "rgba(85, 122, 98, 0.20)"
        }
    }], {
        ...layoutEditorial,
        font: { family: "Manrope, sans-serif", color: "#202923", size: 11.5 },
        margin: { l: 16, r: 16, t: 16, b: 16 }
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
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#777E78;padding:28px;">Nenhum lançamento encontrado para os filtros aplicados.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtrados.map(item => {
        const classeValor = item.tipo === "Receita" ? "val-positive" : "val-negative";
        const sinal = item.tipo === "Receita" ? "+" : "-";
        return `
            <tr>
                <td class="tabular-nums" style="color:#777E78;">#${item.id}</td>
                <td class="tabular-nums">${item.data_br}</td>
                <td><span class="badge badge-${item.tipo}">${item.tipo}</span></td>
                <td>${item.categoria}</td>
                <td><strong>${item.descricao}</strong></td>
                <td><span class="conta-chip">${item.is_demo ? "Demonstração" : "Pessoal"}</span></td>
                <td class="text-right tabular-nums ${classeValor}">${sinal} ${formatarMoeda(item.valor)}</td>
                <td class="text-right">
                    <button class="btn-mini" onclick="abrirModalEdicao(${item.id})">Editar</button>
                    <button class="btn-mini btn-mini-danger" onclick="confirmarExclusaoLancamento(${item.id})">Excluir</button>
                </td>
            </tr>
        `;
    }).join("");
}

async function confirmarExclusaoLancamento(id) {
    const item = estado.lancamentos.find(l => l.id === id);
    const nome = item ? `${item.descricao} (${formatarMoeda(item.valor)})` : `#${id}`;
    if (!confirm(`Confirmar a exclusão do lançamento "${nome}"?`)) return;

    const resp = await fetch(`/api/lancamentos/${id}`, { method: "DELETE" });
    const dados = await resp.json();
    if (resp.ok) {
        mostrarToast(dados.mensagem || "Lançamento excluído.");
        carregarDados();
    } else {
        mostrarToast(`Erro: ${dados.erro}`);
    }
}

// ============================================================
// 5. IMPORTAÇÃO E EXPORTAÇÃO CSV COM VALIDAÇÃO PRÉVIA
// ============================================================
async function validarArquivoCSV() {
    const input = document.getElementById("input-arquivo-csv");
    const boxResultado = document.getElementById("resultado-previa-csv");
    const btnConfirmar = document.getElementById("btn-confirmar-csv");

    if (!input.files || !input.files.length) {
        mostrarToast("Selecione um arquivo .csv antes de validar.");
        return;
    }

    const formData = new FormData();
    formData.append("arquivo", input.files[0]);
    formData.append("modo", estado.modo);

    const resp = await fetch("/api/csv/validar", { method: "POST", body: formData });
    const rel = await resp.json();

    if (!resp.ok) {
        boxResultado.innerHTML = `<div class="suggestion-item alerta"><strong>Erro no arquivo CSV</strong><p>${rel.erro}</p></div>`;
        btnConfirmar.style.display = "none";
        return;
    }

    estado.linhasCsvValidas = rel.linhas_validas || [];
    let html = `
        <div class="suggestion-item ${rel.linhas_validas.length ? "sucesso" : "aviso"}" style="margin-bottom:14px;">
            <strong>Resultado da Validação Prévia</strong>
            <p>Total lido: <b>${rel.total_lidas}</b> &middot; Válidas para importar: <b>${rel.linhas_validas.length}</b> &middot; Duplicadas ignoradas: <b>${rel.duplicadas.length}</b> &middot; Com erro: <b>${rel.erros.length}</b></p>
        </div>
    `;

    if (rel.erros.length > 0) {
        html += `<div class="suggestion-item alerta" style="margin-bottom:14px;"><strong>Linhas com Erro (bloqueadas antes da gravação):</strong><ul style="margin-top:6px;padding-left:18px;font-size:12.5px;">` +
            rel.erros.map(e => `<li>Linha ${e.linha}: ${e.motivo}</li>`).join("") +
            `</ul></div>`;
    }

    if (rel.previa.length > 0) {
        html += `
            <h4 class="editorial-section-title">Prévia das Primeiras Linhas Válidas</h4>
            <div class="table-responsive">
                <table class="finan-table">
                    <thead><tr><th>Linha</th><th>Data</th><th>Tipo</th><th>Categoria</th><th>Descrição</th><th class="text-right">Valor</th></tr></thead>
                    <tbody>
                        ${rel.previa.map(p => `
                            <tr>
                                <td class="tabular-nums">${p.linha}</td>
                                <td class="tabular-nums">${p.data_br}</td>
                                <td><span class="badge badge-${p.tipo}">${p.tipo}</span></td>
                                <td>${p.categoria}</td>
                                <td>${p.descricao}</td>
                                <td class="text-right tabular-nums">${formatarMoeda(p.valor)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }

    boxResultado.innerHTML = html;
    btnConfirmar.style.display = estado.linhasCsvValidas.length > 0 ? "inline-block" : "none";
}

async function confirmarGravacaoCSV() {
    if (!estado.linhasCsvValidas.length) return;
    const resp = await fetch("/api/csv/confirmar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ linhas_validas: estado.linhasCsvValidas, modo: estado.modo })
    });
    const dados = await resp.json();
    if (resp.ok) {
        mostrarToast(dados.mensagem);
        document.getElementById("btn-confirmar-csv").style.display = "none";
        document.getElementById("resultado-previa-csv").innerHTML = "";
        document.getElementById("input-arquivo-csv").value = "";
        estado.linhasCsvValidas = [];
        carregarDados();
    } else {
        mostrarToast(`Erro: ${dados.erro}`);
    }
}

// ============================================================
// 6. METAS E PLANEJAMENTO FINANCEIRO
// ============================================================
function renderizarMetas() {
    const grid = document.getElementById("grid-metas");
    if (!estado.metas.length) {
        grid.innerHTML = `
            <div class="surface-card empty-state" style="grid-column:1/-1;">
                <span class="eyebrow-label">Planejamento Patrimonial</span>
                <h3>Nenhuma meta de economia cadastrada</h3>
                <p>Defina um objetivo financeiro e um prazo para calcularmos o aporte mensal necessário e monitorarmos a viabilidade com base no seu saldo real.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = estado.metas.map(m => `
        <div class="meta-card">
            <div class="meta-top">
                <div>
                    <h4>${limparEmojisLegados(m.titulo)}</h4>
                    <div class="meta-deadline">Vencimento: <strong class="tabular-nums">${m.prazo_br}</strong> (${m.meses_restantes} mês(es) restante(s))</div>
                </div>
                <button class="btn-mini btn-mini-danger" onclick="excluirMeta(${m.id})">Remover</button>
            </div>

            <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width:${Math.min(100, m.percentual_concluido)}%;"></div>
            </div>

            <div class="meta-Amounts tabular-nums">
                <span>Acumulado: <strong>${formatarMoeda(m.valor_acumulado)}</strong> (${m.percentual_concluido.toFixed(1)}%)</span>
                <span>Objetivo: <strong>${formatarMoeda(m.valor_alvo)}</strong></span>
            </div>

            <div class="panel-row tabular-nums">
                <span>Saldo restante para a meta:</span>
                <strong>${formatarMoeda(m.valor_faltante)}</strong>
            </div>
            <div class="panel-row tabular-nums" style="margin-bottom:14px;">
                <span>Aporte mensal necessário:</span>
                <strong style="color:#183D32;">${formatarMoeda(m.economia_mensal_necessaria)}/mês</strong>
            </div>

            <div class="suggestion-item ${m.nivel_alerta}">
                <strong>${m.status_texto}</strong>
                <p>${m.mensagem_alerta}</p>
            </div>
        </div>
    `).join("");
}

async function excluirMeta(id) {
    if (!confirm("Deseja remover esta meta de economia?")) return;
    await fetch(`/api/metas/${id}`, { method: "DELETE" });
    mostrarToast("Meta removida.");
    carregarDados();
}

// ============================================================
// 7. CONSULTORIA ANALÍTICA (FINANPY AI ASSISTANT)
// ============================================================
function renderizarAssistenteIA(diag, statusIa) {
    document.getElementById("ia-status-banner").textContent = statusIa.modo_padrao;
    const labelLlm = document.getElementById("label-check-llm");
    labelLlm.style.display = statusIa.llm_disponivel ? "inline-block" : "none";

    document.getElementById("ia-resumo-executivo").innerHTML = `
        <strong>Síntese Executiva do Período</strong>
        <p>${formatarMarkdownIA(diag.resumo_executivo)}</p>
    `;

    const divMaiores = document.getElementById("ia-maiores-gastos");
    const itensMaiores = (diag.maiores_gastos || []).map(g => `<div class="suggestion-item info"><p>${formatarMarkdownIA(g)}</p></div>`);
    itensMaiores.push(`<div class="suggestion-item info"><strong>Comparação entre Períodos</strong><p>${formatarMarkdownIA(diag.comparacao_periodos)}</p></div>`);
    divMaiores.innerHTML = itensMaiores.join("");

    const divOp = document.getElementById("ia-oportunidades");
    const itensOp = (diag.oportunidades_economia || []).map(o => `<div class="suggestion-item sucesso"><p>${formatarMarkdownIA(o)}</p></div>`);
    (diag.recomendacoes || []).forEach(r => {
        itensOp.push(`<div class="suggestion-item ${r.nivel}"><strong>${formatarMarkdownIA(r.titulo)}</strong><p>${formatarMarkdownIA(r.texto)}</p></div>`);
    });
    divOp.innerHTML = itensOp.join("") || `<p style="color:#777E78;font-size:13px;">Sem recomendações adicionais para o período.</p>`;

    document.getElementById("ia-explicacao").textContent = `Nota Metodológica: ${diag.explicacao_calculo} (${diag.aviso_modo})`;
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
        <strong>Consulta: "${formatarMarkdownIA(pergunta)}"</strong>
        <p style="white-space:pre-line; margin-top:6px;">${formatarMarkdownIA(dados.resposta)}</p>
        <small style="display:block; margin-top:10px; color:#777E78; font-size:11.5px;">Fonte: ${formatarMarkdownIA(dados.aviso_modo)}</small>
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
            ${c !== "Outros" ? `<button class="cat-tag-remove" onclick="removerCategoria('${c}', 'Receita')" title="Remover categoria">&times;</button>` : ""}
        </span>
    `).join("");

    despContainer.innerHTML = (estado.categoriasPorTipo.Despesa || []).map(c => `
        <span class="badge badge-Despesa" style="display:inline-flex;align-items:center;gap:6px;">
            ${c}
            ${c !== "Outros" ? `<button class="cat-tag-remove" onclick="removerCategoria('${c}', 'Despesa')" title="Remover categoria">&times;</button>` : ""}
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
    mostrarToast("Base demonstrativa ativada.");
    carregarDados();
}

// ============================================================
// 9. INICIALIZAÇÃO DE EVENTOS
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
    configurarNavegacao();
    document.getElementById("lanc-tipo").addEventListener("change", e => atualizarOpcoesCategoriaModal(e.target.value));
    document.getElementById("meta-prazo").value = `${new Date().getFullYear() + 1}-12-31`;

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

    document.getElementById("input-busca").addEventListener("input", renderizarTabelaLancamentos);
    document.getElementById("filtro-tipo-tabela").addEventListener("change", renderizarTabelaLancamentos);

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

    document.getElementById("form-pergunta-ia").addEventListener("submit", e => {
        e.preventDefault();
        const input = document.getElementById("input-pergunta-ia");
        if (input.value.trim()) {
            enviarPerguntaIA(input.value.trim());
            input.value = "";
        }
    });

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
        if (!confirm("Confirmar a exclusão permanente de todos os seus lançamentos e metas reais salvos localmente?")) return;
        const resp = await fetch("/api/dados-usuario/limpar", { method: "POST" });
        const dados = await resp.json();
        mostrarToast(dados.mensagem);
        carregarDados();
    });

    carregarDados();
});
