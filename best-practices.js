(async function init() {
  const data = await loadJson("./data/best-practices.json");
  const practices = data.practices || [];
  const topics = data.topics || [];
  const meta = data.meta || {};

  const ui = {
    meta: document.getElementById("bpMeta"),
    topicTabs: document.getElementById("topicTabs"),
    competitorTabs: document.getElementById("competitorTabs"),
    search: document.getElementById("bpSearch"),
    sourceFilter: document.getElementById("sourceFilter"),
    curatedOnly: document.getElementById("curatedOnly"),
    syncInfo: document.getElementById("syncInfo"),
    list: document.getElementById("bpList"),
    count: document.getElementById("bpCount"),
    empty: document.getElementById("emptyBp"),
    detail: document.getElementById("bpDetail")
  };

  const state = {
    topic: "all",
    competitor: "all",
    source: "all",
    search: "",
    curatedOnly: false,
    activeId: null
  };

  const competitorNames = buildCompetitorMap(practices);

  renderMeta(meta, ui);
  renderTopicTabs(topics, state, ui, () => rerender());
  renderCompetitorTabs(competitorNames, state, ui, () => rerender());
  hydrateSourceFilter(practices, ui);
  bindFilters(state, ui, () => rerender());

  state.activeId = resolveInitialPractice(practices);
  rerender();

  window.addEventListener("hashchange", () => {
    const next = resolveInitialPractice(applyFilters(practices, state));
    if (next !== state.activeId) {
      state.activeId = next;
      rerender();
    }
  });

  function rerender() {
    const filtered = applyFilters(practices, state);
    renderList(filtered, state, ui, rerender);
    const active = filtered.find((p) => p.id === state.activeId) || filtered[0];
    if (active) {
      state.activeId = active.id;
      renderDetail(active, ui);
      if (location.hash !== `#${active.id}`) {
        history.replaceState(null, "", `#${active.id}`);
      }
    } else {
      ui.detail.innerHTML = "<p>没有匹配的最佳实践。</p>";
    }
    ui.count.textContent = `共 ${filtered.length} 条`;
    ui.empty.hidden = filtered.length > 0;
  }
})();

async function loadJson(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(res.statusText);
    return await res.json();
  } catch (err) {
    console.warn("加载失败:", url, err);
    return { practices: [], topics: [], meta: {} };
  }
}

function buildCompetitorMap(practices) {
  const map = new Map();
  practices.forEach((p) => {
    if (p.competitorId && !map.has(p.competitorId)) {
      map.set(p.competitorId, p.competitorName || p.competitorId);
    }
  });
  return map;
}

function renderMeta(meta, ui) {
  const cards = [
    { label: "实践总数", value: meta.totalCount || 0 },
    { label: "主题数", value: meta.topicsCount || 0 },
    { label: "策展精选", value: meta.curatedCount || 0 },
    { label: "网络采集", value: meta.webCount || 0 }
  ];
  ui.meta.innerHTML = cards
    .map(
      (c) => `
    <div class="meta-card">
      <div class="meta-value">${c.value}</div>
      <div class="meta-label">${c.label}</div>
    </div>`
    )
    .join("");

  const updated = meta.lastUpdated ? formatDate(meta.lastUpdated) : "未知";
  ui.syncInfo.innerHTML = `<p>最近同步：${updated}</p><p class="sync-note">${meta.note || ""}</p>`;
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

function renderTopicTabs(topics, state, ui, onChange) {
  const tabs = [{ id: "all", label: "全部主题" }, ...topics];
  ui.topicTabs.innerHTML = tabs
    .map(
      (t) =>
        `<button type="button" class="topic-tab${state.topic === t.id ? " active" : ""}" data-topic="${t.id}">${t.label}</button>`
    )
    .join("");

  ui.topicTabs.querySelectorAll(".topic-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.topic = btn.dataset.topic;
      ui.topicTabs.querySelectorAll(".topic-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange();
    });
  });
}

function renderCompetitorTabs(competitorMap, state, ui, onChange) {
  const entries = [["all", "全部竞品"], ...Array.from(competitorMap.entries())];
  ui.competitorTabs.innerHTML = entries
    .map(
      ([id, name]) =>
        `<button type="button" class="competitor-tab${state.competitor === id ? " active" : ""}" data-competitor="${id}">${name}</button>`
    )
    .join("");

  ui.competitorTabs.querySelectorAll(".competitor-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.competitor = btn.dataset.competitor;
      ui.competitorTabs.querySelectorAll(".competitor-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange();
    });
  });
}

function hydrateSourceFilter(practices, ui) {
  const sources = [...new Set(practices.map((p) => p.sourceType).filter(Boolean))].sort();
  sources.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = sourceLabel(s);
    ui.sourceFilter.appendChild(opt);
  });
}

