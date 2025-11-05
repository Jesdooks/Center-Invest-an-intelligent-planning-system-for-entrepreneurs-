import getAPI from "./getApi.js";

export default async function generateRouteTable(routeData) {
  const tableBody = document.querySelector("#routeTable tbody");
  if (!tableBody) return;

  tableBody.innerHTML = ""; // очистка

  const allWaypoints = [...(routeData.routes?.[0]?.waypoints || [])];
  
  console.log(`🔍 [generateRouteTable] Всего waypoints: ${allWaypoints.length}`);
  console.log(`🔍 [generateRouteTable] Типы waypoints:`, allWaypoints.map(wp => ({ type: wp.type, address: wp.address })));
  
  // Фильтруем waypoints: показываем ТОЛЬКО клиентские точки (type="client") С client_id
  // СТРОГО исключаем начальную (type="start") и конечную (type="end") точки
  // Также исключаем точки без client_id или с client_id === null/undefined
  const waypoints = allWaypoints.filter(wp => {
    const isClient = wp.type === "client";
    const hasClientId = wp.client_id !== null && wp.client_id !== undefined;
    const notStart = wp.type !== "start";
    const notEnd = wp.type !== "end";
    const notInitialAddress = wp.address !== "Начальная точка" && wp.address1 !== "Начальная точка";
    
    return isClient && hasClientId && notStart && notEnd && notInitialAddress;
  });

  console.log(`🔍 [generateRouteTable] После фильтрации (только client с client_id): ${waypoints.length}`);
  console.log(`🔍 [generateRouteTable] Отфильтрованные waypoints:`, waypoints.map(wp => ({ 
    type: wp.type, 
    client_id: wp.client_id, 
    address: wp.address?.substring(0, 50) 
  })));

  if (!waypoints.length) {
    console.warn(`⚠️ [generateRouteTable] Нет клиентских точек для отображения`);
    tableBody.innerHTML = `<tr><td colspan="3" class="text-muted">Нет данных для отображения</td></tr>`;
    return;
  }

  // Используем отфильтрованные waypoints
  const finalWaypoints = waypoints;

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

  console.log(`🔍 [generateRouteTable] Начинаем отображение ${finalWaypoints.length} строк в таблице`);

  // Используем Map для отслеживания уникальных адресов по client_id, чтобы избежать дубликатов
  // Используем Map вместо Set, чтобы сохранить порядок и адрес
  const seenClientIds = new Map(); // Map<client_id, waypoint>
  let displayIndex = 0; // Счетчик для отображения (после фильтрации дубликатов)
  
  // Сначала собираем уникальные waypoints по client_id
  for (let i = 0; i < finalWaypoints.length; i++) {
    const p = finalWaypoints[i];
    
    // Пропускаем точки без client_id
    if (p.client_id === null || p.client_id === undefined) {
      console.warn(`⚠️ [generateRouteTable] Пропущена точка без client_id:`, p);
      continue;
    }
    
    // Если client_id уже встречался, пропускаем дубликат
    if (seenClientIds.has(p.client_id)) {
      console.warn(`⚠️ [generateRouteTable] Пропущен дубликат client_id: ${p.client_id}, адрес: ${p.address?.substring(0, 50)}`);
      continue;
    }
    
    // Сохраняем уникальный waypoint
    seenClientIds.set(p.client_id, p);
  }
  
  // Теперь отображаем только уникальные waypoints
  const uniqueWaypoints = Array.from(seenClientIds.values());
  console.log(`🔍 [generateRouteTable] Уникальных адресов (после удаления дубликатов): ${uniqueWaypoints.length}`);
  
  for (let i = 0; i < uniqueWaypoints.length; i++) {
    const p = uniqueWaypoints[i];
    
    const row = document.createElement("tr");

    // === Адрес: ИСПОЛЬЗУЕМ ТОЛЬКО адрес из базы данных (из waypoint) ===
    // НЕ используем геокодирование, чтобы сохранить оригинальные адреса и почтовые индексы из БД
    // Приоритет: address1 (из БД) > address (из БД) > координаты
    // Это гарантирует, что почтовые индексы из файла сохраняются
    let address = p.address1 || p.address;
    
    // Дополнительная проверка: если адрес похож на "Начальная точка", пропускаем
    if (address && (address === "Начальная точка" || address === "Конечная точка")) {
      console.warn(`⚠️ [generateRouteTable] Пропущена служебная точка: ${address} (client_id: ${p.client_id})`);
      continue;
    }
    
    // Если адреса нет в waypoint, показываем координаты (но это не должно происходить для клиентских точек)
    if (!address) {
      console.warn(`⚠️ [generateRouteTable] Нет адреса для waypoint с client_id: ${p.client_id}`);
      address = `lat: ${p.lat.toFixed(5)}, lon: ${p.lon.toFixed(5)}`;
    } else {
      // Логируем адрес для отладки (первые 50 символов)
      console.log(`📋 [generateRouteTable] Адрес из БД (client_id: ${p.client_id}): ${address.substring(0, 50)}...`);
    }

    // Определяем VIP статус из client_level или level
    const clientLevel = p.client_level || p.level || "Standart";
    const isVip = clientLevel.toLowerCase() === "vip";
    const visited = savedVisits[displayIndex] || false;

    row.innerHTML = `
      <td>${address}</td>
      <td>${isVip ? "VIP" : "Стандарт"}</td>
      <td>
        <input type="checkbox" class="form-check-input visit-checkbox" data-index="${displayIndex}" ${
      visited ? "checked" : ""
    }>
      </td>
    `;

    tableBody.appendChild(row);
    displayIndex++; // Увеличиваем счетчик только для отображенных строк
  }
  
  console.log(`✅ [generateRouteTable] Отображено ${displayIndex} строк в таблице (после фильтрации дубликатов)`);

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
