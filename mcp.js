(async function init() {
  const [data, indexData, changesData, primerData] = await Promise.all([
    loadMcps(),
    loadJson("./data/mcps-index.json"),
    loadJson("./data/mcp-changes.json"),
    loadJson("./data/mcp-primer.json")
  ]);

  const curatedMcps = data.mcps || [];
  const indexMcps = indexData.mcps || [];
  const meta = data.meta || {};

  const ui = {
    meta: document.getElementById("mcpsMeta"),
    changesPanel: document.getElementById("mcpChangesPanel"),
    changesList: document.getElementById("mcpChangesList"),
    changesCount: document.getElementById("changesCount"),
    viewTabs: document.getElementById("viewTabs"),
    platformTabs: document.getElementById("platformTabs"),
    transportQuickTabs: document.getElementById("transportQuickTabs"),
    search: document.getElementById("mcpSearch"),
    transportFilter: document.getElementById("transportFilter"),
    categoryFilter: document.getElementById("categoryFilter"),
    featuredOnly: document.getElementById("featuredOnly"),
    syncInfo: document.getElementById("syncInfo"),
    grid: document.getElementById("mcpGrid"),
    count: document.getElementById("mcpCount"),
    empty: document.getElementById("emptyMcps"),
    detail: document.getElementById("mcpDetail"),
    modal: document.getElementById("mcpModal"),
    modalDetail: document.getElementById("mcpModalDetail")
  };

  const state = {
    view: "curated",
    platform: "all",
    transport: "all",
    category: "all",
    search: "",
    featuredOnly: false,
    activeId: null
  };

  hydrateFilters(data, ui);
  renderMeta(meta, data, indexData, ui);
  renderPrimer(primerData);
  renderChanges(changesData, ui);
  renderViewTabs(state, ui, () => rerender());
  renderPlatformTabs(data.platforms || [], state, ui, () => rerender());
  renderTransportQuickTabs(data.transports || [], state, ui, () => rerender());
  bindFilters(state, ui, () => rerender());
  bindModal(ui);

  state.activeId = resolveInitialMcp(getActivePool(state, curatedMcps, indexMcps));
  rerender();

  window.addEventListener("hashchange", () => {
    const pool = getActivePool(state, curatedMcps, indexMcps);
    const next = resolveInitialMcp(pool);
    if (next !== state.activeId) {
      state.activeId = next;
      rerender();
    }
  });

  function rerender() {
    const pool = getActivePool(state, curatedMcps, indexMcps);
    const filtered = applyFilters(pool, state, state.view === "curated");
    renderMcpGrid(filtered, state, ui, state.view === "curated", rerender);
    const active = filtered.find((m) => m.id === state.activeId) || filtered[0];
    if (active) {
      state.activeId = active.id;
      renderMcpDetail(active, ui, state.view === "curated");
    } else {
      ui.detail.innerHTML = "<p>没有匹配的 MCP Server。</p>";
    }
    ui.count.textContent = `共 ${filtered.length} 个`;
    ui.empty.hidden = filtered.length > 0;
    ui.featuredOnly.closest(".checkbox-row").hidden = state.view !== "curated";
  }
})();

function getActivePool(state, curated, index) {
  if (state.view === "index") return index;
  if (state.view === "new") return index.filter((m) => m.isNew);
  return curated;
}

function resolveInitialMcp(mcps) {
  const hash = window.location.hash.replace("#", "");
  if (hash) {
    const bySlug = mcps.find((m) => m.slug === hash);
    if (bySlug) return bySlug.id;
  }
  const featured = mcps.find((m) => m.featured);
  return featured ? featured.id : mcps[0]?.id;
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

async function loadMcps() {
  try {
    const resp = await fetch("./data/mcps.json");
    if (!resp.ok) throw new Error("fetch failed");
    return await resp.json();
  } catch (err) {
    console.warn("mcps.json 加载失败，使用内置回退数据", err);
    return FALLBACK_MCPS;
  }
}

function hydrateFilters(data, ui) {
  (data.transports || []).forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    ui.transportFilter.appendChild(opt);
  });
  (data.categories || []).forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    ui.categoryFilter.appendChild(opt);
  });
}

