(async function init() {
  const [data, indexData, changesData, primerData] = await Promise.all([
    loadLlms(),
    loadJson("./data/llms-index.json"),
    loadJson("./data/llm-changes.json"),
    loadJson("./data/llm-primer.json")
  ]);

  const curatedLlms = data.llms || [];
  const indexLlms = indexData.llms || [];
  const meta = data.meta || {};

  const ui = {
    meta: document.getElementById("llmsMeta"),
    changesPanel: document.getElementById("llmChangesPanel"),
    changesList: document.getElementById("llmChangesList"),
    changesCount: document.getElementById("changesCount"),
    viewTabs: document.getElementById("viewTabs"),
    providerTabs: document.getElementById("providerTabs"),
    benchmarkQuickTabs: document.getElementById("benchmarkQuickTabs"),
    search: document.getElementById("llmSearch"),
    categoryFilter: document.getElementById("categoryFilter"),
    weightsFilter: document.getElementById("weightsFilter"),
    featuredOnly: document.getElementById("featuredOnly"),
    syncInfo: document.getElementById("syncInfo"),
    grid: document.getElementById("llmGrid"),
    count: document.getElementById("llmCount"),
    empty: document.getElementById("emptyLlms"),
    detail: document.getElementById("llmDetail"),
    modal: document.getElementById("llmModal"),
    modalDetail: document.getElementById("llmModalDetail")
  };

  const state = {
    view: "curated",
    provider: "all",
    category: "all",
    weights: "all",
    benchmarkFocus: "all",
    search: "",
    featuredOnly: false,
    activeId: null
  };

  hydrateFilters(data, ui);
  renderMeta(meta, data, indexData, ui);
  renderPrimer(primerData);
  renderChanges(changesData, ui);
  renderViewTabs(state, ui, () => rerender());
  renderProviderTabs(data.providers || [], state, ui, () => rerender());
  renderBenchmarkQuickTabs(state, ui, () => rerender());
  bindFilters(state, ui, () => rerender());
  bindModal(ui);

  state.activeId = resolveInitialLlm(getActivePool(state, curatedLlms, indexLlms));
  rerender();

  window.addEventListener("hashchange", () => {
    const pool = getActivePool(state, curatedLlms, indexLlms);
    const next = resolveInitialLlm(pool);
    if (next !== state.activeId) {
      state.activeId = next;
      rerender();
    }
  });

  function rerender() {
    const pool = getActivePool(state, curatedLlms, indexLlms);
    const filtered = applyFilters(pool, state, state.view === "curated");
    renderLlmGrid(filtered, state, ui, state.view === "curated", rerender);
    const active = filtered.find((l) => l.id === state.activeId) || filtered[0];
    if (active) {
      state.activeId = active.id;
      renderLlmDetail(active, ui, state.view === "curated");
    } else {
      ui.detail.innerHTML = "<p>没有匹配的大模型。</p>";
    }
    ui.count.textContent = `共 ${filtered.length} 个`;
    ui.empty.hidden = filtered.length > 0;
    ui.featuredOnly.closest(".checkbox-row").hidden = state.view !== "curated";
  }
})();

function getActivePool(state, curated, index) {
  if (state.view === "index") return index;
  if (state.view === "new") return index.filter((l) => l.isNew);
  return curated;
}

function resolveInitialLlm(llms) {
  const hash = window.location.hash.replace("#", "");
  if (hash) {
    const bySlug = llms.find((l) => l.slug === hash);
    if (bySlug) return bySlug.id;
  }
  const featured = llms.find((l) => l.featured);
  return featured ? featured.id : llms[0]?.id;
}

async function loadJson(url) {
  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("fetch failed");
    return await resp.json();
  } catch {
    return {};
  }
}

async function loadLlms() {
  try {
    const resp = await fetch("./data/llms.json");
    if (!resp.ok) throw new Error("fetch failed");
    return await resp.json();
  } catch (err) {
    console.warn("llms.json 加载失败，使用内置回退数据", err);
    return FALLBACK_LLMS;
  }
}

