(async function init() {
  const data = await loadSkills();
  const skills = data.skills || [];
  const meta = data.meta || {};

  const ui = {
    meta: document.getElementById("skillsMeta"),
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
    platform: "all",
    phase: "all",
    category: "all",
    search: "",
    featuredOnly: false,
    activeId: resolveInitialSkill(skills)
  };

  hydrateFilters(data, ui);
  renderMeta(meta, data, ui);
  renderPlatformTabs(data.platforms || [], state, ui, () => rerender());
  renderPhaseQuickTabs(data.sdePhases || [], state, ui, () => rerender());
  bindFilters(state, ui, () => rerender());
  bindModal(ui);
  rerender();

  function rerender() {
    const filtered = applyFilters(skills, state);
    renderSkillGrid(filtered, state, ui);
    const active = filtered.find((s) => s.id === state.activeId) || filtered[0];
    if (active) {
      state.activeId = active.id;
      renderSkillDetail(active, ui);
    } else {
      ui.detail.innerHTML = "<p>没有匹配的 Skill。</p>";
    }
    ui.count.textContent = `共 ${filtered.length} 个`;
    ui.empty.hidden = filtered.length > 0;
  }

  window.addEventListener("hashchange", () => {
    const next = resolveInitialSkill(skills);
    if (next !== state.activeId) {
      state.activeId = next;
      rerender();
    }
  });
})();

