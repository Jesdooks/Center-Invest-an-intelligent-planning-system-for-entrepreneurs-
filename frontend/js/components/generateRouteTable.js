import getAPI from "./getApi.js";

export default async function generateRouteTable(routeData) {
  const tableBody = document.querySelector("#routeTable tbody");
  if (!tableBody) return;

  tableBody.innerHTML = ""; // очистка

  const waypoints = [...(routeData.routes?.[0]?.waypoints || [])];

  if (!waypoints.length) {
    tableBody.innerHTML = `<tr><td colspan="3" class="text-muted">Нет данных для отображения</td></tr>`;
    return;
  }

  let routeId = "default";
  if (routeData.index) {
    routeId = routeData.index;
  } else if (window._currentDay) {
    routeId = window._currentDay;
  } else {
    routeId = routeData.routes[0]?.day || "default";
  }
  const storageKey = `visited_points_${routeId}`;
  const savedVisits = JSON.parse(localStorage.getItem(storageKey) || "{}");
  const addressCache = JSON.parse(localStorage.getItem("addressCache") || "{}");

  for (let i = 0; i < waypoints.length; i++) {
    const p = waypoints[i];
    const row = document.createElement("tr");

    // === Адрес (кеш + геокодирование)
    let address = addressCache[`${p.lat},${p.lon}`];
    if (!address) {
      if (typeof tt !== "undefined" && tt.services) {
        try {
          const res = await tt.services
            .reverseGeocode({
              key: getAPI(),
              position: { lat: p.lat, lon: p.lon },
            })
            .go();

          address =
            res?.addresses?.[0]?.address?.freeformAddress ||
            `lat: ${p.lat.toFixed(5)}, lon: ${p.lon.toFixed(5)}`;
          addressCache[`${p.lat},${p.lon}`] = address;
          localStorage.setItem("addressCache", JSON.stringify(addressCache));
        } catch (err) {
          console.warn("⚠️ Ошибка при обратном геокодировании:", err);
          address = `lat: ${p.lat.toFixed(5)}, lon: ${p.lon.toFixed(5)}`;
        }
      } else {
        console.warn("⚠️ TomTom SDK не загружен, адресы не определены.");
        address = `lat: ${p.lat.toFixed(5)}, lon: ${p.lon.toFixed(5)}`;
      }
    }

    const isVip = p.level?.toLowerCase() === "vip";
    const visited = savedVisits[i] || false;

    row.innerHTML = `
      <td>${address}</td>
      <td>${isVip ? "VIP" : "Стандарт"}</td>
      <td>
        <input type="checkbox" class="form-check-input visit-checkbox" data-index="${i}" ${
      visited ? "checked" : ""
    }>
      </td>
    `;

    tableBody.appendChild(row);
  }

  // === Обработка отметок посещения ===
  tableBody.querySelectorAll(".visit-checkbox").forEach((checkbox) => {
    checkbox.addEventListener("change", (e) => {
      const idx = e.target.dataset.index;
      const checked = e.target.checked;
      const data = JSON.parse(localStorage.getItem(storageKey) || "{}");
      data[idx] = checked;
      localStorage.setItem(storageKey, JSON.stringify(data));
    });
  });

  console.log("✅ Таблица маршрута обновлена (ETA и время в пути убраны)");
}

/* === Автообновление таблицы при обновлении геолокации (если нужно) === */
if (!window._geoWatcherAttached) {
  window._geoWatcherAttached = true;
  document.addEventListener("geoUpdated", async () => {
    console.log("📍 Геолокация обновлена — таблица не зависит от координат");
  });
}