function hydrateFilters(data, ui) {
  (data.categories || []).forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    ui.categoryFilter.appendChild(opt);
  });
}

function renderPrimer(primer) {
  const panel = document.getElementById("llmPrimerPanel");
  const titleEl = document.getElementById("primerTitle");
  const subtitleEl = document.getElementById("primerSubtitle");
  const tabsEl = document.getElementById("primerTabs");
  const contentEl = document.getElementById("primerContent");
  const toggleBtn = document.getElementById("primerToggle");
  const bodyEl = document.getElementById("primerBody");

  if (!panel || !primer.meta) return;

  titleEl.textContent = primer.meta.title || "LLM 评测第一性原理";
  subtitleEl.textContent = primer.meta.subtitle || "";

  const sections = [
    { id: "essence", label: "本质与原理", render: () => renderEssenceSection(primer.essence) },
    { id: "value", label: "产品价值", render: () => renderValueSection(primer.value) },
    { id: "adoption", label: "评测体系", render: () => renderAdoptionSection(primer.adoption) },
    { id: "guide", label: "选型指南", render: () => renderGuideSection(primer.guide) }
  ];

  let activeId = "essence";

  function renderTabs() {
    tabsEl.innerHTML = sections
      .map(
        (s) =>
          `<button type="button" class="primer-tab${activeId === s.id ? " active" : ""}" data-section="${s.id}">${escapeHtml(s.label)}</button>`
      )
      .join("");
    tabsEl.querySelectorAll(".primer-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeId = btn.dataset.section;
        renderTabs();
        renderContent();
      });
    });
  }

  function renderContent() {
    const section = sections.find((s) => s.id === activeId);
    contentEl.innerHTML = section ? section.render() : "";
  }

  renderTabs();
  renderContent();

  const collapsedKey = "llm-primer-collapsed";
  const isCollapsed = localStorage.getItem(collapsedKey) === "1";
  setCollapsed(isCollapsed);

  toggleBtn.addEventListener("click", () => {
    const next = !bodyEl.hidden;
    setCollapsed(next);
    localStorage.setItem(collapsedKey, next ? "1" : "0");
  });

  function setCollapsed(collapsed) {
    bodyEl.hidden = collapsed;
    toggleBtn.setAttribute("aria-expanded", String(!collapsed));
    toggleBtn.textContent = collapsed ? "展开" : "收起";
    panel.classList.toggle("primer-collapsed", collapsed);
  }
}

function renderEssenceSection(essence) {
  if (!essence) return "";
  const principlesHtml = (essence.firstPrinciples || [])
    .map(
      (p) => `
      <div class="primer-card">
        <h4>${escapeHtml(p.title)}</h4>
        <p>${escapeHtml(p.body)}</p>
      </div>`
    )
    .join("");

  const comparisonRows = (essence.comparison?.rows || [])
    .map(
      (row) => `
      <tr>
        <th scope="row">${escapeHtml(row.dimension)}</th>
        <td>${escapeHtml(row.automated)}</td>
        <td>${escapeHtml(row.manual)}</td>
        <td>${escapeHtml(row.sentiment)}</td>
      </tr>`
    )
    .join("");

  return `
    <h3>${escapeHtml(essence.headline)}</h3>
    <p class="primer-lead">${escapeHtml(essence.definition)}</p>
    <p class="primer-problem"><strong>核心问题：</strong>${escapeHtml(essence.problem)}</p>
    <div class="primer-grid">${principlesHtml}</div>
    ${
      comparisonRows
        ? `<h4>${escapeHtml(essence.comparison.title)}</h4>
    <div class="primer-table-wrap">
      <table class="primer-table">
        <thead>
          <tr>
            <th scope="col">维度</th>
            <th scope="col">自动化评测</th>
            <th scope="col">人工评测</th>
            <th scope="col">社区口碑</th>
          </tr>
        </thead>
        <tbody>${comparisonRows}</tbody>
      </table>
    </div>`
        : ""
    }`;
}

