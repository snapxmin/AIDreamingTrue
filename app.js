(async function init() {
  const [events, competitors, skillChanges, skillsMeta, mcpChanges, mcpsMeta, llmChanges, llmsMeta] = await Promise.all([
    loadEvents(),
    loadCompetitors(),
    loadJson("./data/skill-changes.json"),
    loadJson("./data/skills.json"),
    loadJson("./data/mcp-changes.json"),
    loadJson("./data/mcps.json"),
    loadJson("./data/llm-changes.json"),
    loadJson("./data/llms.json")
  ]);

  const ui = {
    list: document.getElementById("eventList"),
    detail: document.getElementById("eventDetail"),
    count: document.getElementById("resultCount"),
    trend: document.getElementById("trendList"),
    companyTags: document.getElementById("companyTags"),
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

  const topCompanies = buildTopCompanies(competitors);

  hydrateSelect(ui.category, events.map((e) => e.category));
  hydrateSelect(ui.topic, events.map((e) => e.topic));
  hydrateSelect(ui.company, events.map((e) => e.company));
  renderCompanyTags(topCompanies, ui);
  renderSkillRadar(skillChanges, skillsMeta);
  renderMcpRadar(mcpChanges, mcpsMeta);
  renderLlmRadar(llmChanges, llmsMeta);

  const onChange = () => {
    syncCompanyTags(ui);
    render();
  };

  ui.companyTags.addEventListener("click", (event) => {
    const tag = event.target.closest(".company-tag");
    if (!tag) return;
    ui.company.value = tag.dataset.company;
    onChange();
  });

  [ui.search, ui.time, ui.category, ui.topic, ui.company].forEach((el) => {
    el.addEventListener("input", onChange);
    el.addEventListener("change", onChange);
  });
  ui.heat.addEventListener("input", () => {
    ui.heatValue.textContent = ui.heat.value;
    onChange();
  });
  ui.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      ui.tabs.forEach((it) => it.classList.remove("active"));
      tab.classList.add("active");
      state.view = tab.dataset.view;
      onChange();
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
      state.selectedId = null;
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
    const relatedSkills = (event.relatedSkills || [])
      .map(
        (s) =>
          `<li><a href="./skills.html#${encodeURIComponent(s.slug)}">${escapeHtml(s.displayName || s.slug)}</a> (${escapeHtml(s.ecosystem)})</li>`
      )
      .join("");
    ui.detail.innerHTML = `
      <h3>${escapeHtml(event.title)}</h3>
      <p>${escapeHtml(event.summary)}</p>
      <p><strong>影响分析：</strong>${escapeHtml(event.impact)}</p>
      <p><strong>为什么重要：</strong>${escapeHtml(event.whyImportant)}</p>
      ${relatedSkills ? `<p><strong>相关 Skill：</strong></p><ul>${relatedSkills}</ul>` : ""}
      <p><strong>来源：</strong><a href="${escapeHtml(event.sourceUrl)}" target="_blank" rel="noreferrer">${escapeHtml(event.sourceUrl)}</a></p>
      <p><strong>来源分级：</strong><span class="badge ${event.sourceTier.toLowerCase()}">${escapeHtml(event.sourceTier)}</span></p>
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

const EVENT_COMPANY_BY_COMPETITOR = {
  cursor: "Cursor",
  "github-copilot": "GitHub",
  "devin-desktop": "Cognition",
  "claude-code": "Anthropic",
  replit: "Replit",
  "google-jules": "Google",
  kiro: "AWS"
};

function renderSkillRadar(skillChanges, skillsMeta) {
  const container = document.getElementById("skillRadarList");
  const section = document.getElementById("skillRadarHome");
  if (!container || !section) return;

  const changes = (skillChanges.changes || []).slice(0, 6);
  const meta = skillsMeta.meta || {};

  if (!changes.length && !meta.indexTotalCount) {
    section.hidden = true;
    return;
  }

  const summary = document.createElement("p");
  summary.className = "skill-radar-summary";
  summary.textContent = `全量索引 ${meta.indexTotalCount || "—"} 个 · 本周新增 ${meta.newCount || 0} · 近期变更 ${meta.changesCount || 0}`;
  section.insertBefore(summary, container);

  if (!changes.length) {
    container.innerHTML = "<li>暂无变更记录（首次运行已建立基线快照）。</li>";
    return;
  }

  container.innerHTML = changes
    .map((c) => {
      const label = c.type === "added" ? "新增" : "更新";
      return `<li><strong>[${label}]</strong> <a href="./skills.html#${encodeURIComponent(c.slug)}">${escapeHtml(c.displayName || c.slug)}</a> — ${escapeHtml(c.summary || "")}</li>`;
    })
    .join("");
}

function renderMcpRadar(mcpChanges, mcpsMeta) {
  const container = document.getElementById("mcpRadarList");
  const section = document.getElementById("mcpRadarHome");
  if (!container || !section) return;

  const changes = (mcpChanges.changes || []).slice(0, 6);
  const meta = mcpsMeta.meta || {};

  if (!changes.length && !meta.indexTotalCount) {
    section.hidden = true;
    return;
  }

  const summary = document.createElement("p");
  summary.className = "skill-radar-summary";
  summary.textContent = `全量索引 ${meta.indexTotalCount || "—"} 个 · 本周新增 ${meta.newCount || 0} · 近期变更 ${meta.changesCount || 0}`;
  section.insertBefore(summary, container);

  if (!changes.length) {
    container.innerHTML = "<li>暂无变更记录（首次运行已建立基线快照）。</li>";
    return;
  }

  container.innerHTML = changes
    .map((c) => {
      const label = c.type === "added" ? "新增" : "更新";
      return `<li><strong>[${label}]</strong> <a href="./mcp.html#${encodeURIComponent(c.slug)}">${escapeHtml(c.displayName || c.slug)}</a> — ${escapeHtml(c.summary || "")}</li>`;
    })
    .join("");
}

function renderLlmRadar(llmChanges, llmsMeta) {
  const container = document.getElementById("llmRadarList");
  const section = document.getElementById("llmRadarHome");
  if (!container || !section) return;

  const changes = (llmChanges.changes || []).slice(0, 6);
  const meta = llmsMeta.meta || {};
  const topLlms = (llmsMeta.llms || []).slice(0, 3);

  if (!meta.totalCount && !topLlms.length) {
    section.hidden = true;
    return;
  }

  const summary = document.createElement("p");
  summary.className = "skill-radar-summary";
  summary.textContent = `SOTA 精选 ${meta.totalCount || "—"} 个 · 全量索引 ${meta.indexTotalCount || "—"} · 本周新增 ${meta.newCount || 0}`;
  section.insertBefore(summary, container);

  if (changes.length) {
    container.innerHTML = changes
      .map((c) => {
        const label = c.type === "added" ? "新增" : "更新";
        return `<li><strong>[${label}]</strong> <a href="./llm.html#${encodeURIComponent(c.slug)}">${escapeHtml(c.displayName || c.slug)}</a> — ${escapeHtml(c.summary || "")}</li>`;
      })
      .join("");
    return;
  }

  container.innerHTML = topLlms
    .map((l) => {
      const swe = (l.benchmarks?.automated || []).find((b) => b.name.includes("SWE-bench"));
      const sweLabel = swe ? `SWE-bench ${swe.score}%` : "";
      const sentiment = l.sentiment ? `口碑 ${l.sentiment.score}/${l.sentiment.maxScore}` : "";
      const metrics = [sweLabel, sentiment].filter(Boolean).join(" · ");
      return `<li><strong>#${l.rank}</strong> <a href="./llm.html#${encodeURIComponent(l.slug)}">${escapeHtml(l.displayName)}</a>${metrics ? ` — ${escapeHtml(metrics)}` : ""}</li>`;
    })
    .join("");
}

