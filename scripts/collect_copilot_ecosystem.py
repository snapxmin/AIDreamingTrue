#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Copilot 插件生态深度采集脚本

覆盖 Copilot 生态的多条分发链路，不限于 Marketplace Copilot Extensions 页面：
  1. GitHub Marketplace Copilot Extensions（GitHub App，IDE/Web Chat @ 扩展）
  2. Copilot CLI 官方/社区 Plugin Marketplaces（marketplace.json）
  3. GitHub MCP Registry（MCP 服务目录，与 CLI Plugin 平行）
  4. 组件树统计（Skills / Agents / MCP 等原语文件数）

用法:
  python3 scripts/collect_copilot_ecosystem.py
  python3 scripts/collect_copilot_ecosystem.py --extensions-only
  python3 scripts/collect_copilot_ecosystem.py --dry-run
"""

from __future__ import print_function

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
REPORT_PATH = os.path.join(DATA_DIR, "copilot_ecosystem_report.json")

USER_AGENT = "copilot-ecosystem-research/1.0"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}

EXTENSIONS_URL = "https://github.com/marketplace?type=apps&copilot_app=true"
MCP_REGISTRY_URL = "https://github.com/mcp"

CLI_MARKETPLACES = [
    {
        "name": "copilot-plugins",
        "repo": "github/copilot-plugins",
        "manifestUrl": "https://raw.githubusercontent.com/github/copilot-plugins/main/.github/plugin/marketplace.json",
        "treeUrl": "https://api.github.com/repos/github/copilot-plugins/git/trees/main?recursive=1",
        "role": "official",
    },
    {
        "name": "awesome-copilot",
        "repo": "github/awesome-copilot",
        "manifestUrl": "https://raw.githubusercontent.com/github/awesome-copilot/main/.github/plugin/marketplace.json",
        "treeUrl": "https://api.github.com/repos/github/awesome-copilot/git/trees/main?recursive=1",
        "role": "community",
    },
]

# 扩展分类启发式（基于 slug / 名称 / 描述关键词）
CATEGORY_RULES = [
    ("CI/CD & DevOps", ["circleci", "travis", "codecov", "deploy", "pipeline", "build", "render", "netlify", "vercel", "cloud-build", "bitrise", "appveyor", "codemagic", "jenkins", "spacelift", "argos"]),
    ("Security & Quality", ["snyk", "sonar", "gitguardian", "semgrep", "codacy", "deepsource", "aikido", "socket", "bridgecrew", "codeql", "security", "vulnerability", "scan", "coveralls", "codeclimate", "qodo", "coderabbit", "sourcery", "codeant"]),
    ("Project Management", ["jira", "linear", "asana", "clickup", "monday", "azure-boards", "zenhub", "trello", "atlassian"]),
    ("Communication", ["slack", "teams", "discord", "giscus", "utterances"]),
    ("Cloud & Infrastructure", ["aws", "azure", "google-cloud", "doppler", "infracost", "terraform", "pulumi"]),
    ("Observability", ["datadog", "sentry", "logrocket", "rollbar", "airbrake", "wakatime"]),
    ("Documentation", ["gitbook", "hackmd", "readme"]),
    ("Design & Content", ["figma", "crowdin", "imgbot", "shopify", "builder-io"]),
    ("AI & Code Assist", ["copilot", "sweep", "graphite", "mergify", "fine-ai", "cubic", "bito", "amazon-q", "opencode"]),
    ("Localization & i18n", ["crowdin", "lokalise"]),
]


def fetch_text(url, timeout=45, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, Exception) as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_err


def fetch_json(url, timeout=60):
    return json.loads(fetch_text(url, timeout=timeout))


def categorize_extension(slug, name="", description=""):
    text = " ".join([slug, name, description]).lower()
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in text:
                return category
    return "Other"


def parse_extensions_page(html):
    apps = []
    pattern = re.compile(
        r'href="/marketplace/([a-z0-9-]+)"[^>]*class="[^"]*marketplace-item-link[^"]*"[^>]*>'
        r"([^<]+)</a>.*?<p class=\"[^\"]*\"[^>]*>([^<]+)</p>",
        re.S,
    )
    seen = set()
    for match in pattern.finditer(html):
        slug, name, desc = match.group(1), match.group(2).strip(), match.group(3).strip()
        if slug in ("models", "new", "category", "search") or slug in seen:
            continue
        seen.add(slug)
        apps.append(
            {
                "slug": slug,
                "name": name,
                "description": desc,
                "url": "https://github.com/marketplace/%s" % slug,
                "category": categorize_extension(slug, name, desc),
            }
        )
    return apps


def scrape_copilot_extensions(max_pages=80):
    all_by_slug = OrderedDict()
    page = 1
    empty_streak = 0

    while page <= max_pages:
        url = "%s&page=%d" % (EXTENSIONS_URL, page)
        try:
            html = fetch_text(url)
        except Exception as exc:
            print("  page %d error: %s" % (page, exc))
            break

        apps = parse_extensions_page(html)
        new_count = sum(1 for a in apps if a["slug"] not in all_by_slug)
        print("  extensions page %d: parsed %d, new %d" % (page, len(apps), new_count))

        if not apps or new_count == 0:
            empty_streak += 1
            if empty_streak >= 2:
                break
        else:
            empty_streak = 0

        for app in apps:
            all_by_slug[app["slug"]] = app
        page += 1
        time.sleep(0.15)

    return list(all_by_slug.values())


def scrape_mcp_registry(max_pages=10):
    all_servers = OrderedDict()
    page = 1
    while page <= max_pages:
        url = MCP_REGISTRY_URL if page == 1 else "%s?page=%d" % (MCP_REGISTRY_URL, page)
        try:
            html = fetch_text(url)
        except Exception as exc:
            print("  mcp page %d error: %s" % (page, exc))
            break

        slugs = re.findall(r'href="/mcp/([^"]+)"', html)
        if not slugs:
            break

        new = 0
        for slug in slugs:
            if slug not in all_servers:
                all_servers[slug] = {
                    "slug": slug,
                    "url": "https://github.com/mcp/%s" % slug,
                    "publisher": slug.split("/")[0] if "/" in slug else slug,
                }
                new += 1

        print("  mcp page %d: %d entries, %d new" % (page, len(slugs), new))
        if new == 0 and page > 1:
            break
        page += 1
        time.sleep(0.15)

    return list(all_servers.values())


def count_tree_components(tree_paths):
    counts = Counter()
    details = {
        "skillFiles": [],
        "agentFiles": [],
        "mcpConfigFiles": [],
        "pluginManifests": [],
        "hookFiles": [],
    }

    for path in tree_paths:
        lower = path.lower()
        if path.endswith("SKILL.md"):
            counts["skills"] += 1
            details["skillFiles"].append(path)
        if path.endswith(".agent.md"):
            counts["agents"] += 1
            details["agentFiles"].append(path)
        if path.endswith("plugin.json"):
            counts["pluginManifests"] += 1
            details["pluginManifests"].append(path)
        if "hook" in lower and (lower.endswith(".json") or lower.endswith(".md") or lower.endswith(".sh")):
            if "workflow" not in lower:
                counts["hooks"] += 1
                details["hookFiles"].append(path)
        if lower.endswith(".json") and ("mcp" in lower or lower.endswith("mcp.json") or ".mcp." in lower):
            counts["mcpConfigs"] += 1
            details["mcpConfigFiles"].append(path)

    return dict(counts), details


def analyze_cli_marketplace(marketplace_info):
    manifest = fetch_json(marketplace_info["manifestUrl"])
    plugins = manifest.get("plugins", [])

    tree_data = fetch_json(marketplace_info["treeUrl"])
    paths = [item["path"] for item in tree_data.get("tree", [])]
    component_counts, component_details = count_tree_components(paths)

    external_repos = []
    local_plugins = []
    for plugin in plugins:
        source = plugin.get("source")
        entry = {
            "name": plugin.get("name"),
            "description": plugin.get("description", ""),
            "version": plugin.get("version"),
            "repository": plugin.get("repository"),
            "keywords": plugin.get("keywords", []),
        }
        if isinstance(source, dict) and source.get("repo"):
            entry["sourceRepo"] = source.get("repo")
            entry["sourcePath"] = source.get("path")
            external_repos.append(entry)
        else:
            local_plugins.append(entry)

    return {
        "name": marketplace_info["name"],
        "repo": marketplace_info["repo"],
        "role": marketplace_info["role"],
        "manifest": {
            "description": (manifest.get("metadata") or {}).get("description"),
            "owner": manifest.get("owner"),
            "pluginCount": len(plugins),
        },
        "plugins": plugins,
        "localPlugins": local_plugins,
        "externalPlugins": external_repos,
        "componentCounts": component_counts,
        "componentDetailsSummary": {
            k: len(v) for k, v in component_details.items()
        },
    }


def build_organization_summary(extensions, cli_marketplaces, mcp_servers):
    ext_categories = Counter(e["category"] for e in extensions)
    return {
        "summary": (
            "GitHub Copilot 生态并非单一 Marketplace，而是四条并行扩展链路："
            "IDE/Web 的 Copilot Extensions（GitHub App，@ 提及调用）、"
            "Copilot CLI 的 Git-repo Plugin Marketplaces（agents/skills/hooks/MCP 打包）、"
            "跨表面的 MCP Registry（连接层目录）、"
            "以及 VS Code Extension 的 chatSkills 贡献点。"
            "与 Cursor Marketplace 的「统一插件 bundle」不同，Copilot 将"
            "「Chat 扩展（GitHub App）」与「CLI 插件（原语包）」刻意分离。"
        ),
        "layers": [
            {
                "id": "extensions",
                "name": "Copilot Extensions",
                "surface": "VS Code / Visual Studio / JetBrains / github.com / Mobile",
                "distribution": "GitHub Marketplace (GitHub Apps, copilot_app=true)",
                "count": len(extensions),
                "builderModels": ["Skillsets (≤5 API endpoints)", "Agents (full control)"],
                "install": "GitHub Marketplace 安装 GitHub App → IDE 启用",
            },
            {
                "id": "cli_plugins",
                "name": "Copilot CLI Plugins",
                "surface": "Copilot CLI (terminal)",
                "distribution": "Git repo + .github/plugin/marketplace.json",
                "count": sum(m["manifest"]["pluginCount"] for m in cli_marketplaces),
                "primitives": ["agents", "skills", "hooks", "mcpServers", "commands"],
                "install": "copilot plugin install <name>@<marketplace>",
            },
            {
                "id": "mcp_registry",
                "name": "GitHub MCP Registry",
                "surface": "IDE / CLI / Copilot App / Cloud Agent / Code Review",
                "distribution": "github.com/mcp curated catalog",
                "count": len(mcp_servers),
                "note": "原始 MCP 服务发现，非完整 CLI Plugin bundle",
                "install": "按编辑器/CLI 配置 MCP server",
            },
            {
                "id": "vscode_skills",
                "name": "VS Code Extension Skills",
                "surface": "VS Code Copilot Chat",
                "distribution": "Extension package.json → chatSkills",
                "count": None,
                "note": "开放 Agent Skills 标准，扩展可贡献 SKILL.md",
            },
        ],
        "extensionCategories": dict(ext_categories.most_common()),
        "defaultCliMarketplaces": ["copilot-plugins", "awesome-copilot"],
        "enterprise": {
            "feature": "Enterprise plugin standards (public preview)",
            "config": ".github/copilot/settings.json in enterprise .github-private repo",
            "policies": ["MCP servers in Copilot policy (org/enterprise)", "Default Off / On / Required for team plugins"],
        },
    }


def build_insights(extensions, cli_marketplaces, mcp_servers):
    ac = next((m for m in cli_marketplaces if m["name"] == "awesome-copilot"), {})
    cp = next((m for m in cli_marketplaces if m["name"] == "copilot-plugins"), {})
    ac_counts = ac.get("componentCounts", {})
    cp_counts = cp.get("componentCounts", {})

    ext_cats = Counter(e["category"] for e in extensions)
    top_cats = ext_cats.most_common(5)

    return [
        {
            "title": "双轨生态：Extensions ≠ CLI Plugins",
            "body": (
                "Copilot Extensions（%d 个 GitHub App）面向 IDE Chat 的 @ 工具集成，"
                "以 Skillsets（API 端点）或 Agents（全控交互）实现；"
                "CLI Plugins（官方 %d + 社区 %d）面向终端 Agent，"
                "原语结构与 Cursor Plugin 高度同构（agents/skills/hooks/MCP）。"
                % (
                    len(extensions),
                    cp.get("manifest", {}).get("pluginCount", 0),
                    ac.get("manifest", {}).get("pluginCount", 0),
                )
            ),
        },
        {
            "title": "Extensions 主战场是 DevOps 流水线，不是 SaaS 知识包",
            "body": (
                "Marketplace Copilot Extensions 中 %s 占比最高——"
                "与 Cursor Marketplace（大量 SaaS Skills 说明书）形成鲜明对比。"
                "Copilot Extension 的典型价值是「在 PR/Issue 上下文中触发已有 GitHub App 能力」，"
                "而非向 Agent 注入 50 份 API 场景文档。"
                % ("、".join("%s(%d)" % (c, n) for c, n in top_cats[:3]))
            ),
        },
        {
            "title": "CLI 侧 Skills 密集，但组织方式不同",
            "body": (
                "awesome-copilot 仓库含 %d 个 SKILL.md、%d 个 .agent.md（共享池 + %d 个 plugin 清单），"
                "Skills 数量级接近 Cursor，但大量 Skills 位于仓库根 skills/ 目录而非 per-plugin 拆分；"
                "copilot-plugins 官方仓仅 %d 个插件，偏微软/GitHub 战略合作（WorkIQ、Fabric、Advanced Security）。"
                % (
                    ac_counts.get("skills", 0),
                    ac_counts.get("agents", 0),
                    ac.get("manifest", {}).get("pluginCount", 0),
                    cp.get("manifest", {}).get("pluginCount", 0),
                )
            ),
        },
        {
            "title": "MCP 是第三层连接目录",
            "body": (
                "GitHub MCP Registry 现有 %d 个登记服务（含 github-mcp-server、playwright、azure、notion 等），"
                "与 CLI Plugin Marketplace 独立——开发者可先发现 MCP，再决定是否打包为完整 Plugin。"
                "GitHub 内置 MCP server 支持 toolset 裁剪以优化 Agent 工具选择精度。"
            )
            % len(mcp_servers),
        },
        {
            "title": "与 Cursor Marketplace 的战略差异",
            "body": (
                "Cursor：统一 Marketplace + 人工审核 + per-plugin Skills 细分（SaaS 集成导向）。"
                "GitHub Copilot：Extensions 走 GitHub App 生态（~600+ 既有集成复用）、"
                "CLI 走开源 marketplace.json 联邦、MCP 走开放注册表——"
                "三层分工而非一层打包，因此「组件统计」需在对应层分别解读。"
            ),
        },
    ]


def build_report(extensions_only=False):
    print("=== Scraping Copilot Extensions (GitHub Marketplace) ===")
    extensions = scrape_copilot_extensions()
    print("Total extensions: %d" % len(extensions))

    cli_marketplaces = []
    mcp_servers = []

    if not extensions_only:
        print("\n=== Analyzing CLI Marketplaces ===")
        for mp in CLI_MARKETPLACES:
            print("  %s..." % mp["name"])
            cli_marketplaces.append(analyze_cli_marketplace(mp))

        print("\n=== Scraping MCP Registry ===")
        mcp_servers = scrape_mcp_registry()

    organization = build_organization_summary(extensions, cli_marketplaces, mcp_servers)
    insights = build_insights(extensions, cli_marketplaces, mcp_servers)

    ac = next((m for m in cli_marketplaces if m["name"] == "awesome-copilot"), {})
    cp = next((m for m in cli_marketplaces if m["name"] == "copilot-plugins"), {})

    report = {
        "meta": {
            "scrapedAt": datetime.now(timezone.utc).isoformat(),
            "sources": [
                EXTENSIONS_URL,
                MCP_REGISTRY_URL,
            ]
            + [m["manifestUrl"] for m in CLI_MARKETPLACES],
            "extensionCount": len(extensions),
            "mcpServerCount": len(mcp_servers),
            "cliMarketplaceCount": len(cli_marketplaces),
        },
        "organization": organization,
        "insights": insights,
        "copilotExtensions": extensions,
        "cliMarketplaces": cli_marketplaces,
        "mcpRegistry": mcp_servers,
        "componentTotals": {
            "extensions": len(extensions),
            "cliPluginsOfficial": cp.get("manifest", {}).get("pluginCount", 0),
            "cliPluginsCommunity": ac.get("manifest", {}).get("pluginCount", 0),
            "awesomeCopilotSkills": ac.get("componentCounts", {}).get("skills", 0),
            "awesomeCopilotAgents": ac.get("componentCounts", {}).get("agents", 0),
            "copilotPluginsSkills": cp.get("componentCounts", {}).get("skills", 0),
            "mcpRegistryServers": len(mcp_servers),
        },
        "comparisonWithCursor": {
            "cursorMarketplace": "统一 Plugin bundle（Skills+MCP+Rules+Hooks）",
            "copilotExtensions": "GitHub App 集成（Skillsets/Agents，偏 API 动作）",
            "copilotCliPlugins": "联邦式 marketplace.json（原语包）",
            "copilotMcpRegistry": "独立 MCP 目录（连接层）",
            "keyDifference": (
                "Cursor 将知识（Skills）作为 SaaS 集成主载体；"
                "Copilot Extensions 将 GitHub App 工作流作为主载体，"
                "Skills 密集区在 CLI/Agent Skills 开放标准层。"
            ),
        },
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Scrape GitHub Copilot ecosystem")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--extensions-only",
        action="store_true",
        help="Only scrape Marketplace extensions (faster)",
    )
    args = parser.parse_args()

    report = build_report(extensions_only=args.extensions_only)

    print("\n=== Summary ===")
    print("Extensions:", report["meta"]["extensionCount"])
    print("MCP servers:", report["meta"]["mcpServerCount"])
    for mp in report.get("cliMarketplaces", []):
        print(
            "  %s: %d plugins, skills=%s agents=%s"
            % (
                mp["name"],
                mp["manifest"]["pluginCount"],
                mp["componentCounts"].get("skills", 0),
                mp["componentCounts"].get("agents", 0),
            )
        )

    if args.dry_run:
        print("[dry-run] Not writing file.")
        return 0

    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("\nWrote %s" % REPORT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
