#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业界 Agent Skills 采集脚本 v3 — 策展 Top N + 全量索引 + 变更检测 + 事件联动。
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SKILLS_PATH = os.path.join(DATA_DIR, "skills.json")
INDEX_PATH = os.path.join(DATA_DIR, "skills-index.json")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "skills-snapshot.json")
CHANGES_PATH = os.path.join(DATA_DIR, "skill-changes.json")
LINKS_PATH = os.path.join(DATA_DIR, "skill-event-links.json")
EVENTS_PATH = os.path.join(DATA_DIR, "events.json")
USER_AGENT = "AIDreamingTrue-SkillsCollector/3.0"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

SOURCES = [
    {
        "id": "superpowers",
        "repo": "obra/superpowers",
        "pathTemplate": "skills/{slug}",
        "discoverPaths": ["skills"],
        "primaryPlatform": "Cursor",
        "alsoOn": ["Claude Code", "Codex", "OpenCode", "GitHub Copilot"],
        "installCommand": "npx skills add obra/superpowers  # 或 Cursor/Claude 安装 superpowers 插件",
        "docsUrl": "https://github.com/obra/superpowers",
    },
    {
        "id": "awesome-copilot",
        "repo": "github/awesome-copilot",
        "pathTemplate": "skills/{slug}",
        "discoverPaths": ["skills"],
        "primaryPlatform": "GitHub Copilot",
        "alsoOn": ["OpenCode"],
        "installCommand": "gh skill install github/awesome-copilot {slug}",
        "docsUrl": "https://awesome-copilot.github.com/skills/",
    },
    {
        "id": "anthropics-skills",
        "repo": "anthropics/skills",
        "pathTemplate": "skills/{slug}",
        "discoverPaths": ["skills"],
        "primaryPlatform": "Claude Code",
        "alsoOn": ["OpenCode", "Codex", "Cursor"],
        "installCommand": "npx skills add anthropics/skills --skill {slug}",
        "docsUrl": "https://github.com/anthropics/skills",
    },
    {
        "id": "openai-skills",
        "repo": "openai/skills",
        "pathTemplate": "skills/.curated/{slug}",
        "discoverPaths": ["skills/.curated"],
        "primaryPlatform": "Codex",
        "alsoOn": ["OpenCode"],
        "installCommand": "复制到 ~/.codex/skills/ 或 $REPO/.agents/skills/{slug}/",
        "docsUrl": "https://developers.openai.com/codex/skills",
    },
]

