#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 元数据采集脚本 — 策展 SOTA Top N + 全量索引 + 变更检测。
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
LLMS_PATH = os.path.join(DATA_DIR, "llms.json")
INDEX_PATH = os.path.join(DATA_DIR, "llms-index.json")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "llms-snapshot.json")
CHANGES_PATH = os.path.join(DATA_DIR, "llm-changes.json")

# 全量索引额外条目（策展列表之外的模型）
INDEX_EXTRAS = [
    {
        "slug": "gpt-4o",
        "displayName": "GPT-4o",
        "provider": "OpenAI",
        "providers": ["OpenAI", "Azure OpenAI"],
        "category": "多模态",
        "description": "上一代 OpenAI 多模态旗舰，仍广泛用于生产。",
        "openWeights": False,
        "contextWindow": 128000,
    },
    {
        "slug": "claude-3-5-sonnet",
        "displayName": "Claude 3.5 Sonnet",
        "provider": "Anthropic",
        "providers": ["Anthropic"],
        "category": "代码 Agent",
        "description": "上一代 Claude 代码标杆，部分场景仍被引用对比。",
        "openWeights": False,
        "contextWindow": 200000,
    },
    {
        "slug": "gemini-2-0-flash",
        "displayName": "Gemini 2.0 Flash",
        "provider": "Google",
        "providers": ["Google AI"],
        "category": "高性价比",
        "description": "Google 上一代高速模型，成本极低。",
        "openWeights": False,
        "contextWindow": 1000000,
    },
    {
        "slug": "llama-3-3-70b",
        "displayName": "Llama 3.3 70B",
        "provider": "Meta",
        "providers": ["Meta", "Together AI"],
        "category": "开源权重",
        "description": "Meta 上一代开源主力，社区生态成熟。",
        "openWeights": True,
        "contextWindow": 128000,
    },
    {
        "slug": "command-r-plus",
        "displayName": "Command R+",
        "provider": "Cohere",
        "providers": ["Cohere"],
        "category": "通用对话",
        "description": "Cohere 企业 RAG 优化模型。",
        "openWeights": False,
        "contextWindow": 128000,
    },
    {
        "slug": "yi-lightning",
        "displayName": "Yi Lightning",
        "provider": "01.AI",
        "providers": ["01.AI"],
        "category": "高性价比",
        "description": "零一万物高速低成本模型。",
        "openWeights": False,
        "contextWindow": 32000,
    },
    {
        "slug": "glm-4-plus",
        "displayName": "GLM-4 Plus",
        "provider": "Zhipu",
        "providers": ["Zhipu AI"],
        "category": "通用对话",
        "description": "智谱 AI 旗舰，中文场景优化。",
        "openWeights": False,
        "contextWindow": 128000,
    },
    {
        "slug": "dbrx-instruct",
        "displayName": "DBRX Instruct",
        "provider": "Databricks",
        "providers": ["Databricks"],
        "category": "开源权重",
        "description": "Databricks MoE 开源模型。",
        "openWeights": True,
        "contextWindow": 32768,
    },
    {
        "slug": "mixtral-8x22b",
        "displayName": "Mixtral 8x22B",
        "provider": "Mistral",
        "providers": ["Mistral AI"],
        "category": "开源权重",
        "description": "Mistral 大型 MoE 开源模型。",
        "openWeights": True,
        "contextWindow": 65536,
    },
    {
        "slug": "o1-preview",
        "displayName": "OpenAI o1",
        "provider": "OpenAI",
        "providers": ["OpenAI"],
        "category": "深度推理",
        "description": "OpenAI 第一代推理模型，已被 o3 取代。",
        "openWeights": False,
        "contextWindow": 128000,
    },
    {
        "slug": "nova-pro",
        "displayName": "Amazon Nova Pro",
        "provider": "Amazon",
        "providers": ["AWS Bedrock"],
        "category": "多模态",
        "description": "Amazon 自研多模态模型，Bedrock 原生。",
        "openWeights": False,
        "contextWindow": 300000,
    },
    {
        "slug": "grok-2",
        "displayName": "Grok 2",
        "provider": "xAI",
        "providers": ["xAI"],
        "category": "通用对话",
        "description": "xAI 上一代模型，已被 Grok 3 取代。",
        "openWeights": False,
        "contextWindow": 131072,
    },
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
    curated_llms = curated_data.get("llms", [])
    index_llms = []

    for i, m in enumerate(curated_llms):
        entry = dict(m)
        entry["id"] = "idx-{}-{}".format(m.get("provider", "unknown"), m["slug"])
        entry["inTopCurated"] = True
        entry["activityScore"] = 100 - i * 3
        entry["activityRank"] = i + 1
        entry["isNew"] = False
        index_llms.append(entry)

    base_score = 40
    for j, e in enumerate(INDEX_EXTRAS):
        index_llms.append({
            "id": "idx-extra-{}".format(e["slug"]),
            "slug": e["slug"],
            "displayName": e["displayName"],
            "provider": e["provider"],
            "providers": e["providers"],
            "category": e["category"],
            "description": e["description"],
            "openWeights": e["openWeights"],
            "contextWindow": e["contextWindow"],
            "inTopCurated": False,
            "activityScore": base_score - j * 2,
            "activityRank": len(curated_llms) + j + 1,
            "isNew": j < 2,
            "sourceUrl": "https://artificialanalysis.ai/models/{}".format(e["slug"]),
        })

    return {
        "meta": {
            "lastUpdated": now_iso(),
            "totalCount": len(index_llms),
            "newCount": sum(1 for m in index_llms if m.get("isNew")),
        },
        "llms": index_llms,
    }


def detect_changes(curated_data, prev_snapshot):
    changes = []
    current = {}

    for m in curated_data.get("llms", []):
        key = "{}/{}".format(m.get("provider", ""), m["slug"])
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
                "provider": m.get("provider", ""),
                "summary": m.get("description", "")[:120],
            })
        elif prev_h != h:
            changes.append({
                "type": "updated",
                "slug": m["slug"],
                "displayName": m.get("displayName", m["slug"]),
                "provider": m.get("provider", ""),
                "summary": "评测分数或口碑数据已更新",
            })

    return changes, current


