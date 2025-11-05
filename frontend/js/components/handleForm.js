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

  /* === Функция для отображения данных файла в таблице === */
  function displayFileData(addresses) {
    console.log("📋 displayFileData вызвана с адресами:", addresses);
    const tableBody = document.querySelector("#routeTable tbody");
    if (!tableBody) {
      console.error("❌ Таблица #routeTable tbody не найдена!");
      return;
    }

    tableBody.innerHTML = ""; // очистка

    if (!addresses || addresses.length === 0) {
      console.warn("⚠️ Нет адресов для отображения");
      tableBody.innerHTML = `<tr><td colspan="3" class="text-muted">Нет данных для отображения</td></tr>`;
      return;
    }

    console.log(`📊 Отображаем ${addresses.length} адресов в таблице`);
    addresses.forEach((addr, index) => {
      const row = document.createElement("tr");
      const type = addr.type || (addr.client_level && addr.client_level.toLowerCase() === "vip" ? "VIP" : "Стандарт");
      // Используем адрес из БД без изменений (приоритет: address1 > address)
      // Это гарантирует сохранение оригинальных почтовых индексов из файла
      const addressText = addr.address1 || addr.address || "Адрес не указан";
      
      row.innerHTML = `
        <td>${addressText}</td>
        <td>${type}</td>
        <td>
          <input type="checkbox" class="form-check-input visit-checkbox" data-index="${index}">
        </td>
      `;

      tableBody.appendChild(row);
    });

    // Показываем таблицу
    if (tableBlock) {
      tableBlock.classList.remove("d-none");
      tableBlock.style.display = "block"; // Принудительно показываем
      console.log("✅ Таблица отображена");
      console.log("📊 Элемент .table-block найден и показан");
    } else {
      console.error("❌ Элемент .table-block не найден!");
      // Пробуем найти таблицу напрямую
      const table = document.querySelector("#routeTable");
      if (table) {
        console.log("✅ Таблица #routeTable найдена напрямую");
        const parent = table.closest(".table-block");
        if (parent) {
          parent.classList.remove("d-none");
          parent.style.display = "block";
          console.log("✅ Родительский элемент .table-block найден и показан");
        }
      }
    }
  }

  /* === Отправка формы === */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    console.log("🚀 === НАЧАЛО ОТПРАВКИ ФОРМЫ ===");
    console.log("📋 Статус кнопки:", submitBtn.disabled);
    console.log("📁 Файл выбран:", fileInput.files.length > 0 ? fileInput.files[0].name : "НЕТ");
    console.log("📍 Адрес:", manualAddress.value);
    console.log("📅 Период:", periodSelect.value);

    if (submitBtn.disabled) {
      console.warn("⚠️ Кнопка заблокирована - форма не отправляется");
      formMessage.classList.remove("d-none", "text-success");
      formMessage.classList.add("text-danger");
      formMessage.textContent = "⚠️ Заполните все обязательные поля перед отправкой.";
      return;
    }

    if (!fileInput.files || fileInput.files.length === 0) {
      console.error("❌ Файл не выбран!");
      formMessage.classList.remove("d-none", "text-success");
      formMessage.classList.add("text-danger");
      formMessage.textContent = "⚠️ Выберите файл для загрузки.";
      return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("address", manualAddress.value || "");
    formData.append("period", periodSelect.value || "");

    if (window._userGeo) {
      formData.append("lat", window._userGeo.lat);
      formData.append("lon", window._userGeo.lon);
    }

    console.log("📦 Подготовка данных для отправки:");
    console.log("  - Файл:", fileInput.files[0].name, "размер:", fileInput.files[0].size, "байт");
    console.log("  - Адрес:", manualAddress.value);
    console.log("  - Период:", periodSelect.value);
    console.log("  - Координаты:", window._userGeo || "не указаны");

    try {
      // Базовый URL для API запросов
      const API_BASE_URL = window.location.origin; // http://localhost:8000
      const uploadUrl = `${API_BASE_URL}/api/upload`;
      
      console.log("🌐 Отправка запроса на:", uploadUrl);
      
      /* === Шаг 1. POST — отправляем данные на сервер === */
      const uploadResponse = await fetch(uploadUrl, {
        method: "POST",
        body: formData,
      });
      
      console.log("📡 Ответ сервера получен:", uploadResponse.status, uploadResponse.statusText);

      if (!uploadResponse.ok) {
        const errorText = await uploadResponse.text();
        throw new Error(`Ошибка загрузки файла: HTTP ${uploadResponse.status} - ${errorText}`);
      }

      const uploadResult = await uploadResponse.json();
      console.log("✅ Сервер принял данные:", uploadResult);
      console.log("📦 Количество адресов в ответе:", uploadResult.created_addresses?.length || 0);
      console.log("📋 Полная структура ответа:", JSON.stringify(uploadResult, null, 2));

      /* === Отображаем данные файла сразу после загрузки === */
      // НЕ отображаем данные сразу, ждем построения маршрута
      // Это предотвратит дублирование данных
      if (uploadResult.created_addresses && uploadResult.created_addresses.length > 0) {
        console.log(`📊 Загружено ${uploadResult.created_addresses.length} адресов`);
        console.log("📋 Первые 3 адреса:", uploadResult.created_addresses.slice(0, 3));
        
        // Показываем сообщение об успехе
        formMessage.classList.remove("d-none", "text-danger");
        formMessage.classList.add("text-success");
        formMessage.textContent = `✅ Файл загружен! Обработано записей: ${uploadResult.records_processed || 0}`;
      } else {
        console.warn("⚠️ Нет данных для отображения:", uploadResult);
        console.warn("📋 Полный ответ сервера:", JSON.stringify(uploadResult, null, 2));
        formMessage.classList.remove("d-none", "text-success");
        formMessage.classList.add("text-danger");
        formMessage.textContent = `⚠️ Файл загружен, но данных не найдено. Обработано записей: ${uploadResult.records_processed || 0}, ошибок: ${uploadResult.errors_count || 0}`;
      }

      /* === Шаг 2. GET — получаем готовый маршрут (опционально) === */
      // Пытаемся получить маршрут, но не прерываем выполнение при ошибке
      let routeData = null;
      try {
        const params = new URLSearchParams();
        if (manualAddress.value) params.append("address", manualAddress.value);
        if (periodSelect.value) params.append("period", periodSelect.value);
        if (window._userGeo) {
          params.append("lat", window._userGeo.lat);
          params.append("lon", window._userGeo.lon);
        }

        const routeResponse = await fetch(`${API_BASE_URL}/api/route?${params.toString()}`, {
          method: "GET",
          headers: {
            "Accept": "application/json",
          },
        });

        if (routeResponse.ok) {
          routeData = await routeResponse.json();
          console.log("📍 Получен маршрут:", routeData);
        } else {
          const errorText = await routeResponse.text();
          console.warn(`⚠️ Не удалось получить маршрут: HTTP ${routeResponse.status} - ${errorText}`);
          // Не выбрасываем ошибку, продолжаем работу
        }
      } catch (routeErr) {
        console.warn("⚠️ Ошибка при получении маршрута (продолжаем работу):", routeErr);
        // Не выбрасываем ошибку, продолжаем работу
      }

      // === Заполняем selectDay динамически ===
      if (routeData && routeData.routes && routeData.routes.length > 0) {
        const selectDay = document.getElementById("selectDay");
        if (selectDay) {
          // Очистим перед добавлением
          selectDay.innerHTML = `<option selected disabled>Выбрать день</option>`;

          routeData.routes.forEach((route, idx) => {
            const opt = document.createElement("option");
            opt.value = idx;
            opt.textContent = `День ${route.day || idx + 1}`;
            selectDay.appendChild(opt);
          });

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

          // Активируем первый день (после добавления обработчика)
          selectDay.selectedIndex = 1;
          // НЕ вызываем событие change, чтобы не вызывать generateRouteTable дважды
        }

        /* === Строим маршрут === */
        window._routeData = routeData;
        drawRoute(routeData, map);

        /* === Отображаем таблицу адресов ИЗ БАЗЫ ДАННЫХ, а не из маршрута === */
        // Используем данные из uploadResult.created_addresses, которые пришли из БД
        // Это гарантирует, что отображаются ТОЛЬКО адреса из таблицы addresses
        if (uploadResult.created_addresses && uploadResult.created_addresses.length > 0) {
          console.log("📋 Отображаем адреса из БД (не из маршрута):", uploadResult.created_addresses.length);
          displayFileData(uploadResult.created_addresses);
        } else {
          // Если нет данных из upload, используем данные из маршрута (fallback)
          console.warn("⚠️ Нет данных из upload, используем данные из маршрута");
          generateRouteTable(routeData);
        }

        if (tableBlock) tableBlock.classList.remove("d-none");

        formMessage.classList.remove("d-none", "text-danger");
        formMessage.classList.add("text-success");
        formMessage.textContent = "✅ Маршрут успешно построен!";
      } else {
        // Маршрут не получен, отображаем данные из файла напрямую
        console.log("ℹ️ Маршрут не построен, отображаем данные из файла");
        if (uploadResult.created_addresses && uploadResult.created_addresses.length > 0) {
          displayFileData(uploadResult.created_addresses);
        }
      }
    } catch (err) {
      console.error("❌ === ОШИБКА ПРИ ПОСТРОЕНИИ МАРШРУТА ===");
      console.error("❌ Сообщение:", err.message);
      console.error("❌ Тип ошибки:", err.name);
      console.error("❌ Стек ошибки:", err.stack);
      
      formMessage.classList.remove("d-none", "text-success");
      formMessage.classList.add("text-danger");
      formMessage.textContent = `❌ ${err.message || "Ошибка при построении маршрута"}`;
      if (tableBlock) tableBlock.classList.add("d-none");
      
      // Показываем детали ошибки в консоли
      console.error("📋 Полные детали ошибки:", {
        message: err.message,
        stack: err.stack,
        name: err.name,
        cause: err.cause
      });
    } finally {
      console.log("🏁 === ЗАВЕРШЕНИЕ ОТПРАВКИ ФОРМЫ ===");
    }
  });
}
