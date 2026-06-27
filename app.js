(async function init() {
  const response = await fetch("./data/events.json");
  const events = await response.json();

  const ui = {
    list: document.getElementById("eventList"),
    detail: document.getElementById("eventDetail"),
    count: document.getElementById("resultCount"),
    trend: document.getElementById("trendList"),
    search: document.getElementById("searchInput"),
    time: document.getElementById("timeWindow"),
    category: document.getElementById("categoryFilter"),
    topic: document.getElementById("topicFilter"),
    company: document.getElementById("companyFilter"),
    heat: document.getElementById("heatFilter"),
    heatValue: document.getElementById("heatValue"),
    tabs: Array.from(document.querySelectorAll(".tab"))
  };

  const state = {
    selectedId: null,
    view: "all"
  };

  hydrateSelect(ui.category, events.map((e) => e.category));
  hydrateSelect(ui.topic, events.map((e) => e.topic));
  hydrateSelect(ui.company, events.map((e) => e.company));

  const onChange = () => render();
  [ui.search, ui.time, ui.category, ui.topic, ui.company].forEach((el) => {
    el.addEventListener("input", onChange);
    el.addEventListener("change", onChange);
  });
  ui.heat.addEventListener("input", () => {
    ui.heatValue.textContent = ui.heat.value;
    render();
  });
  ui.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      ui.tabs.forEach((it) => it.classList.remove("active"));
      tab.classList.add("active");
      state.view = tab.dataset.view;
      render();
    });
  });

  function render() {
    const filtered = applyFilters(events, ui, state.view);
    ui.count.textContent = `${filtered.length} 条`;
    renderList(filtered);
    renderTrend(filtered);
    const selected = filtered.find((e) => e.id === state.selectedId) || filtered[0];
    if (selected) {
      state.selectedId = selected.id;
      renderDetail(selected);
      markActive(selected.id);
    } else {
      ui.detail.innerHTML = "<p>暂无符合条件的数据。</p>";
    }
  }

  function renderList(items) {
    ui.list.innerHTML = "";
    items
      .sort((a, b) => new Date(b.date) - new Date(a.date))
      .forEach((event) => {
        const li = document.createElement("li");
        li.className = "event-item";
        li.dataset.id = event.id;
        li.innerHTML = `
          <strong>${event.title}</strong>
          <div class="meta">
            <span>${event.date}</span>
            <span>${event.category}</span>
            <span>${event.topic}</span>
            <span>${event.company}</span>
            <span>热度 ${event.heat}</span>
          </div>
          <p>${event.summary}</p>
        `;
        li.addEventListener("click", () => {
          state.selectedId = event.id;
          renderDetail(event);
          markActive(event.id);
        });
        ui.list.appendChild(li);
      });
  }

  function renderDetail(event) {
    ui.detail.innerHTML = `
      <h3>${event.title}</h3>
      <p>${event.summary}</p>
      <p><strong>影响分析：</strong>${event.impact}</p>
      <p><strong>为什么重要：</strong>${event.whyImportant}</p>
      <p><strong>来源：</strong><a href="${event.sourceUrl}" target="_blank" rel="noreferrer">${event.sourceUrl}</a></p>
      <p><strong>来源分级：</strong><span class="badge ${event.sourceTier.toLowerCase()}">${event.sourceTier}</span></p>
      <p><strong>版本记录：</strong>v1.0（初次收录）</p>
    `;
  }

  function renderTrend(items) {
    ui.trend.innerHTML = "";
    items
      .slice()
      .sort((a, b) => b.heat + b.growth - (a.heat + a.growth))
      .slice(0, 5)
      .forEach((event) => {
        const li = document.createElement("li");
        li.textContent = `${event.title}（热度 ${event.heat} / 增长 ${event.growth}）`;
        ui.trend.appendChild(li);
      });
  }

  function markActive(id) {
    Array.from(ui.list.querySelectorAll(".event-item")).forEach((el) => {
      el.classList.toggle("active", el.dataset.id === id);
    });
  }

  render();
})();

function applyFilters(events, ui, view) {
  const search = ui.search.value.trim().toLowerCase();
  const timeWindow = ui.time.value;
  const category = ui.category.value;
  const topic = ui.topic.value;
  const company = ui.company.value;
  const minHeat = Number(ui.heat.value);

  const now = new Date();
  return events.filter((event) => {
    if (view === "today" && !isWithinDays(event.date, 1, now)) return false;
    if (view === "week" && !isWithinDays(event.date, 7, now)) return false;
    if (timeWindow !== "all" && !isWithinDays(event.date, Number(timeWindow), now)) return false;
    if (category !== "all" && event.category !== category) return false;
    if (topic !== "all" && event.topic !== topic) return false;
    if (company !== "all" && event.company !== company) return false;
    if (event.heat < minHeat) return false;
    if (!search) return true;

    const haystack = [event.title, event.summary, event.company, event.topic, event.category].join(" ").toLowerCase();
    return haystack.includes(search);
  });
}

function isWithinDays(dateString, days, now) {
  const date = new Date(dateString);
  const diff = now - date;
  return diff >= 0 && diff <= days * 24 * 60 * 60 * 1000;
}

function hydrateSelect(select, values) {
  Array.from(new Set(values))
    .sort((a, b) => a.localeCompare(b, "zh-CN"))
    .forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
}