function renderValueSection(value) {
  if (!value) return "";
  const pillarsHtml = (value.pillars || [])
    .map(
      (p) => `
      <div class="primer-card primer-card-value">
        <div class="primer-card-top">
          <h4>${escapeHtml(p.title)}</h4>
          <span class="primer-metric">${escapeHtml(p.metric)}</span>
        </div>
        <p>${escapeHtml(p.body)}</p>
      </div>`
    )
    .join("");

  const audiencesHtml = (value.audiences || [])
    .map(
      (a) => `
      <li>
        <strong>${escapeHtml(a.role)}</strong>
        <span>${escapeHtml(a.benefit)}</span>
      </li>`
    )
    .join("");

  return `
    <h3>${escapeHtml(value.headline)}</h3>
    <div class="primer-grid primer-grid-2">${pillarsHtml}</div>
    <h4>不同角色的收益</h4>
    <ul class="primer-audience-list">${audiencesHtml}</ul>`;
}

function renderAdoptionSection(adoption) {
  if (!adoption) return "";
  const ecoHtml = (adoption.ecosystems || [])
    .map(
      (e) => `
      <div class="primer-card">
        <div class="primer-card-top">
          <h4>${escapeHtml(e.name)}</h4>
          <span class="primer-metric">${escapeHtml(e.scale)}</span>
        </div>
        <p class="primer-meta-line">${escapeHtml(e.platform)} · ${escapeHtml(e.repo)}</p>
        <p>${escapeHtml(e.highlight)}</p>
      </div>`
    )
    .join("");

  const milestonesHtml = (adoption.milestones || [])
    .map(
      (m) => `
      <li class="primer-milestone">
        <time>${escapeHtml(m.date)}</time>
        <div>
          <strong>${escapeHtml(m.event)}</strong>
          <p>${escapeHtml(m.impact)}</p>
        </div>
      </li>`
    )
    .join("");

  const casesHtml = (adoption.cases || [])
    .map(
      (c) => `
      <div class="primer-case-card">
        <div class="primer-case-header">
          <h5>${escapeHtml(c.title)}</h5>
          <span class="badge category">${escapeHtml(c.industry)}</span>
        </div>
        <p class="primer-meta-line">相关模型：<strong>${escapeHtml(c.model)}</strong></p>
        <div class="use-case-label">场景</div>
        <p>${escapeHtml(c.scenario)}</p>
        <div class="use-case-label">落地效果</div>
        <p>${escapeHtml(c.outcome)}</p>
      </div>`
    )
    .join("");

  return `
    <h3>${escapeHtml(adoption.headline)}</h3>
    <p class="primer-lead">${escapeHtml(adoption.summary)}</p>
    <h4>主流评测体系</h4>
    <div class="primer-grid primer-grid-2">${ecoHtml}</div>
    <h4>关键里程碑</h4>
    <ul class="primer-milestone-list">${milestonesHtml}</ul>
    <h4>典型选型案例</h4>
    <div class="primer-cases">${casesHtml}</div>`;
}