# Top 20 — 覆盖 Cursor / Claude Code / Codex / OpenCode / GitHub Copilot
CURATED_SKILLS = [
  {"slug":"brainstorming","sourceId":"superpowers","displayName":"Brainstorming","rank":1,"primaryPlatform":"Cursor","sdePhase":"需求设计","category":"创意与方案","featured":True,"tags":["superpowers","design","requirements"],"introduction":"实现前强制结构化头脑风暴：澄清意图、探索多种方案、分段确认设计，防止 Agent 未对齐就开写代码。Superpowers 生态使用率最高的技能之一，跨 Cursor / Claude Code / Codex / OpenCode 通用。","useCases":[{"title":"模糊需求澄清","scenario":"产品说「加个导出功能」，边界不清。","prompt":"I want to add an export feature — help me brainstorm","expected":"追问格式/权限/数据量，输出分段设计供确认后再实现。"}]},
  {"slug":"test-driven-development","sourceId":"superpowers","displayName":"Test-Driven Development","rank":2,"primaryPlatform":"Cursor","sdePhase":"实现","category":"测试驱动","featured":True,"tags":["TDD","red-green-refactor","superpowers"],"introduction":"红-绿-重构铁律：先写失败测试、最小实现、再重构。业界公认对抗 AI「看起来对」最有效的工程纪律技能。","useCases":[{"title":"API 端点开发","scenario":"新增分页查询接口。","prompt":"implement paginated endpoint using TDD","expected":"先失败测试 → 最小实现 → 全绿后重构。"}]},
  {"slug":"writing-plans","sourceId":"superpowers","displayName":"Writing Plans","rank":3,"primaryPlatform":"Claude Code","sdePhase":"规划拆解","category":"实现规划","featured":True,"tags":["planning","superpowers"],"introduction":"将需求写成可执行的实现计划（含文件路径、步骤、验证方式），与 executing-plans 配对形成 Plan → Execute 两阶段工作流。","useCases":[{"title":"复杂功能拆解","scenario":"支付模块需多 commit 交付。","prompt":"write a plan for payment integration","expected":"生成含 Branch、Steps、Testing 的 plan 文档。"}]},
  {"slug":"systematic-debugging","sourceId":"superpowers","displayName":"Systematic Debugging","rank":4,"primaryPlatform":"Cursor","sdePhase":"调试排错","category":"问题定位","featured":True,"tags":["debug","root-cause","superpowers"],"introduction":"先复现、收集 runtime 证据、定位根因后再修复；禁止无证据猜测。针对 AI Agent 常见「试一把式」调试。","useCases":[{"title":"间歇性 500","scenario":"生产 API 偶发错误。","prompt":"debug intermittent 500 on /api/checkout","expected":"要求日志/复现步骤，假设树逐一验证。"}]},
  {"slug":"verification-before-completion","sourceId":"superpowers","displayName":"Verification Before Completion","rank":5,"primaryPlatform":"Cursor","sdePhase":"输出验证","category":"完成前验证","featured":True,"tags":["verification","evidence","superpowers"],"introduction":"声称完成/通过测试前必须运行验证命令并展示输出。Evidence before assertions。","useCases":[{"title":"修复确认","scenario":"Agent 称已修复 lint。","prompt":"fix lint errors and verify","expected":"实际运行 linter 并展示通过输出。"}]},
  {"slug":"subagent-driven-development","sourceId":"superpowers","displayName":"Subagent-Driven Development","rank":6,"primaryPlatform":"Cursor","sdePhase":"多 Agent 协作","category":"并行开发","featured":True,"tags":["subagent","parallel","superpowers"],"introduction":"将任务派发给子 Agent 并行执行，主 Agent 设质量门与验收标准。适合大任务拆分与加速。","useCases":[{"title":"多模块并行","scenario":"前后端接口同时开发。","prompt":"use subagents to implement API and frontend in parallel","expected":"子任务并行、汇总前逐块验收。"}]},
  {"slug":"requesting-code-review","sourceId":"superpowers","displayName":"Requesting Code Review","rank":7,"primaryPlatform":"Cursor","sdePhase":"代码审查","category":"质量门禁","featured":True,"tags":["code-review","superpowers"],"introduction":"合并前结构化 Code Review 清单：范围、风险、测试、文档，可与 receiving-code-review 配对。","useCases":[{"title":"PR 合并前审查","scenario":"大 PR 需系统性 review。","prompt":"request code review for this PR","expected":"按清单输出 PASS/WARN/FAIL 项。"}]},
  {"slug":"using-superpowers","sourceId":"superpowers","displayName":"Using Superpowers","rank":8,"primaryPlatform":"Cursor","sdePhase":"环境准备","category":"技能框架","featured":False,"tags":["meta","superpowers","onboarding"],"introduction":"Superpowers 技能系统入门：何时加载 skill、如何发现与组合技能。新会话/bootstrap 的基础技能。","useCases":[{"title":"首次使用 Superpowers","scenario":"不确定 Agent 是否会自动用 skill。","prompt":"what skills do you have available?","expected":"列出已安装 skill 及触发条件。"}]},
  {"slug":"ai-ready","sourceId":"awesome-copilot","displayName":"AI Ready","rank":9,"primaryPlatform":"GitHub Copilot","sdePhase":"环境准备","category":"仓库初始化","featured":True,"tags":["AGENTS.md","copilot-instructions"],"introduction":"一键 AI 化仓库：生成 AGENTS.md、copilot-instructions、CI、Issue 模板等。Copilot 生态仓库接入首选。","useCases":[{"title":"仓库 AI 配置","scenario":"fork 开源项目后接入 Copilot。","prompt":"make this repo ai-ready","expected":"生成 AGENTS.md 与 copilot-instructions。"}]},
  {"slug":"security-review","sourceId":"awesome-copilot","displayName":"Security Review","rank":10,"primaryPlatform":"GitHub Copilot","sdePhase":"安全审查","category":"应用安全","featured":True,"tags":["SAST","OWASP","secrets"],"introduction":"数据流追踪 + 依赖 CVE + 密钥扫描，分级报告与修复建议。合并前安全门禁。","useCases":[{"title":"认证模块审查","scenario":"PR 改动 auth 目录。","prompt":"security review on src/auth/","expected":"CRITICAL/HIGH 分级漏洞清单。"}]},
  {"slug":"eval-driven-dev","sourceId":"awesome-copilot","displayName":"Eval-Driven Development","rank":11,"primaryPlatform":"GitHub Copilot","sdePhase":"测试评估","category":"LLM 应用 QA","featured":True,"tags":["eval","LLM","pixie"],"introduction":"Python LLM 应用评估流水线：golden dataset、LLM-as-judge、pixie test。AI 应用专属 QA。","useCases":[{"title":"RAG 质量回归","scenario":"问答机器人偶发幻觉。","prompt":"set up evals for our RAG chatbot","expected":"eval criteria + 数据集 + 评分流水线。"}]},
  {"slug":"harness-engineering","sourceId":"awesome-copilot","displayName":"Harness Engineering","rank":12,"primaryPlatform":"GitHub Copilot","sdePhase":"持续治理","category":"Agent 治理","featured":True,"tags":["governance","drift-check"],"introduction":"将 Agent 反复错误沉淀为 instructions、回归测试与漂移检查。长期可维护的 Agent 工程化。","useCases":[{"title":"Agent 重复犯错","scenario":"总在错误目录写测试。","prompt":"improve agent harness for test file placement","expected":"更新 rules + CI 防复发。"}]},
  {"slug":"acquire-codebase-knowledge","sourceId":"awesome-copilot","displayName":"Acquire Codebase Knowledge","rank":13,"primaryPlatform":"GitHub Copilot","sdePhase":"代码理解","category":"代码库分析","featured":True,"tags":["onboarding","architecture"],"introduction":"产出 7 份带证据链代码库文档 + scan.py。陌生仓库 onboarding 标准技能。","useCases":[{"title":"接手遗留系统","scenario":"两周内理解大型单体。","prompt":"map this codebase","expected":"docs/codebase/ 下 7 份文档。"}]},
  {"slug":"frontend-design","sourceId":"anthropics-skills","displayName":"Frontend Design","rank":14,"primaryPlatform":"Claude Code","sdePhase":"实现","category":"前端设计","featured":True,"tags":["UI","anthropic","design"],"introduction":"Anthropic 官方技能：生成有辨识度、生产级前端界面，避免「AI 味」通用 UI。Claude Code / OpenCode 高频安装技能。","useCases":[{"title":"落地页重做","scenario":"SaaS 首页过于模板化。","prompt":"redesign the landing page with bold frontend design","expected":"非常规排版、字体与动效的高质量 UI 代码。"}]},
  {"slug":"skill-creator","sourceId":"anthropics-skills","displayName":"Skill Creator","rank":15,"primaryPlatform":"Claude Code","sdePhase":"持续治理","category":"技能创作","featured":True,"tags":["meta","anthropic","authoring"],"introduction":"Anthropic 官方：按 Agent Skills 规范创建、测试与迭代自定义 skill。团队自建技能库的基础。","useCases":[{"title":"团队规范固化","scenario":"把 Code Review 清单变成 skill。","prompt":"create a skill for our PR review checklist","expected":"符合规范的 SKILL.md + 触发 description。"}]},
  {"slug":"mcp-builder","sourceId":"anthropics-skills","displayName":"MCP Builder","rank":16,"primaryPlatform":"Claude Code","sdePhase":"工具集成","category":"MCP 开发","featured":True,"tags":["MCP","anthropic","integration"],"introduction":"指导构建 Model Context Protocol 服务器：tools、resources、prompts。Claude Code 连接外部系统的核心技能。","useCases":[{"title":"封装内部 API","scenario":"把工单系统暴露给 Agent。","prompt":"build an MCP server for our ticket API","expected":"可运行的 MCP server 项目结构与实现。"}]},
  {"slug":"security-best-practices","sourceId":"openai-skills","displayName":"Security Best Practices","rank":17,"primaryPlatform":"Codex","sdePhase":"安全审查","category":"安全规范","featured":True,"tags":["security","codex","openai"],"introduction":"OpenAI Codex 官方精选 skill：代码安全最佳实践审查。Codex CLI/App 高频安全类技能。","useCases":[{"title":"提交前安全检查","scenario":"新 API 涉及用户输入。","prompt":"review this code for security best practices","expected":"按 OWASP 类清单输出问题与修复。"}]},
  {"slug":"gh-fix-ci","sourceId":"openai-skills","displayName":"GitHub Fix CI","rank":18,"primaryPlatform":"Codex","sdePhase":"DevOps","category":"CI/CD","featured":True,"tags":["github-actions","codex","ci"],"introduction":"OpenAI 官方：分析并修复 GitHub Actions CI 失败。Codex 用户修 CI 最高频技能之一。","useCases":[{"title":"CI 红灯修复","scenario":"push 后 workflow 失败。","prompt":"fix the failing GitHub Actions CI","expected":"读日志、定位根因、提交修复。"}]},
  {"slug":"playwright","sourceId":"openai-skills","displayName":"Playwright","rank":19,"primaryPlatform":"Codex","sdePhase":"测试评估","category":"E2E 测试","featured":True,"tags":["playwright","e2e","codex"],"introduction":"OpenAI 官方：用 Playwright 编写与调试端到端测试。Codex 自动化测试类代表技能。","useCases":[{"title":"关键路径 E2E","scenario":"结账流程需回归测试。","prompt":"add Playwright e2e tests for checkout flow","expected":"可运行的 spec 与本地执行说明。"}]},
  {"slug":"context-map","sourceId":"awesome-copilot","displayName":"Context Map","rank":20,"primaryPlatform":"GitHub Copilot","sdePhase":"代码理解","category":"上下文管理","featured":False,"tags":["context","refactor","opencode"],"introduction":"改动前生成任务相关文件地图，明确影响范围。Copilot context-engineering 插件核心，OpenCode 亦可复用。","useCases":[{"title":"重构前摸底","scenario":"重命名核心服务。","prompt":"map files relevant to renaming AuthService","expected":"列出相关文件与修改优先级。"}]},
]

