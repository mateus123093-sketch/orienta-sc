/* Orienta SC — frontend do chatbot */

const chatLog = document.getElementById("chat-log");
const chatOptions = document.getElementById("chat-options");
const progressBar = document.getElementById("progress-bar");
const progressText = document.getElementById("progress-text");
const progressTrack = document.getElementById("progress-track");
const profileStrip = document.getElementById("profile-strip");
const profileChips = document.getElementById("profile-chips");
const results = document.getElementById("results");
const coursesGrid = document.getElementById("courses-grid");
const facultiesList = document.getElementById("faculties-list");
const disclaimer = document.getElementById("disclaimer");

const state = {
  sessaoId: null,
  pergunta: null,
  selecao: new Set(),
  busy: false,
  resultado: null,
  total: 11,
};

const reduzirMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ------------------------------ helpers ------------------------------ */

function h(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}

function normalizar(texto) {
  return texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function rolarParaFinal() {
  chatLog.scrollTo({ top: chatLog.scrollHeight, behavior: reduzirMovimento ? "auto" : "smooth" });
}

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  let dados = null;
  try {
    dados = await resposta.json();
  } catch (_) {
    /* resposta sem JSON */
  }
  if (!resposta.ok) {
    const detalhe = dados && dados.detail ? dados.detail : `Erro ${resposta.status}`;
    throw new Error(detalhe);
  }
  return dados;
}

/* ------------------------------ mensagens ---------------------------- */

function adicionarMensagem(tipo, texto, subtitulo) {
  const msg = h("div", `msg msg--${tipo}`);
  if (tipo === "bot") {
    msg.appendChild(h("div", "msg-avatar", "IA"));
  }
  const bolha = h("div", "msg-bubble", texto);
  if (subtitulo) {
    const sub = h("span", "msg-sub", subtitulo);
    bolha.appendChild(sub);
  }
  msg.appendChild(bolha);
  chatLog.appendChild(msg);
  rolarParaFinal();
  return msg;
}

function adicionarErro(texto) {
  const msg = h("div", "msg msg--bot error-msg");
  msg.appendChild(h("div", "msg-avatar", "!"));
  msg.appendChild(h("div", "msg-bubble", texto));
  chatLog.appendChild(msg);
  rolarParaFinal();
}

function mostrarDigitando() {
  const msg = h("div", "msg msg--bot");
  msg.appendChild(h("div", "msg-avatar", "IA"));
  const bolha = h("div", "msg-bubble");
  const pontos = h("span", "typing");
  pontos.innerHTML = "<i></i><i></i><i></i>";
  bolha.appendChild(pontos);
  msg.appendChild(bolha);
  chatLog.appendChild(msg);
  rolarParaFinal();
  return msg;
}

function atualizarProgresso(progresso) {
  if (!progresso) return;
  const pct = Math.min(100, (progresso.atual / progresso.total) * 100);
  progressBar.style.width = `${pct}%`;
  progressText.textContent = `${progresso.atual}/${progresso.total}`;
  progressTrack.setAttribute("aria-valuemax", progresso.total);
  progressTrack.setAttribute("aria-valuenow", progresso.atual);
}

/* ------------------------------- fluxo ------------------------------- */

async function iniciar() {
  try {
    const dados = await api("/api/sessao", { method: "POST" });
    state.sessaoId = dados.sessao_id;
    state.total = dados.progresso.total;
    state.resultado = null;

    chatLog.innerHTML = "";
    chatOptions.innerHTML = "";
    profileStrip.hidden = true;
    results.hidden = true;
    atualizarProgresso({ atual: 0, total: dados.progresso.total });

    adicionarMensagem(
      "bot",
      "Oi! Eu sou o Orienta. 👋",
      "Vou fazer algumas perguntas rápidas para descobrir o curso que combina com você e as faculdades de Santa Catarina que fazem sentido para o seu momento."
    );
    mostrarPergunta(dados);
  } catch (erro) {
    chatLog.innerHTML = "";
    adicionarErro(
      "Não consegui falar com o servidor. Verifique se o backend está rodando (python -m uvicorn app:app) e recarregue a página."
    );
    console.error(erro);
  }
}

function mostrarPergunta(dados) {
  state.pergunta = dados.pergunta;
  state.selecao.clear();
  state.busy = false;
  atualizarProgresso(dados.progresso);

  if (dados.resumo) atualizarChips(dados.resumo);

  if (!dados.pergunta) return;

  adicionarMensagem("bot", dados.pergunta.texto, dados.pergunta.subtitulo);
  renderizarOpcoes();
}

