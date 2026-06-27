(async function init() {
  const events = await loadEvents();

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

async function loadEvents() {
  const fallback = [
    {
      id: "evt-001",
      title: "SpaceX 宣布以 $600 亿全股票收购 Cursor 母公司 Anysphere",
      date: "2026-06-16",
      category: "投融资",
      topic: "IDE",
      company: "Cursor",
      heat: 98,
      growth: 30,
      sourceTier: "A",
      summary: "SpaceX 与 Anysphere 签署合并协议，以 $600 亿全股票交易收购 Cursor 开发商。",
      whyImportant: "创风投支持初创公司被收购纪录，标志 AI Coding 成为巨头战略必争之地。",
      impact: "Cursor 将作为 SpaceX 全资子公司独立运营，行业竞争格局将加速整合。",
      sourceUrl: "https://techcrunch.com/2025/06/05/cursors-anysphere-nabs-9-9b-valuation-soars-past-500m-arr/"
    },
    {
      id: "evt-002",
      title: "Cursor 3.9 发布：统一 Customize 页面管理插件、Skills 与 MCP",
      date: "2026-06-22",
      category: "产品",
      topic: "Agent",
      company: "Cursor",
      heat: 90,
      growth: 16,
      sourceTier: "A",
      summary: "新增 Customize 页面，统一管理 plugins、skills、MCPs、subagents 与团队市场。",
      whyImportant: "将分散的扩展生态整合为统一入口，降低企业团队插件分发门槛。",
      impact: "团队管理员可一键导入 GitLab/Azure DevOps 组织的内部插件仓库。",
      sourceUrl: "https://cursor.com/changelog"
    },
    {
      id: "evt-005",
      title: "Cognition 完成超 $10 亿融资，估值达 $260 亿",
      date: "2026-05-27",
      category: "投融资",
      topic: "Agent",
      company: "Cognition",
      heat: 95,
      growth: 28,
      sourceTier: "A",
      summary: "Devin 开发商 Cognition 获超 $10 亿融资，估值 $260 亿，ARR 达 $4.92 亿。",
      whyImportant: "8 个月内估值从 $102 亿跃升至 $260 亿，企业客户含奔驰、NASA、高盛。",
      impact: "资本验证自主 Agent 赛道独立生存空间。",
      sourceUrl: "https://techcrunch.com/2026/05/27/ai-coding-startup-cognition-raises-1b-at-25b-pre-money-valuation/"
    }
  ];

  try {
    const response = await fetch("./data/events.json");
    if (!response.ok) return fallback;
    return await response.json();
  } catch (error) {
    return fallback;
  }
}

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
