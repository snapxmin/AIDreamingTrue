(async function init() {
  const [events, competitors, milestones] = await Promise.all([
    loadEvents(),
    loadCompetitors(),
    loadMilestones()
  ]);
  const evolutionByCompetitor = buildEvolutionMap(events, milestones, competitors);

  const ui = {
    tabs: document.getElementById("competitorTabs"),
    intro: document.getElementById("competitorIntro"),
    timeline: document.getElementById("timeline"),
    count: document.getElementById("milestoneCount"),
    empty: document.getElementById("emptyTimeline"),
    modal: document.getElementById("detailModal"),
    modalDetail: document.getElementById("modalDetail")
  };

  const state = {
    activeId: resolveInitialCompetitor(competitors)
  };

  renderTabs(competitors, state, ui, () => renderCompetitor(state, ui, evolutionByCompetitor, competitors));
  bindModal(ui);
  renderCompetitor(state, ui, evolutionByCompetitor, competitors);

  window.addEventListener("hashchange", () => {
    const nextId = resolveInitialCompetitor(competitors);
    if (nextId !== state.activeId) {
      state.activeId = nextId;
      renderTabs(competitors, state, ui, () => renderCompetitor(state, ui, evolutionByCompetitor, competitors));
      renderCompetitor(state, ui, evolutionByCompetitor, competitors);
    }
  });
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

const EVOLUTION_CATEGORIES = new Set(["产品", "工具生态", "商业", "投融资"]);

function buildEvolutionMap(events, milestones, competitors) {
  const liveMilestones = events
    .filter(isKeyEvolutionEvent)
    .map((event) => eventToMilestone(event, competitors));

  const merged = dedupeMilestones([...milestones, ...liveMilestones]);
  const map = new Map();

  competitors.forEach((competitor) => {
    const items = merged
      .filter((item) => item.competitorId === competitor.id)
      .sort((a, b) => parseDate(b.date) - parseDate(a.date));
    map.set(competitor.id, items);
  });

  return map;
}

function eventToMilestone(event, competitors) {
  const competitor = competitors.find((item) => {
    const eventCompany = EVENT_COMPANY_BY_COMPETITOR[item.id] || item.company;
    return event.company === eventCompany;
  });

  return {
    id: event.id,
    competitorId: competitor?.id || "unknown",
    date: event.date,
    category: event.category,
    topic: event.topic,
    title: event.title,
    summary: event.summary,
    whyImportant: event.whyImportant,
    impact: event.impact,
    sourceUrl: event.sourceUrl,
    sourceTier: event.sourceTier,
    heat: event.heat,
    growth: event.growth,
    live: true
  };
}

function isKeyEvolutionEvent(event) {
  if (!EVOLUTION_CATEGORIES.has(event.category)) return false;
  if (event.id.startsWith("auto-") && event.heat < 70) return false;
  return true;
}

function dedupeMilestones(items) {
  const byKey = new Map();

  items.forEach((item) => {
    const key = `${item.competitorId}|${normalizeDate(item.date)}|${normalizeTitle(item.title)}`;
    const existing = byKey.get(key);
    if (!existing || preferMilestone(item, existing)) {
      byKey.set(key, item);
    }
  });

  return Array.from(byKey.values());
}

function preferMilestone(candidate, current) {
  if (candidate.live && !current.live) return true;
  if (!candidate.live && current.live) return false;
  if ((candidate.heat || 0) > (current.heat || 0)) return true;
  return candidate.id.startsWith("ms-") && !current.id.startsWith("ms-") ? false : true;
}

function normalizeTitle(title) {
  const versionMatch = title.match(/v?\d+\.\d+\.\d+/i);
  if (versionMatch) return versionMatch[0].toLowerCase();
  return title.slice(0, 48).toLowerCase();
}

function normalizeDate(date) {
  return date.slice(0, 7);
}

function parseDate(date) {
  const normalized = date.length === 4 ? `${date}-01-01` : date.length === 7 ? `${date}-01` : date;
  return new Date(normalized).getTime();
}

function formatYear(date) {
  return date.slice(0, 4);
}

function resolveInitialCompetitor(competitors) {
  const hash = window.location.hash.replace("#", "");
  if (hash && competitors.some((item) => item.id === hash)) return hash;
  return competitors[0]?.id || "";
}

function renderTabs(competitors, state, ui, onSelect) {
  ui.tabs.innerHTML = "";

  competitors.forEach((competitor) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "competitor-tab";
    tab.dataset.id = competitor.id;
    tab.textContent = competitor.name;
    tab.classList.toggle("active", competitor.id === state.activeId);
    tab.addEventListener("click", () => {
      state.activeId = competitor.id;
      window.location.hash = competitor.id;
      renderTabs(competitors, state, ui, onSelect);
      onSelect();
    });
    ui.tabs.appendChild(tab);
  });
}

function renderCompetitor(state, ui, evolutionByCompetitor, competitors) {
  const competitor = competitors.find((item) => item.id === state.activeId);
  if (!competitor) return;

  const milestones = evolutionByCompetitor.get(competitor.id) || [];
  renderIntro(competitor, milestones, ui.intro);
  renderTimeline(milestones, ui);
}

function renderIntro(competitor, milestones, container) {
  const sorted = milestones.slice().sort((a, b) => parseDate(a.date) - parseDate(b.date));
  const founded = sorted[0];
  const foundedLabel = founded ? formatDisplayDate(founded.date) : "未知";
  const spanYears = founded ? new Date().getFullYear() - Number(formatYear(founded.date)) : 0;
  const liveCount = milestones.filter((item) => item.live).length;
  const historyCount = milestones.length - liveCount;

  container.innerHTML = `
    <div class="intro-grid">
      <div>
        <h2>${competitor.name}</h2>
        <p class="intro-company">${competitor.company}</p>
      </div>
      <div class="intro-meta">
        <span class="intro-pill">${competitor.category}</span>
        <span class="intro-pill">${competitor.pricing || "定价未收录"}</span>
        <span class="intro-pill">诞生于 ${foundedLabel}</span>
        <span class="intro-pill">演进 ${spanYears > 0 ? `${spanYears}+ 年` : "进行中"}</span>
        <span class="intro-pill">${milestones.length} 个节点</span>
      </div>
    </div>
    <p class="intro-notes">${competitor.notes || ""}</p>
    <p class="intro-stats">完整历程：${historyCount} 个历史里程碑${liveCount > 0 ? ` + ${liveCount} 条最新动态` : ""}</p>
    <div class="intro-links">
      ${competitor.website ? `<a href="${competitor.website}" target="_blank" rel="noreferrer">产品官网</a>` : ""}
      ${competitor.changelogUrl ? `<a href="${competitor.changelogUrl}" target="_blank" rel="noreferrer">更新日志</a>` : ""}
    </div>
  `;
}

function formatDisplayDate(date) {
  if (date.length === 4) return `${date} 年`;
  if (date.length === 7) return date.replace("-", " 年 ") + " 月";
  return date;
}

function renderTimeline(milestones, ui) {
  ui.timeline.innerHTML = "";
  ui.count.textContent = `${milestones.length} 个节点 · 从诞生至今`;
  ui.empty.hidden = milestones.length > 0;
  ui.timeline.hidden = milestones.length === 0;

  let lastYear = null;

  milestones.forEach((milestone, index) => {
    const year = formatYear(milestone.date);
    if (year !== lastYear) {
      const divider = document.createElement("div");
      divider.className = "timeline-year";
      divider.textContent = `${year} 年`;
      ui.timeline.appendChild(divider);
      lastYear = year;
    }

    const node = document.createElement("button");
    node.type = "button";
    node.className = "timeline-node";
    node.dataset.id = milestone.id;
    node.setAttribute("role", "listitem");
    node.innerHTML = `
      <div class="timeline-axis">
        <span class="timeline-dot ${milestone.category === "诞生" ? "birth" : ""}" aria-hidden="true"></span>
        ${index < milestones.length - 1 ? '<span class="timeline-line" aria-hidden="true"></span>' : ""}
      </div>
      <div class="timeline-card ${milestone.live ? "live" : ""}">
        <div class="timeline-meta">
          <time datetime="${milestone.date}">${formatDisplayDate(milestone.date)}</time>
          <span class="badge category-${milestone.category}">${milestone.category}</span>
          <span class="badge topic">${milestone.topic}</span>
          ${milestone.live ? '<span class="badge live-tag">最新动态</span>' : ""}
          <span class="badge ${milestone.sourceTier.toLowerCase()}">${milestone.sourceTier} 级来源</span>
        </div>
        <h3>${milestone.title}</h3>
        <p>${truncate(milestone.summary, 140)}</p>
        <span class="timeline-cta">点击查看详情 →</span>
      </div>
    `;
    node.addEventListener("click", () => openDetail(milestone, ui));
    ui.timeline.appendChild(node);
  });
}

function openDetail(milestone, ui) {
  const heatBlock =
    milestone.heat != null
      ? `<span class="heat-tag">热度 ${milestone.heat}${milestone.growth != null ? ` · 增长 ${milestone.growth}` : ""}</span>`
      : "";

  ui.modalDetail.innerHTML = `
    <h2 id="modalTitle">${milestone.title}</h2>
    <div class="modal-meta">
      <time datetime="${milestone.date}">${formatDisplayDate(milestone.date)}</time>
      <span class="badge category-${milestone.category}">${milestone.category}</span>
      <span class="badge topic">${milestone.topic}</span>
      ${milestone.live ? '<span class="badge live-tag">最新动态</span>' : ""}
      <span class="badge ${milestone.sourceTier.toLowerCase()}">${milestone.sourceTier} 级来源</span>
      ${heatBlock}
    </div>
    <section>
      <h3>摘要</h3>
      <p>${milestone.summary}</p>
    </section>
    <section>
      <h3>为什么重要</h3>
      <p>${milestone.whyImportant}</p>
    </section>
    <section>
      <h3>影响分析</h3>
      <p>${milestone.impact}</p>
    </section>
    <section>
      <h3>来源</h3>
      <p><a href="${milestone.sourceUrl}" target="_blank" rel="noreferrer">${milestone.sourceUrl}</a></p>
    </section>
  `;
  ui.modal.hidden = false;
  ui.modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeDetail(ui) {
  ui.modal.hidden = true;
  ui.modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function bindModal(ui) {
  ui.modal.addEventListener("click", (event) => {
    if (event.target.dataset.close === "true") closeDetail(ui);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !ui.modal.hidden) closeDetail(ui);
  });
}

function truncate(text, maxLength) {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength)}…`;
}

async function loadEvents() {
  try {
    const response = await fetch("./data/events.json");
    if (!response.ok) return [];
    return await response.json();
  } catch (error) {
    return [];
  }
}

async function loadMilestones() {
  try {
    const response = await fetch("./data/milestones.json");
    if (!response.ok) return [];
    return await response.json();
  } catch (error) {
    return [];
  }
}

async function loadCompetitors() {
  const fallback = [
    { id: "cursor", name: "Cursor", company: "Anysphere", category: "AI IDE", notes: "", website: "", changelogUrl: "", pricing: "" },
    { id: "github-copilot", name: "GitHub Copilot", company: "GitHub / Microsoft", category: "AI 插件", notes: "", website: "", changelogUrl: "", pricing: "" },
    { id: "devin-desktop", name: "Devin Desktop", company: "Cognition", category: "AI IDE", notes: "", website: "", changelogUrl: "", pricing: "" },
    { id: "claude-code", name: "Claude Code", company: "Anthropic", category: "终端 Agent", notes: "", website: "", changelogUrl: "", pricing: "" },
    { id: "replit", name: "Replit Agent", company: "Replit", category: "Vibe Coding 平台", notes: "", website: "", changelogUrl: "", pricing: "" },
    { id: "google-jules", name: "Jules", company: "Google", category: "异步 Agent", notes: "", website: "", changelogUrl: "", pricing: "" },
    { id: "kiro", name: "Kiro", company: "AWS", category: "Spec-Driven IDE", notes: "", website: "", changelogUrl: "", pricing: "" }
  ];

  try {
    const response = await fetch("./data/competitors.json");
    if (!response.ok) return fallback;
    return await response.json();
  } catch (error) {
    return fallback;
  }
}
