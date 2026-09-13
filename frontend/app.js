const API_BASE = window.OTIMIZER_API_BASE || "http://localhost:8000";
const $ = (id) => document.getElementById(id);
$("file-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  $("file-name").textContent = file ? file.name : "Selecione um arquivo .xlsx";
  $("optimize").disabled = !file;
  $("error").hidden = true;
});
$("optimize").addEventListener("click", async () => {
  const file = $("file-input").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  form.append("objective", $("objective").value);
  form.append("return_to_start", $("return-to-start").value);
  $("optimize").disabled = true;
  $("status").textContent = "Otimizando…";
  try {
    const response = await fetch(`${API_BASE}/optimize`, { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Falha ao otimizar.");
    $("result").hidden = false;
    $("delivery-count").textContent = result.summary.routed_deliveries;
    $("stop-count").textContent = result.summary.routed_stops;
    $("distance").textContent = `${(result.summary.distance_meters / 1000).toFixed(1)} km`;
    $("duration").textContent = `${Math.round(result.summary.duration_seconds / 60)} min`;
    $("pending").textContent = `${result.summary.pending} pendência(s)`;
    $("coverage").textContent = result.summary.coverage_complete ? "✓ Rota completa" : "⚠ Rota incompleta";
    $("stops").innerHTML = result.route.map(stop => `<article class="stop"><div class="stop-number">${stop.sequence}</div><div><h3>${stop.address || "Endereço não informado"}</h3><p>${stop.city || ""}</p><p>${stop.delivery_count} entrega(s)</p></div></article>`).join("");
    $("status").textContent = "Rota pronta";
  } catch (err) {
    $("error").textContent = err.message;
    $("error").hidden = false;
    $("status").textContent = "Erro";
  } finally { $("optimize").disabled = false; }
});