function renderizarOpcoes() {
  chatOptions.innerHTML = "";
  const pergunta = state.pergunta;
  if (!pergunta) return;

  if (pergunta.tipo === "cidade") return renderizarCidades(pergunta);
  if (pergunta.tipo === "multi") return renderizarMulti(pergunta);
  return renderizarUnica(pergunta);
}

function renderizarUnica(pergunta) {
  pergunta.opcoes.forEach((opcao) => {
    const botao = h("button", "option-btn");
    botao.type = "button";

    const corpo = h("span", "opt-body");
    corpo.appendChild(h("span", "opt-title", opcao.rotulo));
    if (opcao.descricao) corpo.appendChild(h("span", "opt-desc", opcao.descricao));
    botao.appendChild(corpo);
    botao.appendChild(h("span", "opt-arrow", "→"));

    botao.addEventListener("click", () => {
      if (state.busy) return;
      [...chatOptions.querySelectorAll(".option-btn")].forEach((b) => {
        b.disabled = true;
        b.classList.toggle("is-selected", b === botao);
      });
      enviar(opcao.valor, opcao.rotulo);
    });

    chatOptions.appendChild(botao);
  });
}

function renderizarMulti(pergunta) {
  const max = pergunta.max || pergunta.opcoes.length;
  const contador = h("span", "multi-counter", `0/${max} escolhidos`);

  pergunta.opcoes.forEach((opcao) => {
    const botao = h("button", "option-btn multi-option");
    botao.type = "button";

    const check = h("span", "check", "");
    const corpo = h("span", "opt-body");
    corpo.appendChild(h("span", "opt-title", opcao.rotulo));
    if (opcao.descricao) corpo.appendChild(h("span", "opt-desc", opcao.descricao));

    botao.appendChild(check);
    botao.appendChild(corpo);

    botao.addEventListener("click", () => {
      if (state.busy) return;
      const marcado = state.selecao.has(opcao.valor);
      if (!marcado && state.selecao.size >= max) {
        contador.textContent = `Máximo de ${max}. Desmarque uma opção para trocar.`;
        contador.style.color = "#b25c00";
        return;
      }
      if (marcado) {
        state.selecao.delete(opcao.valor);
      } else {
        state.selecao.add(opcao.valor);
      }
      botao.classList.toggle("is-selected", !marcado);
      check.textContent = !marcado ? "✓" : "";
      contador.style.color = "";
      contador.textContent = `${state.selecao.size}/${max} escolhidos`;
      botaoContinue.disabled = state.selecao.size === 0;
    });

    chatOptions.appendChild(botao);
  });

  const linha = h("div", "continue-row");
  linha.appendChild(contador);
  const botaoContinue = h("button", "btn btn--primary", "Continuar");
  botaoContinue.type = "button";
  botaoContinue.disabled = true;
  botaoContinue.addEventListener("click", () => {
    if (state.busy || state.selecao.size === 0) return;
    const escolhidas = pergunta.opcoes.filter((o) => state.selecao.has(o.valor));
    botaoContinue.disabled = true;
    enviar(
      escolhidas.map((o) => o.valor),
      escolhidas.map((o) => o.rotulo).join(", ")
    );
  });
  linha.appendChild(botaoContinue);
  chatOptions.appendChild(linha);
}

function renderizarCidades(pergunta) {
  const busca = h("input", "city-search");
  busca.type = "search";
  busca.placeholder = "Busque sua cidade...";
  busca.setAttribute("aria-label", "Buscar cidade");

  const lista = h("div", "city-list");
  const vazio = h("p", "city-empty", "Nenhuma cidade encontrada. Digite o nome sem acentos ou escolha a mais próxima.");

  function desenhar(filtro) {
    lista.innerHTML = "";
    const alvo = normalizar(filtro.trim());
    const encontradas = pergunta.opcoes.filter((o) => normalizar(o.rotulo).includes(alvo));
    if (!encontradas.length) {
      lista.appendChild(vazio);
      return;
    }
    encontradas.slice(0, 40).forEach((opcao) => {
      const botao = h("button", "option-btn");
      botao.type = "button";
      botao.appendChild(h("span", "opt-title", opcao.rotulo));
      botao.appendChild(h("span", "opt-arrow", "→"));
      botao.addEventListener("click", () => {
        if (state.busy) return;
        [...lista.querySelectorAll(".option-btn")].forEach((b) => (b.disabled = true));
        enviar(opcao.valor, opcao.rotulo);
      });
      lista.appendChild(botao);
    });
  }

  busca.addEventListener("input", () => desenhar(busca.value));
  desenhar("");

  chatOptions.appendChild(busca);
  chatOptions.appendChild(lista);
}

