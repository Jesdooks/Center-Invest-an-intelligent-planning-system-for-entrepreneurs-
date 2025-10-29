export default function initExportButton() {
  const exportBtn = document.getElementById("getExportFile");
  if (!exportBtn) {
    console.warn("⚠️ Кнопка экспорта не найдена на странице");
    return;
  }

  exportBtn.addEventListener("click", () => {
    const exportData = [];

    // собираем все сохранённые отметки
    for (const key in localStorage) {
      if (key.startsWith("visited_points_")) {
        const day = key.replace("visited_points_", "");
        const visits = JSON.parse(localStorage.getItem(key) || "{}");
        exportData.push({ day, visits });
      }
    }

    if (!exportData.length) {
      alert("Нет данных для экспорта. Отметьте посещённые точки в таблице.");
      return;
    }

    // сортировка по дню (чтобы шли 1, 2, 3...)
    exportData.sort((a, b) => Number(a.day) - Number(b.day));

    // сохраняем для передачи в export.html
    window._exportData = exportData;

    // открываем страницу отчёта
    const win = window.open("export.html", "_blank");
    if (!win) alert("Разрешите всплывающие окна для экспорта.");
  });
}
