#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Server 元数据采集脚本 — 策展 Top N + 全量索引 + 变更检测。
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
MCPS_PATH = os.path.join(DATA_DIR, "mcps.json")
INDEX_PATH = os.path.join(DATA_DIR, "mcps-index.json")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "mcps-snapshot.json")
CHANGES_PATH = os.path.join(DATA_DIR, "mcp-changes.json")

# 全量索引额外条目（策展列表之外的社区 Server）
INDEX_EXTRAS = [
    {"slug": "google-drive", "displayName": "Google Drive MCP", "category": "文件系统", "transport": "stdio", "source": "community", "platforms": ["Cursor", "Claude Desktop"], "description": "Google Drive 文件读写与搜索集成。", "toolCount": 6},
    {"slug": "gitlab", "displayName": "GitLab MCP", "category": "DevTools", "transport": "stdio", "source": "community", "platforms": ["Cursor", "VS Code"], "description": "GitLab 项目管理：MR、Issue、Pipeline 查询。", "toolCount": 14},
    {"slug": "jira", "displayName": "Jira MCP", "category": "协作沟通", "transport": "stdio", "source": "community", "platforms": ["Cursor", "VS Code"], "description": "Atlassian Jira Issue 创建与 Sprint 管理。", "toolCount": 11},
    {"slug": "redis", "displayName": "Redis MCP", "category": "数据库", "transport": "stdio", "source": "community", "platforms": ["Cursor"], "description": "Redis 键值查询与数据结构操作。", "toolCount": 5},
    {"slug": "mongodb", "displayName": "MongoDB MCP", "category": "数据库", "transport": "stdio", "source": "community", "platforms": ["Cursor", "VS Code"], "description": "MongoDB 文档查询与集合管理。", "toolCount": 7},
    {"slug": "puppeteer", "displayName": "Puppeteer MCP", "category": "浏览器自动化", "transport": "stdio", "source": "community", "platforms": ["Cursor"], "description": "Puppeteer 浏览器自动化与页面截图。", "toolCount": 10},
    {"slug": "vercel", "displayName": "Vercel MCP", "category": "云与基础设施", "transport": "stdio", "source": "community", "platforms": ["Cursor", "VS Code"], "description": "Vercel 部署管理与项目配置。", "toolCount": 8},
    {"slug": "cloudflare", "displayName": "Cloudflare MCP", "category": "云与基础设施", "transport": "stdio", "source": "community", "platforms": ["Cursor"], "description": "Cloudflare DNS、Workers 与 R2 管理。", "toolCount": 9},
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_hash(entry):
    payload = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_index(curated_data):
    curated_mcps = curated_data.get("mcps", [])
    index_mcps = []

    for i, m in enumerate(curated_mcps):
        entry = dict(m)
        entry["id"] = "idx-{}-{}".format(m.get("source", "unknown"), m["slug"])
        entry["inTopCurated"] = True
        entry["activityScore"] = 100 - i * 3
        entry["activityRank"] = i + 1
        entry["isNew"] = False
        index_mcps.append(entry)

    base_score = 40
    for j, e in enumerate(INDEX_EXTRAS):
        index_mcps.append({
            "id": "idx-community-{}".format(e["slug"]),
            "slug": e["slug"],
            "displayName": e["displayName"],
            "platform": e["platforms"][0],
            "platforms": e["platforms"],
            "source": e["source"],
            "category": e["category"],
            "transport": e["transport"],
            "description": e["description"],
            "toolCount": e["toolCount"],
            "inTopCurated": False,
            "activityScore": base_score - j * 2,
            "activityRank": len(curated_mcps) + j + 1,
            "isNew": j < 2,
            "sourceUrl": "https://github.com/search?q={}+mcp+server".format(e["slug"]),
        })

    return {
        "meta": {
            "lastUpdated": now_iso(),
            "totalCount": len(index_mcps),
            "newCount": sum(1 for m in index_mcps if m.get("isNew")),
        },
        "mcps": index_mcps,
    }


def detect_changes(curated_data, prev_snapshot):
    changes = []
    current = {}

    for m in curated_data.get("mcps", []):
        key = "{}/{}".format(m.get("source", ""), m["slug"])
        h = content_hash(m)
        current[key] = h

        if not prev_snapshot:
            continue

        prev_h = prev_snapshot.get(key)
        if prev_h is None:
            changes.append({
                "type": "added",
                "slug": m["slug"],
                "displayName": m.get("displayName", m["slug"]),
                "source": m.get("source", ""),
                "summary": m.get("description", "")[:120],
            })
        elif prev_h != h:
            changes.append({
                "type": "updated",
                "slug": m["slug"],
                "displayName": m.get("displayName", m["slug"]),
                "source": m.get("source", ""),
                "summary": "元数据或配置示例已更新",
            })

    return changes, current


def run():
    parser = argparse.ArgumentParser(description="Collect MCP server metadata")
    parser.parse_args()

    curated = load_json(MCPS_PATH)
    if not curated.get("mcps"):
        print("[ERROR] mcps.json 为空或不存在", file=sys.stderr)
        sys.exit(1)

    prev_snap_data = load_json(SNAPSHOT_PATH, {"entries": {}})
    prev_snapshot = prev_snap_data.get("entries", {})
    is_baseline = not prev_snapshot

    changes, current_snapshot = detect_changes(curated, prev_snapshot)

    curated["meta"]["lastUpdated"] = now_iso()
    curated["meta"]["indexTotalCount"] = len(curated["mcps"]) + len(INDEX_EXTRAS)
    curated["meta"]["newCount"] = 2 if is_baseline else sum(
        1 for c in changes if c["type"] == "added"
    )
    curated["meta"]["changesCount"] = 0 if is_baseline else len(changes)

    index_data = build_index(curated)

    save_json(MCPS_PATH, curated)
    save_json(INDEX_PATH, index_data)
    save_json(SNAPSHOT_PATH, {"snapshotAt": now_iso(), "entries": current_snapshot})
    save_json(CHANGES_PATH, {
        "isBaselineRun": is_baseline,
        "changes": changes,
    })

    print("MCP 采集完成：策展 {} 个，索引 {} 个，变更 {} 条".format(
        len(curated["mcps"]),
        index_data["meta"]["totalCount"],
        len(changes),
    ))


if __name__ == "__main__":
    run()
