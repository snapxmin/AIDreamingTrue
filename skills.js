(async function init() {
  const [data, indexData, changesData, equivalentsData, primerData, feedbackData] = await Promise.all([
    loadSkills(),
    loadJson("./data/skills-index.json"),
    loadJson("./data/skill-changes.json"),
    loadJson("./data/skill-equivalents.json"),
    loadJson("./data/skill-primer.json"),
    loadJson("./data/skill-feedback.json")
  ]);

  const curatedSkills = data.skills || [];
  const indexSkills = indexData.skills || [];
  const equivalents = equivalentsData.equivalents || [];
  const meta = data.meta || {};

  const ui = {
    meta: document.getElementById("skillsMeta"),
    changesPanel: document.getElementById("skillChangesPanel"),
    changesList: document.getElementById("skillChangesList"),
    changesCount: document.getElementById("changesCount"),
    viewTabs: document.getElementById("viewTabs"),
    platformTabs: document.getElementById("platformTabs"),
    phaseQuickTabs: document.getElementById("phaseQuickTabs"),
    search: document.getElementById("skillSearch"),
    phaseFilter: document.getElementById("phaseFilter"),
    categoryFilter: document.getElementById("categoryFilter"),
    featuredOnly: document.getElementById("featuredOnly"),
    syncInfo: document.getElementById("syncInfo"),
    grid: document.getElementById("skillGrid"),
    count: document.getElementById("skillCount"),
    empty: document.getElementById("emptySkills"),
    detail: document.getElementById("skillDetail"),
    modal: document.getElementById("skillModal"),
    modalDetail: document.getElementById("skillModalDetail")
  };

  const state = {
    view: "curated",
    platform: "all",
    phase: "all",
    category: "all",
    search: "",
    featuredOnly: false,
    activeId: null
  };

  const equivalentByMember = buildEquivalentLookup(equivalents);
  const feedbackBySkill = feedbackData.feedbackBySkill || {};

  hydrateFilters(data, ui);
  renderMeta(meta, data, indexData, ui);
  renderPrimer(primerData);
  renderChanges(changesData, ui);
  renderViewTabs(state, ui, () => rerender());
  renderPlatformTabs(data.platforms || [], state, ui, () => rerender());
  renderPhaseQuickTabs(data.sdePhases || [], state, ui, () => rerender());
  bindFilters(state, ui, () => rerender());
  bindModal(ui);

  state.activeId = resolveInitialSkill(getActivePool(state, curatedSkills, indexSkills));
  rerender();

  window.addEventListener("hashchange", () => {
    const pool = getActivePool(state, curatedSkills, indexSkills);
    const next = resolveInitialSkill(pool);
    if (next !== state.activeId) {
      state.activeId = next;
      rerender();
    }
  });

  function rerender() {
    const pool = getActivePool(state, curatedSkills, indexSkills);
    const filtered = applyFilters(pool, state, state.view === "curated");
    renderSkillGrid(filtered, state, ui, state.view === "curated", rerender, feedbackBySkill);
    const active = filtered.find((s) => s.id === state.activeId) || filtered[0];
    if (active) {
      state.activeId = active.id;
      renderSkillDetail(active, ui, equivalentByMember, state.view === "curated", feedbackBySkill);
    } else {
      ui.detail.innerHTML = "<p>没有匹配的 Skill。</p>";
    }
    ui.count.textContent = `共 ${filtered.length} 个`;
    ui.empty.hidden = filtered.length > 0;
    ui.featuredOnly.closest(".checkbox-row").hidden = state.view !== "curated";
  }
})();

function getActivePool(state, curated, index) {
  if (state.view === "index") return index;
  if (state.view === "new") return index.filter((s) => s.isNew);
  return curated;
}

function buildEquivalentLookup(equivalents) {
  const map = new Map();
  equivalents.forEach((eq) => {
    (eq.members || []).forEach((m) => {
      map.set(`${m.ecosystem}/${m.slug}`, eq);
    });
  });
  return map;
}

function resolveInitialSkill(skills) {
  const hash = window.location.hash.replace("#", "");
  if (hash) {
    const bySlug = skills.find((s) => s.slug === hash);
    if (bySlug) return bySlug.id;
  }
  const featured = skills.find((s) => s.featured);
  return featured ? featured.id : skills[0]?.id;
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

async function loadSkills() {
  try {
    const resp = await fetch("./data/skills.json");
    if (!resp.ok) throw new Error("fetch failed");
    return await resp.json();
  } catch (err) {
    console.warn("skills.json 加载失败，使用内置回退数据", err);
    return FALLBACK_SKILLS;
  }
}

function hydrateFilters(data, ui) {
  (data.sdePhases || []).forEach((phase) => {
    const opt = document.createElement("option");
    opt.value = phase;
    opt.textContent = phase;
    ui.phaseFilter.appendChild(opt);
  });
  (data.categories || []).forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    ui.categoryFilter.appendChild(opt);
  });
}