function resolveInitialSkill(skills) {
  const hash = window.location.hash.replace("#", "");
  if (hash) {
    const bySlug = skills.find((s) => s.slug === hash);
    if (bySlug) return bySlug.id;
  }
  const featured = skills.find((s) => s.featured);
  return featured ? featured.id : skills[0]?.id;
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

function renderMeta(meta, data, ui) {
  const discovery = meta.discovery || {};
  const copilotTotal = discovery["awesome-copilot"]?.totalInRepo || "365+";
  const cursorTotal = discovery["cursor-superpowers"]?.totalInRepo || "14";

  ui.meta.innerHTML = `
    <div class="meta-card"><strong>${meta.totalCount || data.skills?.length || 0}</strong><span>策展 Top Skills</span></div>
    <div class="meta-card"><strong>${meta.featuredCount || 0}</strong><span>精选推荐</span></div>
    <div class="meta-card"><strong>${copilotTotal}</strong><span>GitHub Copilot 生态</span></div>
    <div class="meta-card"><strong>${cursorTotal}</strong><span>Cursor Superpowers</span></div>
  `;

  const updated = meta.lastUpdated
    ? new Date(meta.lastUpdated).toLocaleString("zh-CN", { hour12: false })
    : "未知";
  ui.syncInfo.innerHTML = `
    <div><strong>自动同步</strong></div>
    <div>最近更新：${escapeHtml(updated)}</div>
    <div>每日 08:30（北京时间）由 GitHub Actions 抓取远程 SKILL.md 并部署门户。</div>
  `;
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

function applyFilters(skills, state) {
  return skills.filter((skill) => {
    if (!skillMatchesPlatform(skill, state.platform)) return false;
    if (state.phase !== "all" && skill.sdePhase !== state.phase) return false;
    if (state.category !== "all" && skill.category !== state.category) return false;
    if (state.featuredOnly && !skill.featured) return false;
    if (state.search) {
      const haystack = [
        skill.displayName,
        skill.slug,
        skill.description,
        skill.introduction,
        skill.platform,
        ...(skill.platforms || []),
        skill.sdePhase,
        skill.category,
        ...(skill.tags || [])
      ]
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
    .map((p) => `<span class="badge ${platformBadgeClass(p)}">${escapeHtml(p)}</span>`)
    .join("");
}
function renderSkillGrid(skills, state, ui) {
  ui.grid.innerHTML = skills
    .map((skill) => {
      return `
        <article class="skill-card${skill.id === state.activeId ? " active" : ""}" role="listitem" data-id="${escapeHtml(skill.id)}" tabindex="0">
          <div class="skill-card-header">
            <h3>${escapeHtml(skill.displayName)}</h3>
            <span class="skill-rank">#${skill.rank}</span>
          </div>
          <p class="skill-desc">${escapeHtml(skill.description || skill.introduction || "")}</p>
          <div class="skill-tags">
            ${renderPlatformBadges(skill)}
            <span class="badge phase">${escapeHtml(skill.sdePhase)}</span>
            ${skill.featured ? '<span class="badge featured">精选</span>' : ""}
          </div>
        </article>
      `;
    })
    .join("");

  ui.grid.querySelectorAll(".skill-card").forEach((card) => {
    const open = () => {
      state.activeId = card.dataset.id;
      const skill = skills.find((s) => s.id === state.activeId);
      if (skill) {
        window.location.hash = skill.slug;
        renderSkillDetail(skill, ui);
      }
      ui.grid.querySelectorAll(".skill-card").forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
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

function renderSkillDetail(skill, ui) {
  ui.detail.innerHTML = buildSkillDetailHtml(skill, false);
}

function buildSkillDetailHtml(skill, inModal) {
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
      </div>
    `
    )
    .join("");

  const tagsHtml = (skill.tags || []).map((t) => `<span class="badge">${escapeHtml(t)}</span>`).join(" ");

  return `
    <h3>${escapeHtml(skill.displayName)} <span class="skill-rank">#${skill.rank}</span></h3>
    <div class="skill-tags" style="margin-bottom:12px">
      ${renderPlatformBadges(skill)}
      <span class="badge phase">${escapeHtml(skill.sdePhase)}</span>
      <span class="badge">${escapeHtml(skill.category)}</span>
      ${skill.featured ? '<span class="badge featured">精选</span>' : ""}
      ${skill.remoteSynced ? '<span class="badge a">已同步远程</span>' : ""}
    </div>

    <section>
      <h4>简介</h4>
      <p>${escapeHtml(skill.description || "")}</p>
    </section>

    <section>
      <h4>详细介绍</h4>
      <p>${escapeHtml(skill.introduction || "")}</p>
    </section>

    <section>
      <h4>安装方式</h4>
      <pre class="install-block">${escapeHtml(skill.installCommand || "")}</pre>
      ${skill.sourceUrl ? `<p><a href="${escapeHtml(skill.sourceUrl)}" target="_blank" rel="noopener">查看源码 →</a></p>` : ""}
    </section>

    <section>
      <h4>标签</h4>
      <div class="skill-tags">${tagsHtml}</div>
    </section>

    <section>
      <h4>使用案例</h4>
      ${useCasesHtml || "<p>暂无案例。</p>"}
    </section>

    ${inModal ? "" : `<p><button type="button" class="tab" id="openModalBtn">全屏查看</button></p>`}
  `;
}

function bindModal(ui) {
  ui.detail.addEventListener("click", (e) => {
    if (e.target.id === "openModalBtn") {
      const html = ui.detail.innerHTML.replace(/<p><button[^]*<\/button><\/p>$/, "");
      ui.modalDetail.innerHTML = html;
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
      rank: 1,
      sdePhase: "环境准备",
      category: "仓库初始化",
      featured: true,
      description: "Make any repo AI-ready",
      introduction: "将代码仓库配置为 AI 友好形态。",
      installCommand: "gh skill install github/awesome-copilot ai-ready",
      sourceUrl: "https://github.com/github/awesome-copilot/tree/main/skills/ai-ready",
      tags: ["AGENTS.md"],
      useCases: [
        {
          title: "新项目 AI 化",
          scenario: "接入 Copilot Agent",
          prompt: "make this repo ai-ready",
          expected: "生成 AGENTS.md"
        }
      ],
      remoteSynced: false
    },
    {
      id: "skill-006",
      slug: "test-driven-development",
      displayName: "Test-Driven Development",
      platform: "Cursor",
      rank: 6,
      sdePhase: "实现",
      category: "测试驱动",
      featured: true,
      description: "Red-green-refactor TDD workflow",
      introduction: "强制执行测试驱动开发循环。",
      installCommand: "Cursor Plugin: superpowers",
      sourceUrl: "https://github.com/obra/superpowers/tree/main/skills/test-driven-development",
      tags: ["TDD"],
      useCases: [],
      remoteSynced: false
    }
  ]
};
