(function () {
  "use strict";

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
    return new Date(iso).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
  }

  function renderStats() {
    const t = report.componentTotals;
    return el("div", { className: "stat-grid" }, [
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(t.extensions) }),
        el("div", { className: "label", textContent: "Copilot Extensions" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(t.cliPluginsOfficial + t.cliPluginsCommunity) }),
        el("div", { className: "label", textContent: "CLI Plugins（官方+社区）" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(t.mcpRegistryServers) }),
        el("div", { className: "label", textContent: "MCP Registry" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(t.awesomeCopilotSkills) }),
        el("div", { className: "label", textContent: "社区 Skills 文件" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(t.awesomeCopilotAgents) }),
        el("div", { className: "label", textContent: "社区 Agents 文件" }),
      ]),
      el("div", { className: "stat-card" }, [
        el("div", { className: "value", textContent: String(t.cliPluginsOfficial) }),
        el("div", { className: "label", textContent: "官方 CLI 插件" }),
      ]),
    ]);
  }

  function renderCategoryBars(categories) {
    const entries = Object.entries(categories).sort((a, b) => b[1] - a[1]);
    const max = Math.max(...entries.map((e) => e[1]), 1);
    const container = el("div", { className: "category-bars" });
    entries.forEach(([label, count]) => {
      container.appendChild(
        el("div", { className: "category-bar" }, [
          el("span", { textContent: label }),
          el("div", { className: "bar-track" }, [
            el("div", { className: "bar-fill", style: `width:${Math.round((count / max) * 100)}%` }),
          ]),
          el("span", { textContent: String(count) }),
        ])
      );
    });
    return container;
  }

  function renderLayers() {
    const container = el("div");
    report.organization.layers.forEach((layer) => {
      container.appendChild(
        el("div", { className: "layer-card" }, [
          el("h4", { textContent: `${layer.name}（${layer.count != null ? layer.count : "N/A"}）` }),
          el("p", { textContent: `运行面：${layer.surface}` }),
          el("p", { textContent: `分发：${layer.distribution}` }),
          el("p", {
            textContent: layer.install || layer.note || (layer.builderModels ? layer.builderModels.join(" · ") : ""),
          }),
        ])
      );
    });
    return container;
  }

  function renderCliMarketplaces() {
    const container = el("div");
    report.cliMarketplaces.forEach((mp) => {
      const card = el("div", { className: "table-card" }, [
        el("h3", { textContent: `${mp.name} (${mp.role}) — ${mp.manifest.pluginCount} plugins` }),
        el("p", { style: "font-size:13px;color:var(--text-muted)", textContent: mp.manifest.description || "" }),
        el("div", { className: "tag-row" }, [
          el("span", { className: "tag", textContent: `skills: ${mp.componentCounts.skills || 0}` }),
          el("span", { className: "tag green", textContent: `agents: ${mp.componentCounts.agents || 0}` }),
          el("span", { className: "tag orange", textContent: `mcp configs: ${mp.componentCounts.mcpConfigs || 0}` }),
          el("span", { className: "tag purple", textContent: `外部源: ${mp.externalPlugins.length}` }),
        ]),
      ]);

      const table = el("table", { className: "data-table" }, [
        el("thead", null, [
          el("tr", null, [el("th", { textContent: "插件" }), el("th", { textContent: "描述" })]),
        ]),
        el("tbody", null, mp.plugins.slice(0, 12).map((p) =>
          el("tr", null, [
            el("td", { textContent: p.name }),
            el("td", { textContent: (p.description || "").slice(0, 100) }),
          ])
        )),
      ]);
      if (mp.plugins.length > 12) {
        table.appendChild(
          el("tbody", null, [
            el("tr", null, [el("td", { colSpan: "2", textContent: `… 另有 ${mp.plugins.length - 12} 个插件` })]),
          ])
        );
      }
      card.appendChild(table);
      container.appendChild(card);
    });
    return container;
  }

  function setupExplorer() {
    const grid = document.getElementById("extGrid");
    const search = document.getElementById("extSearch");
    const category = document.getElementById("extCategory");

    function render() {
      const q = (search.value || "").toLowerCase();
      const cat = category.value;
      grid.innerHTML = "";
      const filtered = report.copilotExtensions.filter((e) => {
        const text = `${e.name} ${e.slug} ${e.description}`.toLowerCase();
        if (q && !text.includes(q)) return false;
        if (cat !== "all" && e.category !== cat) return false;
        return true;
      });
      document.getElementById("extCount").textContent = `显示 ${filtered.length} / ${report.copilotExtensions.length}`;
      filtered.slice(0, 120).forEach((ext) => {
        grid.appendChild(
          el("article", { className: "plugin-card" }, [
            el("h4", { textContent: ext.name }),
            el("p", { textContent: ext.description }),
            el("div", { className: "meta" }, [
              el("span", { className: "tag", textContent: ext.category }),
              el("a", {
                className: "component-pill",
                href: ext.url,
                target: "_blank",
                rel: "noopener",
                textContent: ext.slug,
              }),
            ]),
          ])
        );
      });
      if (filtered.length > 120) {
        grid.appendChild(el("p", { style: "color:var(--text-muted);font-size:13px", textContent: `仅展示前 120 条，请用搜索缩小范围` }));
      }
    }

    search.addEventListener("input", render);
    category.addEventListener("change", render);
    render();
  }

  function buildPage() {
    const main = document.getElementById("canvasMain");
    main.innerHTML = "";
    document.getElementById("reportMeta").textContent =
      `采集于 ${formatDate(report.meta.scrapedAt)} · ${report.meta.extensionCount} Extensions · ${report.meta.mcpServerCount} MCP`;

    main.appendChild(
      el("section", { className: "canvas-section", id: "summary" }, [
        el("h2", { textContent: "执行摘要" }),
        el("p", { className: "section-lead", textContent: report.organization.summary }),
        renderStats(),
      ])
    );

    main.appendChild(
      el("section", { className: "canvas-section", id: "layers" }, [
        el("h2", { textContent: "四层生态架构" }),
        el("p", {
          className: "section-lead",
          textContent: "Copilot 扩展不是单一目录，而是按运行面（IDE / CLI / MCP）刻意分层。",
        }),
        el("div", { className: "diagram-card" }, [
          el("h3", { textContent: "生态分层" }),
          el("div", { className: "mermaid-wrap" }, [
            el("pre", {
              className: "mermaid",
              textContent: `flowchart TB
  subgraph surfaces [Copilot 运行面]
    IDE[IDE Chat VS Code/JetBrains]
    WEB[github.com Chat]
    CLI[Copilot CLI Terminal]
    CLOUD[Cloud Agent / Code Review]
  end
  subgraph layers [四条扩展链路]
    EXT[Copilot Extensions GitHub Apps]
    CLIP[CLI Plugin Marketplaces]
    MCPR[MCP Registry]
    VSC[VS Code chatSkills]
  end
  EXT --> IDE
  EXT --> WEB
  CLIP --> CLI
  MCPR --> IDE
  MCPR --> CLI
  MCPR --> CLOUD
  VSC --> IDE`,
            }),
          ]),
        ]),
        renderLayers(),
      ])
    );

    main.appendChild(
      el("section", { className: "canvas-section", id: "extensions" }, [
        el("h2", { textContent: "Copilot Extensions（GitHub Marketplace）" }),
        el("p", {
          className: "section-lead",
          textContent:
            "通过 GitHub App 集成，在 Chat 中用 @扩展名 调用。构建模型分 Skillsets（≤5 个 API 端点，Copilot 处理 AI 交互）与 Agents（全控交互流）两种。2025-02 GA，覆盖全部 Copilot 许可层级。",
        }),
        el("div", { className: "insight-card" }, [
          el("h3", { textContent: "扩展分类分布" }),
          renderCategoryBars(report.organization.extensionCategories),
        ]),
      ])
    );

    main.appendChild(
      el("section", { className: "canvas-section", id: "cli" }, [
        el("h2", { textContent: "CLI Plugin Marketplaces" }),
        el("p", {
          className: "section-lead",
          textContent:
            "Copilot CLI 预置 copilot-plugins（官方）与 awesome-copilot（社区）两个 marketplace。安装：copilot plugin install <name>@<marketplace>",
        }),
        renderCliMarketplaces(),
      ])
    );

    main.appendChild(
      el("section", { className: "canvas-section", id: "mcp" }, [
        el("h2", { textContent: "GitHub MCP Registry" }),
        el("p", {
          className: "section-lead",
          textContent:
            "独立于 CLI Plugin 的 MCP 服务目录（github.com/mcp）。用于发现连接层，可配置到 IDE/CLI/仓库级 Cloud Agent。GitHub 内置 github-mcp-server 支持 toolset 裁剪。",
        }),
        el("div", { className: "plugin-grid", id: "mcpGrid" }),
      ])
    );

    const mcpGrid = main.querySelector("#mcpGrid");
    report.mcpRegistry.slice(0, 40).forEach((s) => {
      mcpGrid.appendChild(
        el("article", { className: "plugin-card" }, [
          el("h4", { textContent: s.slug }),
          el("div", { className: "meta" }, [
            el("a", { className: "tag", href: s.url, target: "_blank", rel: "noopener", textContent: "Registry →" }),
          ]),
        ])
      );
    });

    main.appendChild(
      el("section", { className: "canvas-section", id: "primitives" }, [
        el("h2", { textContent: "原语与构建模型" }),
        el("div", { className: "table-card" }, [
          el("table", { className: "data-table" }, [
            el("thead", null, [
              el("tr", null, [
                el("th", { textContent: "层" }),
                el("th", { textContent: "核心原语" }),
                el("th", { textContent: "构建模型" }),
              ]),
            ]),
            el("tbody", null, [
              el("tr", null, [
                el("td", { textContent: "Extensions" }),
                el("td", { textContent: "Skillsets (API endpoints) / Agents" }),
                el("td", { textContent: "GitHub App + HTTPS 回调" }),
              ]),
              el("tr", null, [
                el("td", { textContent: "CLI Plugins" }),
                el("td", { textContent: "agents · skills · hooks · mcpServers · commands" }),
                el("td", { textContent: "plugin.json + marketplace.json" }),
              ]),
              el("tr", null, [
                el("td", { textContent: "MCP Registry" }),
                el("td", { textContent: "MCP tools / resources / prompts" }),
                el("td", { textContent: "独立服务注册" }),
              ]),
              el("tr", null, [
                el("td", { textContent: "Agent Skills 标准" }),
                el("td", { textContent: "SKILL.md（开放标准）" }),
                el("td", { textContent: "VS Code chatSkills / CLI skillDirectories" }),
              ]),
            ]),
          ]),
        ]),
      ])
    );

    const cmp = report.comparisonWithCursor;
    main.appendChild(
      el("section", { className: "canvas-section", id: "cursor-compare" }, [
        el("h2", { textContent: "vs Cursor Marketplace" }),
        el("div", { className: "compare-grid" }, [
          el("div", { className: "compare-card" }, [
            el("h4", { textContent: "Cursor" }),
            el("p", { textContent: cmp.cursorMarketplace }),
            el("p", { textContent: "229 插件 · 统一 bundle · SaaS Skills 密集型" }),
          ]),
          el("div", { className: "compare-card" }, [
            el("h4", { textContent: "GitHub Copilot" }),
            el("p", { textContent: `${cmp.copilotExtensions} + ${cmp.copilotCliPlugins} + ${cmp.copilotMcpRegistry}` }),
            el("p", { textContent: "1272 Extensions · 分层联邦 · DevOps App 密集型" }),
          ]),
        ]),
        el("div", { className: "insight-card" }, [
          el("p", { textContent: cmp.keyDifference }),
        ]),
      ])
    );

    main.appendChild(
      el("section", { className: "canvas-section", id: "insights" }, [
        el("h2", { textContent: "深度洞察" }),
        ...report.insights.map((item) =>
          el("div", { className: "insight-card" }, [
            el("h3", { textContent: item.title }),
            el("p", { textContent: item.body }),
          ])
        ),
      ])
    );

    const cats = Object.keys(report.organization.extensionCategories).sort();
    main.appendChild(
      el("section", { className: "canvas-section", id: "explorer" }, [
        el("h2", { textContent: "扩展浏览器" }),
        el("div", { className: "explorer-toolbar" }, [
          el("input", { id: "extSearch", type: "search", placeholder: "搜索扩展名称、slug…" }),
          el("select", { id: "extCategory" }, [
            el("option", { value: "all", textContent: "全部分类" }),
            ...cats.map((c) =>
              el("option", {
                value: c,
                textContent: `${c} (${report.organization.extensionCategories[c]})`,
              })
            ),
          ]),
        ]),
        el("p", { id: "extCount", style: "font-size:13px;color:var(--text-muted)" }),
        el("div", { className: "plugin-grid", id: "extGrid" }),
      ])
    );

    main.appendChild(
      el("section", { className: "canvas-section", id: "methodology" }, [
        el("h2", { textContent: "采集方法论" }),
        el("div", { className: "insight-card" }, [
          el("ul", null, [
            el("li", { textContent: "脚本：scripts/collect_copilot_ecosystem.py" }),
            el("li", { textContent: "Extensions：分页抓取 github.com/marketplace?type=apps&copilot_app=true" }),
            el("li", { textContent: "CLI：解析 copilot-plugins / awesome-copilot 的 marketplace.json + Git tree API" }),
            el("li", { textContent: "MCP：抓取 github.com/mcp 注册表" }),
            el("li", { textContent: "更新：python3 scripts/collect_copilot_ecosystem.py" }),
          ]),
        ]),
      ])
    );

    setupExplorer();

    if (window.mermaid) {
      mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
      mermaid.run({ querySelector: ".mermaid" });
    }

    document.querySelectorAll(".canvas-toc a").forEach((link) => {
      const target = document.querySelector(link.getAttribute("href"));
      if (!target) return;
      new IntersectionObserver(
        (entries) => {
          entries.forEach((e) => {
            if (e.isIntersecting) {
              document.querySelectorAll(".canvas-toc a").forEach((l) => l.classList.remove("active"));
              link.classList.add("active");
            }
          });
        },
        { rootMargin: "-20% 0px -70% 0px" }
      ).observe(target);
    });
  }

  fetch("./data/copilot_ecosystem_report.json")
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
        `加载失败：${err.message}。请先运行 python3 scripts/collect_copilot_ecosystem.py`;
    });
})();
