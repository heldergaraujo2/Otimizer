const API_BASE = window.OTIMIZER_API_BASE || "http://localhost:8000";
const $ = (id) => document.getElementById(id);
let map;
let markers = [];
let currentRoute = [];
let selectedIndex = -1;
let accessToken = sessionStorage.getItem("otimizer_access_token") || "";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[char]));

function setStatus(message, state = "") {
  const status = $("status");
  status.textContent = message;
  status.className = `status${state ? ` status-${state}` : ""}`;
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
}

function clearError() {
  $("error").textContent = "";
  $("error").hidden = true;
}

function showAccountError(message) {
  $("account-error").textContent = message;
  $("account-error").hidden = false;
}

function clearAccountError() {
  $("account-error").textContent = "";
  $("account-error").hidden = true;
}

function authHeaders() {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

function friendlyApiError(response, detail) {
  if (response.status === 401) return "Sua sessão expirou ou é necessário entrar na conta.";
  if (response.status === 403) return detail || "Sua licença não permite gerar esta rota.";
  if (response.status === 413) return `Arquivo muito grande. ${detail || "Envie um arquivo menor."}`;
  if (response.status === 422) return `Arquivo ou rota inválida. ${detail || "Verifique os dados e tente novamente."}`;
  if (response.status === 502) return `Falha no serviço de roteamento. ${detail || "Tente novamente em instantes."}`;
  return detail || `Falha ao otimizar (HTTP ${response.status}).`;
}

async function readApiError(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      const result = await response.json();
      if (typeof result.detail === "string") return result.detail;
      if (result.detail?.message) return result.detail.message;
      return "";
    } catch (_) {
      return "";
    }
  }
  try { return (await response.text()).trim(); } catch (_) { return ""; }
}

function navigationUrl(stop) {
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${stop.latitude},${stop.longitude}`)}&travelmode=driving`;
}

function renderMap(route) {
  if (!route.length || typeof L === "undefined") return;
  if (!map) map = L.map("map");
  markers.forEach(marker => marker.remove());
  markers = [];
  if (!map._otimizerTiles) {
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors" }).addTo(map);
    map._otimizerTiles = true;
  }
  route.forEach((stop, index) => {
    const marker = L.marker([stop.latitude, stop.longitude]).addTo(map);
    marker.bindPopup(`<strong>Parada ${stop.sequence}</strong><br>${escapeHtml(stop.deliveries?.[0]?.address || "Endereço não informado")}`);
    marker.on("click", () => showStop(index));
    markers.push(marker);
  });
  map.fitBounds(L.latLngBounds(route.map(stop => [stop.latitude, stop.longitude])), { padding: [24, 24] });
}

function showStop(index) {
  const stop = currentRoute[index];
  if (!stop) return;
  selectedIndex = index;
  const deliveries = stop.deliveries || [];
  $("detail-title").textContent = `Parada ${stop.sequence}`;
  $("detail-content").innerHTML = `
    <div class="detail-address"><strong>${escapeHtml(deliveries[0]?.address || "Endereço não informado")}</strong><br>${escapeHtml(deliveries[0]?.neighborhood || "")} ${escapeHtml(deliveries[0]?.city || "")}</div>
    <p><strong>${deliveries.length}</strong> entrega(s) nesta parada</p>
    ${deliveries.map(delivery => `<article class="delivery-card"><strong>${escapeHtml(delivery.tracking_number || "Rastreio não informado")}</strong><span>${escapeHtml(delivery.address || "Endereço não informado")}</span></article>`).join("")}
    <a class="navigation-button" href="${navigationUrl(stop)}" target="_blank" rel="noopener">Navegar até esta parada</a>
  `;
  $("stop-detail").hidden = false;
  $("next-stop").hidden = index >= currentRoute.length - 1;
  document.querySelectorAll(".stop").forEach((element, itemIndex) => element.classList.toggle("selected", itemIndex === index));
}

function renderStops(route) {
  $("stops").innerHTML = route.map((stop, index) => {
    const primary = stop.deliveries?.[0] || {};
    return `<article class="stop" data-index="${index}" tabindex="0"><div class="stop-number">${stop.sequence}</div><div><h3>${escapeHtml(primary.address || "Endereço não informado")}</h3><p>${escapeHtml(primary.city || "")}</p><p>${stop.delivery_count} entrega(s)</p></div></article>`;
  }).join("");
  document.querySelectorAll(".stop").forEach((element) => {
    const index = Number(element.dataset.index);
    element.addEventListener("click", () => showStop(index));
    element.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") showStop(index); });
  });
}

function renderSignedOut() {
  $("account-signed-out").hidden = false;
  $("account-signed-in").hidden = true;
  $("license-status").textContent = "";
  $("renew").hidden = true;
}

function renderSignedIn(email) {
  $("account-signed-out").hidden = true;
  $("account-signed-in").hidden = false;
  $("account-email").textContent = email;
}

async function loadAccount() {
  if (!accessToken) return renderSignedOut();
  try {
    const response = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
    if (!response.ok) throw Error(await readApiError(response));
    const account = await response.json();
    renderSignedIn(account.email);
    await loadLicense();
  } catch (_) {
    accessToken = "";
    sessionStorage.removeItem("otimizer_access_token");
    renderSignedOut();
  }
}

