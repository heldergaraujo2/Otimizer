(function (global) {
  const originalRenderStops = global.renderStops;

  function isPending(stop) {
    const location = stop?.location || {};
    const latitude = location.access_latitude ?? location.property_latitude ?? stop?.latitude;
    const longitude = location.access_longitude ?? location.property_longitude ?? stop?.longitude;
    const valid = Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude)) && !(Number(latitude) === 0 && Number(longitude) === 0);
    return !valid || location.source === "pending";
  }

  global.renderStops = function (route) {
    if (typeof originalRenderStops === "function") originalRenderStops(route);
    const container = $("stops");
    if (!container) return;

    const items = Array.from(container.querySelectorAll(".stop"));
    const byIndex = new Map(items.map((item) => [Number(item.dataset.index), item]));
    const pendingIndexes = route.map((stop, index) => ({ stop, index })).filter(({ stop }) => isPending(stop)).map(({ index }) => index);
    const orderedIndexes = [...pendingIndexes, ...route.map((_, index) => index).filter((index) => !pendingIndexes.includes(index))];

    orderedIndexes.forEach((index) => {
      const item = byIndex.get(index);
      if (!item) return;
      const pending = pendingIndexes.includes(index);
      item.classList.toggle("stop-outside-optimization", pending);
      item.setAttribute("aria-label", pending
        ? `Parada ${route[index].sequence}, fora da otimização, localização pendente`
        : item.getAttribute("aria-label") || `Parada ${route[index].sequence}`);
      container.appendChild(item);
    });
  };

  function refreshPendingAlert() {
    const pending = Number($("pending")?.textContent?.match(/\d+/)?.[0] || 0);
    const alert = $("pending-alert");
    if (!alert) return;
    if (pending > 0) {
      alert.hidden = false;
      alert.textContent = `⚠ ATENÇÃO: ${pending} parada(s) ficaram fora da otimização e precisam de atenção. Elas foram colocadas no início da lista e destacadas em vermelho.`;
    } else {
      alert.hidden = true;
      alert.textContent = "";
    }
  }

  const pending = $("pending");
  if (pending) {
    new MutationObserver(refreshPendingAlert).observe(pending, { childList: true, characterData: true, subtree: true });
    refreshPendingAlert();
  }
})(window);