function renderGuideSection(guide) {
  if (!guide) return "";
  const stepsHtml = (guide.steps || [])
    .map(
      (s) => `
      <li class="primer-step">
        <span class="primer-step-num">${s.step}</span>
        <div>
          <strong>${escapeHtml(s.title)}</strong>
          <p>${escapeHtml(s.body)}</p>
        </div>
      </li>`
    )
    .join("");

  const antiHtml = (guide.antiPatterns || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  return `
    <h3>${escapeHtml(guide.headline)}</h3>
    <ol class="primer-steps">${stepsHtml}</ol>
    <h4>常见反模式</h4>
    <ul class="primer-anti-list">${antiHtml}</ul>`;
}

function renderMeta(meta, data, indexData, ui) {
  const discovery = meta.discovery || {};
  const sweBench = discovery["swe-bench"]?.focus || "软件工程";
  const arena = discovery["lmsys-arena"]?.focus || "人工盲测";
  const indexTotal = meta.indexTotalCount || indexData.meta?.totalCount || "—";
  const newCount = meta.newCount || indexData.meta?.newCount || 0;

  ui.meta.innerHTML = `
    <div class="meta-card"><strong>${meta.totalCount || data.llms?.length || 0}</strong><span>SOTA 精选</span></div>
    <div class="meta-card"><strong>${indexTotal}</strong><span>全量索引</span></div>
    <div class="meta-card"><strong>${newCount}</strong><span>本周新增</span></div>
    <div class="meta-card"><strong>${meta.changesCount ?? 0}</strong><span>近期变更</span></div>
    <div class="meta-card"><strong>${sweBench}</strong><span>SWE-bench</span></div>
    <div class="meta-card"><strong>${arena}</strong><span>Arena Elo</span></div>
  `;

  const updated = meta.lastUpdated
    ? new Date(meta.lastUpdated).toLocaleString("zh-CN", { hour12: false })
    : "未知";
  ui.syncInfo.innerHTML = `
    <div><strong>LLM 雷达</strong></div>
    <div>最近更新：${escapeHtml(updated)}</div>
    <div>每周同步评测分数、人工排名与社区口碑，检测模型变更。</div>
  `;
}

function renderChanges(changesData, ui) {
  const changes = (changesData.changes || []).filter((c) => c.type !== "removed");
  if (!changes.length || changesData.isBaselineRun) {
    ui.changesPanel.hidden = true;
    return;
  }
  ui.changesPanel.hidden = false;
  ui.changesCount.textContent = `${changes.length} 条`;
  ui.changesList.innerHTML = changes
    .slice(0, 12)
    .map((c) => {
      const badge = c.type === "added" ? "新增" : "更新";
      const badgeClass = c.type === "added" ? "badge featured" : "badge category";
      return `
        <li class="change-item">
          <span class="${badgeClass}">${badge}</span>
          <a href="#${escapeHtml(c.slug)}" class="change-link">${escapeHtml(c.displayName || c.slug)}</a>
          <span class="change-eco">${escapeHtml(c.provider || "")}</span>
          <p>${escapeHtml(c.summary || "")}</p>
        </li>`;
    })
    .join("");
}

function renderViewTabs(state, ui, onChange) {
  const tabs = [
    { id: "curated", label: "SOTA 精选" },
    { id: "index", label: "全量索引" },
    { id: "new", label: "本周新增" }
  ];
  ui.viewTabs.innerHTML = tabs
    .map(
      (tab) =>
        `<button type="button" class="view-tab${state.view === tab.id ? " active" : ""}" data-view="${tab.id}">${tab.label}</button>`
    )
    .join("");
  ui.viewTabs.querySelectorAll(".view-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.view = btn.dataset.view;
      ui.viewTabs.querySelectorAll(".view-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange();
    });
  });
}

function renderProviderTabs(providers, state, ui, onChange) {
  const tabs = [{ id: "all", label: "全部提供商" }, ...providers.map((p) => ({ id: p, label: p }))];
  ui.providerTabs.innerHTML = tabs
    .map(
      (tab) =>
        `<button type="button" class="provider-tab${state.provider === tab.id ? " active" : ""}" data-provider="${escapeHtml(tab.id)}">${escapeHtml(tab.label)}</button>`
    )
    .join("");

  ui.providerTabs.querySelectorAll(".provider-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.provider = btn.dataset.provider;
      ui.providerTabs.querySelectorAll(".provider-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange();
    });
  });
}

function renderBenchmarkQuickTabs(state, ui, onChange) {
  const tabs = [
    { id: "all", label: "全部" },
    { id: "automated", label: "自动化评测" },
    { id: "manual", label: "人工评测" },
    { id: "sentiment", label: "口碑舆情" }
  ];
  ui.benchmarkQuickTabs.innerHTML = tabs
    .map(
      (tab) =>
        `<button type="button" class="tab${state.benchmarkFocus === tab.id ? " active" : ""}" data-focus="${tab.id}">${tab.label}</button>`
    )
    .join("");

  ui.benchmarkQuickTabs.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.benchmarkFocus = btn.dataset.focus;
      ui.benchmarkQuickTabs.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange();
    });
  });
}

