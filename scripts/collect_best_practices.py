#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竞品最佳实践采集 — 从 Hacker News、Reddit、GitHub、产品文档等公开来源
按主题聚合用户使用竞品的最佳实践。

输出: data/best-practices.json
建议每 3 天运行一次（见 .github/workflows/collect-best-practices-and-deploy.yml）
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
COMPETITORS_PATH = os.path.join(DATA_DIR, "competitors.json")
OUTPUT_PATH = os.path.join(DATA_DIR, "best-practices.json")
USER_AGENT = "AIDreamingTrue-BestPractices/1.0"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# 主题定义：id、展示名、分类关键词（用于自动归类）
TOPICS = [
    {
        "id": "agent-workflow",
        "label": "Agent 工作流",
        "keywords": ["agent", "workflow", "rules", "cursorrules", "autonomous", "plan", "task"],
    },
    {
        "id": "mcp-integration",
        "label": "MCP 集成",
        "keywords": ["mcp", "model context protocol", "server", "tool", "integration"],
    },
    {
        "id": "code-review",
        "label": "代码审查",
        "keywords": ["code review", "review", "pr review", "pull request", "lint"],
    },
    {
        "id": "debugging",
        "label": "调试排错",
        "keywords": ["debug", "troubleshoot", "error", "fix bug", "diagnos"],
    },
    {
        "id": "refactoring",
        "label": "多文件重构",
        "keywords": ["refactor", "multi-file", "migration", "rename", "restructure"],
    },
    {
        "id": "testing",
        "label": "测试驱动",
        "keywords": ["test", "tdd", "unit test", "e2e", "coverage", "playwright"],
    },
    {
        "id": "team-collab",
        "label": "团队协作",
        "keywords": ["team", "enterprise", "collaboration", "shared", "onboarding", "org"],
    },
    {
        "id": "prompt-tips",
        "label": "Prompt 技巧",
        "keywords": ["prompt", "tip", "trick", "how to", "guide", "best practice"],
    },
]

TOPIC_BY_ID = {t["id"]: t for t in TOPICS}
TOPIC_LABELS = {t["label"]: t["id"] for t in TOPICS}

SOURCE_LABELS = {
    "hacker-news": "Hacker News",
    "reddit": "Reddit",
    "github": "GitHub",
    "blog": "博客",
    "docs": "产品文档",
    "forum": "论坛",
    "curated": "策展",
}