CURATED_SLUGS = {(c["sourceId"], c["slug"]) for c in CURATED_SKILLS}
SKILL_EVENT_KEYWORDS = re.compile(r"\bskills?\b|\bsuperpowers\b|\bmcp\b|\bplugin\b", re.I)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def api_headers():
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = "Bearer {}".format(GITHUB_TOKEN)
    return headers


def skill_key(ecosystem, slug):
    return "{}/{}".format(ecosystem, slug)


def slug_to_display(slug):
    return slug.replace("-", " ").title()


def fetch_url(url, timeout=25, accept="*/*"):
    headers = api_headers() if "api.github.com" in url else {"User-Agent": USER_AGENT, "Accept": accept}
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as exc:
        print("  [WARN] 无法抓取 {}: {}".format(url, exc), file=sys.stderr)
        return None


def fetch_repo_stars(repo):
    content = fetch_url("https://api.github.com/repos/{}".format(repo))
    if not content:
        return 0
    try:
        return int(json.loads(content).get("stargazers_count", 0))
    except (ValueError, TypeError):
        return 0


def parse_frontmatter(content):
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip().strip("'\"")
        if value.startswith(">"):
            value = value[1:].strip()
        result[key.strip()] = value
    return result


def fetch_skill_full(source, slug, path_prefix=None):
    if path_prefix:
        rel = "{}/{}".format(path_prefix, slug)
    else:
        rel = source["pathTemplate"].format(slug=slug)
    for branch in ("main", "master"):
        url = "https://raw.githubusercontent.com/{}/{}/{}/SKILL.md".format(
            source["repo"], branch, rel
        )
        content = fetch_url(url)
        if content:
            meta = parse_frontmatter(content)
            desc = meta.get("description", "")
            source_url = "https://github.com/{}/tree/{}/{}".format(source["repo"], branch, rel)
            return {
                "description": desc,
                "sourceUrl": source_url,
                "contentHash": content_hash(content),
                "descriptionHash": content_hash(desc),
            }
    return None


