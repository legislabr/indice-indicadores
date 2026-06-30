(function () {
  "use strict";

  const csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  const $data = document.getElementById("data");
  const $legislatura = document.getElementById("legislatura");
  const $form = document.getElementById("form-executar");
  const $btn = document.getElementById("btn-executar");
  const $status = document.getElementById("status-box");
  const $lista = document.getElementById("lista-csv");
  let pollTimer = null;

  // ---- auto-scroll do log ----
  // Cola no fim enquanto chega conteúdo; pausa quando o usuário rola pra cima;
  // retoma quando o usuário volta pro fim do log.
  let autoScroll = true;
  let $logPre = null;
  const SCROLL_THRESHOLD = 24; // px de tolerância para considerar "no fim"

  function ensureLogStructure() {
    // Cria a estrutura (cabeçalho + <pre>) UMA vez, preservando o elemento
    // de log entre renders (para não perder a posição de scroll do usuário).
    if ($status.querySelector(".log-pre")) return;
    $status.innerHTML =
      '<div class="status-head"></div>' +
      '<div class="autoscroll-hint oculto">auto-scroll pausado — role até o fim para retomar</div>' +
      '<pre class="log-pre"></pre>';
    $logPre = $status.querySelector(".log-pre");
    $logPre.addEventListener("scroll", onLogScroll);
  }

  function onLogScroll() {
    if (!$logPre) return;
    const dist = $logPre.scrollHeight - $logPre.scrollTop - $logPre.clientHeight;
    const noFim = dist <= SCROLL_THRESHOLD;
    if (noFim !== autoScroll) {
      autoScroll = noFim;
      updateAutoScrollHint();
    }
  }

  function updateAutoScrollHint() {
    const hint = $status.querySelector(".autoscroll-hint");
    if (!hint) return;
    hint.classList.toggle("oculto", autoScroll);
  }

  function scrollToBottom() {
    if ($logPre) $logPre.scrollTop = $logPre.scrollHeight;
  }

  // Calendário (só ano/mês importam; o dia é ignorado no backend)
  if (window.flatpickr && $data) {
    flatpickr($data, {
      locale: "pt",
      dateFormat: "Y-m-d",
      altInput: true,
      altFormat: "d/m/Y",
      maxDate: "today",
      defaultDate: "today",
    });
  }

  function flash(msg) {
    const el = document.createElement("div");
    el.className = "flash";
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  }

  function renderStatus(s) {
    if (!s) { $status.classList.add("oculto"); return; }
    // idle: nenhuma execução aconteceu ainda -> esconde a caixa
    if (!s.running && s.exit_code === null && !s.started_at) {
      $status.classList.add("oculto");
      return;
    }
    $status.classList.remove("oculto");

    let cls = "status rodando";
    let head = "Extraindo...";
    if (!s.running && s.exit_code === 0) { cls = "status ok"; head = "Extração concluída"; }
    else if (!s.running && s.exit_code !== null && s.exit_code !== 0) { cls = "status erro"; head = "Extração falhou (código " + s.exit_code + ")"; }
    $status.className = cls;

    const argsTxt = s.args ? `ano ${s.args.ano_final}/${s.args.mes || "—"}` : "";
    const headHtml =
      `<strong>${head}</strong>${argsTxt ? " — " + argsTxt : ""}` +
      (s.started_at ? `<div class="sub">início ${s.started_at}` + (s.finished_at ? ` · fim ${s.finished_at}` : "") + "</div>" : "");

    ensureLogStructure();
    $status.querySelector(".status-head").innerHTML = headHtml;

    const log = (s.log_tail || "").trim();
    const estavaVazio = !$logPre.textContent.trim();
    $logPre.textContent = log || "(aguardando saída do script...)";

    if (autoScroll) scrollToBottom();
    // ao começar uma execução nova, garante colagem no fim
    if (s.running && estavaVazio) { autoScroll = true; updateAutoScrollHint(); scrollToBottom(); }
  }

  function escapeHtml(t) {
    return String(t).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  function renderLista(csvs) {
    if (!csvs || !csvs.length) {
      $lista.innerHTML = '<tr class="vazia"><td colspan="4">Nenhum CSV extraído ainda.</td></tr>';
      return;
    }
    $lista.innerHTML = csvs.map(function (c) {
      return (
        '<tr data-nome="' + escapeHtml(c.nome) + '">' +
        '<td><a href="/download/' + encodeURIComponent(c.nome) + '">' + escapeHtml(c.nome) + "</a></td>" +
        "<td>" + c.tamanho_kb + " KB</td>" +
        "<td>" + escapeHtml(c.modificado) + "</td>" +
        '<td class="acoes">' +
        '<a class="btn-mini" href="/download/' + encodeURIComponent(c.nome) + '">Baixar</a> ' +
        '<button class="btn-mini perigo btn-excluir" data-nome="' + escapeHtml(c.nome) + '">Excluir</button>' +
        "</td></tr>"
      );
    }).join("");
  }

  async function fetchStatus() {
    try {
      const r = await fetch("/api/status", { headers: { Accept: "application/json" } });
      if (!r.ok) return null;
      const j = await r.json();
      return j.ok ? j : null;
    } catch (e) { return null; }
  }

  // Estado inicial
  (async function init() {
    const j = await fetchStatus();
    if (!j) return;
    renderStatus(j.status);
    renderLista(j.csvs);
    if (j.status && j.status.running) { $btn.disabled = true; startPolling(); }
  })();

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(async () => {
      const j = await fetchStatus();
      if (!j) return;
      renderStatus(j.status);
      if (j.status && j.status.running) {
        $btn.disabled = true;
      } else {
        $btn.disabled = false;
        renderLista(j.csvs);
        stopPolling();
      }
    }, 2500);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  // Submeter extração
  if ($form) {
    $form.addEventListener("submit", async function (e) {
      e.preventDefault();
      const data = ($data.value || "").trim();
      if (!data) { flash("Escolha uma data."); return; }
      const legislatura = parseInt(($legislatura.value || "").trim(), 10);
      if (!Number.isFinite(legislatura) || legislatura <= 57) {
        flash("Legislatura deve ser um número maior que 57.");
        $legislatura.focus();
        return;
      }
      $btn.disabled = true;
      autoScroll = true; // nova execução: sempre cola no fim
      try {
        const r = await fetch("/api/executar", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify({ data: data, legislatura: legislatura }),
        });
        const j = await r.json();
        if (r.ok && j.ok) {
          renderStatus(j.status);
          startPolling();
          flash("Extração iniciada");
        } else {
          $btn.disabled = false;
          flash((j && j.detail) || "Erro ao iniciar extração");
        }
      } catch (err) {
        $btn.disabled = false;
        flash("Falha de comunicação");
      }
    });
  }

  // Excluir arquivo
  document.addEventListener("click", async function (e) {
    const btn = e.target.closest(".btn-excluir");
    if (!btn) return;
    const nome = btn.getAttribute("data-nome");
    if (!confirm("Excluir o arquivo " + nome + "?")) return;
    try {
      const r = await fetch("/api/excluir/" + encodeURIComponent(nome), {
        method: "POST",
        headers: { "X-CSRF-Token": csrf },
      });
      const j = await r.json();
      if (r.ok && j.ok) {
        renderLista(j.csvs);
        flash("Arquivo excluído");
      } else {
        flash((j && j.detail) || "Erro ao excluir");
      }
    } catch (err) {
      flash("Falha de comunicação");
    }
  });
})();
