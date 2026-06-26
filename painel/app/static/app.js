(function () {
  "use strict";

  const csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  const $data = document.getElementById("data");
  const $form = document.getElementById("form-executar");
  const $btn = document.getElementById("btn-executar");
  const $status = document.getElementById("status-box");
  const $lista = document.getElementById("lista-csv");
  let pollTimer = null;

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
    $status.classList.remove("oculto");
    let cls = "status rodando";
    let head = "Extraindo...";
    if (!s.running && s.exit_code === 0) { cls = "status ok"; head = "Extração concluída"; }
    else if (!s.running && s.exit_code !== null && s.exit_code !== 0) { cls = "status erro"; head = "Extração falhou (código " + s.exit_code + ")"; }
    $status.className = cls;
    const argsTxt = s.args ? `ano ${s.args.ano_final}/${s.args.mes || "—"}` : "";
    const log = (s.log_tail || "").trim();
    $status.innerHTML =
      `<strong>${head}</strong>${argsTxt ? " — " + argsTxt : ""}` +
      (s.started_at ? `<div class="sub">início ${s.started_at}` + (s.finished_at ? ` · fim ${s.finished_at}` : "") + "</div>" : "") +
      (log ? `<pre>${escapeHtml(log)}</pre>` : "");
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

  async function pollStatus() {
    try {
      const r = await fetch("/api/status", { headers: { Accept: "application/json" } });
      if (!r.ok) return;
      const j = await r.json();
      if (j.ok) {
        renderStatus(j.status);
        if (j.status && j.status.running) {
          $btn.disabled = true;
        } else {
          $btn.disabled = false;
          if (j.status && j.status.finished_at && !pollFinalizado) { pollFinalizado = true; renderLista(j.csvs); flash("Atualizado"); }
        }
      }
    } catch (e) { /* ignora */ }
  }
  let pollFinalizado = false;

  // Inicia estado
  (async function init() {
    try {
      const r = await fetch("/api/status", { headers: { Accept: "application/json" } });
      const j = await r.json();
      if (j.ok) {
        renderStatus(j.status);
        renderLista(j.csvs);
        if (j.status && j.status.running) { $btn.disabled = true; startPolling(); }
      }
    } catch (e) {}
  })();

  function startPolling() {
    if (pollTimer) return;
    pollFinalizado = false;
    pollTimer = setInterval(async () => {
      await pollStatus();
      const cur = $status.classList.contains("rodando");
      if (!cur) { clearInterval(pollTimer); pollTimer = null; $btn.disabled = false; }
    }, 2500);
  }

  // Submeter extração
  if ($form) {
    $form.addEventListener("submit", async function (e) {
      e.preventDefault();
      const data = ($data.value || "").trim();
      if (!data) { flash("Escolha uma data."); return; }
      $btn.disabled = true;
      try {
        const r = await fetch("/api/executar", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify({ data: data }),
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
