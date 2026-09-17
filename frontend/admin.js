const API_BASE = window.OTIMIZER_API_BASE || "http://localhost:8000";
const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem("otimizer_admin_access_token") || "";
let selectedLicense = null;

const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[char]));
const headers = () => token ? { Authorization: `Bearer ${token}` } : {};
function setStatus(text, state = "") { const el = $("status"); el.textContent = text; el.className = `status${state ? ` status-${state}` : ""}`; }
function showLoginError(text) { $("login-error").textContent = text; $("login-error").hidden = false; }
function clearLoginError() { $("login-error").hidden = true; }
function showMessage(text, error = false) { const el = $("generate-message"); el.textContent = text; el.className = error ? "message error" : "message success"; el.hidden = false; }
async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
  if (response.status === 401) { token = ""; sessionStorage.removeItem("otimizer_admin_access_token"); throw new Error("Sessão administrativa expirada."); }
  let body = null;
  try { body = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : body?.detail?.message || `Erro HTTP ${response.status}`);
  return body;
}
function renderMetrics(items) {
  const counts = items.reduce((acc, item) => { const status = item.status || "DESCONHECIDO"; acc[status] = (acc[status] || 0) + 1; return acc; }, {});
  $("metrics").innerHTML = ["GERADA","DISPONIVEL","ATIVA","EXPIRADA","SUSPENSA","REVOGADA"].map((status) => `<article><span>${status}</span><strong>${counts[status] || 0}</strong></article>`).join("");
}
function renderLicenses(items) {
  const container = $("licenses");
  if (!items.length) { container.innerHTML = '<div class="empty">Nenhuma licença encontrada.</div>'; return; }
  container.innerHTML = items.map((item) => `<button class="license-row" data-id="${escapeHtml(item.license_id)}"><span><strong>${escapeHtml(item.plan)}</strong><small>${escapeHtml(item.account_id)}</small></span><span class="badge badge-${escapeHtml(item.status.toLowerCase())}">${escapeHtml(item.status)}</span><span><small>Expira</small><strong>${new Date(item.expires_at).toLocaleDateString("pt-BR")}</strong></span></button>`).join("");
  container.querySelectorAll("[data-id]").forEach((button) => button.addEventListener("click", () => loadDetails(button.dataset.id)));
}
async function loadLicenses() {
  setStatus("Atualizando…", "loading");
  try {
    const params = new URLSearchParams();
    if ($("filter-account").value.trim()) params.set("account_id", $("filter-account").value.trim());
    if ($("filter-status").value) params.set("status", $("filter-status").value);
    const payload = await api(`/admin/licenses${params.toString() ? `?${params}` : ""}`);
    renderMetrics(payload.items || []); renderLicenses(payload.items || []); setStatus(`${payload.count || 0} licença(s)`, "success");
  } catch (error) { setStatus("Erro", "error"); if (!token) return showLogin(); alert(error.message); }
}
function renderDetails(license) {
  selectedLicense = license;
  $("details").hidden = false;
  $("license-details").innerHTML = `<div class="detail-grid"><div><span>Plano</span><strong>${escapeHtml(license.plan)}</strong></div><div><span>Status</span><strong>${escapeHtml(license.status)}</strong></div><div><span>Conta</span><strong>${escapeHtml(license.account_id)}</strong></div><div><span>Chave</span><code>${escapeHtml(license.license_key)}</code></div><div><span>Início</span><strong>${new Date(license.starts_at).toLocaleString("pt-BR")}</strong></div><div><span>Expiração</span><strong>${new Date(license.expires_at).toLocaleString("pt-BR")}</strong></div><div><span>Ativada</span><strong>${license.activated_at ? new Date(license.activated_at).toLocaleString("pt-BR") : "—"}</strong></div><div><span>Renovações</span><strong>${license.renewal_count}</strong></div><div><span>Dispositivos</span><strong>${license.entitlements.max_devices}</strong></div><div><span>Preço</span><strong>${(Number(license.price_cents || 0) / 100).toLocaleString("pt-BR", {style:"currency",currency:"BRL"})}</strong></div></div>`;
  const actions = [];
  if (["GERADA","DISPONIVEL"].includes(license.status)) actions.push(["activate","Ativar"]);
  if (!["REVOGADA"].includes(license.status)) actions.push(["renew","Renovar"]);
  if (license.status === "ATIVA") actions.push(["suspend","Suspender"]);
  if (license.status === "SUSPENSA") actions.push(["reactivate","Reativar"]);
  if (license.status !== "REVOGADA") actions.push(["revoke","Revogar"]);
  $("license-actions").innerHTML = actions.map(([action, label]) => `<button class="secondary action" data-action="${action}">${label}</button>`).join("");
  $("license-actions").querySelectorAll(".action").forEach((button) => button.addEventListener("click", () => runAction(button.dataset.action)));
}
async function loadDetails(id) {
  try {
    const [license, history, devices] = await Promise.all([api(`/admin/licenses/${encodeURIComponent(id)}`), api(`/admin/licenses/${encodeURIComponent(id)}/history`), api(`/admin/licenses/${encodeURIComponent(id)}/devices`)]);
    renderDetails(license);
    $("history").innerHTML = history.items.length ? history.items.map((event) => `<div class="event"><strong>${escapeHtml(event.action)}</strong><span>${new Date(event.occurred_at).toLocaleString("pt-BR")}</span><small>Admin: ${escapeHtml(event.actor_account_id || "sistema")}${event.reason ? ` · ${escapeHtml(event.reason)}` : ""}</small></div>`).join("") : '<div class="empty">Sem eventos.</div>';
    $("devices").innerHTML = devices.items.length ? devices.items.map((device) => `<div class="device"><span><strong>${escapeHtml(device.device_id)}</strong><small>${device.active ? "Ativo" : "Revogado"}</small></span>${device.active ? `<button class="secondary" data-device="${escapeHtml(device.device_id)}">Revogar</button>` : ""}</div>`).join("") : '<div class="empty">Nenhum dispositivo vinculado.</div>';
    $("devices").querySelectorAll("[data-device]").forEach((button) => button.addEventListener("click", () => revokeDevice(button.dataset.device)));
    $("details").scrollIntoView({behavior:"smooth",block:"start"});
  } catch (error) { alert(error.message); }
}
async function runAction(action) {
  if (!selectedLicense) return;
  let body = undefined;
  if (action === "renew") { const days = prompt("Quantos dias deseja renovar?", "30"); if (!days || !/^\d+$/.test(days) || Number(days) < 1) return; body = {duration_days: Number(days)}; }
  if (["suspend","revoke"].includes(action)) { const reason = prompt("Informe o motivo obrigatório:"); if (!reason?.trim()) return; body = {reason: reason.trim()}; }
  if (action === "revoke" && !confirm("Revogar esta licença permanentemente?")) return;
  try {
    await api(`/admin/licenses/${encodeURIComponent(selectedLicense.license_id)}/${action}`, {method:"POST",headers:{"Content-Type":"application/json"},body:body ? JSON.stringify(body) : undefined});
    await loadDetails(selectedLicense.license_id); await loadLicenses();
  } catch (error) { alert(error.message); }
}
async function revokeDevice(id) {
  if (!confirm("Revogar este dispositivo?")) return;
  try { await api(`/admin/devices/${encodeURIComponent(id)}/revoke`, {method:"POST"}); await loadDetails(selectedLicense.license_id); } catch (error) { alert(error.message); }
}
function showAdmin(account) { $("login-panel").hidden = true; $("admin-panel").hidden = false; $("admin-email").textContent = account.email; loadLicenses(); }
function showLogin() { $("login-panel").hidden = false; $("admin-panel").hidden = true; }
$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearLoginError(); const button = event.target.querySelector("button"); button.disabled = true; setStatus("Entrando…", "loading");
  try { const result = await fetch(`${API_BASE}/auth/login`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:$("email").value.trim(),password:$("password").value})}); const data = await result.json(); if (!result.ok) throw new Error(data.detail || "Falha no login"); token = data.access_token; sessionStorage.setItem("otimizer_admin_access_token", token); const account = await api("/auth/me"); if (account.role !== "ADMIN") { token = ""; sessionStorage.removeItem("otimizer_admin_access_token"); throw new Error("Esta conta não possui perfil ADMIN."); } showAdmin(account); } catch (error) { showLoginError(error.message); setStatus("Acesso negado", "error"); } finally { button.disabled = false; }
});
$("logout").addEventListener("click", async () => { try { await api("/auth/logout", {method:"POST"}); } catch (_) {} token = ""; sessionStorage.removeItem("otimizer_admin_access_token"); showLogin(); setStatus("Sessão encerrada"); });
$("refresh").addEventListener("click", loadLicenses);
$("filter-account").addEventListener("change", loadLicenses); $("filter-status").addEventListener("change", loadLicenses);
$("close-details").addEventListener("click", () => { $("details").hidden = true; selectedLicense = null; });
$("generate-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const payload = {account_id:$("gen-account").value.trim(),plan:$("gen-plan").value.trim(),duration_days:Number($("gen-duration").value),max_devices:Number($("gen-devices").value),max_routes_per_day:$("gen-routes").value ? Number($("gen-routes").value) : null,route_optimization:$("gen-optimization").checked,price_cents:Number($("gen-price").value)};
  try { const result = await api("/admin/licenses", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); showMessage(`Licença gerada: ${result.license_key}`); event.target.reset(); $("gen-plan").value="default"; $("gen-duration").value=30; $("gen-devices").value=1; $("gen-price").value=0; $("gen-optimization").checked=true; await loadLicenses(); await loadDetails(result.license_id); } catch (error) { showMessage(error.message, true); }
});
async function bootstrap() {
  if (!token) return showLogin();
  try { const account = await api("/auth/me"); if (account.role !== "ADMIN") throw new Error("Esta conta não possui perfil ADMIN."); showAdmin(account); } catch (_) { token = ""; sessionStorage.removeItem("otimizer_admin_access_token"); showLogin(); }
}
bootstrap();