function bindFilters(state, ui, onChange) {
  ui.search.addEventListener("input", () => {
    state.search = ui.search.value.trim().toLowerCase();
    onChange();
  });
  ui.categoryFilter.addEventListener("change", () => {
    state.category = ui.categoryFilter.value;
    onChange();
  });
  ui.weightsFilter.addEventListener("change", () => {
    state.weights = ui.weightsFilter.value;
    onChange();
  });
  ui.featuredOnly.addEventListener("change", () => {
    state.featuredOnly = ui.featuredOnly.checked;
    onChange();
  });
}

function applyFilters(llms, state, isCurated) {
  return llms.filter((llm) => {
    if (state.provider !== "all" && llm.provider !== state.provider) return false;
    if (isCurated && state.category !== "all" && llm.category !== state.category) return false;
    if (state.weights === "open" && !llm.openWeights) return false;
    if (state.weights === "closed" && llm.openWeights) return false;
    if (isCurated && state.featuredOnly && !llm.featured) return false;
    if (state.benchmarkFocus === "automated" && !(llm.benchmarks?.automated?.length)) return false;
    if (state.benchmarkFocus === "manual" && !(llm.benchmarks?.manual?.length)) return false;
    if (state.benchmarkFocus === "sentiment" && !llm.sentiment) return false;
    if (state.search) {
      const haystack = [
        llm.displayName,
        llm.slug,
        llm.description,
        llm.introduction,
        llm.provider,
        llm.category,
        ...(llm.providers || []),
        ...(llm.tags || []),
        ...(llm.availableIn || [])
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(state.search)) return false;
    }
    return true;
  });
}

function renderBenchmarkPreview(llm) {
  const chips = [];
  const auto = llm.benchmarks?.automated || [];
  const manual = llm.benchmarks?.manual || [];
  const topAuto = auto.find((b) => b.name.includes("SWE-bench")) || auto[0];
  const topManual = manual[0];

  if (topAuto) {
    chips.push(`<span class="bench-chip auto">${escapeHtml(topAuto.name)} ${topAuto.score}${escapeHtml(topAuto.unit)}</span>`);
  }
  if (topManual) {
    chips.push(`<span class="bench-chip manual">${escapeHtml(topManual.name)} ${topManual.score}</span>`);
  }
  if (llm.sentiment) {
    chips.push(`<span class="bench-chip sentiment">口碑 ${llm.sentiment.score}/${llm.sentiment.maxScore}</span>`);
  }
  return chips.length ? `<div class="llm-benchmark-preview">${chips.join("")}</div>` : "";
}

function renderLlmGrid(llms, state, ui, isCurated, onSelect) {
  ui.grid.innerHTML = llms
    .map((llm) => {
      const rankLabel = isCurated
        ? `#${llm.rank}`
        : llm.activityScore != null
          ? `活跃 ${llm.activityScore}`
          : "";
      const extraBadges = [
        llm.featured ? '<span class="badge featured">SOTA</span>' : "",
        llm.isNew ? '<span class="badge new">新</span>' : "",
        llm.inTopCurated ? '<span class="badge category">精选</span>' : "",
        llm.openWeights ? '<span class="badge open-weights">开源</span>' : ""
      ].join("");
      const categoryBadge = llm.category
        ? `<span class="badge category">${escapeHtml(llm.category)}</span>`
        : "";

      return `
        <article class="llm-card${llm.id === state.activeId ? " active" : ""}" role="listitem" data-id="${escapeHtml(llm.id)}" tabindex="0">
          <div class="llm-card-header">
            <h3>${escapeHtml(llm.displayName)}</h3>
            ${rankLabel ? `<span class="llm-rank">${escapeHtml(rankLabel)}</span>` : ""}
          </div>
          <p class="llm-desc">${escapeHtml(llm.description || "")}</p>
          <div class="llm-tags">
            <span class="badge provider-badge">${escapeHtml(llm.provider)}</span>
            ${categoryBadge}
            ${extraBadges}
          </div>
          ${renderBenchmarkPreview(llm)}
        </article>`;
    })
    .join("");

  ui.grid.querySelectorAll(".llm-card").forEach((card) => {
    const open = () => {
      state.activeId = card.dataset.id;
      const llm = llms.find((l) => l.id === state.activeId);
      if (llm) {
        window.location.hash = llm.slug;
      }
      ui.grid.querySelectorAll(".llm-card").forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      if (onSelect) onSelect();
    };
    card.addEventListener("click", open);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
  });
}

