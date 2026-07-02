(async function init() {
  const data = await loadBestPractices();
  const practices = data.practices || [];
  const meta = data.meta || {};

  const ui = {
    meta: document.getElementById("practicesMeta"),
    search: document.getElementById("practiceSearch"),
    themeFilter: document.getElementById("themeFilter"),
    competitorFilter: document.getElementById("competitorFilter"),
    sourceTypeFilter: document.getElementById("sourceTypeFilter"),
    featuredOnly: document.getElementById("featuredOnly"),
    syncInfo: document.getElementById("syncInfo"),
    count: document.getElementById("practiceCount"),
    tabs: document.getElementById("themeTabs"),
    grid: document.getElementById("practiceGrid"),
    empty: document.getElementById("emptyPractices"),
    detail: document.getElementById("practiceDetail")
  };

  const state = {
    theme: "all",
    competitor: "all",
    sourceType: "all",
    search: "",
    featuredOnly: false,
    activeId: practices.find((item) => item.featured)?.id || practices[0]?.id || null
  };

  hydrateFilters(data, ui);
  renderMeta(meta, data, ui);
  renderThemeTabs(data.themes || [], state, ui, rerender);
  bindFilters(state, ui, rerender);
  rerender();

  function rerender() {
    const filtered = applyFilters(practices, state);
    renderGrid(filtered, state, ui);
    const active = filtered.find((item) => item.id === state.activeId) || filtered[0];
    if (active) {
      state.activeId = active.id;
      renderDetail(active, ui);
    } else {
      ui.detail.innerHTML = "<p>没有匹配的最佳实践。</p>";
    }
    ui.count.textContent = `共 ${filtered.length} 条`;
    ui.empty.hidden = filtered.length > 0;
  }
})();

async function loadBestPractices() {
  try {
    const response = await fetch("./data/best_practices.json");
    if (!response.ok) throw new Error("fetch failed");
    return await response.json();
  } catch (error) {
    console.warn("best_practices.json 加载失败，使用内置回退数据", error);
    return FALLBACK_PRACTICES;
  }
}

function hydrateFilters(data, ui) {
  (data.themes || []).forEach((theme) => appendOption(ui.themeFilter, theme));
  (data.competitors || []).forEach((competitor) => appendOption(ui.competitorFilter, competitor));
  (data.sourceTypes || []).forEach((sourceType) => appendOption(ui.sourceTypeFilter, sourceType));
}

function appendOption(select, value) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = value;
  select.appendChild(option);
}

function renderMeta(meta, data, ui) {
  const updated = meta.lastUpdated
    ? new Date(meta.lastUpdated).toLocaleString("zh-CN", { hour12: false })
    : "未知";

  ui.meta.innerHTML = `
    <div class="meta-card"><strong>${meta.totalCount || data.practices?.length || 0}</strong><span>最佳实践</span></div>
    <div class="meta-card"><strong>${meta.featuredCount || 0}</strong><span>精选实践</span></div>
    <div class="meta-card"><strong>${(data.themes || []).length}</strong><span>主题维度</span></div>
    <div class="meta-card"><strong>${(data.competitors || []).length}</strong><span>覆盖竞品</span></div>
  `;

  ui.syncInfo.innerHTML = `
    <div><strong>自动采集</strong></div>
    <div>最近更新：${escapeHtml(updated)}</div>
    <div>每 3 天运行一次 GitHub Actions，同步产品文档、博客与公开页面中的最佳实践线索。</div>
  `;
}

function renderThemeTabs(themes, state, ui, onChange) {
  const tabs = [{ id: "all", label: "全部主题" }, ...themes.map((theme) => ({ id: theme, label: theme }))];
  ui.tabs.innerHTML = tabs
    .map(
      (tab) =>
        `<button type="button" class="tab${state.theme === tab.id ? " active" : ""}" data-theme="${escapeHtml(tab.id)}">${escapeHtml(tab.label)}</button>`
    )
    .join("");

  ui.tabs.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.theme = button.dataset.theme;
      ui.themeFilter.value = state.theme;
      ui.tabs.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      onChange();
    });
  });
}

function bindFilters(state, ui, onChange) {
  ui.search.addEventListener("input", () => {
    state.search = ui.search.value.trim().toLowerCase();
    onChange();
  });

  ui.themeFilter.addEventListener("change", () => {
    state.theme = ui.themeFilter.value;
    ui.tabs.querySelectorAll(".tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.theme === state.theme);
    });
    onChange();
  });

  ui.competitorFilter.addEventListener("change", () => {
    state.competitor = ui.competitorFilter.value;
    onChange();
  });

  ui.sourceTypeFilter.addEventListener("change", () => {
    state.sourceType = ui.sourceTypeFilter.value;
    onChange();
  });

  ui.featuredOnly.addEventListener("change", () => {
    state.featuredOnly = ui.featuredOnly.checked;
    onChange();
  });
}

