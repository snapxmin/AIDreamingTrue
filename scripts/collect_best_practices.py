#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最佳实践采集脚本 — 从产品文档、博客与公开页面同步 AI Coding 竞品最佳实践，输出 data/best_practices.json。
"""

from __future__ import print_function

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUTPUT_PATH = os.path.join(DATA_DIR, "best_practices.json")
USER_AGENT = "AIDreamingTrue-BestPracticesCollector/1.0"

CURATED_PRACTICES = [
    {
        "slug": "copilot-prompt-engineering",
        "title": "Prompt 先宽后窄，补充约束与示例",
        "competitor": "GitHub Copilot",
        "theme": "Prompt 设计",
        "sourceType": "产品文档",
        "sourceTier": "A",
        "sourceUrl": "https://docs.github.com/en/copilot/using-github-copilot/prompt-engineering-for-github-copilot",
        "summary": "先描述目标，再追加边界条件、输入输出格式与示例，让 Copilot 更稳定地产出可用结果。",
        "whyItWorks": "先给任务框架能减少模型误解，再用具体约束收敛输出空间，比一次性丢很多零散要求更稳定。",
        "howToApply": [
            "第一句写清最终目标或用户场景",
            "第二段补充输入、输出、限制条件",
            "复杂任务追加示例或伪输入数据"
        ],
        "takeaway": "目标 → 约束 → 示例，是最稳定的 Copilot 提示结构。",
        "tags": ["prompt", "examples", "copilot"],
        "heat": 95,
        "featured": True,
    },
    {
        "slug": "copilot-prompt-files",
        "title": "把高频任务沉淀成 Prompt Files",
        "competitor": "GitHub Copilot",
        "theme": "团队复用",
        "sourceType": "产品文档",
        "sourceTier": "A",
        "sourceUrl": "https://docs.github.com/en/copilot/tutorials/customization-library/prompt-files",
        "summary": "把 README 生成、代码审查、Onboarding 等高频任务固化为 Prompt Files，统一团队使用方式。",
        "whyItWorks": "将个人高质量提示词产品化，能让团队共享同一套上下文模板，降低使用门槛和输出波动。",
        "howToApply": [
            "挑出团队重复出现的任务场景",
            "沉淀成可复用的 Prompt File 模板",
            "把模板与仓库说明一起维护"
        ],
        "takeaway": "把好的提示从个人技巧升级为团队资产。",
        "tags": ["prompt-files", "template", "team"],
        "heat": 88,
        "featured": True,
    },
    {
        "slug": "copilot-code-review",
        "title": "PR 合并前先请求 Copilot 做一轮代码审查",
        "competitor": "GitHub Copilot",
        "theme": "代码评审",
        "sourceType": "产品文档",
        "sourceTier": "A",
        "sourceUrl": "https://docs.github.com/en/copilot/using-github-copilot/code-review/using-copilot-code-review",
        "summary": "在 GitHub PR 中主动请求 Copilot review，用它先扫一轮风险点，再让人工 reviewer 聚焦关键决策。",
        "whyItWorks": "让 Agent 先承担覆盖型检查工作，可以更快暴露明显问题，把人审资源留给架构、边界和 trade-off。",
        "howToApply": [
            "提交 PR 后先请求 Copilot review",
            "先处理明确的自动化建议",
            "再把剩余风险交给人工 reviewer 聚焦判断"
        ],
        "takeaway": "机器先做覆盖，人类再做判断。",
        "tags": ["review", "pull-request", "quality-gate"],
        "heat": 84,
        "featured": False,
    },
    {
        "slug": "claude-verification-loop",
        "title": "给 Claude 一个可执行验证闭环",
        "competitor": "Claude Code",
        "theme": "验证闭环",
        "sourceType": "产品文档",
        "sourceTier": "A",
        "sourceUrl": "https://docs.anthropic.com/en/docs/claude-code/best-practices",
        "summary": "不要只让 Claude“完成任务”，而要给它测试、构建、脚本或截图比对等可执行校验信号。",
        "whyItWorks": "Claude 会在“看起来完成”时停止；加入可读的 pass/fail 信号后，它才能自行迭代直到通过。",
        "howToApply": [
            "为每类任务准备可运行的校验命令",
            "在需求里明确“完成”的验证标准",
            "要求 Agent 运行校验并根据结果继续修正"
        ],
        "takeaway": "没有验证信号，Agent 就只能凭感觉停下。",
        "tags": ["verification", "tests", "agent-loop"],
        "heat": 96,
        "featured": True,
    },
    {
        "slug": "claude-subagents",
        "title": "把搜索型副任务交给 Subagents",
        "competitor": "Claude Code",
        "theme": "多 Agent 协作",
        "sourceType": "产品文档",
        "sourceTier": "A",
        "sourceUrl": "https://docs.anthropic.com/en/docs/claude-code/sub-agents",
        "summary": "遇到日志排查、代码搜索、资料收集等噪音很大的任务时，优先拆给 subagent，主线程只接收摘要。",
        "whyItWorks": "副任务隔离后能显著节省主会话上下文，降低长任务中的信息污染和注意力切换成本。",
        "howToApply": [
            "把探索、检索、日志分析独立成子任务",
            "限制子 Agent 的工具权限和职责",
            "主线程只消费结论与证据摘要"
        ],
        "takeaway": "把上下文预算留给决策，而不是留给搜索噪音。",
        "tags": ["subagent", "context-window", "delegation"],
        "heat": 93,
        "featured": True,
    },
    {
        "slug": "claude-common-workflows",
        "title": "复杂任务先计划，再并行 worktree 会话",
        "competitor": "Claude Code",
        "theme": "规划拆解",
        "sourceType": "产品文档",
        "sourceTier": "A",
        "sourceUrl": "https://docs.anthropic.com/en/docs/claude-code/common-workflows",
        "summary": "先让 Claude 产出计划，再用并行 session / worktree 推进不同子任务，减少互相覆盖。",
        "whyItWorks": "计划先行能减少返工，并行工作树则适合把相互独立的实现或验证任务分开推进。",
        "howToApply": [
            "先让 Agent 输出完整计划或文件影响面",
            "对独立子问题拆分会话或 worktree",
            "最后统一回到主线程验收与合并"
        ],
        "takeaway": "先规划边界，再并行执行，能降低大任务失控风险。",
        "tags": ["planning", "worktree", "parallelism"],
        "heat": 89,
        "featured": True,
    },
    {
        "slug": "cursor-rules",
        "title": "用 Cursor Rules 固化仓库级约束",
        "competitor": "Cursor",
        "theme": "上下文治理",
        "sourceType": "产品文档",
        "sourceTier": "A",
        "sourceUrl": "https://cursor.com/docs/context/rules",
        "summary": "把代码规范、目录约束、测试要求等沉淀到 Cursor Rules，而不是每次在对话里重复强调。",
        "whyItWorks": "稳定规则前置到上下文层后，Agent 的默认行为更一致，减少对话里临时补丁式约束。",
        "howToApply": [
            "提炼最常被重复提醒的工程规则",
            "优先写成短而明确的仓库级规则",
            "持续把 review 中重复问题反哺到 rules"
        ],
        "takeaway": "把口头提醒升级成系统级默认值。",
        "tags": ["rules", "context", "governance"],
        "heat": 90,
        "featured": True,
    },
    {
        "slug": "replit-plan-mode",
        "title": "先开 Plan Mode，再批准 Agent 真正动手",
        "competitor": "Replit Agent",
        "theme": "规划拆解",
        "sourceType": "产品文档",
        "sourceTier": "A",
        "sourceUrl": "https://docs.replit.com/replitai/agent#plan-mode",
        "summary": "Replit Agent 适合先在 Plan Mode 里拆任务、确认方案，再进入执行模式，避免直接生成偏题产品。",
        "whyItWorks": "对话式产品生成最怕需求没对齐；先评审任务清单能把问题暴露在动手之前。",
        "howToApply": [
            "先用 Plan Mode 明确范围与优先级",
            "确认任务列表和交付物后再批准执行",
            "中途改方向时回到 plan 重新收敛"
        ],
        "takeaway": "先对齐产品意图，再让 Agent 执行。",
        "tags": ["plan-mode", "product", "alignment"],
        "heat": 85,
        "featured": True,
    },
    {
        "slug": "kiro-spec-driven",
        "title": "先把需求变成 Spec，再让 Kiro 生成实现",
        "competitor": "Kiro",
        "theme": "Spec 驱动",
        "sourceType": "官网页面",
        "sourceTier": "B",
        "sourceUrl": "https://kiro.dev",
        "summary": "Kiro 的高价值用法不是直接让模型产代码，而是先把 prompt 转成可执行 spec 和正确性约束。",
        "whyItWorks": "需求显式化之后，验证和实现都有锚点，适合处理多人协作或高风险业务逻辑。",
        "howToApply": [
            "先列出功能需求与必须成立的性质",
            "让 Kiro 生成或补完 spec，而不是直接写最终代码",
            "用 spec 驱动后续实现与正确性校验"
        ],
        "takeaway": "Spec 不是文档附属品，而是生成质量的前置条件。",
        "tags": ["spec", "requirements", "correctness"],
        "heat": 82,
        "featured": True,
    },
]


def fetch_url(url, timeout=20):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain, */*"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            last_modified = resp.headers.get("Last-Modified", "")
            body = resp.read().decode("utf-8", errors="replace")
            return {
                "body": body,
                "content_type": content_type,
                "last_modified": last_modified,
            }
    except (HTTPError, URLError) as exc:
        print("  [WARN] 无法抓取 {}: {}".format(url, exc), file=sys.stderr)
        return None


def strip_tags(value):
    text = re.sub(r"<script[^>]*>.*?</script>", " ", value, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_html_meta(body):
    title = ""
    description = ""

    meta_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', body, re.IGNORECASE)
    if meta_title:
        title = strip_tags(meta_title.group(1))

    if not title:
        title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = strip_tags(title_match.group(1))

    meta_desc = re.search(
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\'](.*?)["\']',
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if meta_desc:
        description = strip_tags(meta_desc.group(1))

    if not description:
        plain = strip_tags(body)
        description = plain[:260]

    return title, description


def extract_text_meta(body):
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    title = ""
    description = ""
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("# ").strip()
            break
    if not title and lines:
        title = lines[0][:120]
    for line in lines[1:]:
        if len(line) > 40:
            description = line[:260]
            break
    if not description and len(lines) > 1:
        description = lines[1][:260]
    return title, description


def fetch_metadata(url):
    payload = fetch_url(url)
    if not payload:
        return {
            "sourceTitle": "",
            "remoteSnippet": "",
            "sourceReachable": False,
            "lastModified": "",
        }

    body = payload["body"]
    content_type = payload.get("content_type", "")
    looks_like_html = "html" in content_type.lower() or "<html" in body.lower()
    title, description = extract_html_meta(body) if looks_like_html else extract_text_meta(body)

    return {
        "sourceTitle": title,
        "remoteSnippet": description,
        "sourceReachable": True,
        "lastModified": payload.get("last_modified", ""),
    }


def build_record(index, curated):
    remote = fetch_metadata(curated["sourceUrl"])
    return {
        "id": "bp-{:03d}".format(index),
        "slug": curated["slug"],
        "title": curated["title"],
        "competitor": curated["competitor"],
        "theme": curated["theme"],
        "sourceType": curated["sourceType"],
        "sourceTier": curated["sourceTier"],
        "sourceTitle": remote["sourceTitle"] or curated["title"],
        "sourceUrl": curated["sourceUrl"],
        "summary": curated["summary"],
        "whyItWorks": curated["whyItWorks"],
        "howToApply": curated["howToApply"],
        "takeaway": curated["takeaway"],
        "tags": curated.get("tags", []),
        "heat": curated["heat"],
        "featured": curated.get("featured", False),
        "remoteSnippet": remote["remoteSnippet"] or curated["summary"],
        "sourceReachable": remote["sourceReachable"],
        "lastModified": remote["lastModified"],
    }


def collect_best_practices(dry_run=False):
    print("采集业界最佳实践...")
    practices = []
    for index, curated in enumerate(CURATED_PRACTICES, start=1):
        print("  → {} / {}".format(curated["competitor"], curated["title"]))
        practices.append(build_record(index, curated))

    practices.sort(key=lambda item: (-item["heat"], item["competitor"], item["title"]))
    payload = {
        "meta": {
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "totalCount": len(practices),
            "featuredCount": sum(1 for item in practices if item["featured"]),
            "note": "按主题策展 GitHub Copilot / Claude Code / Cursor / Replit Agent / Kiro 最佳实践，并同步公开来源摘要。",
        },
        "themes": sorted({item["theme"] for item in practices}),
        "competitors": sorted({item["competitor"] for item in practices}),
        "sourceTypes": sorted({item["sourceType"] for item in practices}),
        "practices": practices,
    }

    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:4000], "...")
        return payload

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(OUTPUT_PATH, "w") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")
    print("\n已写入 {}（{} 条最佳实践）".format(OUTPUT_PATH, len(practices)))
    return payload


def print_sources():
    for curated in CURATED_PRACTICES:
        print("- {} / {} ({})".format(curated["competitor"], curated["theme"], curated["sourceUrl"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sources", action="store_true")
    args = parser.parse_args()

    if args.sources:
        print_sources()
        return 0

    collect_best_practices(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
