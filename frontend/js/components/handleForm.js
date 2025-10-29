import getAPI from "./getApi.js";
import drawRoute from "./drawLine.js";
import generateRouteTable from "./generateRouteTable.js";

export default function handleForm(map) {
  const form = document.getElementById("routeForm");
  const formMessage = document.getElementById("formMessage");
  const fileInput = document.getElementById("fileInput");
  const manualAddress = document.getElementById("manualAddress");
  const geoBtn = document.getElementById("getGeo");
  const geoError = document.getElementById("geoError");
  const periodSelect = document.getElementById("selectPeriod");
  const submitBtn = form.querySelector('button[type="submit"]');
  const removeFileBtn = document.getElementById("removeFileBtn");
  const filePlaceholder = document.getElementById("filePlaceholder");
  const fileInfo = document.getElementById("fileInfo");
  const tableBlock = document.querySelector(".table-block");

  if (!form) return console.warn("⚠️ Форма не найдена на странице.");

  /* === Удаление файла === */
  removeFileBtn?.addEventListener("click", () => {
    fileInput.value = "";
    filePlaceholder.classList.remove("d-none");
    fileInfo.classList.add("d-none");
    if (tableBlock) tableBlock.classList.add("d-none");
    validateFormFields();
  });

  /* === Геолокация === */
  geoBtn?.addEventListener("click", async () => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const { latitude, longitude } = position.coords;
          window._userGeo = { lat: latitude, lon: longitude };
          manualAddress.value = `lat: ${latitude}, lon: ${longitude}`;
          geoError.classList.add("d-none");

          map.flyTo({ center: [longitude, latitude], zoom: 18 });

          if (window._userMarker) window._userMarker.remove();

          let address = "Не удалось определить адрес";
          try {
            const geoRes = await tt.services
              .reverseGeocode({
                key: getAPI(),
                position: { lat: latitude, lon: longitude },
              })
              .go();
            if (geoRes?.addresses?.[0]?.address?.freeformAddress)
              address = geoRes.addresses[0].address.freeformAddress;
          } catch (err) {
            console.warn("⚠️ Ошибка при обратном геокодировании:", err);
          }

          const marker = new tt.Marker({ color: "#ef31ccff" })
            .setLngLat([longitude, latitude])
            .addTo(map);
          window._userMarker = marker;

          const popup = new tt.Popup({ offset: 30 }).setHTML(`
            <div style="font-size:13px;">
              📍 <strong>Вы тут</strong><br>
              <small>${address}</small><br>
              <small>(${latitude.toFixed(5)}, ${longitude.toFixed(5)})</small>
            </div>
          `);
          marker.setPopup(popup).togglePopup();

          validateFormFields();
        },
        (error) => {
          console.error(error);
          geoError.classList.remove("d-none");
          manualAddress.removeAttribute("disabled");
        }
      );
    } else {
      geoError.classList.remove("d-none");
      manualAddress.removeAttribute("disabled");
    }
  });

  /* === Проверка заполненности полей === */
  function validateFormFields() {
    const hasFile = fileInput.files.length > 0;
    const hasAddress = manualAddress.value.trim().length > 0;
    const hasPeriod =
      periodSelect && periodSelect.value && periodSelect.value !== "Выбрать период";

    const isValid = hasFile && hasAddress && hasPeriod;
    submitBtn.disabled = !isValid;
    submitBtn.classList.toggle("opacity-50", !isValid);
    return isValid;
  }

  [fileInput, manualAddress, periodSelect].forEach((el) => {
    el?.addEventListener("input", validateFormFields);
    el?.addEventListener("change", validateFormFields);
  });
  validateFormFields();

  /* === Отправка формы === */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (submitBtn.disabled) {
      formMessage.classList.remove("d-none", "text-success");
      formMessage.classList.add("text-danger");
      formMessage.textContent = "⚠️ Заполните все обязательные поля перед отправкой.";
      return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("address", manualAddress.value);
    formData.append("period", periodSelect.value);

    if (window._userGeo) {
      formData.append("lat", window._userGeo.lat);
      formData.append("lon", window._userGeo.lon);
    }

    console.log("📦 Отправляем данные:", Object.fromEntries(formData));

    try {
      // Базовый URL для API запросов
      const API_BASE_URL = window.location.origin; // http://localhost:8000
      
      /* === Шаг 1. POST — отправляем данные на сервер === */
      const uploadResponse = await fetch(`${API_BASE_URL}/api/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadResponse.ok) {
        const errorText = await uploadResponse.text();
        throw new Error(`Ошибка загрузки файла: HTTP ${uploadResponse.status} - ${errorText}`);
      }

      const uploadResult = await uploadResponse.json();
      console.log("✅ Сервер принял данные:", uploadResult);

      /* === Шаг 2. GET — получаем готовый маршрут === */
      const routeResponse = await fetch(`${API_BASE_URL}/api/route`, {
        method: "GET",
        headers: {
          "Accept": "application/json",
        },
      });

      if (!routeResponse.ok) {
        const errorText = await routeResponse.text();
        throw new Error(`Ошибка получения маршрута: HTTP ${routeResponse.status} - ${errorText}`);
      }

      const routeData = await routeResponse.json();
      console.log("📍 Получен маршрут:", routeData);

      // === Заполняем selectDay динамически ===
const selectDay = document.getElementById("selectDay");
if (selectDay) {
  // Очистим перед добавлением
  selectDay.innerHTML = `<option selected disabled>Выбрать день</option>`;

  if (routeData.routes && routeData.routes.length > 0) {
    routeData.routes.forEach((route, idx) => {
      const opt = document.createElement("option");
      opt.value = idx;
      opt.textContent = `День ${route.day || idx + 1}`;
      selectDay.appendChild(opt);
    });

    // Активируем первый день
    selectDay.selectedIndex = 1;
    selectDay.dispatchEvent(new Event("change"));
  } else {
    const opt = document.createElement("option");
    opt.textContent = "Нет доступных маршрутов";
    opt.disabled = true;
    selectDay.appendChild(opt);
  }

  // При смене дня — перестраиваем маршрут и таблицу
  selectDay.addEventListener("change", (e) => {
    const selectedIndex = parseInt(e.target.value);
    if (isNaN(selectedIndex) || !routeData.routes[selectedIndex]) return;

    const selectedDayData = {
      routes: [routeData.routes[selectedIndex]],
      index: selectedIndex + 1,
    };

    drawRoute(selectedDayData, map);
    generateRouteTable(selectedDayData);
  });
}


      /* === Строим маршрут и таблицу === */
      if (routeData?.routes?.length) {
        window._routeData = routeData;

        drawRoute(routeData, map);
        generateRouteTable(routeData);

        if (tableBlock) tableBlock.classList.remove("d-none");

        formMessage.classList.remove("d-none", "text-danger");
        formMessage.classList.add("text-success");
        formMessage.textContent = "✅ Маршрут успешно построен!";
      } else {
        throw new Error("Сервер вернул пустой маршрут");
      }
    } catch (err) {
      console.error("❌ Ошибка при построении маршрута:", err);
      formMessage.classList.remove("d-none", "text-success");
      formMessage.classList.add("text-danger");
      formMessage.textContent = `❌ ${err.message || "Ошибка при построении маршрута"}`;
      if (tableBlock) tableBlock.classList.add("d-none");
    }
  });
}
