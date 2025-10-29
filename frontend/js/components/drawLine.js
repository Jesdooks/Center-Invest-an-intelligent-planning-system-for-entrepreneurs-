export default function drawRoute(response, map) {
  console.log("✅ Получен ответ от сервера:", response);

  // Проверка структуры
  if (!response?.routes?.length) {
    console.error("⚠️ Нет маршрутов в JSON!");
    return;
  }

  const route = response.routes[0];
  const waypoints = route.waypoints || [];
  const tomtomRoutes = route.tomtom_routes || [];

  if (!tomtomRoutes.length) {
    console.error("⚠️ Нет данных tomtom_routes для построения маршрута!");
    return;
  }

  // === Очистка старых маршрутов ===
  try {
    const style = map.getStyle();
    if (style?.layers) {
      style.layers.forEach(layer => {
        if (layer.id.startsWith("route_") || layer.id === "route") {
          if (map.getLayer(layer.id)) map.removeLayer(layer.id);
        }
      });
    }
    if (style?.sources) {
      Object.keys(style.sources).forEach(srcId => {
        if (srcId.startsWith("route_") || srcId === "route") {
          if (map.getSource(srcId)) map.removeSource(srcId);
        }
      });
    }
  } catch (err) {
    console.warn("⚠️ Ошибка при очистке слоёв:", err);
  }

  if (map.__routeMarkers) {
    map.__routeMarkers.forEach(m => m.remove());
    map.__routeMarkers = [];
  } else {
    map.__routeMarkers = [];
  }

  // === Сбор всех координат из вложенных routes ===
  let allCoords = [];

  tomtomRoutes.forEach((item, idx) => {
    if (!item?.routes?.length) return;

    item.routes.forEach((r, rIdx) => {
      const legs = r.legs || [];
      legs.forEach(leg => {
        const coords = leg.points
          .map(p => [Number(p.longitude), Number(p.latitude)])
          .filter(([lon, lat]) => Number.isFinite(lon) && Number.isFinite(lat));

        if (!coords.length) return;
        allCoords.push(...coords);

        const lineId = `route_${idx}_${rIdx}`;
        if (map.getLayer(lineId)) map.removeLayer(lineId);
        if (map.getSource(lineId)) map.removeSource(lineId);

        map.addSource(lineId, {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: { type: "LineString", coordinates: coords },
          },
        });

        map.addLayer({
          id: lineId,
          type: "line",
          source: lineId,
          paint: {
            "line-color": "#2E8B57",
            "line-width": 5,
            "line-opacity": 0.9,
          },
        });
      });
    });
  });

  // === Добавляем маркеры из waypoints ===
  waypoints.forEach((p, index) => {
    const { lat, lon, level } = p;
    let color = "#f4c542"; // стандарт
    if (index === 0) color = "green";
    else if (index === waypoints.length - 1) color = "red";
    if (level?.toLowerCase() === "vip") color = "#d35400";

    const marker = new tt.Marker({ color }).setLngLat([lon, lat]).addTo(map);

    const popupHtml = `
      <div style="font-size:13px">
        <b>Точка ${index + 1}</b><br/>
        ${level ? `Тип: ${level}` : "Обычная"}<br/>
        Коорд: ${lat.toFixed(5)}, ${lon.toFixed(5)}
      </div>
    `;
    marker.setPopup(new tt.Popup({ offset: 30 }).setHTML(popupHtml));
    map.__routeMarkers.push(marker);
  });

  // === Масштабирование карты под маршрут ===
  if (allCoords.length) {
    const bounds = new tt.LngLatBounds();
    allCoords.forEach(c => bounds.extend(c));
    map.fitBounds(bounds, { padding: 60 });
  }

  console.log("🟢 Маршрут и точки успешно отрисованы!");
}