async function loadJson(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) return {};
    return await response.json();
  } catch {
    return {};
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildTopCompanies(competitors) {
  return competitors.map((competitor) => ({
    id: competitor.id,
    label: competitor.name,
    eventCompany: EVENT_COMPANY_BY_COMPETITOR[competitor.id] || competitor.company
  }));
}

function renderCompanyTags(topCompanies, ui) {
  ui.companyTags.innerHTML = "";

  const allTag = document.createElement("button");
  allTag.type = "button";
  allTag.className = "company-tag active";
  allTag.dataset.company = "all";
  allTag.textContent = "全部";
  ui.companyTags.appendChild(allTag);

  topCompanies.forEach((company) => {
    const tag = document.createElement("button");
    tag.type = "button";
    tag.className = "company-tag";
    tag.dataset.company = company.eventCompany;
    tag.textContent = company.label;
    tag.title = `筛选 ${company.label} 相关动态`;
    ui.companyTags.appendChild(tag);
  });
}

function syncCompanyTags(ui) {
  const activeCompany = ui.company.value;
  Array.from(ui.companyTags.querySelectorAll(".company-tag")).forEach((tag) => {
    const isAll = tag.dataset.company === "all" && activeCompany === "all";
    const isMatch = tag.dataset.company === activeCompany;
    tag.classList.toggle("active", isAll || isMatch);
  });
}

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

async function loadCompetitors() {
  const fallback = [
    { id: "cursor", name: "Cursor", company: "Anysphere" },
    { id: "github-copilot", name: "GitHub Copilot", company: "GitHub / Microsoft" },
    { id: "devin-desktop", name: "Devin Desktop", company: "Cognition" },
    { id: "claude-code", name: "Claude Code", company: "Anthropic" },
    { id: "replit", name: "Replit Agent", company: "Replit" },
    { id: "google-jules", name: "Jules", company: "Google" },
    { id: "kiro", name: "Kiro", company: "AWS" }
  ];

  try {
    const response = await fetch("./data/competitors.json");
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
