(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const wizard = $("#integration-wizard");
  if (!wizard) return;

  let step = 1;
  const maxStep = 4;
  const connector = $("#connector-type");
  const entity = $("#entity-type");
  const configEditor = $("#config-json");
  const mappingEditor = $("#mapping-json");
  const back = $("#wizard-back");
  const next = $("#wizard-next");
  const save = $("#save-source");

  function pretty(value) {
    return JSON.stringify(value, null, 2);
  }

  function setStatus(id, message, ok = null) {
    const element = $(`#${id}-status`);
    if (!element) return;
    element.textContent = message;
    element.classList.remove("success", "error");
    if (ok === true) element.classList.add("success");
    if (ok === false) element.classList.add("error");
  }

  function applyTemplate(kind) {
    if (kind === "config") {
      const value = window.SMARTBUY_CONNECTOR_TEMPLATES[connector.value] || {};
      configEditor.value = pretty(value);
      setStatus("config-json", "Modelo aplicado. Ajuste os dados e valide.", null);
    } else {
      const value = window.SMARTBUY_MAPPING_TEMPLATES[entity.value] || {};
      mappingEditor.value = pretty(value);
      setStatus("mapping-json", "Modelo aplicado para a entidade selecionada.", null);
    }
  }

  async function validateJSON(editorId) {
    const editor = $(`#${editorId}`);
    const response = await fetch("/integration-core/api/json/validate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({value: editor.value}),
    });
    const result = await response.json();
    if (result.ok) {
      editor.value = result.formatted;
      setStatus(editorId, result.message, true);
      return true;
    }
    setStatus(editorId, result.message || "JSON inválido.", false);
    return false;
  }

  async function validateMapping() {
    const response = await fetch("/integration-core/api/mapping/validate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        entity_type: entity.value,
        mapping_json: mappingEditor.value,
      }),
    });
    const result = await response.json();
    if (result.ok) {
      mappingEditor.value = result.formatted;
      setStatus("mapping-json", "Mapeamento válido e completo.", true);
      return true;
    }
    setStatus("mapping-json", (result.errors || ["Mapeamento inválido."]).join(" "), false);
    return false;
  }

  function renderStep() {
    $$(".wizard-panel", wizard).forEach(panel => panel.classList.toggle("active", Number(panel.dataset.step) === step));
    $$(".wizard-step", wizard).forEach(button => button.classList.toggle("active", Number(button.dataset.stepTarget) === step));
    back.disabled = step === 1;
    next.classList.toggle("hidden", step === maxStep);
    save.classList.toggle("hidden", step !== maxStep);
  }

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch]));
  }

  async function previewSource() {
    const message = $("#preview-message");
    const summary = $("#preview-summary");
    const table = $("#preview-table");
    message.textContent = "Testando conexão e lendo uma amostra...";
    summary.classList.add("hidden");
    table.classList.add("hidden");

    const configOK = await validateJSON("config-json");
    const mappingOK = await validateMapping();
    if (!configOK || !mappingOK) {
      message.textContent = "Corrija os campos destacados antes de gerar a prévia.";
      return;
    }

    const response = await fetch("/integration-core/api/source/preview", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        connector_type: connector.value,
        entity_type: entity.value,
        config_json: configEditor.value,
        mapping_json: mappingEditor.value,
        secret_env_prefix: $("#secret-prefix").value,
        limit: 5,
      }),
    });
    const result = await response.json();
    if (!result.ok) {
      message.textContent = result.message || "Não foi possível gerar a prévia.";
      return;
    }

    message.textContent = `Conexão aprovada: ${result.message}`;
    summary.innerHTML = `
      <div><strong>${result.summary.rows}</strong><span>Amostra</span></div>
      <div><strong>${result.summary.valid}</strong><span>Válidos</span></div>
      <div><strong>${result.summary.invalid}</strong><span>Inválidos</span></div>`;
    summary.classList.remove("hidden");

    table.innerHTML = result.preview.map((item, index) => `
      <article class="preview-record">
        <header><strong>Registro ${index + 1}</strong><span class="status-pill ${item.status === "VALID" ? "success" : "danger"}">${item.status}</span></header>
        <pre>${escapeHTML(JSON.stringify(item.canonical, null, 2))}</pre>
        ${item.issues.length ? `<small>${escapeHTML(item.issues.map(issue => issue.message).join(" · "))}</small>` : ""}
      </article>`).join("");
    table.classList.remove("hidden");
  }

  $$("[data-step-target]", wizard).forEach(button => button.addEventListener("click", () => {step = Number(button.dataset.stepTarget); renderStep();}));
  next.addEventListener("click", async () => {
    if (step === 2 && !(await validateJSON("config-json"))) return;
    if (step === 3 && !(await validateMapping())) return;
    step = Math.min(maxStep, step + 1);
    renderStep();
  });
  back.addEventListener("click", () => {step = Math.max(1, step - 1); renderStep();});
  $$("[data-template]", wizard).forEach(button => button.addEventListener("click", () => applyTemplate(button.dataset.template)));
  $$("[data-format]", wizard).forEach(button => button.addEventListener("click", () => validateJSON(button.dataset.format)));
  $$("[data-validate]", wizard).forEach(button => button.addEventListener("click", () => validateJSON(button.dataset.validate)));
  $("[data-validate-mapping]", wizard).addEventListener("click", validateMapping);
  $("#preview-source").addEventListener("click", previewSource);
  connector.addEventListener("change", () => applyTemplate("config"));
  entity.addEventListener("change", () => applyTemplate("mapping"));

  applyTemplate("config");
  applyTemplate("mapping");
  renderStep();
})();