def run():
    parser = argparse.ArgumentParser(description="Collect LLM metadata and benchmarks")
    parser.parse_args()

    curated = load_json(LLMS_PATH)
    if not curated.get("llms"):
        print("[ERROR] llms.json 为空或不存在", file=sys.stderr)
        sys.exit(1)

    prev_snap_data = load_json(SNAPSHOT_PATH, {"entries": {}})
    prev_snapshot = prev_snap_data.get("entries", {})
    is_baseline = not prev_snapshot

    changes, current_snapshot = detect_changes(curated, prev_snapshot)

    index_data = build_index(curated)

    curated["meta"]["lastUpdated"] = now_iso()
    curated["meta"]["indexTotalCount"] = index_data["meta"]["totalCount"]
    curated["meta"]["newCount"] = index_data["meta"]["newCount"]
    curated["meta"]["changesCount"] = len(changes)

    save_json(LLMS_PATH, curated)
    save_json(INDEX_PATH, index_data)
    save_json(SNAPSHOT_PATH, {"meta": {"lastUpdated": now_iso()}, "entries": current_snapshot})
    save_json(CHANGES_PATH, {
        "meta": {"lastUpdated": now_iso(), "totalChanges": len(changes)},
        "isBaselineRun": is_baseline,
        "changes": changes,
    })

    print("[OK] LLM index: {} total, {} new, {} changes".format(
        index_data["meta"]["totalCount"],
        index_data["meta"]["newCount"],
        len(changes),
    ))


if __name__ == "__main__":
    run()