async function loadLicense() {
  if (!accessToken) return;
  const response = await fetch(`${API_BASE}/licenses/me`, { headers: authHeaders() });
  if (response.status === 401) return logoutLocal();
  if (!response.ok) {
    $("license-status").textContent = "Não foi possível consultar a licença.";
    return;
  }
  const payload = await response.json();
  const license = payload.license;
  if (!license || !payload.active) {
    $("license-status").textContent = "Licença inativa. Renove para continuar usando o Otimizer.";
    $("renew").hidden = true;
    return;
  }
  const expires = new Date(license.expires_at).toLocaleString("pt-BR");
  const price = (license.price_cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  $("license-status").textContent = `Licença ativa até ${expires} · Renovação: ${price}`;
  $("renew").hidden = false;
  $("renew").dataset.licenseId = license.license_id;
}

function logoutLocal() {
  accessToken = "";
  sessionStorage.removeItem("otimizer_access_token");
  renderSignedOut();
  setStatus("Sessão encerrada");
}

$("login").addEventListener("click", async () => {
  clearAccountError();
  const email = $("login-email").value.trim();
  const password = $("login-password").value;
  if (!email || !password) return showAccountError("Informe e-mail e senha.");
  $("login").disabled = true;
  setStatus("Entrando…", "loading");
  try {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) throw Error(await readApiError(response) || "E-mail ou senha inválidos.");
    const result = await response.json();
    accessToken = result.access_token;
    sessionStorage.setItem("otimizer_access_token", accessToken);
    renderSignedIn(result.account.email);
    await loadLicense();
    setStatus("Conta conectada", "success");
  } catch (err) {
    showAccountError(err.message || "Não foi possível entrar.");
    setStatus("Erro", "error");
  } finally {
    $("login").disabled = false;
  }
});

$("logout").addEventListener("click", async () => {
  try {
    if (accessToken) await fetch(`${API_BASE}/auth/logout`, { method: "POST", headers: authHeaders() });
  } finally {
    logoutLocal();
  }
});

$("renew").addEventListener("click", async () => {
  const licenseId = $("renew").dataset.licenseId;
  if (!licenseId) return;
  $("renew").disabled = true;
  clearAccountError();
  try {
    const response = await fetch(`${API_BASE}/payments/pix`, {
      method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ license_id: licenseId }),
    });
    if (!response.ok) throw Error(await readApiError(response));
    const charge = await response.json();
    showAccountError(`Pix gerado. Copie o código de pagamento e conclua a cobrança. ID: ${charge.payment_id}`);
    $("account-error").classList.add("info");
  } catch (err) {
    showAccountError(err.message || "Não foi possível gerar o Pix.");
  } finally {
    $("renew").disabled = false;
  }
});

$("file-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  $("file-name").textContent = file ? file.name : "Selecione um arquivo .xlsx";
  $("optimize").disabled = !file;
  clearError();
  setStatus(file ? "Arquivo pronto" : "Pronto");
});

$("close-detail").addEventListener("click", () => { $("stop-detail").hidden = true; selectedIndex = -1; });
$("next-stop").addEventListener("click", () => { if (selectedIndex >= 0) showStop(selectedIndex + 1); });

$("optimize").addEventListener("click", async () => {
  const file = $("file-input").files[0];
  if (!file || $("optimize").disabled) return;
  const form = new FormData();
  form.append("file", file);
  form.append("objective", $("objective").value);
  form.append("return_to_start", $("return-to-start").value);
  const endpoint = (latId, lonId, latName, lonName) => {
    const lat = $(latId).value.trim(), lon = $(lonId).value.trim();
    if (!lat && !lon) return;
    if (!lat || !lon) throw Error("Preencha latitude e longitude do mesmo ponto.");
    form.append(latName, lat); form.append(lonName, lon);
  };

  clearError();
  $("optimize").disabled = true;
  setStatus("Otimizando…", "loading");
  try {
    endpoint("origin-lat", "origin-lon", "origin_latitude", "origin_longitude");
    endpoint("destination-lat", "destination-lon", "destination_latitude", "destination_longitude");
    if ($("destination-lat").value.trim() && $("return-to-start").value === "true") {
      throw Error("Destino e retorno ao início não podem ser usados juntos.");
    }

    const response = await fetch(`${API_BASE}/optimize`, { method: "POST", headers: authHeaders(), body: form });
    if (!response.ok) {
      const detail = await readApiError(response);
      if (response.status === 401) {
        logoutLocal();
      }
      const error = Error(friendlyApiError(response, detail));
      error.status = response.status;
      throw error;
    }
    const result = await response.json();
    if (!Array.isArray(result.route) || !result.summary) throw Error("A API retornou uma resposta de rota inválida.");

    currentRoute = result.route;
    $("result").hidden = false;
    $("delivery-count").textContent = result.summary.routed_deliveries;
    $("stop-count").textContent = result.summary.routed_stops;
    $("distance").textContent = `${(result.summary.distance_meters / 1000).toFixed(1)} km`;
    $("duration").textContent = `${Math.round(result.summary.duration_seconds / 60)} min`;
    $("pending").textContent = `${result.summary.pending} pendência(s)`;
    $("coverage").textContent = result.summary.coverage_complete
      ? `✓ Rota completa · ${result.summary.routed_deliveries} entrega(s) · ${result.summary.routed_stops} parada(s)`
      : `⚠ Rota incompleta · ${result.summary.routed_deliveries} entrega(s) · ${result.summary.routed_stops} parada(s)`;
    $("coverage").classList.toggle("pending", !result.summary.coverage_complete || result.summary.pending > 0);
    renderStops(currentRoute);
    renderMap(currentRoute);
    $("stop-detail").hidden = true;
    selectedIndex = -1;
    setStatus("Rota pronta", "success");
  } catch (err) {
    const message = err instanceof TypeError
      ? "Não foi possível conectar à API. Verifique se o backend está em execução."
      : (err.message || "Não foi possível otimizar a rota.");
    showError(message);
    setStatus("Erro", "error");
  } finally {
    $("optimize").disabled = !$("file-input").files[0];
  }
});

loadAccount();
