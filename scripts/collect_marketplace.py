#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cursor Marketplace 深度采集脚本

从 cursor.com/marketplace 的 Next.js RSC 载荷中解析插件与自动化列表，
并可选抓取各插件详情页以获取 Skills / MCP / Rules 等组件构成。

用法:
  python3 scripts/collect_marketplace.py
  python3 scripts/collect_marketplace.py --dry-run
  python3 scripts/collect_marketplace.py --no-details   # 跳过详情页（更快）
  python3 scripts/collect_marketplace.py --limit 20     # 仅抓取前 20 个详情
"""

from __future__ import print_function

import argparse
import codecs
import json
import os
import re
import sys
import time
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
REPORT_PATH = os.path.join(DATA_DIR, "marketplace_report.json")

MARKETPLACE_URL = "https://cursor.com/marketplace"
GITHUB_MARKETPLACE_JSON = (
    "https://raw.githubusercontent.com/cursor/plugins/main/.cursor-plugin/marketplace.json"
)
GITHUB_REPO_API = "https://api.github.com/repos/cursor/plugins/contents?ref=main"

USER_AGENT = "cursor-marketplace-research/1.0"
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}

CATEGORY_LABELS = {
    "FEATURED": "Featured",
    "INFRASTRUCTURE": "Infrastructure",
    "DATA_ANALYTICS": "Data & Analytics",
    "PRODUCTIVITY": "Productivity",
    "PAYMENTS": "Payments",
    "AGENT_ORCHESTRATION": "Agent Orchestration",
    "CANVAS": "Canvas",
    "RECENTLY_ADDED": "Recently Added",
    "PLUGINS": "Plugins",
    "AUTOMATIONS": "Automations",
}


def fetch_url(url, timeout=45):
    req = Request(url, headers=REQUEST_HEADERS)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def decode_rsc_flights(html):
    chunks = []
    for match in re.finditer(
        r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html
    ):
        chunk = match.group(1)
        try:
            chunk = bytes(chunk, "utf-8").decode("unicode_escape")
        except Exception:
            pass
        chunks.append(chunk)
    return "".join(chunks)


def unescape_text(value):
    if not value:
        return value
    try:
        return codecs.decode(value, "unicode_escape")
    except Exception:
        return value


def extract_plugins_from_rsc(rsc_data):
    plugins = []
    for match in re.finditer(
        r'\{"id":"(\d+)","name":"([a-z0-9-]+)","displayName":"([^"]+)"',
        rsc_data,
    ):
        block = rsc_data[match.start() : match.start() + 4000]
        if '"category":"automation"' in block:
            continue

        desc_match = re.search(r'"description":"((?:[^"\\]|\\.)*)"', block)
        description = (
            unescape_text(desc_match.group(1)) if desc_match else ""
        )

        cats_match = re.search(r'"curatedCategoryKeys":\[([^\]]*)\]', block)
        categories = (
            re.findall(r'"([A-Z_]+)"', cats_match.group(1))
            if cats_match
            else []
        )

        repo_match = re.search(r'"repositoryUrl":"([^"]+)"', block)
        publisher_match = re.search(r'"publisherName":"([^"]+)"', block)
        logo_match = re.search(r'"logoUrl":"([^"]+)"', block)
        homepage_match = re.search(r'"homepageUrl":"([^"]+)"', block)

        plugins.append(
            {
                "id": match.group(1),
                "slug": match.group(2),
                "displayName": match.group(3),
                "description": description,
                "categories": categories,
                "categoryLabels": [
                    CATEGORY_LABELS.get(c, c) for c in categories
                ],
                "repositoryUrl": repo_match.group(1) if repo_match else None,
                "publisherName": publisher_match.group(1) if publisher_match else None,
                "logoUrl": logo_match.group(1) if logo_match else None,
                "homepageUrl": homepage_match.group(1) if homepage_match else None,
            }
        )

    by_slug = OrderedDict()
    for plugin in plugins:
        slug = plugin["slug"]
        existing = by_slug.get(slug)
        if not existing or len(plugin["categories"]) > len(existing["categories"]):
            by_slug[slug] = plugin
    return list(by_slug.values())


def extract_automations_from_rsc(rsc_data):
    automations = []
    for match in re.finditer(
        r'\{"id":"([a-z0-9-]+)","name":"([^"]+)","description":"((?:[^"\\]|\\.)*)","category":"automation"',
        rsc_data,
    ):
        block = rsc_data[match.start() : match.start() + 2500]
        icon_match = re.search(r'"icon":"([^"]+)"', block)
        automations.append(
            {
                "id": match.group(1),
                "name": match.group(2),
                "description": unescape_text(match.group(3)),
                "icon": icon_match.group(1) if icon_match else None,
            }
        )

    by_id = OrderedDict()
    for item in automations:
        by_id[item["id"]] = item
    return list(by_id.values())


def parse_plugin_detail(html):
    rsc_data = decode_rsc_flights(html)
    idx = rsc_data.find("initialPluginJson")
    if idx < 0:
        return None

    start = rsc_data.find("{", idx)
    depth = 0
    end = start
    for i, ch in enumerate(rsc_data[start : start + 80000]):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = start + i + 1
                break

    raw = rsc_data[start:end]
    result = {}

    for key in (
        "id",
        "name",
        "displayName",
        "description",
        "repositoryUrl",
        "publisherName",
        "homepageUrl",
    ):
        match = re.search(r'"%s":"([^"]*)"' % key, raw)
        if match:
            result[key] = unescape_text(match.group(1))

    for key in ("verified", "isPreview"):
        match = re.search(r'"%s":(true|false)' % key, raw)
        if match:
            result[key] = match.group(1) == "true"

    skills_match = re.search(
        r'"skills":(\[[^\]]*(?:\{[^\}]*\}[^\]]*)*\])', raw
    )
    if skills_match:
        skills_blob = skills_match.group(1)
        skills = []
        for skill_match in re.finditer(
            r'\{"name":"([^"]+)"(?:,"displayName":"([^"]*)")?.*?"description":"((?:[^"\\]|\\.)*)"',
            skills_blob,
        ):
            skills.append(
                {
                    "name": skill_match.group(1),
                    "displayName": skill_match.group(2) or skill_match.group(1),
                    "description": unescape_text(skill_match.group(3)),
                }
            )
        if not skills:
            skills = [
                {"name": name}
                for name in re.findall(r'"name":"([^"]+)"', skills_blob)
            ]
        result["skills"] = skills

    mcp_match = re.search(
        r'"mcpServers":(\[[^\]]*(?:\{[^\}]*\}[^\]]*)*\])', raw
    )
    if mcp_match:
        result["mcpServers"] = [
            {"name": name}
            for name in re.findall(r'"name":"([^"]+)"', mcp_match.group(1))
        ]

    for component in ("rules", "hooks", "commands", "subagents"):
        comp_match = re.search(r'"%s":(\[[^\]]*\])' % component, raw)
        if comp_match:
            result[component] = re.findall(
                r'"name":"([^"]+)"', comp_match.group(1)
            )

    cats_match = re.search(r'"curatedCategoryKeys":\[([^\]]*)\]', raw)
    if cats_match:
        result["categories"] = re.findall(
            r'"([A-Z_]+)"', cats_match.group(1)
        )
        result["categoryLabels"] = [
            CATEGORY_LABELS.get(c, c) for c in result["categories"]
        ]

    return result


def fetch_plugin_detail(slug):
    url = "%s/%s" % (MARKETPLACE_URL, slug)
    try:
        html = fetch_url(url, timeout=40)
        detail = parse_plugin_detail(html)
        if detail:
            detail["detailUrl"] = url
        return slug, detail, None
    except (HTTPError, URLError, Exception) as exc:
        return slug, None, str(exc)


def fetch_official_github_plugins():
    official = {"marketplace_manifest": None, "plugin_dirs": [], "error": None}
    try:
        official["marketplace_manifest"] = json.loads(
            fetch_url(GITHUB_MARKETPLACE_JSON)
        )
    except Exception as exc:
        official["error"] = "marketplace.json: %s" % exc

    try:
        contents = json.loads(fetch_url(GITHUB_REPO_API))
        for item in contents:
            if item.get("type") == "dir" and not item["name"].startswith("."):
                if item["name"] not in (".github",):
                    official["plugin_dirs"].append(item["name"])
    except Exception as exc:
        if not official["error"]:
            official["error"] = "repo api: %s" % exc

    return official


def summarize_components(plugins_with_details):
    totals = Counter()
    for plugin in plugins_with_details:
        for key in ("skills", "mcpServers", "rules", "hooks", "commands", "subagents"):
            value = plugin.get(key)
            if isinstance(value, list) and value:
                totals[key] += len(value)
    return dict(totals)


def build_report(fetch_details=True, detail_limit=None):
    print("Fetching marketplace homepage...")
    html = fetch_url(MARKETPLACE_URL)
    rsc_data = decode_rsc_flights(html)
    print("Decoded RSC payload: %d chars" % len(rsc_data))

    plugins = extract_plugins_from_rsc(rsc_data)
    automations = extract_automations_from_rsc(rsc_data)
    print("Found %d plugins, %d automations" % (len(plugins), len(automations)))

    official = fetch_official_github_plugins()

    details_map = {}
    if fetch_details:
        slugs = [p["slug"] for p in plugins]
        if detail_limit:
            slugs = slugs[:detail_limit]
        print("Fetching details for %d plugins..." % len(slugs))

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(fetch_plugin_detail, slug): slug for slug in slugs
            }
            done = 0
            for future in as_completed(futures):
                slug, detail, error = future.result()
                done += 1
                if detail:
                    details_map[slug] = detail
                elif error:
                    details_map[slug] = {"error": error}
                if done % 25 == 0:
                    print("  ... %d/%d" % (done, len(slugs)))
                time.sleep(0.05)

    enriched_plugins = []
    for plugin in plugins:
        merged = dict(plugin)
        detail = details_map.get(plugin["slug"])
        if detail and "error" not in detail:
            for key, value in detail.items():
                if key not in ("id",) and value:
                    merged[key] = value
            merged["components"] = {
                "skills": len(merged.get("skills") or []),
                "mcpServers": len(merged.get("mcpServers") or []),
                "rules": len(merged.get("rules") or []),
                "hooks": len(merged.get("hooks") or []),
                "commands": len(merged.get("commands") or []),
                "subagents": len(merged.get("subagents") or []),
            }
        enriched_plugins.append(merged)

    category_index = {}
    for plugin in enriched_plugins:
        cats = plugin.get("categories") or ["UNCATEGORIZED"]
        if not cats:
            cats = ["UNCATEGORIZED"]
        for cat in cats:
            category_index.setdefault(cat, []).append(plugin["slug"])

    category_stats = {
        CATEGORY_LABELS.get(cat, cat): {
            "key": cat,
            "count": len(slugs),
            "slugs": slugs,
        }
        for cat, slugs in sorted(
            category_index.items(), key=lambda item: -len(item[1])
        )
    }

    with_details = [p for p in enriched_plugins if p.get("components")]
    component_totals = summarize_components(with_details)

    report = {
        "meta": {
            "source": MARKETPLACE_URL,
            "scrapedAt": datetime.now(timezone.utc).isoformat(),
            "pluginCount": len(enriched_plugins),
            "automationCount": len(automations),
            "detailsFetched": len(with_details),
            "rscPayloadBytes": len(rsc_data),
        },
        "organization": {
            "summary": (
                "Cursor Marketplace 是官方插件分发与发现入口，内容分为 Plugins（可安装扩展包）"
                "与 Automations（预置 Agent 工作流）两大类型。插件按 curatedCategoryKeys 分区展示，"
                "每个插件是包含 Skills、MCP Servers、Rules、Hooks、Commands、Subagents 等原语的 Git 仓库 bundle。"
            ),
            "contentTypes": [
                {
                    "type": "plugin",
                    "description": "可安装扩展包，通过 .cursor-plugin/plugin.json 清单定义",
                    "install": "Customize 侧栏或 /add-plugin<slug> 命令",
                },
                {
                    "type": "automation",
                    "description": "预置 Agent 工作流，含 triggers（Git/Slack 等）与 actions",
                    "install": "Marketplace Automations 区域",
                },
            ],
            "categories": category_stats,
            "pluginPrimitives": [
                "skills",
                "mcpServers",
                "rules",
                "hooks",
                "commands",
                "subagents",
            ],
            "distribution": {
                "officialReview": True,
                "openSourceRequired": True,
                "publishUrl": "https://cursor.com/marketplace/publish",
                "communityDirectory": "https://cursor.directory",
                "officialGitHub": "https://github.com/cursor/plugins",
            },
        },
        "componentTotals": component_totals,
        "plugins": enriched_plugins,
        "automations": automations,
        "officialCursorPlugins": official,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Scrape Cursor Marketplace")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument(
        "--no-details", action="store_true", help="Skip per-plugin detail pages"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit detail fetches"
    )
    args = parser.parse_args()

    report = build_report(
        fetch_details=not args.no_details,
        detail_limit=args.limit,
    )

    print("\n=== Summary ===")
    print("Plugins:", report["meta"]["pluginCount"])
    print("Automations:", report["meta"]["automationCount"])
    print("Details fetched:", report["meta"]["detailsFetched"])
    print("Categories:", len(report["organization"]["categories"]))
    for label, info in list(report["organization"]["categories"].items())[:8]:
        print("  %s: %d" % (label, info["count"]))

    if args.dry_run:
        print("\n[dry-run] Not writing file.")
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
