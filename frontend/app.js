const API_BASE = window.OTIMIZER_API_BASE || "http://localhost:8000";
const $ = (id) => document.getElementById(id);
let map;
let markers = [];
let currentRoute = [];
let selectedIndex = -1;

const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[char]));

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

$("file-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  $("file-name").textContent = file ? file.name : "Selecione um arquivo .xlsx";
  $("optimize").disabled = !file;
  $("error").hidden = true;
});

$("close-detail").addEventListener("click", () => { $("stop-detail").hidden = true; selectedIndex = -1; });
$("next-stop").addEventListener("click", () => { if (selectedIndex >= 0) showStop(selectedIndex + 1); });

$("optimize").addEventListener("click", async () => {
  const file = $("file-input").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  form.append("objective", $("objective").value);
  form.append("return_to_start", $("return-to-start").value);
  const endpoint = (latId, lonId, latName, lonName) => {
    const lat=$(latId).value.trim(), lon=$(lonId).value.trim();
    if (!lat && !lon) return;
    if (!lat || !lon) throw Error("Preencha latitude e longitude do mesmo ponto.");
    form.append(latName, lat); form.append(lonName, lon);
  };
  $("optimize").disabled = true; $("status").textContent = "Otimizando…";
  try {
    endpoint("origin-lat","origin-lon","origin_latitude","origin_longitude");
    endpoint("destination-lat","destination-lon","destination_latitude","destination_longitude");
    if ($("destination-lat").value.trim() && $("return-to-start").value === "true") throw Error("Destino e retorno ao início não podem ser usados juntos.");
    const response = await fetch(`${API_BASE}/optimize`, { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Falha ao otimizar.");
    currentRoute = result.route || [];
    $("result").hidden = false;
    $("delivery-count").textContent = result.summary.routed_deliveries;
    $("stop-count").textContent = result.summary.routed_stops;
    $("distance").textContent = `${(result.summary.distance_meters / 1000).toFixed(1)} km`;
    $("duration").textContent = `${Math.round(result.summary.duration_seconds / 60)} min`;
    $("pending").textContent = `${result.summary.pending} pendência(s)`;
    $("coverage").textContent = result.summary.coverage_complete ? "✓ Rota completa" : "⚠ Rota incompleta";
    renderStops(currentRoute);
    renderMap(currentRoute);
    $("stop-detail").hidden = true;
    selectedIndex = -1;
    $("status").textContent = "Rota pronta";
  } catch (err) {
    $("error").textContent = err.message; $("error").hidden = false; $("status").textContent = "Erro";
  } finally { $("optimize").disabled = false; }
});