function sourceLabel(type) {
  const labels = {
    "hacker-news": "Hacker News",
    reddit: "Reddit",
    github: "GitHub",
    blog: "博客",
    docs: "产品文档",
    forum: "论坛",
    curated: "策展"
  };
  return labels[type] || type;
}

function bindFilters(state, ui, onChange) {
  ui.search.addEventListener("input", () => {
    state.search = ui.search.value.trim().toLowerCase();
    onChange();
  });
  ui.sourceFilter.addEventListener("change", () => {
    state.source = ui.sourceFilter.value;
    onChange();
  });
  ui.curatedOnly.addEventListener("change", () => {
    state.curatedOnly = ui.curatedOnly.checked;
    onChange();
  });
}

function applyFilters(practices, state) {
  return practices.filter((p) => {
    if (state.topic !== "all" && p.topicId !== state.topic) return false;
    if (state.competitor !== "all" && p.competitorId !== state.competitor) return false;
    if (state.source !== "all" && p.sourceType !== state.source) return false;
    if (state.curatedOnly && !p.curated) return false;
    if (state.search) {
      const hay = [p.title, p.summary, p.competitorName, p.topic, ...(p.tags || [])]
        .join(" ")
        .toLowerCase();
      if (!hay.includes(state.search)) return false;
    }
    return true;
  });
}

function resolveInitialPractice(pool) {
  const hash = location.hash.replace("#", "");
  if (hash && pool.some((p) => p.id === hash)) return hash;
  return pool[0]?.id || null;
}

function renderList(filtered, state, ui, onSelect) {
  ui.list.innerHTML = filtered
    .map((p) => {
      const active = p.id === state.activeId ? " active" : "";
      return `
      <article class="bp-card${active}" role="listitem" data-id="${p.id}" tabindex="0">
        <div class="bp-card-header">
          <div>
            <h3 class="bp-card-title">${escapeHtml(p.title)}</h3>
            <div class="bp-card-meta">
              <span class="bp-badge topic">${escapeHtml(p.topic)}</span>
              <span class="bp-badge competitor">${escapeHtml(p.competitorName)}</span>
              <span class="bp-badge source-${p.sourceType}">${escapeHtml(p.sourceLabel || sourceLabel(p.sourceType))}</span>
              ${p.qualityScore ? `<span class="bp-badge quality">质量 ${p.qualityScore}</span>` : ""}
            </div>
          </div>
        </div>
        <p class="bp-card-summary">${escapeHtml(truncate(p.summary, 160))}</p>
      </article>`;
    })
    .join("");

  ui.list.querySelectorAll(".bp-card").forEach((card) => {
    const select = () => {
      state.activeId = card.dataset.id;
      location.hash = card.dataset.id;
      onSelect();
    };
    card.addEventListener("click", select);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        select();
      }
    });
  });
}

function renderDetail(p, ui) {
  const highlights =
    p.highlights && p.highlights.length
      ? `<ul class="bp-highlights">${p.highlights.map((h) => `<li>${escapeHtml(h)}</li>`).join("")}</ul>`
      : "<p>暂无要点列表。</p>";

  const tags =
    p.tags && p.tags.length
      ? `<div class="bp-tags">${p.tags.map((t) => `<span class="bp-tag">${escapeHtml(t)}</span>`).join("")}</div>`
      : "";

  ui.detail.innerHTML = `
    <h3>${escapeHtml(p.title)}</h3>
    <div class="bp-detail-meta">
      <span class="bp-badge topic">${escapeHtml(p.topic)}</span>
      <span class="bp-badge competitor">${escapeHtml(p.competitorName)}</span>
      <span class="bp-badge source-${p.sourceType}">${escapeHtml(p.sourceLabel || sourceLabel(p.sourceType))}</span>
      ${p.curated ? '<span class="bp-badge source-curated">策展</span>' : ""}
    </div>
    <div class="bp-detail-section">
      <h4>摘要</h4>
      <p>${escapeHtml(p.summary)}</p>
    </div>
    <div class="bp-detail-section">
      <h4>要点</h4>
      ${highlights}
    </div>
    ${tags ? `<div class="bp-detail-section"><h4>标签</h4>${tags}</div>` : ""}
    <div class="bp-detail-section">
      <h4>来源</h4>
      <p>
        <a class="bp-source-link" href="${escapeAttr(p.sourceUrl)}" target="_blank" rel="noopener noreferrer">
          ${escapeHtml(p.sourceLabel || p.sourceUrl)} ↗
        </a>
      </p>
      <p class="bp-card-summary">${escapeHtml(p.author || "")}${p.date ? ` · ${p.date}` : ""}</p>
    </div>`;
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/'/g, "&#39;");
}

function truncate(str, len) {
  const s = String(str || "");
  return s.length > len ? `${s.slice(0, len)}…` : s;
}