# 策展种子：网络采集失败时仍保证页面有内容
SEED_PRACTICES = [
    {
        "id": "bp-seed-cursor-rules",
        "title": "Cursor Rules：用 .cursor/rules 分层管理项目规范",
        "topic": "Agent 工作流",
        "topicId": "agent-workflow",
        "competitorId": "cursor",
        "competitorName": "Cursor",
        "summary": "将全局规范、语言约定、目录级规则拆分到 .cursor/rules 多文件，Agent 按上下文自动加载，避免单文件 rules 过长导致遗忘。",
        "highlights": [
            "按目录拆分 rules，靠近代码的规范优先",
            "用 alwaysApply 控制全局 vs 局部规则",
            "结合 @file 引用减少重复描述",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://cursor.com/docs/rules",
        "author": "Cursor Docs",
        "date": "2026-05-01",
        "qualityScore": 95,
        "tags": ["rules", "agent", "project-setup"],
        "curated": True,
    },
    {
        "id": "bp-seed-cursor-agent-success-check",
        "title": "Cursor Agent：在提示词里写清目标、边界和验收命令",
        "topic": "Agent 工作流",
        "topicId": "agent-workflow",
        "competitorId": "cursor",
        "competitorName": "Cursor",
        "summary": "把任务说明写成「目标 + 不可改变的约束 + 相关文件 + 如何验证」。复杂改动先让 Agent 产出计划，确认范围后再执行，最后要求它运行指定测试或构建命令。",
        "highlights": [
            "用 @file 指向关键上下文，减少 Agent 盲目搜索",
            "明确 public API、数据库、依赖等不能随意改动的边界",
            "把成功标准写成可运行命令，如 pytest、npm test 或 lint",
        ],
        "sourceType": "blog",
        "sourceLabel": "博客",
        "sourceUrl": "https://cursor.com/blog/agent-best-practices",
        "author": "Cursor",
        "date": "2026-06-01",
        "qualityScore": 96,
        "tags": ["agent", "prompting", "verification"],
        "curated": True,
    },
    {
        "id": "bp-seed-cursor-mcp",
        "title": "Cursor MCP：stdio 本地 Server + 项目级 mcp.json",
        "topic": "MCP 集成",
        "topicId": "mcp-integration",
        "competitorId": "cursor",
        "competitorName": "Cursor",
        "summary": "在 Cursor Settings → MCP 或项目 .cursor/mcp.json 配置 Server；优先 stdio 本地进程，敏感 Token 走环境变量而非明文写入配置。",
        "highlights": [
            "项目级 mcp.json 可版本化，团队共享",
            "stdio 适合本地 CLI 工具集成",
            "限制工具权限，避免 Agent 过度调用",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://docs.cursor.com/context/mcp",
        "author": "Cursor Docs",
        "date": "2026-05-01",
        "qualityScore": 92,
        "tags": ["mcp", "configuration"],
        "curated": True,
    },
    {
        "id": "bp-seed-copilot-instructions",
        "title": "Copilot Instructions：仓库级 copilot-instructions.md",
        "topic": "Agent 工作流",
        "topicId": "agent-workflow",
        "competitorId": "github-copilot",
        "competitorName": "GitHub Copilot",
        "summary": "在仓库根目录添加 copilot-instructions.md，定义编码风格、测试要求与 PR 规范，Copilot Chat 与 Agent 模式会自动读取。",
        "highlights": [
            "与 CODEOWNERS、CONTRIBUTING 互补",
            "明确「禁止」项比泛泛「写好代码」更有效",
            "组织级可配置默认 instructions",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot",
        "author": "GitHub Docs",
        "date": "2026-04-15",
        "qualityScore": 94,
        "tags": ["instructions", "repository"],
        "curated": True,
    },
    {
        "id": "bp-seed-copilot-validation-instructions",
        "title": "Copilot Instructions：把构建、测试、验证流水线写进仓库上下文",
        "topic": "测试驱动",
        "topicId": "testing",
        "competitorId": "github-copilot",
        "competitorName": "GitHub Copilot",
        "summary": "在 .github/copilot-instructions.md 里记录 bootstrap、build、test、lint、run 的准确命令和运行顺序，让 Copilot coding agent 不必每次重新猜测验证方式。",
        "highlights": [
            "列出运行时版本、依赖安装方式和常见环境变量",
            "把 PR 合格标准写成明确检查项，降低 agent PR 被拒概率",
            "当验证流程变化时同步更新 instructions，避免旧命令误导 Agent",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot",
        "author": "GitHub Docs",
        "date": "2026-06-01",
        "qualityScore": 95,
        "tags": ["instructions", "testing", "validation"],
        "curated": True,
    },
    {
        "id": "bp-seed-copilot-review",
        "title": "Copilot Code Review：在 PR 中自动审查 + 人工复核",
        "topic": "代码审查",
        "topicId": "code-review",
        "competitorId": "github-copilot",
        "competitorName": "GitHub Copilot",
        "summary": "启用 Copilot PR Review 后，在描述中 @copilot 或依赖自动触发；将审查重点写入 instructions，减少风格类误报。",
        "highlights": [
            "instructions 中声明安全与性能优先级",
            "大 PR 拆分后审查质量更高",
            "结合 branch protection 强制人工批准",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://docs.github.com/en/copilot/using-github-copilot/code-review/using-copilot-code-review",
        "author": "GitHub Docs",
        "date": "2026-03-20",
        "qualityScore": 90,
        "tags": ["code-review", "pull-request"],
        "curated": True,
    },
    {
        "id": "bp-seed-copilot-path-scoped-review",
        "title": "Copilot Code Review：用路径级 instructions 提升审查命中率",
        "topic": "代码审查",
        "topicId": "code-review",
        "competitorId": "github-copilot",
        "competitorName": "GitHub Copilot",
        "summary": "为 frontend、backend、security 等目录分别创建 .github/instructions/*.instructions.md，并用 applyTo glob 绑定路径，让 Copilot Review 按模块规则给出更相关的建议。",
        "highlights": [
            "每个 instructions 文件只写该路径真正需要的审查准则",
            "用 applyTo 精准匹配目录，避免前端规则污染后端代码审查",
            "从真实 PR 反馈中迭代规则，删除泛泛而谈的风格要求",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://docs.github.com/en/copilot/tutorials/customize-code-review",
        "author": "GitHub Docs",
        "date": "2026-06-01",
        "qualityScore": 94,
        "tags": ["code-review", "instructions", "pull-request"],
        "curated": True,
    },
    {
        "id": "bp-seed-claude-claude-md",
        "title": "Claude Code：CLAUDE.md 作为项目记忆入口",
        "topic": "Agent 工作流",
        "topicId": "agent-workflow",
        "competitorId": "claude-code",
        "competitorName": "Claude Code",
        "summary": "在项目根维护 CLAUDE.md，记录架构决策、常用命令、测试方式；Claude Code 启动时自动加载，减少重复解释。",
        "highlights": [
            "写清「如何运行测试」与「目录结构」",
            "更新 CLAUDE.md 当作 onboarding 文档",
            "子目录可放额外 CLAUDE.md 覆盖局部约定",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://docs.anthropic.com/en/docs/claude-code/overview",
        "author": "Anthropic Docs",
        "date": "2026-05-10",
        "qualityScore": 93,
        "tags": ["claude-md", "context"],
        "curated": True,
    },
    {
        "id": "bp-seed-claude-four-phase",
        "title": "Claude Code：Explore → Plan → Implement → Commit 四阶段工作流",
        "topic": "Agent 工作流",
        "topicId": "agent-workflow",
        "competitorId": "claude-code",
        "competitorName": "Claude Code",
        "summary": "不要让 Claude Code 直接改复杂任务。先让它探索代码、写实施计划并与你确认，再进入实现阶段，完成后要求它总结改动、运行验证并准备提交说明。",
        "highlights": [
            "Plan Mode 用于读代码和制定方案，避免过早写错方向",
            "实现阶段保持小步提交，方便人类在关键节点介入",
            "提交前让 Agent 对照计划和测试结果自检遗漏项",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://code.claude.com/docs/en/best-practices",
        "author": "Anthropic Docs",
        "date": "2026-06-01",
        "qualityScore": 96,
        "tags": ["planning", "workflow", "verification"],
        "curated": True,
    },
    {
        "id": "bp-seed-claude-mcp",
        "title": "Claude Code MCP：连接 GitHub / 文件系统 / 浏览器工具",
        "topic": "MCP 集成",
        "topicId": "mcp-integration",
        "competitorId": "claude-code",
        "competitorName": "Claude Code",
        "summary": "通过 claude mcp add 注册 Server；终端 Agent 场景下 MCP 是扩展能力的核心，优先官方 GitHub、Filesystem Server。",
        "highlights": [
            "OAuth Server 适合 SaaS 集成",
            "限制同时启用的 Server 数量",
            "用 /mcp 命令检查连接状态",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://docs.anthropic.com/en/docs/claude-code/mcp",
        "author": "Anthropic Docs",
        "date": "2026-05-10",
        "qualityScore": 91,
        "tags": ["mcp", "terminal"],
        "curated": True,
    },
    {
        "id": "bp-seed-devin-plan",
        "title": "Devin：先写 Plan 再执行，人工在关键节点审批",
        "topic": "Agent 工作流",
        "topicId": "agent-workflow",
        "competitorId": "devin-desktop",
        "competitorName": "Devin Desktop",
        "summary": "复杂任务要求 Devin 先输出分步计划；对数据库迁移、依赖升级等高风险步骤设置人工确认，避免全自动跑偏。",
        "highlights": [
            "计划阶段可调整范围再执行",
            "并行子任务适合独立模块",
            "保留会话上下文便于迭代",
        ],
        "sourceType": "blog",
        "sourceLabel": "博客",
        "sourceUrl": "https://devin.ai",
        "author": "Cognition",
        "date": "2026-06-01",
        "qualityScore": 88,
        "tags": ["planning", "approval"],
        "curated": True,
    },
    {
        "id": "bp-seed-replit-agent",
        "title": "Replit Agent：Design Canvas + 自然语言迭代 UI",
        "topic": "Prompt 技巧",
        "topicId": "prompt-tips",
        "competitorId": "replit",
        "competitorName": "Replit Agent",
        "summary": "非专业开发者先用自然语言描述产品形态，在 Design Canvas 上微调布局后再让 Agent 生成代码，减少返工。",
        "highlights": [
            "先原型后代码，降低沟通成本",
            "小步迭代，每次只改一个界面区域",
            "利用 Replit 一键部署验证效果",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://docs.replit.com/replitai/agent",
        "author": "Replit Docs",
        "date": "2026-04-01",
        "qualityScore": 85,
        "tags": ["vibe-coding", "ui"],
        "curated": True,
    },
    {
        "id": "bp-seed-jules-async",
        "title": "Jules：异步修复 CI 失败与小型 PR",
        "topic": "调试排错",
        "topicId": "debugging",
        "competitorId": "google-jules",
        "competitorName": "Jules",
        "summary": "将 Jules 接到 GitHub 仓库，对 CI 红灯、依赖漏洞、lint 失败等「明确问题」触发异步修复 PR，人工仅做合并决策。",
        "highlights": [
            "适合机械性修复，不适合架构变更",
            "在 PR 模板中标注 Jules 可处理的问题类型",
            "配合 CODEOWNERS 路由审查",
        ],
        "sourceType": "docs",
        "sourceLabel": "产品文档",
        "sourceUrl": "https://jules.google",
        "author": "Google",
        "date": "2026-05-15",
        "qualityScore": 87,
        "tags": ["ci", "async", "github"],
        "curated": True,
    },
    {
        "id": "bp-seed-kiro-spec",
        "title": "Kiro：Spec-Driven — 先写规范再生成实现",
        "topic": "测试驱动",
        "topicId": "testing",
        "competitorId": "kiro",
        "competitorName": "Kiro",
        "summary": "Kiro 强调从需求规范（Spec）驱动代码与测试生成；规范即契约，变更先改 Spec 再让 Agent 同步实现与测试。",
        "highlights": [
            "Spec 与测试用例对齐",
            "适合 API 与数据模型先行",
            "减少「代码写了但需求变了」的漂移",
        ],
        "sourceType": "blog",
        "sourceLabel": "博客",
        "sourceUrl": "https://kiro.dev/blog",
        "author": "AWS Kiro",
        "date": "2026-06-10",
        "qualityScore": 86,
        "tags": ["spec-driven", "requirements"],
        "curated": True,
    },
]

COMPETITOR_SEARCH_NAMES = {
    "cursor": ["Cursor IDE", "Cursor AI", "cursor.com", ".cursor/rules", ".cursorrules", "Cursor Rules"],
    "github-copilot": ["GitHub Copilot", "Copilot Chat", "Copilot coding agent", "Copilot Code Review"],
    "devin-desktop": ["Devin Desktop", "Devin AI", "Devin agent", "Windsurf"],
    "claude-code": ["Claude Code", "claude code cli", "CLAUDE.md"],
    "replit": ["Replit Agent", "Replit AI"],
    "google-jules": ["Google Jules", "Jules AI", "jules.google", "Jules agent"],
    "kiro": ["Kiro IDE", "Kiro dev", "AWS Kiro", "Kiro Agentic AI IDE"],
}

CODING_AGENT_CONTEXT_TERMS = [
    "coding agent", "ai coding", "agent mode", "agentic", "ai ide",
    "code assistant", "ai pair programmer", "autonomous agent",
    "copilot", "claude code", "cursor ide", "cursor ai", ".cursor",
    "cursorrules", "devin", "windsurf", "replit agent", "jules",
    "kiro", "mcp", "model context protocol", "claude.md",
    "copilot-instructions", "spec-driven", "prompt", "prompting",
]

PRACTICE_SIGNAL_TERMS = [
    "best practice", "best practices", "tip", "tips", "how to",
    "workflow", "playbook", "guide", "pattern", "setup", "configure",
    "configuration", "instructions", "rules", "prompt", "prompting",
    "checklist", "template", "recipe", "use case", "example",
    "技巧", "实践", "工作流", "建议", "指南", "配置", "提示词",
]

GITHUB_TITLE_PRACTICE_TERMS = [
    "best practice", "best practices", "how to", "guide", "workflow",
    "tips", "playbook", "instructions", "rules", "prompt", "plan mode",
    "claude.md", "copilot-instructions", "code review",
]

ACTIONABLE_VERBS = [
    "ask", "write", "keep", "split", "review", "run", "test", "verify",
    "configure", "set up", "add", "create", "document", "commit",
    "use", "enable", "limit", "connect", "define", "include",
    "要求", "编写", "维护", "拆分", "审查", "运行", "测试", "验证",
    "配置", "启用", "限制", "连接", "定义", "加入",
]

EXCLUSION_TERMS = [
    "feature request", "bug report", "preflight checklist", "problem statement",
    "pricing", "billing", "quota", "premium request", "wallet-wrecking",
    "unusable", "does not work", "doesn't work", "broken", "crash",
    "does not respect", "open source",
    "roadmap", "rfc:", "[wip]", "wip]", "implement a wayland",
    "security vulnerability", "billing can be bypassed",
]

EXCLUSION_TITLE_PREFIXES = [
    "feature request:", "[feature]", "bug:", "[bug]", "fix:", "ci:",
    "roadmap:", "rfc:", "[wip]",
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def fetch_json(url, headers=None):
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if GITHUB_TOKEN and "api.github.com" in url:
        hdrs["Authorization"] = "Bearer {}".format(GITHUB_TOKEN)
    req = Request(url, headers=hdrs)
    try:
        with urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, ValueError) as exc:
        print("  [WARN] 无法抓取 {}: {}".format(url, exc), file=sys.stderr)
        return None


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def term_count(lower, terms):
    return sum(1 for term in terms if term in lower)


def practice_id(source, url, title):
    raw = "{}|{}|{}".format(source, url, title)
    return "bp-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def classify_topic(text, fallback_topic_id="prompt-tips"):
    lower = text.lower()
    best_id = fallback_topic_id
    best_score = 0
    for topic in TOPICS:
        score = sum(1 for kw in topic["keywords"] if kw in lower)
        if score > best_score:
            best_score = score
            best_id = topic["id"]
    return best_id, TOPIC_BY_ID[best_id]["label"]


def mentions_competitor(text, competitor_id, competitor_name):
    lower = text.lower()
    if competitor_id == "cursor":
        return any(term in lower for term in [
            "cursor ide", "cursor ai", "cursor editor", "cursor rules",
            ".cursor", "cursorrules", "cursor.com", "cursor agent",
            "cursor composer", "cursor tab", "cursor chat",
        ])
    if competitor_id == "github-copilot":
        return "github copilot" in lower or any(term in lower for term in [
            "copilot chat", "copilot agent", "copilot coding",
            "copilot code review", "copilot instructions",
        ])
    if competitor_id == "devin-desktop":
        return "windsurf" in lower or "devin desktop" in lower or (
            "devin" in lower and term_count(lower, ["agent", "ai", "coding", "cloud"]) > 0
        )
    if competitor_id == "claude-code":
        return "claude code" in lower or "claude.md" in lower
    if competitor_id == "google-jules":
        return "jules.google" in lower or "google jules" in lower or (
            "jules" in lower and term_count(lower, ["agent", "ai", "github", "coding"]) > 0
        )
    if competitor_id == "kiro":
        return "kiro.dev" in lower or "kiro ide" in lower or "kiro agentic" in lower or (
            "kiro" in lower and term_count(lower, ["spec", "agent", "ai ide", "coding"]) > 0
        )
    names = COMPETITOR_SEARCH_NAMES.get(competitor_id, [competitor_name])
    return any(n.lower() in lower for n in names)


def is_practice_like(text):
    if not text or len(text) < 60:
        return False
    lower = text.lower()
    stripped = lower.strip()
    if any(stripped.startswith(prefix) for prefix in EXCLUSION_TITLE_PREFIXES):
        return False
    if term_count(lower, EXCLUSION_TERMS) > 0:
        return False
    if term_count(lower, CODING_AGENT_CONTEXT_TERMS) == 0:
        return False

    practice_signals = term_count(lower, PRACTICE_SIGNAL_TERMS)
    actionable_signals = term_count(lower, ACTIONABLE_VERBS)
    return practice_signals >= 1 and actionable_signals >= 1


def is_github_practice_title(title):
    lower = normalize_text(title).lower()
    if not lower:
        return False
    if any(lower.startswith(prefix) for prefix in EXCLUSION_TITLE_PREFIXES):
        return False
    if term_count(lower, EXCLUSION_TERMS) > 0:
        return False
    return term_count(lower, GITHUB_TITLE_PRACTICE_TERMS) > 0


def extract_highlights(text, limit=3):
    cleaned = normalize_text(re.sub(r"<[^>]+>", " ", text or ""))
    chunks = re.split(r"(?:\n|[。！？.!?]\s+| - |\* )", cleaned)
    highlights = []
    for chunk in chunks:
        chunk = normalize_text(chunk)
        lower = chunk.lower()
        if len(chunk) < 24 or len(chunk) > 180:
            continue
        if term_count(lower, EXCLUSION_TERMS) > 0:
            continue
        if term_count(lower, ACTIONABLE_VERBS) == 0 and term_count(lower, PRACTICE_SIGNAL_TERMS) == 0:
            continue
        if chunk not in highlights:
            highlights.append(chunk)
        if len(highlights) >= limit:
            break
    return highlights


def quality_score(item):
    if item.get("curated") and item.get("qualityScore"):
        return item.get("qualityScore")
    score = 50
    score += min(item.get("engagement", 0) // 5, 25)
    if item.get("sourceType") == "docs":
        score += 15
    if item.get("curated"):
        score += 10
    text_len = len(item.get("summary", ""))
    if text_len > 80:
        score += 5
    if text_len > 150:
        score += 5
    return min(score, 99)


def build_search_queries(competitor_name, topic):
    topic_terms = {
        "agent-workflow": "workflow plan mode rules",
        "mcp-integration": "mcp setup tools",
        "code-review": "code review instructions",
        "debugging": "debugging workflow tests",
    }
    topic_query = topic_terms.get(topic["id"], "workflow tips")
    return [
        '"{}" {} agent'.format(competitor_name, topic_query),
        '"{}" "best practices" "coding agent"'.format(competitor_name),
        '"{}" "how to use" coding'.format(competitor_name),
    ]


def search_hacker_news(query, competitor_id, competitor_name, max_hits=6):
    url = "https://hn.algolia.com/api/v1/search?{}".format(urllib.parse.urlencode({
        "query": query,
        "tags": "comment,story",
        "hitsPerPage": max_hits,
    }))
    data = fetch_json(url)
    if not data:
        return []

    results = []
    for hit in data.get("hits", []):
        title = normalize_text(hit.get("title") or "")
        body = normalize_text(hit.get("comment_text") or hit.get("story_text") or "")
        text = normalize_text("{} {}".format(title, body))
        if not mentions_competitor(text, competitor_id, competitor_name):
            continue
        if not is_practice_like(text):
            continue
        created = hit.get("created_at_i") or 0
        date_str = datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d") if created else ""
        item_url = hit.get("url") or "https://news.ycombinator.com/item?id={}".format(
            hit.get("objectID", hit.get("story_id", ""))
        )
        topic_id, topic_label = classify_topic(text)
        display_title = title or body[:80] or "HN 讨论"
        highlights = extract_highlights(text)
        if not highlights:
            continue
        results.append({
            "id": practice_id("hacker-news", item_url, display_title),
            "title": display_title[:120],
            "topic": topic_label,
            "topicId": topic_id,
            "competitorId": competitor_id,
            "competitorName": competitor_name,
            "summary": (body or title)[:400],
            "highlights": highlights,
            "sourceType": "hacker-news",
            "sourceLabel": SOURCE_LABELS["hacker-news"],
            "sourceUrl": item_url,
            "author": hit.get("author") or "anonymous",
            "date": date_str,
            "engagement": hit.get("points") or 0,
            "tags": [],
            "curated": False,
        })
    return results


def search_reddit(query, competitor_id, competitor_name, max_hits=5):
    url = "https://www.reddit.com/search.json?{}".format(urllib.parse.urlencode({
        "q": query,
        "sort": "relevance",
        "limit": max_hits,
        "type": "link",
    }))
    data = fetch_json(url)
    if not data:
        return []

    results = []
    for child in (data.get("data") or {}).get("children", []):
        post = child.get("data") or {}
        text = normalize_text("{} {}".format(post.get("title", ""), post.get("selftext", "")))
        if not mentions_competitor(text, competitor_id, competitor_name):
            continue
        if not is_practice_like(text):
            continue
        author = post.get("author") or "reddit-user"
        permalink = "https://www.reddit.com{}".format(post.get("permalink", ""))
        date_str = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d") if post.get("created_utc") else ""
        topic_id, topic_label = classify_topic(text)
        title = normalize_text(post.get("title", ""))[:120]
        highlights = extract_highlights(text)
        if not highlights:
            continue
        results.append({
            "id": practice_id("reddit", permalink, title),
            "title": title,
            "topic": topic_label,
            "topicId": topic_id,
            "competitorId": competitor_id,
            "competitorName": competitor_name,
            "summary": text[:400],
            "highlights": highlights,
            "sourceType": "reddit",
            "sourceLabel": SOURCE_LABELS["reddit"],
            "sourceUrl": permalink,
            "author": author,
            "date": date_str,
            "engagement": post.get("score", 0),
            "tags": [],
            "curated": False,
        })
    return results


def search_github(query, competitor_id, competitor_name, max_hits=5):
    q = '"{}" "best practice" OR "{}" tips OR "{}" workflow in:title,body'.format(
        query, query, query
    )
    url = "https://api.github.com/search/issues?{}".format(urllib.parse.urlencode({
        "q": q,
        "sort": "reactions",
        "per_page": max_hits,
    }))
    data = fetch_json(url)
    if not data:
        return []

    results = []
    for item in data.get("items", []):
        text = normalize_text("{} {}".format(item.get("title", ""), item.get("body", "")))
        if not mentions_competitor(text, competitor_id, competitor_name):
            continue
        if not is_practice_like(text):
            continue
        author = (item.get("user") or {}).get("login") or "github-user"
        date_str = (item.get("created_at") or "")[:10]
        topic_id, topic_label = classify_topic(text)
        title = normalize_text(item.get("title", ""))[:120]
        if not is_github_practice_title(title):
            continue
        highlights = extract_highlights(text)
        if not highlights:
            continue
        results.append({
            "id": practice_id("github", item.get("html_url", ""), title),
            "title": title,
            "topic": topic_label,
            "topicId": topic_id,
            "competitorId": competitor_id,
            "competitorName": competitor_name,
            "summary": text[:400],
            "highlights": highlights,
            "sourceType": "github",
            "sourceLabel": SOURCE_LABELS["github"],
            "sourceUrl": item.get("html_url", ""),
            "author": author,
            "date": date_str,
            "engagement": item.get("comments", 0),
            "tags": [],
            "curated": False,
        })
    return results


def dedupe_practices(practices):
    seen_urls = set()
    seen_ids = set()
    unique = []
    for p in practices:
        url = p.get("sourceUrl", "")
        pid = p.get("id", "")
        if pid in seen_ids:
            continue
        if url and url in seen_urls and not p.get("curated"):
            continue
        seen_ids.add(pid)
        if url:
            seen_urls.add(url)
        p["qualityScore"] = quality_score(p)
        unique.append(p)
    unique.sort(key=lambda x: (-x.get("qualityScore", 0), x.get("date", "")))
    return unique


def validated_web_practices(practices):
    valid = []
    for p in practices:
        text = normalize_text("{} {} {}".format(
            p.get("title", ""), p.get("summary", ""), " ".join(p.get("highlights", []))
        ))
        if not mentions_competitor(text, p.get("competitorId", ""), p.get("competitorName", "")):
            continue
        if not is_practice_like(text):
            continue
        if p.get("sourceType") == "github" and not is_github_practice_title(p.get("title", "")):
            continue
        if not p.get("highlights"):
            continue
        valid.append(p)
    return valid


def collect_web_practices(competitors, max_per_competitor=12):
    collected = []
    for comp in competitors:
        cid = comp["id"]
        cname = comp["name"]
        search_names = COMPETITOR_SEARCH_NAMES.get(cid, [cname])
        primary_name = search_names[0]
        print("  → {} ({})".format(cname, cid))
        comp_results = []

        for topic in TOPICS[:4]:
            queries = build_search_queries(primary_name, topic)
            for query in queries[:1]:
                print("    HN: {}".format(query[:55]))
                comp_results.extend(search_hacker_news(query, cid, cname))
                time.sleep(0.35)

        query = '"{}" best practices tips coding agent'.format(primary_name)
        print("    Reddit: {}".format(query[:55]))
        comp_results.extend(search_reddit(query, cid, cname))
        time.sleep(1.0)

        print("    GitHub: {}".format(primary_name))
        comp_results.extend(search_github(primary_name, cid, cname))
        time.sleep(0.5)

        comp_results = dedupe_practices(comp_results)
        collected.extend(comp_results[:max_per_competitor])
        print("    采集 {} 条".format(min(len(comp_results), max_per_competitor)))

    return collected


def build_payload(competitors, web_practices, dry_run=False):
    seeds = [dict(p) for p in SEED_PRACTICES]
    clean_web_practices = validated_web_practices(web_practices)
    all_practices = dedupe_practices(seeds + clean_web_practices)

    competitor_ids = [c["id"] for c in competitors]
    topic_labels = [t["label"] for t in TOPICS]
    source_types = sorted(set(p.get("sourceType", "") for p in all_practices if p.get("sourceType")))

    payload = {
        "meta": {
            "lastUpdated": now_iso(),
            "totalCount": len(all_practices),
            "curatedCount": sum(1 for p in all_practices if p.get("curated")),
            "webCount": sum(1 for p in all_practices if not p.get("curated")),
            "rejectedWebCount": max(len(web_practices) - len(clean_web_practices), 0),
            "topicsCount": len(TOPICS),
            "competitorsCount": len(competitor_ids),
            "sources": source_types,
            "collectIntervalDays": 3,
            "note": "仅保留可操作的 coding-agent 使用实践；策展官方最佳实践 + 通过质量门禁的 HN / Reddit / GitHub 公开讨论，每 3 天自动更新。",
        },
        "topics": [{"id": t["id"], "label": t["label"]} for t in TOPICS],
        "competitorIds": competitor_ids,
        "practices": all_practices,
    }

    if dry_run:
        print("\n[DRY-RUN] 共 {} 条最佳实践（策展 {} + 网络 {}）".format(
            len(all_practices),
            payload["meta"]["curatedCount"],
            payload["meta"]["webCount"],
        ))
        return payload

    save_json(OUTPUT_PATH, payload)
    print("\n已写入 {}（共 {} 条）".format(OUTPUT_PATH, len(all_practices)))
    return payload


def main():
    parser = argparse.ArgumentParser(description="采集竞品最佳实践")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入文件")
    parser.add_argument("--seeds-only", action="store_true", help="仅输出策展种子，跳过网络采集")
    args = parser.parse_args()

    competitors = load_json(COMPETITORS_PATH, default=[])
    if not competitors:
        print("[ERROR] competitors.json 为空", file=sys.stderr)
        return 1

    print("采集竞品最佳实践（{} 个竞品，{} 个主题）...".format(len(competitors), len(TOPICS)))

    if args.seeds_only:
        web_practices = []
    else:
        web_practices = collect_web_practices(competitors)

    build_payload(competitors, web_practices, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