function renderPrimer(primer) {
  const panel = document.getElementById("mcpPrimerPanel");
  const titleEl = document.getElementById("primerTitle");
  const subtitleEl = document.getElementById("primerSubtitle");
  const tabsEl = document.getElementById("primerTabs");
  const contentEl = document.getElementById("primerContent");
  const toggleBtn = document.getElementById("primerToggle");
  const bodyEl = document.getElementById("primerBody");

  if (!panel || !primer.meta) return;

  titleEl.textContent = primer.meta.title || "MCP 第一性原理";
  subtitleEl.textContent = primer.meta.subtitle || "";

  const sections = [
    { id: "essence", label: "本质与原理", render: () => renderEssenceSection(primer.essence) },
    { id: "value", label: "产品价值", render: () => renderValueSection(primer.value) },
    { id: "adoption", label: "业界落地", render: () => renderAdoptionSection(primer.adoption) },
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

  const collapsedKey = "mcp-primer-collapsed";
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
        <td>${escapeHtml(row.skill)}</td>
        <td>${escapeHtml(row.mcp)}</td>
        <td>${escapeHtml(row.plugin)}</td>
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
            <th scope="col">Skill</th>
            <th scope="col">MCP</th>
            <th scope="col">Plugin</th>
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
        <p class="primer-meta-line">相关 MCP：<strong>${escapeHtml(c.server)}</strong></p>
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
    <h4>四大生态</h4>
    <div class="primer-grid primer-grid-2">${ecoHtml}</div>
    <h4>关键里程碑</h4>
    <ul class="primer-milestone-list">${milestonesHtml}</ul>
    <h4>典型落地案例</h4>
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
  const officialTotal = discovery["official-servers"]?.totalInRepo || "15";
  const communityTotal = discovery["community"]?.totalInRepo || "500+";
  const indexTotal = meta.indexTotalCount || indexData.meta?.totalCount || "—";
  const newCount = meta.newCount || indexData.meta?.newCount || 0;

  ui.meta.innerHTML = `
    <div class="meta-card"><strong>${meta.totalCount || data.mcps?.length || 0}</strong><span>策展 Top</span></div>
    <div class="meta-card"><strong>${indexTotal}</strong><span>全量索引</span></div>
    <div class="meta-card"><strong>${newCount}</strong><span>本周新增</span></div>
    <div class="meta-card"><strong>${meta.changesCount ?? 0}</strong><span>近期变更</span></div>
    <div class="meta-card"><strong>${officialTotal}</strong><span>官方 Reference</span></div>
    <div class="meta-card"><strong>${communityTotal}</strong><span>社区生态</span></div>
  `;

  const updated = meta.lastUpdated
    ? new Date(meta.lastUpdated).toLocaleString("zh-CN", { hour12: false })
    : "未知";
  ui.syncInfo.innerHTML = `
    <div><strong>MCP 雷达</strong></div>
    <div>最近更新：${escapeHtml(updated)}</div>
    <div>每周自动同步 MCP Server 元数据、检测变更并更新全量索引。</div>
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
          <span class="change-eco">${escapeHtml(c.source || "")}</span>
          <p>${escapeHtml(c.summary || "")}</p>
        </li>`;
    })
    .join("");
}

function renderViewTabs(state, ui, onChange) {
  const tabs = [
    { id: "curated", label: "精选 Top 20" },
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

function renderPlatformTabs(platforms, state, ui, onChange) {
  const tabs = [{ id: "all", label: "全部平台" }, ...platforms.map((p) => ({ id: p, label: p }))];
  ui.platformTabs.innerHTML = tabs
    .map(
      (tab) =>
        `<button type="button" class="platform-tab${state.platform === tab.id ? " active" : ""}" data-platform="${escapeHtml(tab.id)}">${escapeHtml(tab.label)}</button>`
    )
    .join("");

  ui.platformTabs.querySelectorAll(".platform-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.platform = btn.dataset.platform;
      ui.platformTabs.querySelectorAll(".platform-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange();
    });
  });
}

