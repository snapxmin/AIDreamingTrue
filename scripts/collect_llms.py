#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 评测数据采集脚本 — 从公开评测网站抓取业界最新 SOTA 大模型数据。

用法:
  python scripts/collect_llms.py            # 抓取最新数据并重建 llms.json / index / changes
  python scripts/collect_llms.py --dry-run    # 仅预览，不写入
  python scripts/collect_llms.py --offline    # 跳过网络抓取，仅基于现有 llms.json 重建索引
  python scripts/collect_llms.py --top 24      # 指定策展 Top N 数量（默认 24）
  python scripts/collect_llms.py --sources    # 列出数据来源

数据来源:
  - Chatbot Arena（openlm.ai 镜像）: 人工盲测 Elo、编程 Elo、Vision、AAII、MMLU-Pro、ARC-AGI
  - SWE-bench（swebench.com Verified 榜单内联数据）: 真实软件工程任务解决率
  - Hacker News（Algolia Search API）: 外网社区口碑信号

设计原则:
  - 每个来源独立 try/except，任一来源失败均降级而非中断
  - 网络完全不可用时，回退到现有 llms.json 并仅重建索引（保持旧行为）
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
LLMS_PATH = os.path.join(DATA_DIR, "llms.json")
INDEX_PATH = os.path.join(DATA_DIR, "llms-index.json")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "llms-snapshot.json")
CHANGES_PATH = os.path.join(DATA_DIR, "llm-changes.json")

USER_AGENT = "AIDreamingTrue-LLMCollector/2.0"

# 全量索引最多保留的模型数量（按 Arena Elo 排序），避免历史模型无限膨胀
INDEX_CAP = 60

ARENA_URL = "https://openlm.ai/chatbot-arena/"
SWEBENCH_URL = "https://www.swebench.com/"
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"

SOURCES = [
    {"id": "chatbot-arena", "name": "Chatbot Arena (openlm.ai)", "url": ARENA_URL, "focus": "人工盲测 Elo + 综合基准"},
    {"id": "swe-bench", "name": "SWE-bench Verified", "url": SWEBENCH_URL, "focus": "真实软件工程任务"},
    {"id": "community-sentiment", "name": "Hacker News", "url": HN_SEARCH_URL, "focus": "外网社区口碑"},
]

# 组织名 -> 规范化提供商名
PROVIDER_ALIASES = {
    "google deepmind": "Google",
    "google": "Google",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "xai": "xAI",
    "x ai": "xAI",
    "meta": "Meta",
    "meta ai": "Meta",
    "mistral": "Mistral",
    "mistral ai": "Mistral",
    "deepseek": "DeepSeek",
    "deepseek ai": "DeepSeek",
    "alibaba": "Alibaba",
    "qwen": "Alibaba",
    "moonshot": "Moonshot",
    "moonshot ai": "Moonshot",
    "zhipu": "Zhipu",
    "zhipu ai": "Zhipu",
    "z.ai": "Zhipu",
    "z ai": "Zhipu",
    "bytedance": "ByteDance",
    "byte dance": "ByteDance",
    "01 ai": "01.AI",
    "01.ai": "01.AI",
    "minimax": "MiniMax",
    "microsoft": "Microsoft",
    "nvidia": "NVIDIA",
    "cohere": "Cohere",
    "amazon": "Amazon",
    "reka ai": "Reka",
    "databricks": "Databricks",
    "tencent": "Tencent",
    "baidu": "Baidu",
}

# 提供商 -> 可用 AI Coding 产品（启发式）
PROVIDER_PRODUCTS = {
    "Anthropic": ["Cursor", "Claude Code", "GitHub Copilot", "AWS Bedrock"],
    "OpenAI": ["GitHub Copilot", "ChatGPT", "Azure OpenAI", "Cursor"],
    "Google": ["Google Antigravity", "Gemini", "Vertex AI"],
    "xAI": ["Grok", "API"],
    "DeepSeek": ["OpenRouter", "Cursor", "Ollama"],
    "Alibaba": ["Alibaba Cloud", "Ollama", "OpenRouter"],
    "Meta": ["Ollama", "Together AI", "AWS Bedrock"],
    "Mistral": ["Mistral API", "Le Chat", "Continue.dev"],
    "Moonshot": ["GitHub Copilot", "Kimi Chat"],
    "Zhipu": ["Zhipu API", "OpenRouter"],
    "MiniMax": ["MiniMax API", "OpenRouter"],
    "Microsoft": ["Azure AI", "Ollama"],
    "01.AI": ["01.AI API"],
    "Cohere": ["Cohere API"],
    "Amazon": ["AWS Bedrock"],
    "ByteDance": ["Volcengine", "Trae"],
    "Baidu": ["百度智能云", "文心"],
    "Tencent": ["腾讯云"],
}

