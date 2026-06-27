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
      title: "Cursor 推出团队级 Agent 协作能力",
      date: "2026-06-20",
      category: "产品",
      topic: "Agent",
      company: "Cursor",
      heat: 92,
      growth: 18,
      sourceTier: "A",
      summary: "新增多 Agent 协同与任务看板，提升团队级开发流程效率。",
      whyImportant: "标志 AI Coding 从个人工具向团队生产系统演进。",
      impact: "企业团队在需求拆解、评审和交付上可获得更高吞吐。",
      sourceUrl: "https://example.com/cursor-agent-release"
    },
    {
      id: "evt-002",
      title: "某 AI Coding 初创公司完成新一轮融资",
      date: "2026-06-10",
      category: "投融资",
      topic: "IDE",
      company: "CodeWave",
      heat: 80,
      growth: 22,
      sourceTier: "B",
      summary: "融资将用于构建企业安全合规能力与私有化部署。",
      whyImportant: "资本流向反映企业级 AI Coding 需求持续增长。",
      impact: "推动行业从通用 Copilot 向垂直场景解决方案细分。",
      sourceUrl: "https://example.com/codewave-funding"
    },
    {
      id: "evt-003",
      title: "大型电商技术团队发布 AI 代码评审实践",
      date: "2026-06-24",
      category: "用户故事",
      topic: "代码评审",
      company: "ShopScale",
      heat: 88,
      growth: 15,
      sourceTier: "A",
      summary: "通过 AI 预审减少人工 review 负担，并保持缺陷检出率。",
      whyImportant: "提供了可复用的组织落地样板。",
      impact: "研发管理者可借鉴指标体系推进规模化实施。",
      sourceUrl: "https://example.com/shopsale-review-story"
    },
    {
      id: "evt-004",
      title: "GitHub 生态新增自动化测试 Agent 模板",
      date: "2026-05-29",
      category: "工具生态",
      topic: "自动化测试",
      company: "GitHub",
      heat: 75,
      growth: 12,
      sourceTier: "A",
      summary: "开源模板可直接接入 CI，自动生成与维护测试用例。",
      whyImportant: "降低 AI Coding 在测试环节的接入门槛。",
      impact: "中小团队可更快构建端到端自动化质量流程。",
      sourceUrl: "https://example.com/github-test-agent-template"
    },
    {
      id: "evt-005",
      title: "SaaS 厂商公布 AI Coding 商业化数据",
      date: "2026-06-26",
      category: "商业",
      topic: "IDE",
      company: "DevFlux",
      heat: 84,
      growth: 25,
      sourceTier: "B",
      summary: "企业付费渗透与续费率提升，订阅收入持续增长。",
      whyImportant: "验证 AI Coding 具备可持续商业模式。",
      impact: "有助于判断市场成熟度和竞争格局演化速度。",
      sourceUrl: "https://example.com/devflux-business-update"
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