function renderLlmDetail(llm, ui, isCurated) {
  ui.detail.innerHTML = buildLlmDetailHtml(llm, isCurated, false);
}

function buildLlmDetailHtml(llm, isCurated, inModal) {
  const autoRows = (llm.benchmarks?.automated || [])
    .map(
      (b) => `
      <tr>
        <td><span class="eval-type-badge auto">自动</span>${escapeHtml(b.name)}</td>
        <td class="${b.rank === 1 ? "rank-1" : ""}">${b.score}${escapeHtml(b.unit)}</td>
        <td>${b.rank ? "#" + b.rank : "—"}</td>
        <td>${escapeHtml(b.source || "")}</td>
        <td>${escapeHtml(b.updated || "")}</td>
      </tr>`
    )
    .join("");

  const manualRows = (llm.benchmarks?.manual || [])
    .map(
      (b) => `
      <tr>
        <td><span class="eval-type-badge manual">人工</span>${escapeHtml(b.name)}</td>
        <td class="${b.rank === 1 ? "rank-1" : ""}">${b.score}${escapeHtml(b.unit)}</td>
        <td>${b.rank ? "#" + b.rank : "—"}</td>
        <td>${escapeHtml(b.source || "")}</td>
        <td>${escapeHtml(b.note || b.updated || "")}</td>
      </tr>`
    )
    .join("");

  const benchmarkHtml =
    autoRows || manualRows
      ? `<table class="benchmark-table">
        <thead>
          <tr><th>评测集</th><th>分数</th><th>排名</th><th>来源</th><th>备注</th></tr>
        </thead>
        <tbody>${autoRows}${manualRows}</tbody>
      </table>`
      : "<p>暂无评测数据。</p>";

  const sentiment = llm.sentiment;
  const sentimentHtml = sentiment
    ? `<div class="sentiment-card">
        <p><span class="sentiment-stars">${"★".repeat(Math.round(sentiment.score))}${"☆".repeat(sentiment.maxScore - Math.round(sentiment.score))}</span>
        <strong>${sentiment.score}/${sentiment.maxScore}</strong>
        <span class="trend-${sentiment.trend || "stable"}"> · ${sentiment.trend === "rising" ? "↑ 上升" : sentiment.trend === "falling" ? "↓ 下降" : "→ 稳定"}</span>
        <span> · 样本 ${sentiment.sampleSize || "—"} · ${(sentiment.sources || []).join(" / ")}</span></p>
        <p>${escapeHtml(sentiment.summary || "")}</p>
        ${(sentiment.highlights || [])
          .map(
            (h) =>
              `<blockquote class="sentiment-quote ${h.sentiment || ""}"><strong>${escapeHtml(h.source)}:</strong> ${escapeHtml(h.quote)}</blockquote>`
          )
          .join("")}
      </div>`
    : "<p>暂无口碑数据。</p>";

  const pricing = llm.pricing;
  const pricingHtml = pricing
    ? `<div class="pricing-block">
        输入 <strong>$${pricing.input}</strong> / 输出 <strong>$${pricing.output}</strong> ${escapeHtml(pricing.unit || "")}
      </div>`
    : "";

  const availableHtml = (llm.availableIn || []).length
    ? (llm.availableIn || []).map((p) => `<span class="badge">${escapeHtml(p)}</span>`).join(" ")
    : "—";

  const tagsHtml = (llm.tags || []).map((t) => `<span class="badge">${escapeHtml(t)}</span>`).join(" ");

  const useCasesHtml = (llm.useCases || [])
    .map(
      (uc) => `
      <div class="use-case-card">
        <h5>${escapeHtml(uc.title)}</h5>
        <div class="use-case-label">场景</div>
        <p>${escapeHtml(uc.scenario)}</p>
        <div class="use-case-label">示例 Prompt</div>
        <div class="prompt-block">${escapeHtml(uc.prompt)}</div>
        <div class="use-case-label">预期结果</div>
        <p>${escapeHtml(uc.expected)}</p>
      </div>`
    )
    .join("");

  const rankHtml = isCurated
    ? `<span class="llm-rank">SOTA #${llm.rank}</span>`
    : llm.inTopCurated
      ? '<span class="badge featured">已精选</span>'
      : "";

  const contextHtml = llm.contextWindow
    ? `<span class="badge">${(llm.contextWindow / 1000).toFixed(0)}K 上下文</span>`
    : "";

  return `
    <h3>${escapeHtml(llm.displayName)} ${rankHtml}</h3>
    <div class="llm-tags" style="margin-bottom:12px">
      <span class="badge provider-badge">${escapeHtml(llm.provider)}</span>
      ${llm.category ? `<span class="badge category">${escapeHtml(llm.category)}</span>` : ""}
      ${llm.openWeights ? '<span class="badge open-weights">开源权重</span>' : ""}
      ${llm.featured ? '<span class="badge featured">SOTA</span>' : ""}
      ${llm.isNew ? '<span class="badge new">本周新增</span>' : ""}
      ${contextHtml}
    </div>

    <section>
      <h4>简介</h4>
      <p>${escapeHtml(llm.description || "暂无描述。")}</p>
      ${llm.introduction ? `<p>${escapeHtml(llm.introduction)}</p>` : ""}
    </section>

    <section>
      <h4>评测成绩</h4>
      ${benchmarkHtml}
    </section>

    <section>
      <h4>社区口碑</h4>
      ${sentimentHtml}
    </section>

    <section>
      <h4>定价</h4>
      ${pricingHtml || "<p>暂无定价信息。</p>"}
    </section>

    <section>
      <h4>可用产品</h4>
      <div class="llm-tags">${availableHtml}</div>
    </section>

    ${tagsHtml ? `<section><h4>标签</h4><div class="llm-tags">${tagsHtml}</div></section>` : ""}

    ${llm.sourceUrl ? `<p><a href="${escapeHtml(llm.sourceUrl)}" target="_blank" rel="noopener">查看官方文档 →</a></p>` : ""}

    ${isCurated && useCasesHtml ? `<section><h4>使用案例</h4>${useCasesHtml}</section>` : ""}

    ${inModal ? "" : `<p><button type="button" class="tab" id="openModalBtn">全屏查看</button></p>`}
  `;
}

function bindModal(ui) {
  ui.detail.addEventListener("click", (e) => {
    if (e.target.id === "openModalBtn") {
      ui.modalDetail.innerHTML = ui.detail.innerHTML.replace(/<p><button[^]*<\/button><\/p>$/, "");
      openModal(ui);
    }
  });

  ui.modal.querySelectorAll("[data-close]").forEach((el) => {
    el.addEventListener("click", () => closeModal(ui));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !ui.modal.hidden) closeModal(ui);
  });
}

function openModal(ui) {
  ui.modal.hidden = false;
  ui.modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeModal(ui) {
  ui.modal.hidden = true;
  ui.modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const FALLBACK_LLMS = {
  meta: { totalCount: 1, featuredCount: 1, lastUpdated: new Date().toISOString() },
  providers: ["Anthropic"],
  categories: ["代码 Agent"],
  llms: [
    {
      id: "llm-001",
      slug: "claude-sonnet-4",
      displayName: "Claude Sonnet 4",
      provider: "Anthropic",
      rank: 1,
      category: "代码 Agent",
      featured: true,
      description: "Claude 系列性价比之选",
      benchmarks: { automated: [], manual: [] },
      availableIn: ["Cursor"]
    }
  ]
};
