#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竞品信息采集脚本 — 从公开来源抓取 AI Coding 竞品动态并更新 events.json。

用法:
  python scripts/collect_events.py              # 抓取并合并到 data/events.json
  python scripts/collect_events.py --dry-run      # 仅预览，不写入
  python scripts/collect_events.py --sources      # 列出监控来源

数据来源:
  - 官方 Changelog / Release Notes
  - 科技媒体报道 (TechCrunch, Bloomberg 等)
  - 社区论坛 (Hacker News)
"""

from __future__ import print_function

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
EVENTS_PATH = os.path.join(DATA_DIR, "events.json")
COMPETITORS_PATH = os.path.join(DATA_DIR, "competitors.json")

# 监控来源配置
SOURCES = [
    {
        "company": "Cursor",
        "category": "产品",
        "topic": "Agent",
        "url": "https://cursor.com/changelog",
        "sourceTier": "A",
    },
    {
        "company": "Anthropic",
        "category": "产品",
        "topic": "Agent",
        "url": "https://api.github.com/repos/anthropics/claude-code/releases?per_page=5",
        "sourceTier": "A",
        "type": "github_releases",
    },
    {
        "company": "GitHub",
        "category": "产品",
        "topic": "Agent",
        "url": "https://github.blog/changelog/feed/",
        "sourceTier": "A",
        "type": "rss",
        "filter": "copilot",
    },
    {
        "company": "Cognition",
        "category": "产品",
        "topic": "Agent",
        "url": "https://devin.ai/blog",
        "sourceTier": "A",
    },
    {
        "company": "Replit",
        "category": "产品",
        "topic": "Agent",
        "url": "https://replit.com/blog",
        "sourceTier": "A",
    },
    {
        "company": "Google",
        "category": "产品",
        "topic": "Agent",
        "url": "https://jules.google",
        "sourceTier": "A",
    },
    {
        "company": "AWS",
        "category": "产品",
        "topic": "IDE",
        "url": "https://kiro.dev/blog",
        "sourceTier": "A",
    },
]


def fetch_url(url, timeout=15):
    """抓取 URL 内容，带 User-Agent 头。"""
    req = Request(url, headers={"User-Agent": "AIDreamingTrue-Collector/1.0"})
    try:
        resp = urlopen(req, timeout=timeout)
        return resp.read()
    except (HTTPError, URLError) as e:
        print("  [WARN] 无法抓取 {}: {}".format(url, e), file=sys.stderr)
        return None


def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_github_releases(content, source):
    """解析 GitHub Releases API 响应。"""
    events = []
    try:
        releases = json.loads(content)
    except json.JSONDecodeError:
        return events

    for rel in releases[:5]:
        tag = rel.get("tag_name", "")
        title = "Claude Code {} 发布".format(tag)
        published = rel.get("published_at", "")[:10]
        body = rel.get("body", "") or ""
        summary = body[:200].replace("\n", " ").strip()
        if not summary:
            summary = "Claude Code 新版本 {}".format(tag)

        events.append({
            "id": "auto-claude-{}".format(tag.replace(".", "-")),
            "title": title,
            "date": published,
            "category": source["category"],
            "topic": source["topic"],
            "company": source["company"],
            "heat": 75,
            "growth": 8,
            "sourceTier": source["sourceTier"],
            "summary": summary,
            "whyImportant": "Claude Code 持续高频迭代，终端 Agent 能力不断增强。",
            "impact": "关注 release notes 中的权限、MCP 和 subagent 相关变更。",
            "sourceUrl": rel.get("html_url", source["url"]),
        })
    return events


def parse_rss_items(content, source):
    """简易 RSS 解析，提取 title/link/pubDate。"""
    events = []
    if not content:
        return events

    text = content.decode("utf-8", errors="replace")
    items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
    keyword = source.get("filter", "").lower()

    for item in items[:10]:
        title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item)
        link_m = re.search(r"<link>(.*?)</link>", item)
        date_m = re.search(r"<pubDate>(.*?)</pubDate>", item)

        if not title_m:
            continue
        title = title_m.group(1).strip()
        if keyword and keyword not in title.lower():
            continue

        link = link_m.group(1).strip() if link_m else source["url"]
        date_str = "2026-01-01"
        if date_m:
            try:
                date_str = parsedate_to_datetime(date_m.group(1)).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40]
        events.append({
            "id": "auto-gh-{}".format(slug),
            "title": title,
            "date": date_str,
            "category": source["category"],
            "topic": source["topic"],
            "company": source["company"],
            "heat": 70,
            "growth": 6,
            "sourceTier": source["sourceTier"],
            "summary": "GitHub 官方 Changelog 更新：{}".format(title),
            "whyImportant": "GitHub Copilot 生态动态，影响企业开发者工作流。",
            "impact": "关注 Agent 模式、CLI 和企业策略相关变更。",
            "sourceUrl": link,
        })
    return events


def collect_from_sources():
    """遍历所有来源，尝试抓取新事件。"""
    all_new = []
    for src in SOURCES:
        print("抓取: {} ({})".format(src["company"], src["url"]))
        content = fetch_url(src["url"])
        if not content:
            continue

        src_type = src.get("type", "")
        if src_type == "github_releases":
            events = parse_github_releases(content, src)
        elif src_type == "rss":
            events = parse_rss_items(content, src)
        else:
            # HTML 页面暂不自动解析，仅记录可达性
            print("  [OK] 页面可达 ({} bytes)，需人工审核后录入".format(len(content)))
            continue

        print("  发现 {} 条".format(len(events)))
        all_new.extend(events)
        time.sleep(1)

    return all_new


def merge_events(existing, new_events):
    """按 id 去重合并，保留已有事件不被覆盖。"""
    by_id = {}
    for e in existing:
        by_id[e["id"]] = e
    added = 0
    for e in new_events:
        if e["id"] not in by_id:
            by_id[e["id"]] = e
            added += 1
    merged = sorted(by_id.values(), key=lambda x: x.get("date", ""), reverse=True)
    return merged, added


def list_sources():
    print("监控来源列表:\n")
    competitors = load_json(COMPETITORS_PATH)
    for c in competitors:
        print("  [{}] {} — {}".format(c.get("category", ""), c["name"], c.get("changelogUrl", "")))
    print("\n自动采集来源:\n")
    for s in SOURCES:
        print("  {} — {} ({})".format(s["company"], s["url"], s.get("type", "html")))


def main():
    parser = argparse.ArgumentParser(description="AI Coding 竞品信息采集")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入文件")
    parser.add_argument("--sources", action="store_true", help="列出监控来源")
    args = parser.parse_args()

    if args.sources:
        list_sources()
        return

    print("=== AI Coding 竞品信息采集 ===")
    print("时间: {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M")))

    existing = load_json(EVENTS_PATH)
    print("现有事件: {} 条\n".format(len(existing)))

    new_events = collect_from_sources()
    merged, added = merge_events(existing, new_events)

    print("\n新增: {} 条，合并后总计: {} 条".format(added, len(merged)))

    if args.dry_run:
        print("\n[DRY-RUN] 未写入文件")
        for e in new_events[:5]:
            print("  - {} ({})".format(e["title"], e["date"]))
        return

    save_json(EVENTS_PATH, merged)
    print("\n已更新: {}".format(EVENTS_PATH))


if __name__ == "__main__":
    main()