function renderTransportQuickTabs(transports, state, ui, onChange) {
  const tabs = [{ id: "all", label: "全部" }, ...transports.map((t) => ({ id: t, label: t }))];
  ui.transportQuickTabs.innerHTML = tabs
    .map(
      (tab) =>
        `<button type="button" class="tab${state.transport === tab.id ? " active" : ""}" data-transport="${escapeHtml(tab.id)}">${escapeHtml(tab.label)}</button>`
    )
    .join("");

  ui.transportQuickTabs.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.transport = btn.dataset.transport;
      ui.transportFilter.value = state.transport;
      ui.transportQuickTabs.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
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
  ui.transportFilter.addEventListener("change", () => {
    state.transport = ui.transportFilter.value;
    ui.transportQuickTabs.querySelectorAll(".tab").forEach((b) => {
      b.classList.toggle("active", b.dataset.transport === state.transport);
    });
    onChange();
  });
  ui.categoryFilter.addEventListener("change", () => {
    state.category = ui.categoryFilter.value;
    onChange();
  });
  ui.featuredOnly.addEventListener("change", () => {
    state.featuredOnly = ui.featuredOnly.checked;
    onChange();
  });
}

function applyFilters(mcps, state, isCurated) {
  return mcps.filter((mcp) => {
    if (!mcpMatchesPlatform(mcp, state.platform)) return false;
    if (isCurated && state.transport !== "all" && mcp.transport !== state.transport) return false;
    if (isCurated && state.category !== "all" && mcp.category !== state.category) return false;
    if (isCurated && state.featuredOnly && !mcp.featured) return false;
    if (state.search) {
      const haystack = [
        mcp.displayName,
        mcp.slug,
        mcp.description,
        mcp.introduction,
        mcp.platform,
        mcp.source,
        mcp.transport,
        mcp.category,
        mcp.authType,
        ...(mcp.platforms || []),
        ...(mcp.tags || []),
        ...(mcp.tools || [])
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(state.search)) return false;
    }
    return true;
  });
}

function platformBadgeClass(platform) {
  if (!platform) return "platform-default";
  if (platform.includes("Cursor")) return "platform-cursor";
  if (platform.includes("Copilot")) return "platform-copilot";
  if (platform.includes("Claude")) return "platform-claude";
  if (platform.includes("VS Code")) return "platform-codex";
  if (platform.includes("Windsurf")) return "platform-opencode";
  return "platform-default";
}

function transportBadgeClass(transport) {
  if (transport === "stdio") return "transport-stdio";
  if (transport === "streamable-http") return "transport-http";
  return "transport-stdio";
}

function mcpMatchesPlatform(mcp, platformFilter) {
  if (platformFilter === "all") return true;
  const all = mcp.platforms || [mcp.platform];
  return all.includes(platformFilter) || mcp.platform === platformFilter;
}

function renderPlatformBadges(mcp) {
  const platforms = mcp.platforms || [mcp.platform];
  return platforms
    .filter(Boolean)
    .map((p) => `<span class="badge ${platformBadgeClass(p)}">${escapeHtml(p)}</span>`)
    .join("");
}