# 提供商 -> 官方主页
PROVIDER_URLS = {
    "Anthropic": "https://www.anthropic.com/claude",
    "OpenAI": "https://openai.com",
    "Google": "https://deepmind.google/technologies/gemini",
    "xAI": "https://x.ai",
    "DeepSeek": "https://www.deepseek.com",
    "Alibaba": "https://github.com/QwenLM",
    "Meta": "https://llama.meta.com",
    "Mistral": "https://mistral.ai",
    "Moonshot": "https://www.moonshot.cn",
    "Zhipu": "https://www.zhipuai.cn",
    "MiniMax": "https://www.minimaxi.com",
    "Microsoft": "https://azure.microsoft.com/products/ai-services",
    "01.AI": "https://www.01.ai",
    "Cohere": "https://cohere.com",
    "Amazon": "https://aws.amazon.com/bedrock",
    "ByteDance": "https://www.volcengine.com",
    "Baidu": "https://yiyan.baidu.com",
    "Tencent": "https://hunyuan.tencent.com",
}

# 已知定价（USD / 1M tokens），仅覆盖主流家族，未命中则省略
PRICING_HINTS = [
    ("claude opus", {"input": 15.0, "output": 75.0, "unit": "USD / 1M tokens"}),
    ("claude sonnet", {"input": 3.0, "output": 15.0, "unit": "USD / 1M tokens"}),
    ("claude haiku", {"input": 0.8, "output": 4.0, "unit": "USD / 1M tokens"}),
    ("gpt-5", {"input": 10.0, "output": 30.0, "unit": "USD / 1M tokens"}),
    ("o3", {"input": 20.0, "output": 80.0, "unit": "USD / 1M tokens"}),
    ("gemini", {"input": 3.5, "output": 10.5, "unit": "USD / 1M tokens"}),
    ("deepseek", {"input": 0.55, "output": 2.19, "unit": "USD / 1M tokens"}),
    ("grok", {"input": 3.0, "output": 15.0, "unit": "USD / 1M tokens"}),
    ("qwen", {"input": 0.4, "output": 1.6, "unit": "USD / 1M tokens"}),
    ("llama", {"input": 0.2, "output": 0.6, "unit": "USD / 1M tokens"}),
    ("kimi", {"input": 2.0, "output": 8.0, "unit": "USD / 1M tokens"}),
    ("mistral", {"input": 2.0, "output": 6.0, "unit": "USD / 1M tokens"}),
    ("glm", {"input": 0.6, "output": 2.2, "unit": "USD / 1M tokens"}),
    ("minimax", {"input": 0.3, "output": 1.2, "unit": "USD / 1M tokens"}),
]

# 已知上下文窗口（token），未命中则省略
CONTEXT_HINTS = [
    ("gemini", 1000000),
    ("claude", 200000),
    ("gpt-5", 256000),
    ("gpt-4", 128000),
    ("o3", 200000),
    ("o4", 200000),
    ("deepseek", 128000),
    ("qwen", 128000),
    ("llama", 128000),
    ("grok", 131072),
    ("kimi", 256000),
    ("mistral", 128000),
    ("glm", 128000),
    ("minimax", 1000000),
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


def fetch_url(url, timeout=25, retries=2):
    hdrs = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}
    last_err = None
    for attempt in range(retries + 1):
        req = Request(url, headers=hdrs)
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, ValueError) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    print("  [WARN] 抓取失败 {}: {}".format(url, last_err), file=sys.stderr)
    return None


def slugify(name):
    s = name.lower().strip()
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = s.replace("+", " plus ")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "model"