async function enviar(valor, rotulo) {
  if (state.busy || !state.sessaoId) return;
  state.busy = true;

  adicionarMensagem("user", rotulo || String(valor));
  chatOptions.innerHTML = "";
  const digitando = mostrarDigitando();

  try {
    const dados = await api(`/api/sessao/${state.sessaoId}/resposta`, {
      method: "POST",
      body: JSON.stringify({ valor }),
    });
    digitando.remove();

    if (dados.tipo === "resultado") {
      renderizarResultado(dados.resultado);
    } else {
      mostrarPergunta(dados);
    }
  } catch (erro) {
    digitando.remove();
    adicionarErro(`Não consegui registrar sua resposta: ${erro.message}`);
    state.busy = false;
    renderizarOpcoes();
  }
}

/* ----------------------------- resultado ----------------------------- */

function atualizarChips(resumo) {
  profileChips.innerHTML = "";
  resumo.forEach((item) => {
    const chip = h("span", "chip");
    chip.appendChild(h("strong", null, `${item.rotulo}:`));
    chip.appendChild(document.createTextNode(item.valor));
    profileChips.appendChild(chip);
  });
}

function renderizarResultado(resultado) {
  state.resultado = resultado;
  state.busy = false;
  atualizarProgresso({ atual: state.total, total: state.total });

  adicionarMensagem(
    "bot",
    "Pronto! Montei seu mapa de cursos e faculdades. 🎯",
    "As notas são uma estimativa de encaixe com o seu perfil — use como ponto de partida para conversar com as instituições."
  );

  atualizarChips(resultado.resumo || []);
  profileStrip.hidden = false;

  renderizarCursos(resultado.cursos);
  renderizarFaculdades(resultado.faculdades);

  disclaimer.innerHTML = "";
  disclaimer.appendChild(h("strong", null, "Importante: "));
  disclaimer.appendChild(
    document.createTextNode(
      `${resultado.aviso} Mensalidades, turnos e ofertas mudam; confirme sempre no site oficial da instituição.`
    )
  );

  results.hidden = false;
  results.scrollIntoView({ behavior: reduzirMovimento ? "auto" : "smooth", block: "start" });
}

function renderizarCursos(cursos) {
  coursesGrid.innerHTML = "";
  cursos.forEach((curso) => {
    const card = h("article", "course-card");

    const topo = h("div", "course-top");
    const info = h("div");
    info.appendChild(h("h4", null, curso.nome));
    info.appendChild(
      h("span", "course-meta", `${curso.grau} · ${curso.duracao} · ${curso.faculdades} faculdades na base`)
    );
    topo.appendChild(info);

    const anel = h("div", "score-ring");
    anel.style.setProperty("--p", curso.nota);
    anel.appendChild(h("span", null, Math.round(curso.nota)));
    topo.appendChild(anel);
    card.appendChild(topo);

    card.appendChild(h("p", "course-desc", curso.descricao));

    if (curso.motivos && curso.motivos.length) {
      const motivos = h("ul", "course-reasons");
      curso.motivos.slice(0, 3).forEach((motivo) => motivos.appendChild(h("li", null, motivo)));
      card.appendChild(motivos);
    }

    const carreiras = h("div", "careers");
    (curso.carreiras || []).forEach((carreira) => carreiras.appendChild(h("span", "career", carreira)));
    card.appendChild(carreiras);

    coursesGrid.appendChild(card);
  });
}