function renderPrimer(primer) {
  const panel = document.getElementById("skillPrimerPanel");
  const titleEl = document.getElementById("primerTitle");
  const subtitleEl = document.getElementById("primerSubtitle");
  const tabsEl = document.getElementById("primerTabs");
  const contentEl = document.getElementById("primerContent");
  const toggleBtn = document.getElementById("primerToggle");
  const bodyEl = document.getElementById("primerBody");

  if (!panel || !primer.meta) return;

  titleEl.textContent = primer.meta.title || "Skill 第一性原理";
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

  const collapsedKey = "skill-primer-collapsed";
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
        <td>${escapeHtml(row.rules)}</td>
        <td>${escapeHtml(row.prompt)}</td>
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
            <th scope="col">Rules</th>
            <th scope="col">长 Prompt</th>
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
          <span class="badge phase">${escapeHtml(c.industry)}</span>
        </div>
        <p class="primer-meta-line">相关 Skill：<strong>${escapeHtml(c.skill)}</strong></p>
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
  const copilotTotal = discovery["awesome-copilot"]?.totalInRepo || "365+";
  const superpowersTotal = discovery["superpowers"]?.totalInRepo || "14";
  const indexTotal = meta.indexTotalCount || indexData.meta?.totalCount || "—";
  const newCount = meta.newCount || indexData.meta?.newCount || 0;

  ui.meta.innerHTML = `
    <div class="meta-card"><strong>${meta.totalCount || data.skills?.length || 0}</strong><span>策展 Top</span></div>
    <div class="meta-card"><strong>${indexTotal}</strong><span>全量索引</span></div>
    <div class="meta-card"><strong>${newCount}</strong><span>本周新增</span></div>
    <div class="meta-card"><strong>${meta.changesCount ?? 0}</strong><span>近期变更</span></div>
    <div class="meta-card"><strong>${copilotTotal}</strong><span>Copilot 生态</span></div>
    <div class="meta-card"><strong>${superpowersTotal}</strong><span>Superpowers</span></div>
  `;

  const updated = meta.lastUpdated
    ? new Date(meta.lastUpdated).toLocaleString("zh-CN", { hour12: false })
    : "未知";
  ui.syncInfo.innerHTML = `
    <div><strong>Skill 雷达</strong></div>
    <div>最近更新：${escapeHtml(updated)}</div>
    <div>每日自动同步 SKILL.md、检测变更并更新全量索引。</div>
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
      const badgeClass = c.type === "added" ? "badge featured" : "badge phase";
      return `
        <li class="change-item">
          <span class="${badgeClass}">${badge}</span>
          <a href="#${escapeHtml(c.slug)}" class="change-link">${escapeHtml(c.displayName || c.slug)}</a>
          <span class="change-eco">${escapeHtml(c.ecosystem)}</span>
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

function renderPhaseQuickTabs(phases, state, ui, onChange) {
  const tabs = [{ id: "all", label: "全部" }, ...phases.map((p) => ({ id: p, label: p }))];
  ui.phaseQuickTabs.innerHTML = tabs
    .map(
      (tab) =>
        `<button type="button" class="tab${state.phase === tab.id ? " active" : ""}" data-phase="${escapeHtml(tab.id)}">${escapeHtml(tab.label)}</button>`
    )
    .join("");

  ui.phaseQuickTabs.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.phase = btn.dataset.phase;
      ui.phaseFilter.value = state.phase;
      ui.phaseQuickTabs.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
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
  ui.phaseFilter.addEventListener("change", () => {
    state.phase = ui.phaseFilter.value;
    ui.phaseQuickTabs.querySelectorAll(".tab").forEach((b) => {
      b.classList.toggle("active", b.dataset.phase === state.phase);
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

function applyFilters(skills, state, isCurated) {
  return skills.filter((skill) => {
    if (!skillMatchesPlatform(skill, state.platform)) return false;
    if (isCurated && state.phase !== "all" && skill.sdePhase !== state.phase) return false;
    if (isCurated && state.category !== "all" && skill.category !== state.category) return false;
    if (isCurated && state.featuredOnly && !skill.featured) return false;
    if (state.search) {
      const haystack = [
        skill.displayName,
        skill.slug,
        skill.description,
        skill.introduction,
        skill.platform,
        skill.ecosystem,
        ...(skill.platforms || []),
        skill.sdePhase,
        skill.category,
        ...(skill.tags || [])
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
  if (platform.includes("Codex")) return "platform-codex";
  if (platform.includes("OpenCode")) return "platform-opencode";
  return "platform-default";
}

function skillMatchesPlatform(skill, platformFilter) {
  if (platformFilter === "all") return true;
  const all = skill.platforms || [skill.platform];
  return all.includes(platformFilter) || skill.platform === platformFilter;
}

function renderPlatformBadges(skill) {
  const platforms = skill.platforms || [skill.platform];
  return platforms
    .filter(Boolean)
    .map((p) => `<span class="badge ${platformBadgeClass(p)}">${escapeHtml(p)}</span>`)
    .join("");
}

function renderSkillGrid(skills, state, ui, isCurated, onSelect, feedbackBySkill) {
  ui.grid.innerHTML = skills
    .map((skill) => {
      const rankLabel = isCurated
        ? `#${skill.rank}`
        : skill.activityScore != null
          ? `活跃 ${skill.activityScore}`
          : "";
      const fbCount = isCurated
        ? (feedbackBySkill?.[`${skill.ecosystem}/${skill.slug}`]?.feedbackCount || 0)
        : 0;
      const extraBadges = [
        skill.featured ? '<span class="badge featured">精选</span>' : "",
        skill.isNew ? '<span class="badge new">新</span>' : "",
        skill.inTopCurated ? '<span class="badge phase">Top</span>' : "",
        fbCount > 0 ? `<span class="badge feedback">${fbCount} 反馈</span>` : ""
      ].join("");
      const phaseBadge = skill.sdePhase
        ? `<span class="badge phase">${escapeHtml(skill.sdePhase)}</span>`
        : "";

      return `
        <article class="skill-card${skill.id === state.activeId ? " active" : ""}" role="listitem" data-id="${escapeHtml(skill.id)}" tabindex="0">
          <div class="skill-card-header">
            <h3>${escapeHtml(skill.displayName)}</h3>
            ${rankLabel ? `<span class="skill-rank">${escapeHtml(rankLabel)}</span>` : ""}
          </div>
          <p class="skill-desc">${escapeHtml(skill.description || skill.introduction || "")}</p>
          <div class="skill-tags">
            ${renderPlatformBadges(skill)}
            ${phaseBadge}
            ${extraBadges}
          </div>
        </article>`;
    })
    .join("");

  ui.grid.querySelectorAll(".skill-card").forEach((card) => {
    const open = () => {
      state.activeId = card.dataset.id;
      const skill = skills.find((s) => s.id === state.activeId);
      if (skill) {
        window.location.hash = skill.slug;
      }
      ui.grid.querySelectorAll(".skill-card").forEach((c) => c.classList.remove("active"));
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

function renderSkillDetail(skill, ui, equivalentByMember, isCurated, feedbackBySkill) {
  ui.detail.innerHTML = buildSkillDetailHtml(skill, equivalentByMember, isCurated, feedbackBySkill, false);
}

function buildFeedbackHtml(skill, feedbackBySkill) {
  const key = `${skill.ecosystem}/${skill.slug}`;
  const entry = feedbackBySkill[key];
  const comments = entry?.comments || [];
  if (!comments.length) {
    return `<section class="feedback-section"><h4>用户反馈</h4><p class="feedback-empty">暂无匹配的公开讨论。采集来源：Hacker News、GitHub Issues、Reddit。</p></section>`;
  }

  const cards = comments
    .map((c) => {
      const sentimentClass = c.sentiment === "positive" ? "sentiment-pos" : c.sentiment === "negative" ? "sentiment-neg" : "sentiment-neu";
      const sentimentLabel = c.sentiment === "positive" ? "正面" : c.sentiment === "negative" ? "负面" : "中性";
      const scoreLabel = c.score ? ` · ${c.score} 赞` : "";
      return `
        <article class="feedback-card">
          <div class="feedback-meta">
            <span class="feedback-source">${escapeHtml(c.sourceLabel || c.source)}</span>
            <span class="feedback-author">@${escapeHtml(c.author)}</span>
            <span class="feedback-date">${escapeHtml(c.date || "")}${scoreLabel}</span>
            <span class="feedback-sentiment ${sentimentClass}">${sentimentLabel}</span>
          </div>
          <p class="feedback-text">${escapeHtml(c.text)}</p>
          <a class="feedback-link" href="${escapeHtml(c.url)}" target="_blank" rel="noopener">查看原文 →</a>
        </article>`;
    })
    .join("");

  return `
    <section class="feedback-section">
      <h4>用户反馈 <span class="feedback-count">${comments.length} 条</span></h4>
      <p class="feedback-note">来自 Hacker News、GitHub Issues、Reddit 的公开讨论，按相关性与热度自动筛选。</p>
      <div class="feedback-list">${cards}</div>
    </section>`;
}

function buildSkillDetailHtml(skill, equivalentByMember, isCurated, feedbackBySkill, inModal) {
  const useCasesHtml = (skill.useCases || [])
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

  const tagsHtml = (skill.tags || []).map((t) => `<span class="badge">${escapeHtml(t)}</span>`).join(" ");

  const eq = equivalentByMember.get(`${skill.ecosystem}/${skill.slug}`);
  const equivalentsHtml = eq
    ? `<section><h4>同类能力（${escapeHtml(eq.label)}）</h4><ul>${eq.members
        .filter((m) => !(m.ecosystem === skill.ecosystem && m.slug === skill.slug))
        .map(
          (m) =>
            `<li><a href="#${escapeHtml(m.slug)}">${escapeHtml(m.platform)} · ${escapeHtml(m.slug)}</a></li>`
        )
        .join("")}</ul></section>`
    : "";

  const eventsHtml = (skill.relatedEvents || []).length
    ? `<section><h4>相关动态</h4><ul>${skill.relatedEvents
        .map(
          (e) =>
            `<li><a href="./index.html">${escapeHtml(e.eventDate)} · ${escapeHtml(e.eventTitle)}</a></li>`
        )
        .join("")}</ul></section>`
    : "";

  const scoreHtml =
    skill.activityScore != null
      ? `<span class="badge">活跃度 ${skill.activityScore}</span><span class="badge">活跃排名 #${skill.activityRank || "—"}</span>`
      : "";

  const rankHtml = isCurated
    ? `<span class="skill-rank">编辑推荐 #${skill.rank}</span>`
    : skill.inTopCurated
      ? '<span class="badge featured">已策展</span>'
      : "";

  return `
    <h3>${escapeHtml(skill.displayName)} ${rankHtml}</h3>
    <div class="skill-tags" style="margin-bottom:12px">
      ${renderPlatformBadges(skill)}
      ${skill.sdePhase ? `<span class="badge phase">${escapeHtml(skill.sdePhase)}</span>` : ""}
      ${skill.category ? `<span class="badge">${escapeHtml(skill.category)}</span>` : ""}
      ${skill.featured ? '<span class="badge featured">精选</span>' : ""}
      ${skill.remoteSynced ? '<span class="badge a">已同步远程</span>' : ""}
      ${skill.isNew ? '<span class="badge new">本周新增</span>' : ""}
      ${scoreHtml}
    </div>

    <section>
      <h4>简介</h4>
      <p>${escapeHtml(skill.description || "暂无远程描述。")}</p>
    </section>

    ${skill.introduction ? `<section><h4>详细介绍</h4><p>${escapeHtml(skill.introduction)}</p></section>` : ""}

    <section>
      <h4>安装方式</h4>
      <pre class="install-block">${escapeHtml(skill.installCommand || "见源码仓库")}</pre>
      ${skill.sourceUrl ? `<p><a href="${escapeHtml(skill.sourceUrl)}" target="_blank" rel="noopener">查看源码 →</a></p>` : ""}
    </section>

    ${tagsHtml ? `<section><h4>标签</h4><div class="skill-tags">${tagsHtml}</div></section>` : ""}

    ${isCurated ? `<section><h4>使用案例</h4>${useCasesHtml || "<p>暂无案例。</p>"}</section>` : ""}

    ${isCurated ? buildFeedbackHtml(skill, feedbackBySkill || {}) : ""}

    ${equivalentsHtml}
    ${eventsHtml}

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

const FALLBACK_SKILLS = {
  meta: { totalCount: 2, featuredCount: 2, lastUpdated: new Date().toISOString() },
  sdePhases: ["环境准备", "实现"],
  platforms: ["GitHub Copilot", "Cursor"],
  categories: ["仓库初始化", "测试驱动"],
  skills: [
    {
      id: "skill-001",
      slug: "ai-ready",
      displayName: "AI Ready",
      platform: "GitHub Copilot",
      ecosystem: "awesome-copilot",
      rank: 1,
      sdePhase: "环境准备",
      category: "仓库初始化",
      featured: true,
      description: "Make any repo AI-ready",
      introduction: "将代码仓库配置为 AI 友好形态。",
      installCommand: "gh skill install github/awesome-copilot ai-ready",
      sourceUrl: "https://github.com/github/awesome-copilot/tree/main/skills/ai-ready",
      tags: ["AGENTS.md"],
      useCases: [],
      remoteSynced: false
    }
  ]
};