def discover_repo_skills(source):
    paths = source.get("discoverPaths") or [source["pathTemplate"].split("/{slug}")[0]]
    found = {}
    for base_path in paths:
        api_url = "https://api.github.com/repos/{}/contents/{}".format(source["repo"], base_path)
        content = fetch_url(api_url)
        if not content:
            continue
        try:
            entries = json.loads(content)
        except ValueError:
            continue
        for entry in entries:
            if entry.get("type") == "dir" and not entry["name"].startswith("."):
                slug = entry["name"]
                if slug not in found:
                    found[slug] = base_path
        time.sleep(0.05)
    return found


def build_install_command(source, slug):
    install_tpl = source.get("installCommand", "")
    if "{slug}" in install_tpl:
        return install_tpl.format(slug=slug)
    return install_tpl


def compute_activity_score(signals):
    score = 0.0
    score += min(signals.get("repoStars", 0) / 200.0, 25)
    score += signals.get("mentionedInEvents", 0) * 12
    score += signals.get("crossPlatformCount", 0) * 8
    score += 15 if signals.get("inTopCurated") else 0
    score += 10 if signals.get("featured") else 0
    if signals.get("isNew"):
        score += 5
    return min(int(round(score)), 100)


def match_event_to_skills(event, index_by_slug):
    text = " ".join([
        event.get("title", ""),
        event.get("summary", ""),
        event.get("impact", ""),
    ]).lower()
    if not SKILL_EVENT_KEYWORDS.search(text):
        return []
    related = []
    for (ecosystem, slug), entry in index_by_slug.items():
        slug_dash = slug.lower()
        slug_norm = slug_dash.replace("-", " ")
        confidence = 0.0
        if slug_dash in text or slug_norm in text:
            confidence = 0.9
        if confidence >= 0.6:
            related.append({
                "slug": slug,
                "ecosystem": ecosystem,
                "displayName": entry.get("displayName", slug_to_display(slug)),
                "confidence": confidence,
            })
    related.sort(key=lambda x: -x["confidence"])
    return related[:5]


