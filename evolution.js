(async function init() {
  const [events, competitors] = await Promise.all([loadEvents(), loadCompetitors()]);
  const evolutionByCompetitor = buildEvolutionMap(events, competitors);

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
    activeId: resolveInitialCompetitor(competitors),
    eventsById: indexEvents(events)
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

function buildEvolutionMap(events, competitors) {
  const keyEvents = dedupeEvolutionEvents(events.filter(isKeyEvolutionEvent));
  const map = new Map();

  competitors.forEach((competitor) => {
    const eventCompany = EVENT_COMPANY_BY_COMPETITOR[competitor.id] || competitor.company;
    const milestones = keyEvents
      .filter((event) => event.company === eventCompany)
      .sort((a, b) => new Date(b.date) - new Date(a.date));
    map.set(competitor.id, milestones);
  });

  return map;
}

function isKeyEvolutionEvent(event) {
  if (!EVOLUTION_CATEGORIES.has(event.category)) return false;
  if (event.id.startsWith("auto-") && event.heat < 70) return false;
  return true;
}

function dedupeEvolutionEvents(events) {
  const byKey = new Map();

  events.forEach((event) => {
    const key = `${event.date}|${event.company}|${normalizeTitle(event.title)}`;
    const existing = byKey.get(key);
    if (!existing || preferEvent(event, existing)) {
      byKey.set(key, event);
    }
  });

  return Array.from(byKey.values());
}

function preferEvent(candidate, current) {
  const candidateAuto = candidate.id.startsWith("auto-");
  const currentAuto = current.id.startsWith("auto-");
  if (candidateAuto && !currentAuto) return false;
  if (!candidateAuto && currentAuto) return true;
  return candidate.heat > current.heat;
}

function normalizeTitle(title) {
  const versionMatch = title.match(/v?\d+\.\d+\.\d+/i);
  if (versionMatch) return versionMatch[0].toLowerCase();
  return title.slice(0, 48).toLowerCase();
}

function indexEvents(events) {
  return new Map(events.map((event) => [event.id, event]));
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
  renderIntro(competitor, milestones.length, ui.intro);
  renderTimeline(milestones, ui, state.eventsById);
}

function renderIntro(competitor, milestoneCount, container) {
  container.innerHTML = `
    <div class="intro-grid">
      <div>
        <h2>${competitor.name}</h2>
        <p class="intro-company">${competitor.company}</p>
      </div>
      <div class="intro-meta">
        <span class="intro-pill">${competitor.category}</span>
        <span class="intro-pill">${competitor.pricing || "定价未收录"}</span>
        <span class="intro-pill">${milestoneCount} 个关键节点</span>
      </div>
    </div>
    <p class="intro-notes">${competitor.notes || ""}</p>
    <div class="intro-links">
      ${competitor.website ? `<a href="${competitor.website}" target="_blank" rel="noreferrer">产品官网</a>` : ""}
      ${competitor.changelogUrl ? `<a href="${competitor.changelogUrl}" target="_blank" rel="noreferrer">更新日志</a>` : ""}
    </div>
  `;
}

function renderTimeline(milestones, ui, eventsById) {
  ui.timeline.innerHTML = "";
  ui.count.textContent = `${milestones.length} 个节点`;
  ui.empty.hidden = milestones.length > 0;
  ui.timeline.hidden = milestones.length === 0;

  milestones.forEach((event, index) => {
    const node = document.createElement("button");
    node.type = "button";
    node.className = "timeline-node";
    node.dataset.id = event.id;
    node.setAttribute("role", "listitem");
    node.innerHTML = `
      <div class="timeline-axis">
        <span class="timeline-dot" aria-hidden="true"></span>
        ${index < milestones.length - 1 ? '<span class="timeline-line" aria-hidden="true"></span>' : ""}
      </div>
      <div class="timeline-card">
        <div class="timeline-meta">
          <time datetime="${event.date}">${event.date}</time>
          <span class="badge category-${event.category}">${event.category}</span>
          <span class="badge topic">${event.topic}</span>
          <span class="badge ${event.sourceTier.toLowerCase()}">${event.sourceTier} 级来源</span>
        </div>
        <h3>${event.title}</h3>
        <p>${truncate(event.summary, 140)}</p>
        <span class="timeline-cta">点击查看详情 →</span>
      </div>
    `;
    node.addEventListener("click", () => openDetail(event, ui));
    ui.timeline.appendChild(node);
  });
}

function openDetail(event, ui) {
  ui.modalDetail.innerHTML = `
    <h2 id="modalTitle">${event.title}</h2>
    <div class="modal-meta">
      <time datetime="${event.date}">${event.date}</time>
      <span class="badge category-${event.category}">${event.category}</span>
      <span class="badge topic">${event.topic}</span>
      <span class="badge ${event.sourceTier.toLowerCase()}">${event.sourceTier} 级来源</span>
      <span class="heat-tag">热度 ${event.heat} · 增长 ${event.growth}</span>
    </div>
    <section>
      <h3>摘要</h3>
      <p>${event.summary}</p>
    </section>
    <section>
      <h3>为什么重要</h3>
      <p>${event.whyImportant}</p>
    </section>
    <section>
      <h3>影响分析</h3>
      <p>${event.impact}</p>
    </section>
    <section>
      <h3>来源</h3>
      <p><a href="${event.sourceUrl}" target="_blank" rel="noreferrer">${event.sourceUrl}</a></p>
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
