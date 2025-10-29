import getAPI from "./getApi.js";

const searchInput = document.getElementById("manualAddress");

export default function getSearchPosition(map) {
  return tt.services
    .fuzzySearch({
      key: getAPI(),
      query: searchInput.value,
    })
    .go()
    .then((result) => handleResults(result, map));
}

export async function handleResults(result, map) {
  if (result.results?.length) {
    const myPos = result.results[0].position;
    await moveMap(myPos, map);
  } else {
    console.warn("⚠️ Адрес не найден.");
  }
}

export async function moveMap(myPos, map) {
  console.log("📍 Новая позиция:", myPos);

  // Обновляем поле формы и сохраняем координаты
  searchInput.value = `lat: ${myPos.lat}, lon: ${myPos.lng}`;
  window._userGeo = { lat: myPos.lat, lon: myPos.lng };

  // Центрируем карту без пересоздания
  map.flyTo({
    center: [myPos.lng, myPos.lat],
    zoom: 18,
  });

  // Удаляем предыдущий маркер (если есть)
if (window._userMarker) {
  window._userMarker.remove();
}

  // === Определяем адрес по координатам ===
  let address = "Не удалось определить адрес";
  try {
    const geoRes = await tt.services
      .reverseGeocode({
        key: getAPI(),
        position: { lat: myPos.lat, lon: myPos.lng },
      })
      .go();

    if (geoRes?.addresses?.[0]?.address?.freeformAddress) {
      address = geoRes.addresses[0].address.freeformAddress;
    }
  } catch (err) {
    console.warn("⚠️ Ошибка при обратном геокодировании:", err);
  }

  // Создаём маркер
  const marker = new tt.Marker({ color: "#ef31ccff" })
    .setLngLat([myPos.lng, myPos.lat])
    .addTo(map);
 window._userMarker = marker;

  // Создаём попап с адресом
  const popup = new tt.Popup({ offset: 30 }).setHTML(`
    <div style="font-size:13px;">
      📍 <strong>Вы тут</strong><br>
      <small>${address}</small><br>
      <small>(${myPos.lat.toFixed(5)}, ${myPos.lng.toFixed(5)})</small>
    </div>
  `);

  marker.setPopup(popup).togglePopup();
}