function renderMcpGrid(mcps, state, ui, isCurated, onSelect) {
  ui.grid.innerHTML = mcps
    .map((mcp) => {
      const rankLabel = isCurated
        ? `#${mcp.rank}`
        : mcp.activityScore != null
          ? `活跃 ${mcp.activityScore}`
          : "";
      const extraBadges = [
        mcp.featured ? '<span class="badge featured">精选</span>' : "",
        mcp.isNew ? '<span class="badge new">新</span>' : "",
        mcp.inTopCurated ? '<span class="badge category">Top</span>' : ""
      ].join("");
      const transportBadge = mcp.transport
        ? `<span class="badge ${transportBadgeClass(mcp.transport)}">${escapeHtml(mcp.transport)}</span>`
        : "";
      const categoryBadge = mcp.category
        ? `<span class="badge category">${escapeHtml(mcp.category)}</span>`
        : "";
      const toolsBadge = mcp.toolCount
        ? `<span class="badge tools">${mcp.toolCount} tools</span>`
        : "";

      return `
        <article class="mcp-card${mcp.id === state.activeId ? " active" : ""}" role="listitem" data-id="${escapeHtml(mcp.id)}" tabindex="0">
          <div class="mcp-card-header">
            <h3>${escapeHtml(mcp.displayName)}</h3>
            ${rankLabel ? `<span class="mcp-rank">${escapeHtml(rankLabel)}</span>` : ""}
          </div>
          <p class="mcp-desc">${escapeHtml(mcp.description || mcp.introduction || "")}</p>
          <div class="mcp-tags">
            ${renderPlatformBadges(mcp)}
            ${transportBadge}
            ${categoryBadge}
            ${toolsBadge}
            ${extraBadges}
          </div>
        </article>`;
    })
    .join("");

  ui.grid.querySelectorAll(".mcp-card").forEach((card) => {
    const open = () => {
      state.activeId = card.dataset.id;
      const mcp = mcps.find((m) => m.id === state.activeId);
      if (mcp) {
        window.location.hash = mcp.slug;
      }
      ui.grid.querySelectorAll(".mcp-card").forEach((c) => c.classList.remove("active"));
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

function renderMcpDetail(mcp, ui, isCurated) {
  ui.detail.innerHTML = buildMcpDetailHtml(mcp, isCurated, false);
}

function buildMcpDetailHtml(mcp, isCurated, inModal) {
  const useCasesHtml = (mcp.useCases || [])
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

  const tagsHtml = (mcp.tags || []).map((t) => `<span class="badge">${escapeHtml(t)}</span>`).join(" ");

  const toolsHtml = (mcp.tools || []).length
    ? `<div class="tools-list">${(mcp.tools || []).map((t) => `<span class="tool-chip">${escapeHtml(t)}</span>`).join("")}</div>`
    : `<p>${mcp.toolCount ? `约 ${mcp.toolCount} 个 tools` : "暂无工具清单。"}</p>`;

  const scoreHtml =
    mcp.activityScore != null
      ? `<span class="badge">活跃度 ${mcp.activityScore}</span><span class="badge">活跃排名 #${mcp.activityRank || "—"}</span>`
      : "";

  const rankHtml = isCurated
    ? `<span class="mcp-rank">编辑推荐 #${mcp.rank}</span>`
    : mcp.inTopCurated
      ? '<span class="badge featured">已策展</span>'
      : "";

  return `
    <h3>${escapeHtml(mcp.displayName)} ${rankHtml}</h3>
    <div class="mcp-tags" style="margin-bottom:12px">
      ${renderPlatformBadges(mcp)}
      ${mcp.transport ? `<span class="badge ${transportBadgeClass(mcp.transport)}">${escapeHtml(mcp.transport)}</span>` : ""}
      ${mcp.category ? `<span class="badge category">${escapeHtml(mcp.category)}</span>` : ""}
      ${mcp.authType ? `<span class="badge">${escapeHtml(mcp.authType)}</span>` : ""}
      ${mcp.featured ? '<span class="badge featured">精选</span>' : ""}
      ${mcp.isNew ? '<span class="badge new">本周新增</span>' : ""}
      ${scoreHtml}
    </div>

    <section>
      <h4>简介</h4>
      <p>${escapeHtml(mcp.description || "暂无描述。")}</p>
    </section>

    ${mcp.introduction ? `<section><h4>详细介绍</h4><p>${escapeHtml(mcp.introduction)}</p></section>` : ""}

    <section>
      <h4>Host 配置示例</h4>
      <pre class="config-block">${escapeHtml(mcp.configSnippet || "见源码仓库文档")}</pre>
      ${mcp.sourceUrl ? `<p><a href="${escapeHtml(mcp.sourceUrl)}" target="_blank" rel="noopener">查看源码 / 文档 →</a></p>` : ""}
    </section>

    <section>
      <h4>Tools 清单</h4>
      ${toolsHtml}
    </section>

    ${tagsHtml ? `<section><h4>标签</h4><div class="mcp-tags">${tagsHtml}</div></section>` : ""}

    ${isCurated ? `<section><h4>使用案例</h4>${useCasesHtml || "<p>暂无案例。</p>"}</section>` : ""}

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

const FALLBACK_MCPS = {
  meta: { totalCount: 1, featuredCount: 1, lastUpdated: new Date().toISOString() },
  transports: ["stdio"],
  platforms: ["Cursor"],
  categories: ["DevTools"],
  mcps: [
    {
      id: "mcp-001",
      slug: "github",
      displayName: "GitHub MCP",
      platform: "Cursor",
      platforms: ["Cursor"],
      source: "official-servers",
      rank: 1,
      category: "DevTools",
      transport: "stdio",
      authType: "PAT",
      featured: true,
      description: "GitHub 仓库集成 MCP Server",
      configSnippet: '{ "mcpServers": { "github": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"] } } }',
      sourceUrl: "https://github.com/modelcontextprotocol/servers",
      tools: ["create_issue", "search_code"],
      toolCount: 2,
      useCases: []
    }
  ]
};
