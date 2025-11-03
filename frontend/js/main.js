import getAPI from "./components/getApi.js";
import getSearchPosition from "./components/getSearchPosition.js";
import drawRoute from "./components/drawLine.js";
import handleForm from "./components/handleForm.js";
import generateRouteTable from "./components/generateRouteTable.js";
import initExportButton from "./components/exportReport.js";
// import initAuth from "./components/auth.js";


const searchInput = document.getElementById("manualAddress");
const fileInput = document.getElementById("fileInput");
const filePlaceholder = document.getElementById("filePlaceholder");
const fileInfo = document.getElementById("fileInfo");
const fileName = document.getElementById("fileName");
const removeFileBtn = document.getElementById("removeFileBtn");

fileInput.addEventListener("change", function () {
  if (this.files && this.files.length > 0) {
    fileName.textContent = `Файл: ${this.files[0].name}`;
    fileName.classList.add("col-6");
    removeFileBtn.classList.add("col-6");
    filePlaceholder.classList.add("d-none");
    fileInfo.classList.remove("d-none");
    fileInfo.classList.add("d-flex");
  }
});

removeFileBtn.addEventListener("click", function () {
  // сбрасываем input
  fileInput.value = "";

  // возвращаем интерфейс в исходное состояние
  filePlaceholder.classList.remove("d-none");
  fileInfo.classList.add("d-none");
});

// === Инициализация карты TomTom ===

document.addEventListener("DOMContentLoaded", () => {

  // Проверяем, подгружен ли TomTom SDK
  if (typeof tt === "undefined") {
    console.error(
      "TomTom SDK не найден. Проверь порядок подключения скриптов."
    );
    return;
  }

  const map = tt.map({
    key: getAPI(),
    container: "map",
    style: "tomtom://vector/1/basic-main",
    center: [39.7203, 47.2357], // Ростов-на-Дону
    zoom: 12,
  });

  searchInput.addEventListener("change", () => getSearchPosition(map));

  map.addControl(new tt.NavigationControl());

  handleForm(map); // 👈 запуск логики формы
  initExportButton();
  // initAuth(); // 👈 инициализация авторизации
});

const geoBtn = document.getElementById("getGeo");
const geoError = document.getElementById("geoError");
const manualAddress = document.getElementById("manualAddress");

geoBtn.addEventListener("click", () => {
  if ("geolocation" in navigator) {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        window._userGeo = {
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        };
        document.dispatchEvent(new Event("geoUpdated"));
        geoError.classList.add("d-none");
        manualAddress.value = `lat: ${position.coords.latitude}, lon: ${position.coords.longitude}`;
      },
      (error) => {
        console.error(error);
        geoError.classList.remove("d-none"); // показать ошибку
        manualAddress.removeAttribute("disabled"); // разрешить ввод вручную
      }
    );
  } else {
    geoError.classList.remove("d-none");
    manualAddress.removeAttribute("disabled");
  }
});

// === Бургер для мобильной версии ===
const burgerBtn = document.getElementById("burgerBtn");
const leftPanel = document.querySelector(".col-lg-3");
const burgerIcon = document.getElementById("burgerIcon");

burgerBtn.addEventListener("click", () => {
  const isHidden = leftPanel.classList.contains("d-none");

  if (isHidden) {
    leftPanel.classList.remove("d-none");
    burgerIcon.textContent = "✕"; // ← заглушка под твою иконку "закрыть"
    burgerBtn.style.backgroundColor = "#FF6B6B";
    burgerBtn.style.color = "#fff";
  } else {
    leftPanel.classList.add("d-none");
    burgerIcon.textContent = "≡"; // ← заглушка под твою иконку "меню"
    burgerBtn.style.backgroundColor = "#00A86B";
    burgerBtn.style.color = "#fff";
  }
});
