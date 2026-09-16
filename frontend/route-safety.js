(function (global) {
  function validCoordinate(value, min, max) {
    if (value === null || value === undefined || value === "") return false;
    const number = Number(value);
    return Number.isFinite(number) && number >= min && number <= max;
  }

  function validCoordinatePair(latitude, longitude) {
    if (!validCoordinate(latitude, -90, 90) || !validCoordinate(longitude, -180, 180)) return false;
    return !(Number(latitude) === 0 && Number(longitude) === 0);
  }

  function mapCoordinates(stop) {
    const location = stop?.location || {};
    if (location.source && validCoordinatePair(location.access_latitude, location.access_longitude)) {
      return { latitude: Number(location.access_latitude), longitude: Number(location.access_longitude), kind: "access" };
    }
    if (location.source && validCoordinatePair(location.property_latitude, location.property_longitude)) {
      return { latitude: Number(location.property_latitude), longitude: Number(location.property_longitude), kind: "property" };
    }
    if (validCoordinatePair(stop?.latitude, stop?.longitude)) {
      return { latitude: Number(stop.latitude), longitude: Number(stop.longitude), kind: "route" };
    }
    if (validCoordinatePair(location.access_latitude, location.access_longitude)) {
      return { latitude: Number(location.access_latitude), longitude: Number(location.access_longitude), kind: "access" };
    }
    if (validCoordinatePair(location.property_latitude, location.property_longitude)) {
      return { latitude: Number(location.property_latitude), longitude: Number(location.property_longitude), kind: "property" };
    }
    return null;
  }

  function navigationTarget(stop) {
    const location = stop?.location || {};
    if (validCoordinatePair(location.access_latitude, location.access_longitude)) {
      return { latitude: Number(location.access_latitude), longitude: Number(location.access_longitude) };
    }
    if (!location.source && validCoordinatePair(stop?.latitude, stop?.longitude)) {
      return { latitude: Number(stop.latitude), longitude: Number(stop.longitude) };
    }
    return null;
  }

  function navigationUrl(stop) {
    const target = navigationTarget(stop);
    if (!target) return null;
    return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${target.latitude},${target.longitude}`)}&travelmode=driving`;
  }

  function locationSummary(stop) {
    const location = stop?.location || {};
    const confidence = Number(location.confidence);
    const percentage = Number.isFinite(confidence) ? ` · confiança ${Math.round(confidence * 100)}%` : "";
    if (!location.source && validCoordinatePair(stop?.latitude, stop?.longitude)) {
      return "Localização: GPS da planilha";
    }
    if (validCoordinatePair(location.access_latitude, location.access_longitude)) {
      return `Ponto de acesso viário resolvido${percentage}`;
    }
    if (validCoordinatePair(location.property_latitude, location.property_longitude)) {
      return `Localização da propriedade resolvida${percentage} · acesso exato pendente`;
    }
    return location.source ? `Localização pendente${percentage}` : "Localização pendente";
  }

  function stopState(stop) {
    const coordinates = mapCoordinates(stop);
    if (!coordinates) return "pending";
    if (coordinates.kind === "property" && !navigationTarget(stop)) return "approximate";
    return "located";
  }

  function installUi() {
    stopIcon = function (stop, visited = false) {
      const visitedClass = visited ? " visited" : "";
      return L.divIcon({
        className: "otimizer-stop-marker",
        html: `<span class="${visitedClass.trim()}">${escapeHtml(stop.sequence)}</span>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18]
      });
    };

    markStopVisited = function (index) {
      if (index < 0 || index >= currentRoute.length) return;
      visitedStops.add(index);
      const marker = markers[index];
      const stop = currentRoute[index];
      if (marker && typeof L !== "undefined") marker.setIcon(stopIcon(stop, true));
      const element = document.querySelector(`.stop[data-index="${index}"]`);
      if (element) element.classList.add("visited");
    };

    fetchRouteGeometry = async function (route) {
      const runs = [];
      let currentRun = [];
      for (const stop of route) {
        if (mapCoordinates(stop)) {
          currentRun.push(stop);
        } else {
          if (currentRun.length >= 2) runs.push(currentRun);
          currentRun = [];
        }
      }
      if (currentRun.length >= 2) runs.push(currentRun);
      if (!runs.length) return null;

      const features = [];
      for (const run of runs) {
        const coordinates = run.map((stop) => {
          const point = mapCoordinates(stop);
          return `${point.longitude},${point.latitude}`;
        }).join(";");
        const url = `https://router.project-osrm.org/route/v1/driving/${coordinates}?overview=full&geometries=geojson&steps=false`;
        const response = await fetch(url, { headers: { Accept: "application/json" } });
        if (!response.ok) throw Error(`OSRM retornou HTTP ${response.status}`);
        const result = await response.json();
        const geometry = result.routes?.[0]?.geometry;
        if (!geometry) throw Error("OSRM não retornou a geometria da rota.");
        features.push({ type: "Feature", properties: {}, geometry });
      }
      return { type: "FeatureCollection", features };
    };

    renderMap = async function (route) {
      if (!route.length || typeof L === "undefined") return;
      if (!map) map = L.map("map");
      markers.forEach((marker) => marker?.remove());
      markers = [];
      if (routeLine) {
        routeLine.remove();
        routeLine = null;
      }
      if (!map._otimizerTiles) {
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors" }).addTo(map);
        map._otimizerTiles = true;
      }

      route.forEach((stop, index) => {
        const point = mapCoordinates(stop);
        if (!point) {
          markers[index] = null;
          return;
        }
        const marker = L.marker([point.latitude, point.longitude], {
          icon: stopIcon(stop, visitedStops.has(index))
        }).addTo(map);
        const state = stopState(stop);
        const label = state === "pending" ? "Localização pendente" : state === "approximate" ? "Localização aproximada" : "Localização disponível";
        marker.bindPopup(`<strong>Parada ${escapeHtml(stop.sequence)}</strong><br>${escapeHtml(stop.deliveries?.[0]?.address || "Endereço não informado")}<br><span>${label}</span>`);
        marker.on("click", () => showStop(index));
        markers[index] = marker;
      });

      try {
        const geometry = await fetchRouteGeometry(route);
        if (geometry) {
          routeLine = L.geoJSON(geometry, {
            style: { weight: 6, opacity: 0.8, color: "#2563eb" }
          }).addTo(map);
        }
      } catch (error) {
        console.warn("Não foi possível desenhar a geometria viária da rota:", error);
      }

      const layers = routeLine ? [routeLine, ...markers.filter(Boolean)] : markers.filter(Boolean);
      if (layers.length) {
        const bounds = L.featureGroup(layers).getBounds();
        if (bounds.isValid()) map.fitBounds(bounds, { padding: [24, 24] });
      }
    };

    showStop = function (index) {
      const stop = currentRoute[index];
      if (!stop) return;
      selectedIndex = index;
      const deliveries = stop.deliveries || [];
      const targetUrl = navigationUrl(stop);
      const state = stopState(stop);
      const action = targetUrl
        ? `<a class="navigation-button" href="${targetUrl}" target="_blank" rel="noopener">Navegar até esta parada</a>`
        : `<button class="navigation-button navigation-disabled" type="button" disabled>Localização de navegação pendente</button>`;
      $("detail-title").textContent = `Parada ${stop.sequence}`;
      $("detail-content").innerHTML = `
        <div class="detail-address"><strong>${escapeHtml(deliveries[0]?.address || "Endereço não informado")}</strong><br>${escapeHtml(deliveries[0]?.neighborhood || "")} ${escapeHtml(deliveries[0]?.city || "")}</div>
        <p><strong>${deliveries.length}</strong> entrega(s) nesta parada</p>
        <p>${escapeHtml(locationSummary(stop))}</p>
        <p class="location-state location-state-${state}">${state === "pending" ? "Esta entrega permanece na rota, mas ainda não possui um ponto geográfico utilizável." : state === "approximate" ? "A propriedade foi localizada, mas o acesso exato ainda não foi determinado." : "Ponto geográfico disponível para esta parada."}</p>
        ${deliveries.map(delivery => `<article class="delivery-card"><strong>${escapeHtml(delivery.tracking_number || "Rastreio não informado")}</strong><span>${escapeHtml(delivery.address || "Endereço não informado")}</span></article>`).join("")}
        ${action}
      `;
      $("stop-detail").hidden = false;
      $("next-stop").hidden = index >= currentRoute.length - 1;
      document.querySelectorAll(".stop").forEach((element, itemIndex) => {
        element.classList.toggle("selected", itemIndex === index);
        element.classList.toggle("visited", visitedStops.has(itemIndex));
      });
    };

    renderStops = function (route) {
      $("stops").innerHTML = route.map((stop, index) => {
        const primary = stop.deliveries?.[0] || {};
        const state = stopState(stop);
        const visitedClass = visitedStops.has(index) ? " visited" : "";
        const stateLabel = state === "pending" ? "Localização pendente" : state === "approximate" ? "Localização aproximada" : "Localização disponível";
        return `<article class="stop${visitedClass} stop-${state}" data-index="${index}" tabindex="0" aria-label="Parada ${escapeHtml(stop.sequence)}, ${stateLabel}"><div class="stop-number">${escapeHtml(stop.sequence)}</div><div><h3>${escapeHtml(primary.address || "Endereço não informado")}</h3><p>${escapeHtml(primary.city || "")}</p><p>${escapeHtml(stop.delivery_count)} entrega(s)</p><p class="location-state location-state-${state}">${stateLabel}</p></div></article>`;
      }).join("");
      document.querySelectorAll(".stop").forEach((element) => {
        const index = Number(element.dataset.index);
        element.addEventListener("click", () => showStop(index));
        element.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            showStop(index);
          }
        });
      });
    };
  }

  global.OtimizerRouteUI = { validCoordinatePair, mapCoordinates, navigationTarget, navigationUrl, locationSummary, stopState };
  installUi();
})(window);
