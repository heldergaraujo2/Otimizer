(function (global) {
  // Fonte oficial da Prefeitura de Goiânia. O autocomplete consulta a base
  // municipal em tempo real; não existe catálogo de ruas hardcoded aqui.
  const ARCGIS_BASE = "https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/MapaServer/Feature_Base/FeatureServer";
  const STREET_LAYER = 10; // Logradouro por Bairro
  const suggestionCache = new Map();
  let timer = null;
  let activeRequest = 0;
  let dropdown = null;

  function normalize(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function encodeWhereValue(value) {
    return String(value || "").replaceAll("'", "''");
  }

  async function arcgisQuery(layer, params) {
    const url = new URL(`${ARCGIS_BASE}/${layer}/query`);
    Object.entries({ ...params, f: "json" }).forEach(([key, value]) => url.searchParams.set(key, value));
    const response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Consulta municipal HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.error) throw new Error(payload.error.message || "Consulta municipal recusada");
    return Array.isArray(payload.features) ? payload.features : [];
  }

  async function suggestStreets(query, neighborhood) {
    const normalized = normalize(query);
    if (normalized.length < 2) return [];
    const key = `${normalized}|${normalize(neighborhood)}`;
    if (suggestionCache.has(key)) return suggestionCache.get(key);

    // Layer 10 = "Logradouro por Bairro". As sugestões são obtidas da base
    // municipal em tempo real e nunca de uma lista fixa do aplicativo.
    const term = encodeWhereValue(query.trim());
    let where = `(nm_log LIKE '%${term}%' OR nm LIKE '%${term}%')`;
    if (neighborhood.trim()) {
      where += ` AND nm_bai LIKE '%${encodeWhereValue(neighborhood.trim())}%'`;
    }

    const features = await arcgisQuery(STREET_LAYER, {
      where,
      outFields: "id,tp_log,nm_log,nm,nm_bai",
      returnGeometry: "false",
      resultRecordCount: "100",
      orderByFields: "nm_log ASC,nm_bai ASC",
    });

    const seen = new Set();
    const results = [];
    for (const feature of features) {
      const a = feature.attributes || {};
      const street = String(a.nm_log || a.nm || "").trim();
      const neighborhoodName = String(a.nm_bai || "").trim();
      if (!street) continue;
      const resultKey = `${normalize(street)}|${normalize(neighborhoodName)}`;
      if (seen.has(resultKey)) continue;
      seen.add(resultKey);
      results.push({ street, neighborhood: neighborhoodName, id: String(a.id || "").trim() });
    }

    results.sort((a, b) => {
      const qa = normalize(a.street);
      const qb = normalize(b.street);
      const prefix = (qa.startsWith(normalized) ? 0 : 1) - (qb.startsWith(normalized) ? 0 : 1);
      if (prefix) return prefix;
      return qa.localeCompare(qb, "pt-BR") || normalize(a.neighborhood).localeCompare(normalize(b.neighborhood), "pt-BR");
    });

    const limited = results.slice(0, 10);
    suggestionCache.set(key, limited);
    return limited;
  }

  function ensureDropdown(input) {
    if (dropdown) return dropdown;
    dropdown = document.createElement("div");
    dropdown.className = "address-suggestions";
    dropdown.hidden = true;
    dropdown.setAttribute("role", "listbox");
    input.parentElement.style.position = "relative";
    input.parentElement.appendChild(dropdown);
    return dropdown;
  }

  function hideDropdown() {
    if (!dropdown) return;
    dropdown.hidden = true;
    dropdown.innerHTML = "";
  }

  function renderSuggestions(input, results) {
    const box = ensureDropdown(input);
    if (!results.length) return hideDropdown();
    box.innerHTML = results.map((item, index) => `
      <button type="button" class="address-suggestion" role="option" data-index="${index}">
        <strong>${escapeHtml(item.street)}</strong>
        ${item.neighborhood ? `<small>${escapeHtml(item.neighborhood)}</small>` : ""}
      </button>
    `).join("");
    box.hidden = false;
    box.querySelectorAll(".address-suggestion").forEach((button) => {
      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", () => {
        const item = results[Number(button.dataset.index)];
        if (!item) return;
        input.value = item.street;
        const neighborhoodInput = $("manual-neighborhood");
        if (item.neighborhood && neighborhoodInput && !neighborhoodInput.value.trim()) {
          neighborhoodInput.value = item.neighborhood;
        }
        hideDropdown();
        input.dispatchEvent(new Event("change", { bubbles: true }));
        input.focus();
      });
    });
  }

  function installAutocomplete() {
    const input = $("manual-street");
    if (!input || input.dataset.autocompleteInstalled === "true") return Boolean(input);
    input.dataset.autocompleteInstalled = "true";
    ensureDropdown(input);
    input.setAttribute("autocomplete", "off");
    input.addEventListener("input", () => {
      clearTimeout(timer);
      const query = input.value.trim();
      if (query.length < 2) return hideDropdown();
      timer = setTimeout(async () => {
        const requestId = ++activeRequest;
        try {
          const results = await suggestStreets(query, $("manual-neighborhood")?.value || "");
          if (requestId === activeRequest) renderSuggestions(input, results);
        } catch (_) {
          hideDropdown();
        }
      }, 220);
    });
    input.addEventListener("blur", () => setTimeout(hideDropdown, 180));
    return true;
  }

  function waitForManualForm() {
    if (installAutocomplete()) return;
    const observer = new MutationObserver(() => {
      if (installAutocomplete()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", waitForManualForm, { once: true });
  } else {
    waitForManualForm();
  }
})(window);