def detect_changes(previous_snapshot, current_snapshot, is_baseline):
    changes = []
    prev_keys = set(previous_snapshot.keys())
    curr_keys = set(current_snapshot.keys())
    ts = now_iso()

    for key in sorted(curr_keys - prev_keys):
        if is_baseline:
            continue
        entry = current_snapshot[key]
        changes.append({
            "type": "added",
            "key": key,
            "ecosystem": entry["ecosystem"],
            "slug": entry["slug"],
            "displayName": entry.get("displayName", entry["slug"]),
            "summary": "生态新增 Skill：{}".format(entry.get("displayName", entry["slug"])),
            "detectedAt": ts,
        })

    for key in sorted(curr_keys & prev_keys):
        prev = previous_snapshot[key]
        curr = current_snapshot[key]
        changed_fields = []
        if curr.get("contentHash") != prev.get("contentHash"):
            changed_fields.append("content")
        if curr.get("descriptionHash") != prev.get("descriptionHash"):
            changed_fields.append("description")
        if not changed_fields:
            continue
        summary = "Skill 内容已更新"
        if "description" in changed_fields and curr.get("description"):
            summary = "description 更新：{}…".format(curr["description"][:100])
        changes.append({
            "type": "updated",
            "key": key,
            "ecosystem": curr["ecosystem"],
            "slug": curr["slug"],
            "displayName": curr.get("displayName", curr["slug"]),
            "changedFields": changed_fields,
            "summary": summary,
            "sourceUrl": curr.get("sourceUrl", ""),
            "detectedAt": ts,
        })
    return changes


