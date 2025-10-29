import getAPI from "./getApi.js";

export default function getRoute(map) {
  const waypoints = [
    { lat: 47.2357, lon: 39.7015 },
    { lat: 47.2222, lon: 39.7200 },
    { lat: 47.2500, lon: 39.7100 },
  ];

  const locations = waypoints.map(p => `${p.lon},${p.lat}`).join(":");
  tt.services
    .calculateRoute({
      key: getAPI(),
      traffic: true,
      locations,
    })
    .go()
    .then((response) => {
      if (!response?.routes?.length) {
        console.error("⚠️ Маршрут не найден!");
        return;
      }

      const route = response.routes[0];
      const legs = route.legs || [];

      if (!legs.length || !legs[0].points?.length) {
        console.error("⚠️ Нет координат в legs!");
        return;
      }

      // ✅ В твоём ответе точки имеют формат {lng, lat}
      const allPoints = legs.flatMap(leg =>
        leg.points
          .map(p => [Number(p.lng), Number(p.lat)])
          .filter(([lng, lat]) => Number.isFinite(lng) && Number.isFinite(lat))
      );

      if (!allPoints.length) {
        console.error("❌ Нет координат для построения маршрута!");
        return;
      }

      // 🧹 Удаляем старые слои/источники
      if (map.getLayer("route")) map.removeLayer("route");
      if (map.getSource("route")) map.removeSource("route");

      // 🗺️ Добавляем маршрут
      map.addSource("route", {
        type: "geojson",
        data: {
          type: "Feature",
          geometry: { type: "LineString", coordinates: allPoints },
        },
      });

      map.addLayer({
        id: "route",
        type: "line",
        source: "route",
        paint: {
          "line-color": "#2E8B57",
          "line-width": 5,
        },
      });

      // 📍 Маркеры старта и финиша
      const start = allPoints[0];
      const end = allPoints[allPoints.length - 1];

      new tt.Marker({ color: "green" }).setLngLat(start).addTo(map);
      new tt.Marker({ color: "red" }).setLngLat(end).addTo(map);

      // 🔍 Масштабируем карту под маршрут
      const bounds = tt.LngLatBounds.convert(allPoints);
      map.fitBounds(bounds, { padding: 50 });
    })
    .catch((err) => {
      console.error("❌ Ошибка маршрута:", err);
    });
}