def parse_number(text):
    if text is None:
        return None
    t = re.sub(r"<[^>]+>", "", str(text)).strip()
    t = t.replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def strip_tags(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


def clean_model_name(name):
    """去除表格中的校验标记 emoji、多余空白，保留模型名主体。"""
    # 移除常见 emoji / 符号（✅🏆🥇🥈🥉➡️ 等非 ASCII 装饰字符）
    name = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u2B00-\u2BFF]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def clean_query_text(name):
    """为 HN 查询清洗模型名：去括号补充说明、保留核心名称。"""
    q = re.sub(r"[（(].*?[)）]", "", name)
    q = re.sub(r'["\\]', "", q)
    return re.sub(r"\s+", " ", q).strip()


def normalize_provider(org):
    key = re.sub(r"[^a-z0-9 .]", "", (org or "").lower()).strip()
    return PROVIDER_ALIASES.get(key, org.strip() if org else "未知")


def guess_category(name, coding_elo, arena_elo, open_weights):
    low = name.lower()
    tokens = set(re.split(r"[^a-z0-9]+", low))  # 按分隔符分词，避免 gemini 命中 "mini"
    if any(k in low for k in ["coder", "codestral", "devstral"]) or "code" in tokens:
        return "代码 Agent"
    if any(k in low for k in ["thinking", "reasoning", "deepthink"]) or tokens & {"o3", "o4", "r1"}:
        return "深度推理"
    if tokens & {"flash", "mini", "haiku", "lite", "nano", "small", "turbo", "air", "fast"}:
        return "高性价比"
    if tokens & {"vision", "vl", "omni", "multimodal"}:
        return "多模态"
    if open_weights:
        return "开源权重"
    if coding_elo and arena_elo and coding_elo >= arena_elo:
        return "代码 Agent"
    return "通用对话"


def match_hint(name, hints):
    low = name.lower()
    for key, val in hints:
        if key in low:
            return val
    return None


