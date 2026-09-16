(function (global) {
  function html(value) {
    return escapeHtml(value ?? "");
  }

  let manualStops = [];
  let manualMap = null;
  let manualMarkers = [];
  let selectedManualIndex = -1;

  function setupManualMap() {
    if (manualMap || typeof L === "undefined") return;
    manualMap = L.map("manual-map").setView([-16.6869, -49.2648], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors" }).addTo(manualMap);
    manualMap.on("click", (event) => {
      if (selectedManualIndex < 0) {
        setManualStatus("Selecione uma parada e depois clique no mapa para marcar o ponto.");
        return;
      }
      const stop = manualStops[selectedManualIndex];
      if (!stop) return;
      stop.latitude = event.latlng.lat;
      stop.longitude = event.latlng.lng;
      stop.locationSource = "manual-map";
      renderManualStops();
      renderManualMarkers();
      setManualStatus(`Ponto da parada ${selectedManualIndex + 1} marcado no mapa.`, "success");
    });
  }

  function setManualStatus(message, state = "") {
    const element = $("manual-status");
    if (!element) return;
    element.textContent = message;
    element.className = `manual-status${state ? ` manual-status-${state}` : ""}`;
  }

  function renderManualMarkers() {
    if (!manualMap) return;
    manualMarkers.forEach((marker) => marker.remove());
    manualMarkers = [];
    manualStops.forEach((stop, index) => {
      if (!OtimizerRouteUI.validCoordinatePair(stop.latitude, stop.longitude)) return;
      const marker = L.marker([stop.latitude, stop.longitude]).addTo(manualMap);
      marker.bindPopup(`<strong>Parada ${index + 1}</strong><br>${html(stop.address || stop.street || "Endereço não informado")}`);
      marker.on("click", () => selectManualStop(index));
      manualMarkers.push(marker);
    });
    if (manualMarkers.length) {
      const bounds = L.featureGroup(manualMarkers).getBounds();
      if (bounds.isValid()) manualMap.fitBounds(bounds, { padding: [24, 24] });
    }
  }

  function selectManualStop(index) {
    selectedManualIndex = index;
    renderManualStops();
    setManualStatus(`Parada ${index + 1} selecionada. O alfinete municipal pode ser ajustado clicando no mapa.`, "loading");
  }

  function renderManualStops() {
    const container = $("manual-stops");
    if (!container) return;
    if (!manualStops.length) {
      container.innerHTML = `<p class="manual-empty">Nenhuma parada adicionada ainda.</p>`;
      return;
    }
    container.innerHTML = manualStops.map((stop, index) => {
      const hasPoint = OtimizerRouteUI.validCoordinatePair(stop.latitude, stop.longitude);
      const selected = index === selectedManualIndex ? " selected" : "";
      const address = stop.address || [stop.street, stop.number].filter(Boolean).join(", ") || "Endereço não informado";
      const sourceText = stop.locationSource === "municipal-street" ? "📍 Alfinete automático na rua municipal" : hasPoint ? `📍 Ponto marcado: ${Number(stop.latitude).toFixed(6)}, ${Number(stop.longitude).toFixed(6)}` : "Sem alfinete — será tentada a localização pelo endereço.";
      return `<article class="manual-stop${selected}">
        <button class="manual-stop-select" type="button" data-index="${index}">
          <strong>${index + 1}. ${html(address)}</strong>
          <span>${html(stop.neighborhood || "")}${stop.quadra ? ` · Qd ${html(stop.quadra)}` : ""}${stop.lote ? ` · Lt ${html(stop.lote)}` : ""}</span>
          <small>${html(sourceText)}</small>
        </button>
        <button class="secondary manual-stop-remove" type="button" data-index="${index}">Remover</button>
      </article>`;
    }).join("");
    container.querySelectorAll(".manual-stop-select").forEach((button) => button.addEventListener("click", () => selectManualStop(Number(button.dataset.index))));
    container.querySelectorAll(".manual-stop-remove").forEach((button) => button.addEventListener("click", () => {
      const index = Number(button.dataset.index);
      manualStops.splice(index, 1);
      selectedManualIndex = manualStops.length ? Math.min(selectedManualIndex, manualStops.length - 1) : -1;
      renderManualStops();
      renderManualMarkers();
    }));
  }

  function invalidateMunicipalStreetSelection() {
    const streetInput = $("manual-street");
    if (!streetInput) return;
    delete streetInput.dataset.selectedLatitude;
    delete streetInput.dataset.selectedLongitude;
    delete streetInput.dataset.selectedStreetId;
  }

  function readManualForm() {
    const value = (id) => $(id).value.trim();
    const address = value("manual-address");
    const streetInput = $("manual-street");
    const street = value("manual-street");
    const number = value("manual-number");
    if (!address && !street) throw Error("Informe a rua ou o endereço da parada.");
    const latitude = Number(streetInput?.dataset.selectedLatitude);
    const longitude = Number(streetInput?.dataset.selectedLongitude);
    const hasMunicipalPoint = Number.isFinite(latitude) && Number.isFinite(longitude);
    return {
      address,
      street,
      number,
      neighborhood: value("manual-neighborhood"),
      city: value("manual-city") || "Goiânia",
      zipcode: value("manual-zipcode"),
      quadra: value("manual-quadra"),
      lote: value("manual-lote"),
      latitude: hasMunicipalPoint ? latitude : null,
      longitude: hasMunicipalPoint ? longitude : null,
      locationSource: hasMunicipalPoint ? "municipal-street" : null,
    };
  }

  function clearManualForm() {
    ["manual-address", "manual-street", "manual-number", "manual-neighborhood", "manual-zipcode", "manual-quadra", "manual-lote"].forEach((id) => { $(id).value = ""; });
    invalidateMunicipalStreetSelection();
  }

  async function optimizeManualRoute() {
    clearError();
    if (!accessToken) return showError("Entre na conta para criar uma rota manual.");
    if (!manualStops.length) return showError("Adicione pelo menos uma parada antes de otimizar.");
    const button = $("manual-optimize");
    button.disabled = true;
    setManualStatus("Otimizando rota manual…", "loading");
    try {
      const response = await fetch(`${API_BASE}/optimize-manual`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ objective: $("manual-objective").value, return_to_start: $("manual-return-to-start").value === "true", stops: manualStops }),
      });
      if (!response.ok) {
        const detail = await readApiError(response);
        if (response.status === 401) logoutLocal();
        throw Error(friendlyApiError(response, detail));
      }
      const result = await response.json();
      if (!Array.isArray(result.route) || !result.summary) throw Error("A API retornou uma resposta de rota manual inválida.");
      currentRoute = result.route;
      visitedStops = new Set();
      $("result").hidden = false;
      const summary = result.summary;
      const routedDeliveries = Number(summary.routed_deliveries);
      const routedStops = Number(summary.routed_stops);
      const pending = Number(summary.pending);
      const distanceMeters = Number(summary.distance_meters);
      const durationSeconds = Number(summary.duration_seconds);
      const routingComplete = summary.routing_complete === true;
      $("delivery-count").textContent = Number.isFinite(routedDeliveries) ? routedDeliveries : "—";
      $("stop-count").textContent = Number.isFinite(routedStops) ? routedStops : "—";
      $("distance").textContent = Number.isFinite(distanceMeters) ? `${(distanceMeters / 1000).toFixed(1)} km${routingComplete ? "" : " (parcial)"}` : "—";
      $("duration").textContent = Number.isFinite(durationSeconds) ? `${Math.round(durationSeconds / 60)} min${routingComplete ? "" : " (parcial)"}` : "—";
      $("pending").textContent = Number.isFinite(pending) ? `${pending} pendência(s)` : "Pendências não informadas";
      $("coverage").textContent = summary.coverage_complete ? `✓ Rota completa · ${routedDeliveries} entrega(s) · ${routedStops} parada(s)` : `⚠ Rota incompleta · ${routedDeliveries} entrega(s) · ${routedStops} parada(s)`;
      $("coverage").classList.toggle("pending", !summary.coverage_complete || (Number.isFinite(pending) && pending > 0) || !routingComplete);
      renderStops(currentRoute);
      await renderMap(currentRoute);
      $("stop-detail").hidden = true;
      selectedIndex = -1;
      setManualStatus(routingComplete ? "Rota manual pronta." : "Rota manual pronta com pendência(s).", routingComplete ? "success" : "");
      setStatus(routingComplete ? "Rota pronta" : "Rota pronta com pendência(s)", routingComplete ? "success" : "");
    } catch (err) {
      showError(err.message || "Não foi possível otimizar a rota manual.");
      setManualStatus("Erro ao otimizar a rota manual.", "error");
      setStatus("Erro", "error");
    } finally {
      button.disabled = false;
    }
  }

  function install() {
    const setup = $("file-input")?.closest(".setup-panel");
    if (!setup) return;
    setup.insertAdjacentHTML("afterend", `
      <section class="panel manual-route-panel">
        <h2>Ou crie uma rota manualmente</h2>
        <p class="manual-intro">Adicione as paradas pelo endereço. O alfinete na rua é automático quando você escolhe uma sugestão municipal; depois você pode ajustar manualmente se quiser.</p>
        <div class="controls">
          <label>Objetivo<select id="manual-objective"><option value="time">Menor tempo</option><option value="distance">Menor distância</option></select></label>
          <label>Retornar ao início<select id="manual-return-to-start"><option value="false">Não</option><option value="true">Sim</option></select></label>
        </div>
        <div class="manual-form">
          <div class="controls">
            <label>Endereço completo<input id="manual-address" placeholder="Opcional se informar a rua"></label>
            <label>Rua<input id="manual-street" placeholder="Ex.: Rua 10"></label>
            <label>Número<input id="manual-number" placeholder="Ex.: 123"></label>
            <label>Bairro<input id="manual-neighborhood" placeholder="Ex.: Setor Bueno"></label>
            <label>Cidade<input id="manual-city" value="Goiânia"></label>
            <label>CEP<input id="manual-zipcode" placeholder="Ex.: 74230-010"></label>
            <label>Quadra<input id="manual-quadra" placeholder="Ex.: 12"></label>
            <label>Lote<input id="manual-lote" placeholder="Ex.: 8"></label>
          </div>
          <button id="manual-add" class="secondary" type="button">+ Adicionar parada</button>
        </div>
        <div class="manual-workspace">
          <div id="manual-stops" class="manual-stops"><p class="manual-empty">Nenhuma parada adicionada ainda.</p></div>
          <div>
            <p class="manual-map-hint">Ao escolher uma rua municipal e adicionar a parada, o alfinete será colocado automaticamente em um ponto real da rua. Clique no mapa apenas para ajustar.</p>
            <div id="manual-map" class="manual-map"></div>
          </div>
        </div>
        <button id="manual-optimize" class="primary" type="button">Otimizar rota manual</button>
        <div id="manual-status" class="manual-status">Adicione as paradas para começar.</div>
      </section>
    `);
    $("manual-neighborhood").addEventListener("input", invalidateMunicipalStreetSelection);
    $("manual-city").addEventListener("input", invalidateMunicipalStreetSelection);
    $("manual-add").addEventListener("click", () => {
      try {
        manualStops.push(readManualForm());
        selectedManualIndex = manualStops.length - 1;
        renderManualStops();
        clearManualForm();
        setupManualMap();
        renderManualMarkers();
        setManualStatus(`Parada ${manualStops.length} adicionada${manualStops[manualStops.length - 1]?.locationSource === "municipal-street" ? " com alfinete automático na rua." : ". Se quiser, marque o ponto no mapa."}`);
      } catch (error) { setManualStatus(error.message, "error"); }
    });
    $("manual-optimize").addEventListener("click", optimizeManualRoute);
    setupManualMap();
    setTimeout(() => manualMap?.invalidateSize(), 0);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})(window);
