(async function init() {
  const data = await loadJson("./data/context-engineering.json");
  const articles = data.articles || [];
  const topics = data.topics || [];
  const meta = data.meta || {};

  const ui = {
    meta: document.getElementById("ceMeta"),
    topicTabs: document.getElementById("ceTopicTabs"),
    competitorTabs: document.getElementById("ceCompetitorTabs"),
    search: document.getElementById("ceSearch"),
    sourceFilter: document.getElementById("ceSourceFilter"),
    curatedOnly: document.getElementById("ceCuratedOnly"),
    syncInfo: document.getElementById("ceSyncInfo"),
    list: document.getElementById("ceList"),
    count: document.getElementById("ceCount"),
    empty: document.getElementById("emptyCe"),
    detail: document.getElementById("ceDetail")
  };

  const state = {
    topic: "all",
    competitor: "all",
    source: "all",
    search: "",
    curatedOnly: false,
    activeId: null
  };

  const competitorNames = buildCompetitorMap(articles);

  renderMeta(meta, ui);
  renderTopicTabs(topics, state, ui, () => rerender());
  renderCompetitorTabs(competitorNames, state, ui, () => rerender());
  hydrateSourceFilter(articles, ui);
  bindFilters(state, ui, () => rerender());

  state.activeId = resolveInitialArticle(articles);
  rerender();

  window.addEventListener("hashchange", () => {
    const next = resolveInitialArticle(applyFilters(articles, state));
    if (next !== state.activeId) {
      state.activeId = next;
      rerender();
    }
  });

  function rerender() {
    const filtered = applyFilters(articles, state);
    renderList(filtered, state, ui, rerender);
    const active = filtered.find((a) => a.id === state.activeId) || filtered[0];
    if (active) {
      state.activeId = active.id;
      renderDetail(active, ui);
      if (location.hash !== `#${active.id}`) {
        history.replaceState(null, "", `#${active.id}`);
      }
    } else {
      ui.detail.innerHTML = "<p>没有匹配的文章。</p>";
    }
    ui.count.textContent = `共 ${filtered.length} 篇`;
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
    return { articles: [], topics: [], meta: {} };
  }
}

function buildCompetitorMap(articles) {
  const map = new Map();
  articles.forEach((a) => {
    if (a.competitorId && !map.has(a.competitorId)) {
      map.set(a.competitorId, a.competitorName || a.competitorId);
    }
  });
  return map;
}

function renderMeta(meta, ui) {
  const cards = [
    { label: "文章总数", value: meta.totalCount || 0 },
    { label: "主题数", value: meta.topicsCount || 0 },
    { label: "策展精选", value: meta.curatedCount || 0 },
    { label: "覆盖竞品", value: meta.competitorsCount || 0 }
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
        `<button type="button" class="ce-topic-tab${state.topic === t.id ? " active" : ""}" data-topic="${t.id}">${t.label}</button>`
    )
    .join("");

  ui.topicTabs.querySelectorAll(".ce-topic-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.topic = btn.dataset.topic;
      ui.topicTabs.querySelectorAll(".ce-topic-tab").forEach((b) => b.classList.remove("active"));
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
        `<button type="button" class="ce-competitor-tab${state.competitor === id ? " active" : ""}" data-competitor="${id}">${name}</button>`
    )
    .join("");

  ui.competitorTabs.querySelectorAll(".ce-competitor-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.competitor = btn.dataset.competitor;
      ui.competitorTabs.querySelectorAll(".ce-competitor-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange();
    });
  });
}

function hydrateSourceFilter(articles, ui) {
  const sources = [...new Set(articles.map((a) => a.sourceType).filter(Boolean))].sort();
  sources.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = sourceLabel(s);
    ui.sourceFilter.appendChild(opt);
  });
}

function sourceLabel(type) {
  const labels = {
    blog: "博客",
    docs: "产品文档",
    paper: "学术论文",
    github: "GitHub",
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

function applyFilters(articles, state) {
  return articles.filter((a) => {
    if (state.topic !== "all" && a.topicId !== state.topic) return false;
    if (state.competitor !== "all" && a.competitorId !== state.competitor) return false;
    if (state.source !== "all" && a.sourceType !== state.source) return false;
    if (state.curatedOnly && !a.curated) return false;
    if (state.search) {
      const hay = [a.title, a.summary, a.competitorName, a.topic, ...(a.tags || [])]
        .join(" ")
        .toLowerCase();
      if (!hay.includes(state.search)) return false;
    }
    return true;
  });
}

function resolveInitialArticle(pool) {
  const hash = location.hash.replace("#", "");
  if (hash && pool.some((a) => a.id === hash)) return hash;
  return pool[0]?.id || null;
}

function renderList(filtered, state, ui, onSelect) {
  ui.list.innerHTML = filtered
    .map((a) => {
      const active = a.id === state.activeId ? " active" : "";
      return `
      <article class="ce-card${active}" role="listitem" data-id="${a.id}" tabindex="0">
        <div class="ce-card-header">
          <div>
            <h3 class="ce-card-title">${escapeHtml(a.title)}</h3>
            <div class="ce-card-meta">
              <span class="ce-badge topic">${escapeHtml(a.topic)}</span>
              <span class="ce-badge competitor">${escapeHtml(a.competitorName)}</span>
              <span class="ce-badge source-${a.sourceType}">${escapeHtml(a.sourceLabel || sourceLabel(a.sourceType))}</span>
              ${a.qualityScore ? `<span class="ce-badge quality">质量 ${a.qualityScore}</span>` : ""}
            </div>
          </div>
        </div>
        <p class="ce-card-summary">${escapeHtml(truncate(a.summary, 160))}</p>
      </article>`;
    })
    .join("");

  ui.list.querySelectorAll(".ce-card").forEach((card) => {
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

function renderDetail(a, ui) {
  const highlights =
    a.highlights && a.highlights.length
      ? `<ul class="ce-highlights">${a.highlights.map((h) => `<li>${escapeHtml(h)}</li>`).join("")}</ul>`
      : "<p>暂无要点列表。</p>";

  const tags =
    a.tags && a.tags.length
      ? `<div class="ce-tags">${a.tags.map((t) => `<span class="ce-tag">${escapeHtml(t)}</span>`).join("")}</div>`
      : "";

  ui.detail.innerHTML = `
    <h3>${escapeHtml(a.title)}</h3>
    <div class="ce-detail-meta">
      <span class="ce-badge topic">${escapeHtml(a.topic)}</span>
      <span class="ce-badge competitor">${escapeHtml(a.competitorName)}</span>
      <span class="ce-badge source-${a.sourceType}">${escapeHtml(a.sourceLabel || sourceLabel(a.sourceType))}</span>
      ${a.curated ? '<span class="ce-badge source-curated">策展</span>' : ""}
    </div>
    <div class="ce-detail-section">
      <h4>摘要</h4>
      <p>${escapeHtml(a.summary)}</p>
    </div>
    <div class="ce-detail-section">
      <h4>要点</h4>
      ${highlights}
    </div>
    ${tags ? `<div class="ce-detail-section"><h4>标签</h4>${tags}</div>` : ""}
    <div class="ce-detail-section">
      <h4>来源</h4>
      <p>
        <a class="ce-source-link" href="${escapeAttr(a.sourceUrl)}" target="_blank" rel="noopener noreferrer">
          ${escapeHtml(a.sourceLabel || a.sourceUrl)} ↗
        </a>
      </p>
      <p class="ce-card-summary">${escapeHtml(a.author || "")}${a.date ? ` · ${a.date}` : ""}</p>
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
