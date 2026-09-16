(function (global) {
  const ARCGIS_BASE = "https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/MapaServer/Feature_Base/FeatureServer";
  const STREET_LAYER = 7;
  const CADASTRAL_LAYER = 3;
  const suggestionCache = new Map();
  const resolveCache = new Map();
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
    if (!response.ok) throw new Error(`Consulta cadastral HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.error) throw new Error(payload.error.message || "Consulta cadastral recusada");
    return Array.isArray(payload.features) ? payload.features : [];
  }

  function resultStreet(feature) {
    const a = feature.attributes || {};
    return String(a.nm || a.nm_log || "").trim();
  }

  async function suggestStreets(query, neighborhood) {
    const normalized = normalize(query);
    if (normalized.length < 2) return [];
    const key = `${normalized}|${normalize(neighborhood)}`;
    if (suggestionCache.has(key)) return suggestionCache.get(key);
    const term = encodeWhereValue(query.trim());
    let where = `(nm_log LIKE '%${term}%' OR nm LIKE '%${term}%')`;
    if (neighborhood.trim()) where += ` AND logbai LIKE '%${encodeWhereValue(neighborhood.trim())}%'`;
    const features = await arcgisQuery(STREET_LAYER, {
      where,
      outFields: "id,id_log,nm,nm_log,logbai,id_bai",
      returnGeometry: "false",
      resultRecordCount: "40",
      orderByFields: "nm ASC",
    });
    const seen = new Set();
    const results = [];
    for (const feature of features) {
      const street = resultStreet(feature);
      const keyStreet = normalize(street);
      if (!street || seen.has(keyStreet)) continue;
      seen.add(keyStreet);
      const a = feature.attributes || {};
      results.push({ street, neighborhood: String(a.logbai || "").trim(), id: String(a.id_log || a.id || "").trim() });
    }
    results.sort((a, b) => {
      const qa = normalize(a.street);
      const qb = normalize(b.street);
      return (qa.startsWith(normalized) ? 0 : 1) - (qb.startsWith(normalized) ? 0 : 1) || qa.localeCompare(qb, "pt-BR");
    });
    const limited = results.slice(0, 8);
    suggestionCache.set(key, limited);
    return limited;
  }

  function geometryPoint(geometry) {
    if (!geometry) return null;
    if (Number.isFinite(Number(geometry.x)) && Number.isFinite(Number(geometry.y))) return { latitude: Number(geometry.y), longitude: Number(geometry.x) };
    const points = [];
    for (const ring of geometry.rings || []) for (const point of ring || []) if (Array.isArray(point) && point.length >= 2) points.push(point);
    if (!points.length) return null;
    const longitude = points.reduce((sum, point) => sum + Number(point[0]), 0) / points.length;
    const latitude = points.reduce((sum, point) => sum + Number(point[1]), 0) / points.length;
    return Number.isFinite(latitude) && Number.isFinite(longitude) ? { latitude, longitude } : null;
  }

  async function resolveAddress(stop) {
    const street = String(stop.street || "").trim();
    const number = String(stop.number || "").trim();
    const neighborhood = String(stop.neighborhood || "").trim();
    const city = String(stop.city || "Goiânia").trim();
    if (!street || !number || normalize(city) !== "goiania") return stop;
    const key = [street, number, neighborhood, String(stop.quadra || ""), String(stop.lote || "")].map(normalize).join("|");
    if (resolveCache.has(key)) {
      const cached = resolveCache.get(key);
      return cached ? { ...stop, latitude: cached.latitude, longitude: cached.longitude } : stop;
    }
    let where = `nmlogradou LIKE '%${encodeWhereValue(street)}%' AND nrimovel = '${encodeWhereValue(number)}'`;
    if (neighborhood) where += ` AND nmbairro LIKE '%${encodeWhereValue(neighborhood)}%'`;
    if (stop.quadra) where += ` AND nrquadra = '${encodeWhereValue(stop.quadra)}'`;
    if (stop.lote) where += ` AND nrlote = '${encodeWhereValue(stop.lote)}'`;
    const features = await arcgisQuery(CADASTRAL_LAYER, {
      where,
      outFields: "id,cdlogradou,nmlogradou,nrimovel,nrquadra,nrlote,nmbairro,ci",
      returnGeometry: "true",
      outSR: "4326",
      resultRecordCount: "25",
    });
    let best = null;
    let bestScore = -Infinity;
    const targetStreet = normalize(street);
    const targetNeighborhood = normalize(neighborhood);
    for (const feature of features) {
      const a = feature.attributes || {};
      const candidateStreet = normalize(a.nmlogradou);
      const candidateNeighborhood = normalize(a.nmbairro);
      let score = 0;
      if (candidateStreet === targetStreet) score += 8;
      else if (candidateStreet.includes(targetStreet) || targetStreet.includes(candidateStreet)) score += 4;
      if (targetNeighborhood && candidateNeighborhood === targetNeighborhood) score += 5;
      if (String(a.nrimovel || "").trim() === number) score += 8;
      if (stop.quadra && normalize(a.nrquadra) === normalize(stop.quadra)) score += 4;
      if (stop.lote && normalize(a.nrlote) === normalize(stop.lote)) score += 4;
      const point = geometryPoint(feature.geometry);
      if (point && score > bestScore) best = point;
      if (score > bestScore) bestScore = score;
    }
    const resolved = best && Number.isFinite(best.latitude) && Number.isFinite(best.longitude) ? best : null;
    resolveCache.set(key, resolved);
    return resolved ? { ...stop, latitude: resolved.latitude, longitude: resolved.longitude } : stop;
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
        if (item.neighborhood && !$("manual-neighborhood").value.trim()) $("manual-neighborhood").value = item.neighborhood;
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

  function installFetchResolver() {
    if (global.__otimizerAddressFetchResolver) return;
    const originalFetch = global.fetch.bind(global);
    global.fetch = async function (input, init) {
      const url = typeof input === "string" ? input : input?.url || "";
      if (!String(url).includes("/optimize-manual") || !init?.body || typeof init.body !== "string") return originalFetch(input, init);
      try {
        const payload = JSON.parse(init.body);
        if (Array.isArray(payload.stops)) {
          payload.stops = await Promise.all(payload.stops.map((stop) => resolveAddress(stop)));
          init = { ...init, body: JSON.stringify(payload) };
        }
      } catch (_) {
        // The original API remains authoritative if address lookup fails.
      }
      return originalFetch(input, init);
    };
    global.__otimizerAddressFetchResolver = true;
  }

  function waitForManualForm() {
    if (installAutocomplete()) return;
    const observer = new MutationObserver(() => {
      if (installAutocomplete()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => { installFetchResolver(); waitForManualForm(); }, { once: true });
  } else {
    installFetchResolver();
    waitForManualForm();
  }
})(window);