def build_curated_record(curated, source, remote, signals, skill_events):
    slug = curated["slug"]
    primary = curated.get("primaryPlatform", source["primaryPlatform"])
    also_on = list(source.get("alsoOn", []))
    platforms = [primary] + [p for p in also_on if p != primary]
    remote_desc = remote["description"] if remote else ""

    return {
        "id": "skill-{:03d}".format(curated["rank"]),
        "slug": slug,
        "name": slug,
        "displayName": curated["displayName"],
        "platform": primary,
        "platforms": platforms,
        "ecosystem": source["id"],
        "category": curated["category"],
        "sdePhase": curated["sdePhase"],
        "rank": curated["rank"],
        "rankType": "editorial",
        "featured": curated.get("featured", False),
        "description": remote_desc or curated.get("description", ""),
        "introduction": curated["introduction"],
        "useCases": curated.get("useCases", []),
        "installCommand": build_install_command(source, slug),
        "sourceUrl": remote["sourceUrl"] if remote else "",
        "docsUrl": source.get("docsUrl", ""),
        "tags": curated.get("tags", []),
        "remoteSynced": bool(remote_desc),
        "contentHash": remote["contentHash"] if remote else "",
        "lastChangedAt": remote.get("lastChangedAt", "") if remote else "",
        "activityScore": signals["activityScore"],
        "activityRank": 0,
        "signals": signals,
        "relatedEvents": skill_events[:5],
    }


