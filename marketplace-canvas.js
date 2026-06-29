(function () {
  "use strict";

  const CATEGORY_COLORS = {
    FEATURED: "purple",
    INFRASTRUCTURE: "tag",
    DATA_ANALYTICS: "tag",
    PRODUCTIVITY: "green",
    PAYMENTS: "orange",
    AGENT_ORCHESTRATION: "purple",
    CANVAS: "purple",
    UNCATEGORIZED: "tag",
  };

  const PRIMITIVE_DESC = {
    skills: "领域知识包（SKILL.md），Agent 按需加载执行特定工作流",
    mcpServers: "Model Context Protocol 服务，连接外部 API / SaaS",
    rules: "持久化编码规则（.mdc），影响 Agent 行为与代码风格",
    hooks: "生命周期脚本，在 Agent 动作前后触发",
    commands: "可显式调用的斜杠命令",
    subagents: "专用子 Agent，处理特定子任务",
  };

  let report = null;

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (k === "className") node.className = v;
        else if (k === "textContent") node.textContent = v;
        else if (k === "innerHTML") node.innerHTML = v;
        else node.setAttribute(k, v);
      });
    }
    (children || []).forEach((child) => {
      if (typeof child === "string") node.appendChild(document.createTextNode(child));
      else if (child) node.appendChild(child);
    });
    return node;
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
  }

  function renderStats() {
    const meta = report.meta;
    const totals = report.componentTotals || {};
    return el("div", { className: "stat-grid" }, [
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(meta.pluginCount) }),
        el("div", { className: "label", textContent: "插件总数" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(meta.automationCount) }),
        el("div", { className: "label", textContent: "自动化工作流" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(meta.detailsFetched) }),
        el("div", { className: "label", textContent: "已解析详情" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(totals.skills || 0) }),
        el("div", { className: "label", textContent: "Skills 总量" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(totals.mcpServers || 0) }),
        el("div", { className: "label", textContent: "MCP Server 总量" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(Object.keys(report.organization.categories).length) }),
        el("div", { className: "label", textContent: "展示分类" }),
      ]),
    ]);
  }

  function renderCategoryBars() {
    const cats = report.organization.categories;
    const max = Math.max(...Object.values(cats).map((c) => c.count), 1);
    const container = el("div", { className: "category-bars" });
    Object.entries(cats)
      .sort((a, b) => b[1].count - a[1].count)
      .forEach(([label, info]) => {
        const pct = Math.round((info.count / max) * 100);
        container.appendChild(
          el("div", { className: "category-bar" }, [
            el("span", { textContent: label }),
            el("div", { className: "bar-track" }, [
              el("div", { className: "bar-fill", style: `width:${pct}%` }),
            ]),
            el("span", { textContent: String(info.count) }),
          ])
        );
      });
    return container;
  }

  function renderPluginCard(plugin) {
    const card = el("article", {
      className: "plugin-card",
      "data-slug": plugin.slug,
      tabindex: "0",
      role: "button",
    });
    card.appendChild(el("h4", { textContent: plugin.displayName }));
    card.appendChild(el("p", { textContent: plugin.description || "暂无描述" }));

    const meta = el("div", { className: "meta" });
    (plugin.categoryLabels || []).slice(0, 2).forEach((label) => {
      meta.appendChild(el("span", { className: "tag", textContent: label }));
    });
    if (plugin.components) {
      Object.entries(plugin.components).forEach(([key, count]) => {
        if (count > 0) {
          meta.appendChild(el("span", { className: "component-pill", textContent: `${key}: ${count}` }));
        }
      });
    }
    card.appendChild(meta);

    card.addEventListener("click", () => openDetail(plugin));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openDetail(plugin);
      }
    });
    return card;
  }

  function openDetail(plugin) {
    const panel = document.getElementById("detailPanel");
    const content = document.getElementById("detailContent");
    content.innerHTML = "";

    content.appendChild(el("h3", { textContent: plugin.displayName }));
    content.appendChild(el("p", { className: "desc", textContent: plugin.description || "" }));

    const tags = el("div", { className: "tag-row" });
    (plugin.categoryLabels || []).forEach((l) => tags.appendChild(el("span", { className: "tag", textContent: l })));
    if (plugin.verified) tags.appendChild(el("span", { className: "tag green", textContent: "Verified" }));
    if (plugin.isPreview) tags.appendChild(el("span", { className: "tag orange", textContent: "Preview" }));
    content.appendChild(tags);

    const list = el("ul", { className: "component-list" });
    const addSection = (title, items, renderItem) => {
      if (!items || !items.length) return;
      const li = el("li");
      li.appendChild(el("strong", { textContent: `${title} (${items.length})` }));
      items.forEach((item) => {
        const sub = el("div", { textContent: renderItem(item) });
        sub.style.color = "var(--text-muted)";
        sub.style.fontSize = "12px";
        sub.style.marginTop = "4px";
        li.appendChild(sub);
      });
      list.appendChild(li);
    };

    addSection("Skills", plugin.skills, (s) => s.displayName || s.name);
    addSection("MCP Servers", plugin.mcpServers, (s) => s.name);
    addSection("Rules", (plugin.rules || []).map((n) => ({ name: n })), (s) => s.name);
    addSection("Hooks", (plugin.hooks || []).map((n) => ({ name: n })), (s) => s.name);
    addSection("Commands", (plugin.commands || []).map((n) => ({ name: n })), (s) => s.name);
    addSection("Subagents", (plugin.subagents || []).map((n) => ({ name: n })), (s) => s.name);

    if (list.children.length) content.appendChild(list);

    const links = el("div", { style: "margin-top:16px;font-size:13px" });
    if (plugin.detailUrl || plugin.slug) {
      links.appendChild(
        el("a", {
          href: plugin.detailUrl || `https://cursor.com/marketplace/${plugin.slug}`,
          target: "_blank",
          rel: "noopener",
          textContent: "Marketplace 页面 →",
        })
      );
      links.appendChild(document.createTextNode(" · "));
    }
    if (plugin.repositoryUrl) {
      links.appendChild(
        el("a", { href: plugin.repositoryUrl, target: "_blank", rel: "noopener", textContent: "GitHub 源码 →" })
      );
    }
    content.appendChild(links);

    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    document.querySelectorAll(".plugin-card").forEach((c) => c.classList.remove("selected"));
    const selected = document.querySelector(`.plugin-card[data-slug="${plugin.slug}"]`);
    if (selected) selected.classList.add("selected");
  }

  function setupExplorer() {
    const grid = document.getElementById("pluginGrid");
    const search = document.getElementById("pluginSearch");
    const category = document.getElementById("pluginCategory");
    const component = document.getElementById("pluginComponent");

    function render() {
      const q = (search.value || "").toLowerCase();
      const cat = category.value;
      const comp = component.value;
      grid.innerHTML = "";

      const filtered = report.plugins.filter((p) => {
        const text = `${p.displayName} ${p.slug} ${p.description || ""}`.toLowerCase();
        if (q && !text.includes(q)) return false;
        if (cat !== "all") {
          const cats = p.categories || [];
          if (cat === "UNCATEGORIZED" && cats.length) return false;
          if (cat !== "UNCATEGORIZED" && !cats.includes(cat)) return false;
        }
        if (comp !== "all" && p.components) {
          if (!(p.components[comp] > 0)) return false;
        }
        return true;
      });

      document.getElementById("pluginCount").textContent = `显示 ${filtered.length} / ${report.plugins.length}`;
      filtered.forEach((p) => grid.appendChild(renderPluginCard(p)));
    }

    search.addEventListener("input", render);
    category.addEventListener("change", render);
    component.addEventListener("change", render);
    render();
  }

  function renderAutomations() {
    const list = document.getElementById("automationList");
    report.automations.forEach((auto) => {
      list.appendChild(
        el("article", { className: "automation-item" }, [
          el("div", { className: "icon", textContent: iconFor(auto.icon) }),
          el("div", null, [
            el("h4", { textContent: auto.name }),
            el("p", { textContent: auto.description }),
          ]),
        ])
      );
    });
  }

  function iconFor(name) {
    const map = {
      beaker: "🧪",
      shield: "🛡️",
      bug: "🐛",
      slack: "💬",
      git: "🔀",
      chart: "📊",
    };
    return map[name] || "⚡";
  }

  function renderOfficialTable() {
    const tbody = document.getElementById("officialTableBody");
    const manifest = report.officialCursorPlugins.marketplace_manifest;
    if (!manifest || !manifest.plugins) return;

    manifest.plugins.forEach((p) => {
      tbody.appendChild(
        el("tr", null, [
          el("td", { textContent: p.name }),
          el("td", { textContent: p.description || "" }),
          el("td", null, [
            el("a", {
              href: `https://github.com/cursor/plugins/tree/main/${p.source || p.name}`,
              target: "_blank",
              rel: "noopener",
              textContent: "GitHub →",
            }),
          ]),
        ])
      );
    });
  }

  function computeInsights() {
    const withComp = report.plugins.filter((p) => p.components);
    const mcpOnly = withComp.filter((p) => p.components.mcpServers && !p.components.skills).length;
    const skillsOnly = withComp.filter((p) => p.components.skills && !p.components.mcpServers).length;
    const both = withComp.filter((p) => p.components.skills && p.components.mcpServers).length;

    const topSkills = [...withComp]
      .sort((a, b) => (b.components.skills || 0) - (a.components.skills || 0))
      .slice(0, 5)
      .map((p) => `${p.displayName} (${p.components.skills})`)
      .join("、");

    return { mcpOnly, skillsOnly, both, topSkills };
  }

  function buildPage() {
    const main = document.getElementById("canvasMain");
    const insights = computeInsights();
    const org = report.organization;

    main.innerHTML = "";

    document.getElementById("reportMeta").textContent =
      `采集于 ${formatDate(report.meta.scrapedAt)} · 来源 ${report.meta.source}`;

    // Summary
    main.appendChild(
      el("section", { className: "canvas-section", id: "summary" }, [
        el("h2", { textContent: "执行摘要" }),
        el("p", {
          className: "section-lead",
          textContent: org.summary,
        }),
        renderStats(),
        el("div", { className: "insight-card" }, [
          el("h3", { textContent: "关键发现" }),
          el("ul", null, [
            el("li", {
              textContent: `Marketplace 当前收录 ${report.meta.pluginCount} 个插件与 ${report.meta.automationCount} 条预置自动化，详情页成功解析 ${report.meta.detailsFetched} 个。`,
            }),
            el("li", {
              textContent: `插件组合模式：${insights.both} 个同时含 Skills+MCP，${insights.mcpOnly} 个纯 MCP 集成，${insights.skillsOnly} 个纯 Skills 知识包。`,
            }),
            el("li", {
              textContent: `Skills 是最大组件类型（共 ${report.componentTotals.skills || 0} 个），PostHog、Scandit、Twilio 等 SaaS 插件以大量细分 Skill 覆盖 API 场景。`,
            }),
            el("li", {
              textContent: "Featured 精选插件：Datadog、Slack、Figma、Linear — 均以 MCP Server 为核心连接外部平台。",
            }),
            el("li", {
              textContent: "社区插件与 MCP 目录另见 cursor.directory；官方 Marketplace 插件需开源并经人工审核。",
            }),
          ]),
        ]),
      ])
    );

    // Architecture
    main.appendChild(
      el("section", { className: "canvas-section", id: "architecture" }, [
        el("h2", { textContent: "架构与数据流" }),
        el("p", {
          className: "section-lead",
          textContent:
            "Marketplace 网站基于 Next.js RSC（React Server Components）渲染，插件元数据嵌入在 __next_f flight 载荷中；详情页通过 initialPluginJson 暴露完整组件清单。",
        }),
        el("div", { className: "diagram-card" }, [
          el("h3", { textContent: "数据流" }),
          el("div", { className: "mermaid-wrap" }, [
            el("pre", {
              className: "mermaid",
              textContent: `flowchart LR
  subgraph publish [发布侧]
    Dev[开发者] --> Repo[Git 仓库]
    Repo --> Manifest[".cursor-plugin/plugin.json"]
    Manifest --> Review[Cursor 人工审核]
  end
  Review --> CDN[cursor.com/marketplace]
  CDN --> RSC[RSC Flight Payload]
  RSC --> IDE[Cursor IDE Customize]
  IDE --> Agent[Agent 运行时]
  Agent --> Skills[Skills]
  Agent --> MCP[MCP Servers]
  Agent --> Rules[Rules/Hooks/Commands]`,
            }),
          ]),
        ]),
      ])
    );

    // Organization
    main.appendChild(
      el("section", { className: "canvas-section", id: "organization" }, [
        el("h2", { textContent: "内容组织方式" }),
        el("p", {
          className: "section-lead",
          textContent: "首页分区展示 + 详情页深度信息；插件与自动化是两条独立内容线。",
        }),
        el("div", { className: "diagram-card" }, [
          el("h3", { textContent: "首页分区结构" }),
          el("div", { className: "mermaid-wrap" }, [
            el("pre", {
              className: "mermaid",
              textContent: `mindmap
  root((Cursor Marketplace))
    Featured Plugins
      Datadog
      Slack
      Figma
      Linear
    Featured Automations
      PR Review
      Security Scan
      Slack Digest
    Recently Added
    Category Rows
      Infrastructure
      Data Analytics
      Productivity
      Payments
      Agent Orchestration
      Canvas
    All Automations`,
            }),
          ]),
        ]),
        el("div", { className: "table-card" }, [
          el("h3", { textContent: "内容类型对比" }),
          el("table", { className: "data-table" }, [
            el("thead", null, [
              el("tr", null, [
                el("th", { textContent: "类型" }),
                el("th", { textContent: "说明" }),
                el("th", { textContent: "安装方式" }),
              ]),
            ]),
            el("tbody", null, org.contentTypes.map((ct) =>
              el("tr", null, [
                el("td", { textContent: ct.type }),
                el("td", { textContent: ct.description }),
                el("td", { textContent: ct.install }),
              ])
            )),
          ]),
        ]),
      ])
    );

    // Primitives
    main.appendChild(
      el("section", { className: "canvas-section", id: "primitives" }, [
        el("h2", { textContent: "插件原语剖析" }),
        el("p", {
          className: "section-lead",
          textContent:
            "Plugin 是可分发 bundle，由以下 Agent 原语组合而成。每个插件目录必须包含 .cursor-plugin/plugin.json 清单。",
        }),
        el("div", { className: "diagram-card" }, [
          el("h3", { textContent: "Plugin Bundle 结构" }),
          el("div", { className: "mermaid-wrap" }, [
            el("pre", {
              className: "mermaid",
              textContent: `flowchart TB
  Plugin["plugin.json 清单"]
  Plugin --> Skills["skills/ SKILL.md"]
  Plugin --> MCP["mcp.json MCP Servers"]
  Plugin --> Rules["rules/ .mdc"]
  Plugin --> Hooks["hooks/ 脚本"]
  Plugin --> Commands["commands/"]
  Plugin --> Subagents["agents/ 子Agent"]
  Skills --> Agent[Cursor Agent]
  MCP --> Agent
  Rules --> Agent
  Hooks --> Agent
  Commands --> Agent
  Subagents --> Agent`,
            }),
          ]),
        ]),
        el("div", { className: "table-card" }, [
          el("h3", { textContent: "原语说明与统计" }),
          el("table", { className: "data-table" }, [
            el("thead", null, [
              el("tr", null, [
                el("th", { textContent: "原语" }),
                el("th", { textContent: "作用" }),
                el("th", { textContent: "全站总量" }),
              ]),
            ]),
            el("tbody", null, org.pluginPrimitives.map((key) =>
              el("tr", null, [
                el("td", { textContent: key }),
                el("td", { textContent: PRIMITIVE_DESC[key] || "" }),
                el("td", { textContent: String(report.componentTotals[key] || 0) }),
              ])
            )),
          ]),
        ]),
      ])
    );

    // Categories
    main.appendChild(
      el("section", { className: "canvas-section", id: "categories" }, [
        el("h2", { textContent: "分类全景" }),
        el("p", {
          className: "section-lead",
          textContent: "curatedCategoryKeys 决定首页分区；一个插件可属于多个分类（如 Datadog 同时出现在 Featured 与 Infrastructure）。",
        }),
        el("div", { className: "insight-card" }, [
          el("h3", { textContent: "各分类插件数量" }),
          renderCategoryBars(),
        ]),
      ])
    );

    // Explorer
    const categoryOptions = [
      el("option", { value: "all", textContent: "全部分类" }),
      ...Object.entries(org.categories).map(([label, info]) =>
        el("option", { value: info.key, textContent: `${label} (${info.count})` })
      ),
    ];

    main.appendChild(
      el("section", { className: "canvas-section", id: "explorer" }, [
        el("h2", { textContent: "插件浏览器" }),
        el("p", { className: "section-lead", textContent: "点击卡片查看 Skills / MCP 等组件详情。" }),
        el("div", { className: "explorer-toolbar" }, [
          el("input", { id: "pluginSearch", type: "search", placeholder: "搜索插件名称、slug、描述…" }),
          el("select", { id: "pluginCategory" }, categoryOptions),
          el("select", { id: "pluginComponent" }, [
            el("option", { value: "all", textContent: "全部组件类型" }),
            el("option", { value: "skills", textContent: "含 Skills" }),
            el("option", { value: "mcpServers", textContent: "含 MCP" }),
            el("option", { value: "rules", textContent: "含 Rules" }),
            el("option", { value: "hooks", textContent: "含 Hooks" }),
          ]),
        ]),
        el("p", { id: "pluginCount", style: "font-size:13px;color:var(--text-muted)" }),
        el("div", { className: "plugin-grid", id: "pluginGrid" }),
      ])
    );

    // Automations
    main.appendChild(
      el("section", { className: "canvas-section", id: "automations" }, [
        el("h2", { textContent: "自动化工作流" }),
        el("p", {
          className: "section-lead",
          textContent:
            "Automations 是预置 Agent 工作流，包含 triggers（Git PR、Slack 等事件）与 actions（发 Slack、开 PR 等），与 Plugin 是平行内容类型。",
        }),
        el("div", { className: "automation-list", id: "automationList" }),
      ])
    );

    // Official
    main.appendChild(
      el("section", { className: "canvas-section", id: "official" }, [
        el("h2", { textContent: "官方 GitHub 仓库" }),
        el("p", {
          className: "section-lead",
          textContent:
            "github.com/cursor/plugins 是 Cursor 官方多插件 Marketplace 仓库，根目录 marketplace.json 列出所有官方自研插件。",
        }),
        el("div", { className: "table-card" }, [
          el("h3", { textContent: "marketplace.json 收录（官方自研）" }),
          el("table", { className: "data-table" }, [
            el("thead", null, [
              el("tr", null, [
                el("th", { textContent: "slug" }),
                el("th", { textContent: "描述" }),
                el("th", { textContent: "链接" }),
              ]),
            ]),
            el("tbody", { id: "officialTableBody" }),
          ]),
        ]),
      ])
    );

    // Insights
    main.appendChild(
      el("section", { className: "canvas-section", id: "insights" }, [
        el("h2", { textContent: "数据洞察" }),
        el("div", { className: "insight-card" }, [
          el("h3", { textContent: "生态画像" }),
          el("ul", null, [
            el("li", { textContent: `Skills 密集型插件 Top 5：${insights.topSkills}` }),
            el("li", {
              textContent: `基础设施/可观测性类（Infrastructure）占比最高，Datadog、Coralogix、Grafana、AWS 等云厂商深度集成。`,
            }),
            el("li", {
              textContent: `Agent Orchestration 分类含 AWS Agents、Arize、Merge、Sourcegraph 等，聚焦多 Agent 协作与企业工具连接。`,
            }),
            el("li", {
              textContent: `Canvas 分类仅 2-3 个插件（PR Review Canvas、Docs Canvas），将 PR diff 与文档渲染为可导航 Canvas。`,
            }),
            el("li", {
              textContent: `Team Marketplace（企业私有）支持 Default Off / Default On / Required 三种安装策略（2026-05 changelog）。`,
            }),
          ]),
        ]),
      ])
    );

    // Methodology
    main.appendChild(
      el("section", { className: "canvas-section", id: "methodology" }, [
        el("h2", { textContent: "采集方法论" }),
        el("div", { className: "insight-card" }, [
          el("ul", null, [
            el("li", { textContent: "脚本：scripts/collect_marketplace.py" }),
            el("li", {
              textContent: `解析 cursor.com/marketplace 首页 RSC flight 载荷（${(report.meta.rscPayloadBytes / 1024 / 1024).toFixed(1)} MB）提取插件列表与自动化。`,
            }),
            el("li", { textContent: "并发抓取各插件详情页 initialPluginJson，解析 Skills/MCP/Rules 等组件。" }),
            el("li", { textContent: "同步拉取 github.com/cursor/plugins 的 marketplace.json 官方清单。" }),
            el("li", {
              textContent: "更新数据：python3 scripts/collect_marketplace.py",
            }),
          ]),
        ]),
      ])
    );

    setupExplorer();
    renderAutomations();
    renderOfficialTable();

    if (window.mermaid) {
      mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
      mermaid.run({ querySelector: ".mermaid" });
    }

    setupTocSpy();
  }

  function setupTocSpy() {
    const links = document.querySelectorAll(".canvas-toc a");
    const sections = [...links].map((a) => document.querySelector(a.getAttribute("href"))).filter(Boolean);

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            links.forEach((l) => l.classList.remove("active"));
            const active = document.querySelector(`.canvas-toc a[href="#${entry.target.id}"]`);
            if (active) active.classList.add("active");
          }
        });
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );

    sections.forEach((s) => observer.observe(s));
  }

  document.getElementById("closeDetail").addEventListener("click", () => {
    const panel = document.getElementById("detailPanel");
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    document.querySelectorAll(".plugin-card").forEach((c) => c.classList.remove("selected"));
  });

  fetch("./data/marketplace_report.json")
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => {
      report = data;
      document.getElementById("loadingState")?.remove();
      buildPage();
    })
    .catch((err) => {
      document.getElementById("loadingState").textContent =
        `加载失败：${err.message}。请先运行 python3 scripts/collect_marketplace.py`;
    });
})();