function renderizarFaculdades(faculdades) {
  facultiesList.innerHTML = "";

  if (!faculdades.length) {
    const vazio = h(
      "p",
      "disclaimer",
      "Não encontramos combinações dentro de todos os seus filtros. Tente aumentar o limite de distância ou o orçamento."
    );
    facultiesList.appendChild(vazio);
    return;
  }

  const rotulosTipo = { publica: "Pública", privada: "Privada", comunitaria: "Comunitária" };

  faculdades.forEach((fac, indice) => {
    const card = h("article", "fac-card");
    card.appendChild(h("div", "fac-rank", `${indice + 1}º`));

    const corpo = h("div", "fac-body");

    const topo = h("div", "fac-top");
    topo.appendChild(h("h4", null, fac.sigla));
    const badge = h("span", `badge badge--${fac.tipo}`, rotulosTipo[fac.tipo] || fac.tipo);
    topo.appendChild(badge);
    corpo.appendChild(topo);

    corpo.appendChild(
      h("p", "fac-course", `${fac.curso} · ${fac.campus} · ${fac.grau} · ${fac.duracao}`)
    );

    const meta = h("div", "fac-meta");
    let textoCusto;
    if (fac.mensalidade <= 0) {
      textoCusto =
        fac.bolsa_aplicada && fac.bolsa_aplicada !== "Gratuito"
          ? "Mensalidade zerada com bolsa"
          : "Curso gratuito";
    } else {
      textoCusto = `R$ ${fac.mensalidade.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}/mês (estimativa)`;
    }
    meta.appendChild(h("span", "meta-pill", textoCusto));

    if (fac.bolsa_aplicada && fac.bolsa_aplicada !== "Gratuito") {
      meta.appendChild(h("span", "meta-pill meta-pill--bolsa", fac.bolsa_aplicada));
      if (fac.mensalidade_cheia > fac.mensalidade) {
        meta.appendChild(
          h(
            "span",
            "meta-pill",
            `Mensalidade cheia: R$ ${fac.mensalidade_cheia.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}`
          )
        );
      }
    }

    meta.appendChild(
      h("span", "meta-pill", fac.distancia_km <= 1 ? "Na sua cidade" : `${fac.distancia_km.toFixed(0)} km de distância`)
    );
    meta.appendChild(h("span", "meta-pill meta-pill--score", `Encaixe ${fac.nota_final.toFixed(0)}/100`));
    corpo.appendChild(meta);

    if (fac.motivos && fac.motivos.length) {
      const motivos = h("ul", "fac-reasons");
      fac.motivos.slice(0, 5).forEach((motivo) => motivos.appendChild(h("li", null, motivo)));
      corpo.appendChild(motivos);
    }

    const detalhes = document.createElement("details");
    detalhes.className = "fac-details";
    detalhes.appendChild(h("summary", null, "Ver nota por critério"));
    const breakdown = h("div", "breakdown");
    [
      ["financeiro", "Financeiro"],
      ["localizacao", "Localização"],
      ["social", "Ambiente"],
      ["qualidade", "Reputação"],
    ].forEach(([chave, rotulo]) => {
      const item = h("div", "bd-item");
      const topoBd = h("div", "bd-top");
      topoBd.appendChild(h("span", null, rotulo));
      topoBd.appendChild(h("span", null, Math.round(fac.breakdown[chave])));
      item.appendChild(topoBd);
      const trilha = h("div", "bd-track");
      const preenchimento = h("div", "bd-fill");
      preenchimento.style.width = `${Math.max(2, fac.breakdown[chave])}%`;
      trilha.appendChild(preenchimento);
      item.appendChild(trilha);
      breakdown.appendChild(item);
    });
    detalhes.appendChild(breakdown);
    corpo.appendChild(detalhes);

    const rodape = h("div", "fac-footer");
    const link = h("a", "site-link", "Site oficial ↗");
    link.href = fac.site;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    rodape.appendChild(link);

    if (fac.bolsas && fac.bolsas.length) {
      rodape.appendChild(h("span", "block-hint", `Bolsas: ${fac.bolsas.join(" · ")}`));
    }
    corpo.appendChild(rodape);

    card.appendChild(corpo);
    facultiesList.appendChild(card);
  });
}

/* ----------------------------- reiniciar ----------------------------- */

async function reiniciar() {
  if (!state.sessaoId) return iniciar();
  try {
    const dados = await api(`/api/sessao/${state.sessaoId}/reiniciar`, { method: "POST" });
    state.resultado = null;
    state.pergunta = null;
    state.selecao.clear();
    chatLog.innerHTML = "";
    chatOptions.innerHTML = "";
    profileStrip.hidden = true;
    results.hidden = true;
    atualizarProgresso({ atual: 0, total: dados.progresso.total });

    adicionarMensagem(
      "bot",
      "Vamos começar de novo. 🔄",
      "Suas respostas anteriores foram apagadas. Pode responder com calma."
    );
    mostrarPergunta(dados);
    document.getElementById("chat-card").scrollIntoView({
      behavior: reduzirMovimento ? "auto" : "smooth",
      block: "start",
    });
  } catch (erro) {
    adicionarErro(`Não consegui reiniciar: ${erro.message}`);
  }
}

document.getElementById("restart").addEventListener("click", reiniciar);
document.getElementById("restart-top").addEventListener("click", reiniciar);

iniciar();