def collect_skills(dry_run=False, fetch_index_descriptions=True):
    source_by_id = {s["id"]: s for s in SOURCES}
    previous_snapshot = load_json(SNAPSHOT_PATH, default={})
    is_baseline = len(previous_snapshot) == 0
    generated_at = now_iso()

    repo_stars = {}
    for source in SOURCES:
        repo_stars[source["id"]] = fetch_repo_stars(source["repo"])
        print("  [STARS] {} — {}".format(source["repo"], repo_stars[source["id"]]))

    discovered = {}
    for source in SOURCES:
        discovered[source["id"]] = discover_repo_skills(source)
        print("  [DISCOVER] {} — {} 个 skill 目录".format(source["id"], len(discovered[source["id"]])))

    current_snapshot = {}
    index_entries = []
    curated_remote = {}

    print("\n采集策展 Top 20（完整 SKILL.md）...")
    for curated in CURATED_SKILLS:
        source = source_by_id.get(curated["sourceId"])
        if not source:
            continue
        slug = curated["slug"]
        path_prefix = discovered[source["id"]].get(slug)
        if not path_prefix:
            path_prefix = source["pathTemplate"].split("/{slug}")[0]
        print("  → #{} {} [{}]".format(
            curated["rank"], slug, curated.get("primaryPlatform", source["primaryPlatform"])))
        remote = fetch_skill_full(source, slug, path_prefix)
        if remote:
            key = skill_key(source["id"], slug)
            prev = previous_snapshot.get(key, {})
            last_changed = prev.get("lastChangedAt", generated_at)
            if prev and prev.get("contentHash") != remote["contentHash"]:
                last_changed = generated_at
            remote["lastChangedAt"] = last_changed
            current_snapshot[key] = {
                "ecosystem": source["id"],
                "slug": slug,
                "displayName": curated["displayName"],
                "description": remote["description"],
                "contentHash": remote["contentHash"],
                "descriptionHash": remote["descriptionHash"],
                "sourceUrl": remote["sourceUrl"],
                "lastSeenAt": generated_at,
                "lastChangedAt": last_changed,
            }
        curated_remote[(source["id"], slug)] = remote
        time.sleep(0.05)

    print("\n构建全量索引...")
    slug_platform_count = {}
    for source in SOURCES:
        for slug in discovered[source["id"]]:
            slug_platform_count[slug] = slug_platform_count.get(slug, 0) + 1

    index_total = sum(len(d) for d in discovered.values())
    index_done = 0
    for source in SOURCES:
        for slug, path_prefix in sorted(discovered[source["id"]].items()):
            index_done += 1
            in_top = (source["id"], slug) in CURATED_SLUGS
            is_new = not is_baseline and skill_key(source["id"], slug) not in previous_snapshot

            remote = curated_remote.get((source["id"], slug))
            if not remote and fetch_index_descriptions:
                if index_done % 50 == 0:
                    print("  ... 索引进度 {}/{}".format(index_done, index_total))
                remote = fetch_skill_full(source, slug, path_prefix)
                time.sleep(0.03)

            key = skill_key(source["id"], slug)
            if remote:
                prev = previous_snapshot.get(key, {})
                last_changed = prev.get("lastChangedAt", generated_at)
                if prev and prev.get("contentHash") != remote["contentHash"]:
                    last_changed = generated_at
                remote["lastChangedAt"] = last_changed
                current_snapshot[key] = {
                    "ecosystem": source["id"],
                    "slug": slug,
                    "displayName": slug_to_display(slug),
                    "description": remote["description"],
                    "contentHash": remote["contentHash"],
                    "descriptionHash": remote["descriptionHash"],
                    "sourceUrl": remote["sourceUrl"],
                    "lastSeenAt": generated_at,
                    "lastChangedAt": last_changed,
                }

            curated_match = next(
                (c for c in CURATED_SKILLS if c["slug"] == slug and c["sourceId"] == source["id"]),
                None,
            )
            display = curated_match["displayName"] if curated_match else slug_to_display(slug)

            index_entries.append({
                "id": "idx-{}-{}".format(source["id"], slug),
                "slug": slug,
                "displayName": display,
                "ecosystem": source["id"],
                "platform": source["primaryPlatform"],
                "platforms": [source["primaryPlatform"]] + [
                    p for p in source.get("alsoOn", []) if p != source["primaryPlatform"]
                ],
                "description": remote["description"] if remote else "",
                "sourceUrl": remote["sourceUrl"] if remote else "",
                "installCommand": build_install_command(source, slug),
                "inTopCurated": in_top,
                "isNew": is_new,
                "discoveredAt": previous_snapshot.get(key, {}).get("lastSeenAt", generated_at),
                "lastChangedAt": current_snapshot.get(key, {}).get("lastChangedAt", ""),
                "pathPrefix": path_prefix,
            })

    changes = detect_changes(previous_snapshot, current_snapshot, is_baseline)

    events = load_json(EVENTS_PATH, default=[])
    event_links = []
    if isinstance(events, list):
        index_by_slug = {(e["ecosystem"], e["slug"]): e for e in index_entries}
        for event in events:
            related = match_event_to_skills(event, index_by_slug)
            for rel in related:
                event_links.append({
                    "eventId": event.get("id", ""),
                    "eventTitle": event.get("title", ""),
                    "eventDate": event.get("date", ""),
                    "slug": rel["slug"],
                    "ecosystem": rel["ecosystem"],
                    "displayName": rel["displayName"],
                    "confidence": rel["confidence"],
                })
            if related:
                event["relatedSkills"] = related
                if event.get("topic") == "Agent" and SKILL_EVENT_KEYWORDS.search(event.get("title", "")):
                    event["topic"] = "Skill"

    mention_counts = {}
    for link in event_links:
        k = (link["ecosystem"], link["slug"])
        mention_counts[k] = mention_counts.get(k, 0) + 1

    skills = []
    print("\n组装策展记录...")
    for curated in CURATED_SKILLS:
        source = source_by_id.get(curated["sourceId"])
        if not source:
            continue
        slug = curated["slug"]
        remote = curated_remote.get((source["id"], slug))
        key = (source["id"], slug)
        signals = {
            "repoStars": repo_stars.get(source["id"], 0),
            "mentionedInEvents": mention_counts.get(key, 0),
            "crossPlatformCount": max(slug_platform_count.get(slug, 1) - 1, 0),
            "inTopCurated": True,
            "featured": curated.get("featured", False),
            "isNew": False,
        }
        signals["activityScore"] = compute_activity_score(signals)
        skill_events = [
            {"eventId": l["eventId"], "eventTitle": l["eventTitle"], "eventDate": l["eventDate"]}
            for l in event_links if l["slug"] == slug and l["ecosystem"] == source["id"]
        ]
        skills.append(build_curated_record(curated, source, remote, signals, skill_events))

    by_activity = sorted(skills, key=lambda s: -s["activityScore"])
    activity_rank = {s["id"]: i + 1 for i, s in enumerate(by_activity)}
    for skill in skills:
        skill["activityRank"] = activity_rank[skill["id"]]
    skills.sort(key=lambda s: s["rank"])

    for entry in index_entries:
        key = (entry["ecosystem"], entry["slug"])
        sig = {
            "repoStars": repo_stars.get(entry["ecosystem"], 0),
            "mentionedInEvents": mention_counts.get(key, 0),
            "crossPlatformCount": max(slug_platform_count.get(entry["slug"], 1) - 1, 0),
            "inTopCurated": entry["inTopCurated"],
            "featured": False,
            "isNew": entry["isNew"],
        }
        entry["activityScore"] = compute_activity_score(sig)
    index_entries.sort(key=lambda e: (-e["activityScore"], e["displayName"]))

    discovery = {}
    for source in SOURCES:
        discovery[source["id"]] = {
            "platform": source["primaryPlatform"],
            "alsoOn": source.get("alsoOn", []),
            "repo": source["repo"],
            "repoStars": repo_stars.get(source["id"], 0),
            "totalInRepo": len(discovered[source["id"]]),
            "curatedCount": sum(1 for s in skills if s["ecosystem"] == source["id"]),
        }

    all_platforms = sorted({p for s in skills for p in s["platforms"]})
    skills_payload = {
        "meta": {
            "lastUpdated": generated_at,
            "totalCount": len(skills),
            "featuredCount": sum(1 for s in skills if s["featured"]),
            "indexTotalCount": len(index_entries),
            "newCount": sum(1 for e in index_entries if e["isNew"]),
            "changesCount": len(changes),
            "sources": [s["id"] for s in SOURCES],
            "discovery": discovery,
            "note": "Top 20 策展 + 全量索引；含 activityScore、变更 feed 与事件联动。",
        },
        "sdePhases": sorted({s["sdePhase"] for s in skills}),
        "platforms": all_platforms,
        "categories": sorted({s["category"] for s in skills}),
        "skills": skills,
    }

    index_payload = {
        "meta": {
            "lastUpdated": generated_at,
            "totalCount": len(index_entries),
            "newCount": sum(1 for e in index_entries if e["isNew"]),
            "sources": [s["id"] for s in SOURCES],
        },
        "skills": index_entries,
    }

    changes_payload = {
        "generatedAt": generated_at,
        "isBaselineRun": is_baseline,
        "changes": changes[:100],
    }

    links_payload = {"generatedAt": generated_at, "links": event_links}

    if dry_run:
        print("\n[DRY-RUN] 策展 {} / 索引 {} / 变更 {}".format(
            len(skills), len(index_entries), len(changes)))
        return skills_payload

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    save_json(SKILLS_PATH, skills_payload)
    save_json(INDEX_PATH, index_payload)
    save_json(SNAPSHOT_PATH, current_snapshot)
    save_json(CHANGES_PATH, changes_payload)
    save_json(LINKS_PATH, links_payload)
    if isinstance(events, list) and events:
        save_json(EVENTS_PATH, events)

    print("\n已写入:")
    print("  {} ({} 策展)".format(SKILLS_PATH, len(skills)))
    print("  {} ({} 索引)".format(INDEX_PATH, len(index_entries)))
    print("  {} ({} 快照键)".format(SNAPSHOT_PATH, len(current_snapshot)))
    print("  {} ({} 变更)".format(CHANGES_PATH, len(changes)))
    print("  {} ({} 事件关联)".format(LINKS_PATH, len(event_links)))
    return skills_payload


def print_sources():
    for s in SOURCES:
        print("- {} ({})".format(s["primaryPlatform"], s["repo"]))
        if s.get("alsoOn"):
            print("  亦适用于: {}".format(", ".join(s["alsoOn"])))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sources", action="store_true")
    parser.add_argument("--skip-index-fetch", action="store_true",
                        help="跳过非策展 Skill 的远程 description 抓取")
    args = parser.parse_args()
    if args.sources:
        print_sources()
        return 0
    collect_skills(dry_run=args.dry_run, fetch_index_descriptions=not args.skip_index_fetch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