function applyFilters(practices, state) {
  return practices.filter((practice) => {
    if (state.theme !== "all" && practice.theme !== state.theme) return false;
    if (state.competitor !== "all" && practice.competitor !== state.competitor) return false;
    if (state.sourceType !== "all" && practice.sourceType !== state.sourceType) return false;
    if (state.featuredOnly && !practice.featured) return false;
    if (!state.search) return true;

    const haystack = [
      practice.title,
      practice.competitor,
      practice.theme,
      practice.summary,
      practice.whyItWorks,
      practice.takeaway,
      practice.sourceTitle,
      ...(practice.tags || [])
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(state.search);
  });
}

function renderGrid(practices, state, ui) {
  ui.grid.innerHTML = practices
    .map(
      (practice) => `
        <article class="practice-card${practice.id === state.activeId ? " active" : ""}" role="listitem" data-id="${escapeHtml(practice.id)}" tabindex="0">
          <div class="practice-card-header">
            <h3>${escapeHtml(practice.title)}</h3>
            <span class="practice-score">${practice.heat}</span>
          </div>
          <p class="practice-summary">${escapeHtml(practice.summary)}</p>
          <div class="skill-tags">
            <span class="badge platform-default">${escapeHtml(practice.competitor)}</span>
            <span class="badge phase">${escapeHtml(practice.theme)}</span>
            <span class="badge">${escapeHtml(practice.sourceType)}</span>
            ${practice.featured ? '<span class="badge featured">精选</span>' : ""}
          </div>
        </article>
      `
    )
    .join("");

  ui.grid.querySelectorAll(".practice-card").forEach((card) => {
    const open = () => {
      state.activeId = card.dataset.id;
      const practice = practices.find((item) => item.id === state.activeId);
      if (practice) renderDetail(practice, ui);
      ui.grid.querySelectorAll(".practice-card").forEach((item) => item.classList.remove("active"));
      card.classList.add("active");
    };
    card.addEventListener("click", open);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

function renderDetail(practice, ui) {
  const checklist = (practice.howToApply || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const tags = (practice.tags || []).map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join(" ");

  ui.detail.innerHTML = `
    <h3>${escapeHtml(practice.title)}</h3>
    <div class="skill-tags" style="margin: 12px 0;">
      <span class="badge platform-default">${escapeHtml(practice.competitor)}</span>
      <span class="badge phase">${escapeHtml(practice.theme)}</span>
      <span class="badge">${escapeHtml(practice.sourceType)}</span>
      <span class="badge ${String(practice.sourceTier || "c").toLowerCase()}">来源 ${escapeHtml(practice.sourceTier || "C")}</span>
      ${practice.featured ? '<span class="badge featured">精选</span>' : ""}
    </div>

    <section>
      <h4>核心做法</h4>
      <p>${escapeHtml(practice.summary)}</p>
    </section>

    <section>
      <h4>为什么有效</h4>
      <p>${escapeHtml(practice.whyItWorks)}</p>
    </section>

    <section>
      <h4>落地清单</h4>
      <ul class="practice-checklist">${checklist}</ul>
    </section>

    <section>
      <h4>一句话 takeaway</h4>
      <p>${escapeHtml(practice.takeaway)}</p>
    </section>

    <section class="source-snippet">
      <h5>${escapeHtml(practice.sourceTitle || practice.title)}</h5>
      <p>${escapeHtml(practice.remoteSnippet || practice.summary)}</p>
      <p><a class="link-inline" href="${escapeHtml(practice.sourceUrl)}" target="_blank" rel="noopener">查看来源 →</a></p>
    </section>

    <section>
      <h4>标签</h4>
      <div class="skill-tags">${tags}</div>
    </section>
  `;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const FALLBACK_PRACTICES = {
  meta: { totalCount: 1, featuredCount: 1, lastUpdated: new Date().toISOString() },
  themes: ["Prompt 设计"],
  competitors: ["GitHub Copilot"],
  sourceTypes: ["产品文档"],
  practices: [
    {
      id: "bp-001",
      title: "先给目标，再给约束",
      competitor: "GitHub Copilot",
      theme: "Prompt 设计",
      sourceType: "产品文档",
      sourceTier: "A",
      sourceTitle: "Prompt engineering for GitHub Copilot",
      sourceUrl: "https://docs.github.com/en/copilot/using-github-copilot/prompt-engineering-for-github-copilot",
      summary: "先用一句话描述目标，再分点补充输入、输出、限制条件。",
      whyItWorks: "先建立问题框架，再压缩搜索空间，可以减少跑偏。",
      howToApply: ["先写目标", "再列约束", "补充示例"],
      takeaway: "目标、约束、示例三段式是通用起手式。",
      tags: ["prompt", "copilot"],
      heat: 92,
      featured: true,
      remoteSnippet: "Follow these strategies to improve your Copilot results."
    }
  ]
};