def parse_arena(html):
    """解析 Chatbot Arena 排行榜表格，返回按 Arena Elo 排序的模型列表。"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    if not rows:
        return []

    def cells(row):
        return [strip_tags(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]

    header = None
    parsed = []
    seen = set()
    for row in rows:
        cs = cells(row)
        if not cs:
            continue
        joined = " ".join(cs).lower()
        if header is None:
            if "model" in joined and ("arena" in joined or "elo" in joined):
                header = [c.lower() for c in cs]
            continue

        col = {}
        for i, val in enumerate(cs):
            if i < len(header):
                col[header[i]] = val

        name = clean_model_name(col.get("model") or "")
        if not name or name.lower() in seen:
            continue
        arena_elo = parse_number(col.get("arena elo") or col.get("arena score") or col.get("elo"))
        if arena_elo is None:
            continue
        seen.add(name.lower())

        org = col.get("organization") or col.get("org") or ""
        license_txt = (col.get("license") or "").lower()
        open_weights = bool(license_txt) and "proprietary" not in license_txt and "closed" not in license_txt

        parsed.append({
            "name": name,
            "provider": normalize_provider(org),
            "orgRaw": org,
            "license": col.get("license") or "",
            "openWeights": open_weights,
            "arenaElo": arena_elo,
            "codingElo": parse_number(col.get("coding")),
            "visionElo": parse_number(col.get("vision")),
            "aaii": parse_number(col.get("aaii")),
            "mmluPro": parse_number(col.get("mmlu-pro") or col.get("mmlu pro") or col.get("mmlu")),
            "arcAgi": parse_number(col.get("arc-agi") or col.get("arc agi")),
        })

    parsed.sort(key=lambda m: m["arenaElo"], reverse=True)
    return parsed


def parse_swebench(html):
    """解析 swebench.com 内联 Verified 榜单，返回 {模型家族关键词: (最佳解决率, 日期)}。"""
    m = re.search(r'<script[^>]*id="leaderboard-data"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return {}
    verified = next((lb for lb in data if lb.get("name") == "Verified"), None)
    if not verified:
        return {}

    best = {}
    for r in verified.get("results", []):
        entry_name = (r.get("name") or "").lower()
        resolved = r.get("resolved")
        date = r.get("date", "")
        if resolved is None:
            continue
        # 提取候选模型家族关键词（尽量带上版本号，跨空格/连字符）
        patterns = (
            r"claude[\w. -]*opus[\w. -]*\d[\w.]*",
            r"claude[\w. -]*sonnet[\w. -]*\d[\w.]*",
            r"gpt-?5[\w.]*", r"gpt-?4[\w.o]*",
            r"gemini[\w. -]*\d[\w.]*",
            r"deepseek[\w. -]*\d[\w.]*", r"deepseek-?[rv]\d[\w.-]*",
            r"qwen[\w. -]*\d[\w.]*",
            r"kimi[\w. -]*\d[\w.]*",
            r"glm[\w. -]*\d[\w.]*",
            r"grok[\w. -]*\d[\w.]*",
            r"minimax[\w. -]*m?\d[\w.]*",
            r"llama[\w. -]*\d[\w.]*",
            r"doubao[\w.-]*",
        )
        for pat in patterns:
            for fam in re.findall(pat, entry_name):
                fam = re.sub(r"\s+", " ", fam).strip()
                if fam not in best or resolved > best[fam][0]:
                    best[fam] = (round(resolved, 1), date)
    return best


def _versions(text):
    return set(re.findall(r"\d+(?:\.\d+)+|\d+", text.lower()))


def match_swebench(model_name, swe_best):
    """为模型名匹配 SWE-bench 最佳分数。

    要求家族关键词（如 opus/gpt-5/gemini）与版本号同时匹配，避免把
    旧版本（如 Opus 4.6）的分数错误归给新版本（Opus 4.8）。
    """
    low = model_name.lower()
    name_versions = _versions(model_name)
    candidates = []
    for fam, (score, date) in swe_best.items():
        core = fam.split("(")[0].strip()
        words = [t for t in re.split(r"[ .-]+", core) if t and not re.match(r"^\d", t)]
        if not words:
            continue
        # 家族关键词需全部出现在模型名中
        if not all(w in low for w in words):
            continue
        # 若模型名带版本号，则必须与 SWE 条目版本号有交集，
        # 避免把旧版本/无版本的历史分数错配给新版本模型
        fam_versions = _versions(fam)
        if name_versions:
            if not fam_versions or not (name_versions & fam_versions):
                continue
        candidates.append((score, date, len(core)))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[2]), reverse=True)
    return {"score": candidates[0][0], "date": candidates[0][1]}


def fetch_hn_sentiment(model_name, min_points=5):
    """通过 HN Algolia 抓取社区口碑信号。"""
    q = clean_query_text(model_name)
    if len(q) < 3:
        return None
    params = urllib.parse.urlencode({
        "query": '"{}"'.format(q),
        "tags": "story",
        "hitsPerPage": 20,
    })
    url = "{}?{}".format(HN_SEARCH_URL, params)
    raw = fetch_url(url, timeout=20, retries=1)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None

    all_hits = data.get("hits", [])
    hits = [h for h in all_hits if (h.get("points", 0) or 0) >= min_points]
    nb = data.get("nbHits", 0)
    if not hits:
        return None

    total_points = sum(h.get("points", 0) or 0 for h in hits)
    total_comments = sum(h.get("num_comments", 0) or 0 for h in hits)

    # 简单启发式评分：讨论热度映射到 3.5~4.8
    heat = total_points + total_comments * 2
    score = 3.5 + min(1.3, heat / 4000.0)
    score = round(score, 1)

    highlights = []
    for h in sorted(hits, key=lambda x: x.get("points", 0) or 0, reverse=True)[:3]:
        title = h.get("title") or ""
        if not title:
            continue
        highlights.append({
            "source": "HN",
            "quote": title,
            "sentiment": "positive" if (h.get("points", 0) or 0) >= 100 else "mixed",
        })

    return {
        "score": score,
        "maxScore": 5,
        "sampleSize": nb,
        "sources": ["Hacker News"],
        "summary": "HN 近期相关讨论 {} 条，累计 {} 点赞 / {} 评论。热度反映社区关注度，非情感极性判定。".format(
            nb, total_points, total_comments
        ),
        "highlights": highlights,
        "trend": "rising" if heat > 1500 else "stable",
    }


def build_automated_benchmarks(m, swe):
    items = []
    if swe:
        items.append({"name": "SWE-bench Verified", "score": swe["score"], "unit": "%",
                      "rank": None, "source": "swe-bench", "updated": swe.get("date", "")})
    if m.get("mmluPro") is not None:
        items.append({"name": "MMLU-Pro", "score": m["mmluPro"], "unit": "%",
                      "rank": None, "source": "chatbot-arena", "updated": ""})
    if m.get("arcAgi") is not None:
        items.append({"name": "ARC-AGI", "score": m["arcAgi"], "unit": "%",
                      "rank": None, "source": "chatbot-arena", "updated": ""})
    if m.get("aaii") is not None:
        items.append({"name": "Artificial Analysis Index", "score": m["aaii"], "unit": "",
                      "rank": None, "source": "artificial-analysis", "updated": ""})
    return items


def build_manual_benchmarks(m, elo_rank, coding_rank):
    items = [{"name": "LMArena Arena Elo", "score": int(m["arenaElo"]), "unit": "Elo",
              "rank": elo_rank, "source": "lmsys-arena", "updated": "",
              "note": "人工盲测偏好排名"}]
    if m.get("codingElo") is not None:
        items.append({"name": "LMArena 编程 Elo", "score": int(m["codingElo"]), "unit": "Elo",
                      "rank": coding_rank, "source": "lmsys-arena", "updated": "",
                      "note": "编程场景人工盲测"})
    if m.get("visionElo") is not None:
        items.append({"name": "LMArena Vision Elo", "score": int(m["visionElo"]), "unit": "Elo",
                      "rank": None, "source": "lmsys-arena", "updated": ""})
    return items


def build_description(m, swe):
    parts = ["{} 出品".format(m["provider"])]
    parts.append("Arena Elo {}".format(int(m["arenaElo"])))
    if m.get("codingElo"):
        parts.append("编程 Elo {}".format(int(m["codingElo"])))
    if swe:
        parts.append("SWE-bench {}%".format(swe["score"]))
    if m.get("mmluPro"):
        parts.append("MMLU-Pro {}".format(m["mmluPro"]))
    tail = "开源权重" if m["openWeights"] else "闭源"
    return "，".join(parts) + "。" + tail + "。"


def build_models(arena, swe_best, top_n, prev_slugs, fetch_sentiment=True):
    """将抓取结果转换为 curated + index 两套模型数据。"""
    # 编程 Elo 排名映射
    coding_sorted = sorted(
        [m for m in arena if m.get("codingElo") is not None],
        key=lambda x: x["codingElo"], reverse=True,
    )
    coding_rank = {m["name"]: i + 1 for i, m in enumerate(coding_sorted)}

    curated = []
    index = []
    for i, m in enumerate(arena):
        if i >= INDEX_CAP:
            break
        slug = slugify(m["name"])
        swe = match_swebench(m["name"], swe_best)
        elo_rank = i + 1
        automated = build_automated_benchmarks(m, swe)
        manual = build_manual_benchmarks(m, elo_rank, coding_rank.get(m["name"]))
        category = guess_category(m["name"], m.get("codingElo"), m.get("arenaElo"), m["openWeights"])
        is_new = slug not in prev_slugs if prev_slugs else False

        base = {
            "slug": slug,
            "displayName": m["name"],
            "provider": m["provider"],
            "providers": [m["provider"]],
            "category": category,
            "openWeights": m["openWeights"],
            "description": build_description(m, swe),
            "benchmarks": {"automated": automated, "manual": manual},
            "availableIn": PROVIDER_PRODUCTS.get(m["provider"], ["API"]),
            "sourceUrl": PROVIDER_URLS.get(m["provider"], ARENA_URL),
            "isNew": is_new,
        }

        ctx = match_hint(m["name"], CONTEXT_HINTS)
        if ctx:
            base["contextWindow"] = ctx
        pricing = match_hint(m["name"], PRICING_HINTS)
        if pricing:
            base["pricing"] = pricing

        tags = []
        if m["openWeights"]:
            tags.append("open-weights")
        tags.append(category)
        if swe:
            tags.append("swe-bench")
        base["tags"] = tags

        # 全量索引条目（轻量）
        idx_entry = dict(base)
        idx_entry["id"] = "idx-{}-{}".format(slugify(m["provider"]), slug)
        idx_entry["inTopCurated"] = elo_rank <= top_n
        idx_entry["activityScore"] = int(m["arenaElo"])
        idx_entry["activityRank"] = elo_rank
        index.append(idx_entry)

        # 策展 Top N（更丰富，补充口碑）
        if elo_rank <= top_n:
            cur = dict(base)
            cur["id"] = "llm-{:03d}".format(elo_rank)
            cur["rank"] = elo_rank
            cur["featured"] = elo_rank <= min(top_n, 18)
            if fetch_sentiment:
                sentiment = fetch_hn_sentiment(m["name"])
                time.sleep(0.6)
                if sentiment:
                    cur["sentiment"] = sentiment
            curated.append(cur)

    return curated, index


def build_meta(arena, curated, index, changes_count):
    providers = []
    for m in curated:
        if m["provider"] not in providers:
            providers.append(m["provider"])
    categories = []
    for m in curated:
        if m["category"] not in categories:
            categories.append(m["category"])

    return {
        "meta": {
            "lastUpdated": now_iso(),
            "totalCount": len(curated),
            "featuredCount": sum(1 for m in curated if m.get("featured")),
            "indexTotalCount": len(index),
            "newCount": sum(1 for m in index if m.get("isNew")),
            "changesCount": changes_count,
            "sources": [s["id"] for s in SOURCES],
            "discovery": {s["id"]: {"name": s["name"], "url": s["url"], "focus": s["focus"]} for s in SOURCES},
            "note": "自动抓取 Chatbot Arena + SWE-bench + HN；策展 Top {} 覆盖自动化评测、人工盲测与社区口碑。".format(len(curated)),
        },
        "providers": providers,
        "categories": categories,
        "benchmarkSets": [
            "SWE-bench Verified", "MMLU-Pro", "ARC-AGI",
            "Artificial Analysis Index", "LMArena Arena Elo", "LMArena 编程 Elo",
        ],
        "llms": curated,
    }


def detect_changes(curated, prev_snapshot):
    changes = []
    current = {}
    for m in curated:
        key = "{}/{}".format(m.get("provider", ""), m["slug"])
        h = content_hash({k: m[k] for k in ("displayName", "provider", "benchmarks", "category") if k in m})
        current[key] = h
        if not prev_snapshot:
            continue
        prev_h = prev_snapshot.get(key)
        if prev_h is None:
            changes.append({
                "type": "added", "slug": m["slug"],
                "displayName": m.get("displayName", m["slug"]),
                "provider": m.get("provider", ""),
                "summary": m.get("description", "")[:120],
            })
        elif prev_h != h:
            changes.append({
                "type": "updated", "slug": m["slug"],
                "displayName": m.get("displayName", m["slug"]),
                "provider": m.get("provider", ""),
                "summary": "评测分数或排名已更新",
            })
    return changes, current


def rebuild_index_from_existing(curated_data):
    """离线降级：仅基于现有 llms.json 重建索引（不含额外条目）。"""
    curated_llms = curated_data.get("llms", [])
    index_llms = []
    for i, m in enumerate(curated_llms):
        entry = dict(m)
        entry["id"] = "idx-{}-{}".format(slugify(m.get("provider", "unknown")), m["slug"])
        entry["inTopCurated"] = True
        entry["activityScore"] = 100 - i * 3
        entry["activityRank"] = i + 1
        entry.setdefault("isNew", False)
        index_llms.append(entry)
    return {
        "meta": {"lastUpdated": now_iso(), "totalCount": len(index_llms),
                 "newCount": sum(1 for m in index_llms if m.get("isNew"))},
        "llms": index_llms,
    }


def run():
    parser = argparse.ArgumentParser(description="Collect latest LLM benchmark & sentiment data")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入文件")
    parser.add_argument("--offline", action="store_true", help="跳过网络抓取，仅基于现有数据重建索引")
    parser.add_argument("--no-sentiment", action="store_true", help="跳过 HN 口碑抓取以加速")
    parser.add_argument("--top", type=int, default=24, help="策展 Top N 数量（默认 24）")
    parser.add_argument("--sources", action="store_true", help="列出数据来源后退出")
    args = parser.parse_args()

    if args.sources:
        for s in SOURCES:
            print("- {} ({}) — {}".format(s["name"], s["url"], s["focus"]))
        return

    prev_snap_data = load_json(SNAPSHOT_PATH, {"entries": {}})
    prev_snapshot = prev_snap_data.get("entries", {})
    prev_slugs = {k.split("/", 1)[-1] for k in prev_snapshot} if prev_snapshot else set()
    is_baseline = not prev_snapshot

    arena = []
    if not args.offline:
        print("[1/3] 抓取 Chatbot Arena 排行榜 ...")
        arena_html = fetch_url(ARENA_URL)
        if arena_html:
            arena = parse_arena(arena_html)
            print("      解析到 {} 个模型".format(len(arena)))

    if not arena:
        # 网络失败或离线：降级为基于现有 llms.json 重建索引
        print("[!] 未获取到在线榜单，降级为基于现有 llms.json 重建索引。", file=sys.stderr)
        curated = load_json(LLMS_PATH)
        if not curated.get("llms"):
            print("[ERROR] llms.json 为空且无法抓取在线数据。", file=sys.stderr)
            sys.exit(1)
        changes, current = detect_changes(curated["llms"], prev_snapshot)
        index_data = rebuild_index_from_existing(curated)
        curated["meta"]["lastUpdated"] = now_iso()
        curated["meta"]["indexTotalCount"] = index_data["meta"]["totalCount"]
        curated["meta"]["changesCount"] = len(changes)
        if args.dry_run:
            print("[dry-run] 降级重建：index {} 条".format(index_data["meta"]["totalCount"]))
            return
        save_json(LLMS_PATH, curated)
        save_json(INDEX_PATH, index_data)
        save_json(SNAPSHOT_PATH, {"meta": {"lastUpdated": now_iso()}, "entries": current})
        save_json(CHANGES_PATH, {"meta": {"lastUpdated": now_iso(), "totalChanges": len(changes)},
                                 "isBaselineRun": is_baseline, "changes": changes})
        print("[OK] 离线重建完成：index {} 条，{} 条变更".format(index_data["meta"]["totalCount"], len(changes)))
        return

    print("[2/3] 抓取 SWE-bench Verified 榜单 ...")
    swe_html = fetch_url(SWEBENCH_URL)
    swe_best = parse_swebench(swe_html) if swe_html else {}
    print("      匹配到 {} 个模型家族的 SWE-bench 成绩".format(len(swe_best)))

    print("[3/3] 构建模型数据（含 HN 口碑抓取）...")
    curated_list, index_list = build_models(
        arena, swe_best, args.top, prev_slugs,
        fetch_sentiment=not args.no_sentiment,
    )

    changes, current = detect_changes(curated_list, prev_snapshot)
    llms_data = build_meta(arena, curated_list, index_list, len(changes))
    index_data = {
        "meta": {"lastUpdated": now_iso(), "totalCount": len(index_list),
                 "newCount": sum(1 for m in index_list if m.get("isNew"))},
        "llms": index_list,
    }

    if args.dry_run:
        print("[dry-run] curated {} 条，index {} 条，{} 条变更".format(
            len(curated_list), len(index_list), len(changes)))
        for m in curated_list[:8]:
            swe = next((b for b in m["benchmarks"]["automated"] if b["name"].startswith("SWE")), None)
            print("  #{:<2} {:<32} Elo {} {}".format(
                m["rank"], m["displayName"], m["benchmarks"]["manual"][0]["score"],
                "SWE {}%".format(swe["score"]) if swe else ""))
        return

    save_json(LLMS_PATH, llms_data)
    save_json(INDEX_PATH, index_data)
    save_json(SNAPSHOT_PATH, {"meta": {"lastUpdated": now_iso()}, "entries": current})
    save_json(CHANGES_PATH, {"meta": {"lastUpdated": now_iso(), "totalChanges": len(changes)},
                             "isBaselineRun": is_baseline, "changes": changes})

    print("[OK] LLM 数据已更新：策展 {} · 索引 {} · 新增 {} · 变更 {}".format(
        len(curated_list), len(index_list),
        index_data["meta"]["newCount"], len(changes)))


if __name__ == "__main__":
    run()
