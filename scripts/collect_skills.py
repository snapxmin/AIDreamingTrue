#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业界 Top Agent Skills 采集脚本 — 从 GitHub Copilot、Cursor、Claude Code、Codex、OpenCode
等生态抓取 Skill 元数据，合并策展内容与远程 SKILL.md 描述，输出 data/skills.json。
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
SKILLS_PATH = os.path.join(DATA_DIR, "skills.json")
USER_AGENT = "AIDreamingTrue-SkillsCollector/2.0"

SOURCES = [
    {
        "id": "superpowers",
        "repo": "obra/superpowers",
        "pathTemplate": "skills/{slug}",
        "primaryPlatform": "Cursor",
        "alsoOn": ["Claude Code", "Codex", "OpenCode", "GitHub Copilot"],
        "installCommand": "npx skills add obra/superpowers  # 或 Cursor/Claude 安装 superpowers 插件",
        "docsUrl": "https://github.com/obra/superpowers",
    },
    {
        "id": "awesome-copilot",
        "repo": "github/awesome-copilot",
        "pathTemplate": "skills/{slug}",
        "primaryPlatform": "GitHub Copilot",
        "alsoOn": ["OpenCode"],
        "installCommand": "gh skill install github/awesome-copilot {slug}",
        "docsUrl": "https://awesome-copilot.github.com/skills/",
    },
    {
        "id": "anthropics-skills",
        "repo": "anthropics/skills",
        "pathTemplate": "skills/{slug}",
        "primaryPlatform": "Claude Code",
        "alsoOn": ["OpenCode", "Codex", "Cursor"],
        "installCommand": "npx skills add anthropics/skills --skill {slug}",
        "docsUrl": "https://github.com/anthropics/skills",
    },
    {
        "id": "openai-skills",
        "repo": "openai/skills",
        "pathTemplate": "skills/.curated/{slug}",
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


def fetch_url(url, timeout=20):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as exc:
        print("  [WARN] 无法抓取 {}: {}".format(url, exc), file=sys.stderr)
        return None


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


def fetch_skill_remote(source, slug):
    path = source["pathTemplate"].format(slug=slug)
    for branch in ("main", "master"):
        url = "https://raw.githubusercontent.com/{}/{}/{}/SKILL.md".format(
            source["repo"], branch, path
        )
        content = fetch_url(url)
        if content:
            meta = parse_frontmatter(content)
            desc = meta.get("description", "")
            base = "https://github.com/{}/tree/{}/{}".format(source["repo"], branch, path)
            return desc, base
    return "", ""


def discover_repo_skills(source):
    base_path = source["pathTemplate"].split("/{slug}")[0]
    api_url = "https://api.github.com/repos/{}/contents/{}".format(source["repo"], base_path)
    content = fetch_url(api_url)
    if not content:
        return []
    try:
        entries = json.loads(content)
    except ValueError:
        return []
    return sorted(e["name"] for e in entries if e.get("type") == "dir" and not e["name"].startswith("."))


def build_record(curated, source, remote_desc, source_url):
    slug = curated["slug"]
    install_tpl = source.get("installCommand", "")
    install = install_tpl.format(slug=slug) if "{slug}" in install_tpl else install_tpl

    primary = curated.get("primaryPlatform", source["primaryPlatform"])
    also_on = list(source.get("alsoOn", []))
    platforms = [primary] + [p for p in also_on if p != primary]

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
        "featured": curated.get("featured", False),
        "description": remote_desc or curated.get("description", ""),
        "introduction": curated["introduction"],
        "useCases": curated.get("useCases", []),
        "installCommand": install,
        "sourceUrl": source_url or "",
        "docsUrl": source.get("docsUrl", ""),
        "tags": curated.get("tags", []),
        "remoteSynced": bool(remote_desc),
    }


def collect_skills(dry_run=False):
    source_by_id = {s["id"]: s for s in SOURCES}
    skills = []
    discovery = {}

    print("采集业界 Top 20 Agent Skills（跨平台）...")
    for curated in CURATED_SKILLS:
        source = source_by_id.get(curated["sourceId"])
        if not source:
            continue
        print("  → #{} {} [{}]".format(curated["rank"], curated["slug"], curated.get("primaryPlatform", source["primaryPlatform"])))
        remote_desc, source_url = fetch_skill_remote(source, curated["slug"])
        skills.append(build_record(curated, source, remote_desc, source_url))

    for source in SOURCES:
        total = len(discover_repo_skills(source))
        curated_count = sum(1 for s in skills if s["ecosystem"] == source["id"])
        discovery[source["id"]] = {
            "platform": source["primaryPlatform"],
            "alsoOn": source.get("alsoOn", []),
            "repo": source["repo"],
            "totalInRepo": total,
            "curatedCount": curated_count,
        }
        print("  [DISCOVER] {} — 仓库约 {} 个，策展 {} 个".format(source["primaryPlatform"], total, curated_count))

    skills.sort(key=lambda s: s["rank"])
    all_platforms = sorted({p for s in skills for p in s["platforms"]})

    payload = {
        "meta": {
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "totalCount": len(skills),
            "featuredCount": sum(1 for s in skills if s["featured"]),
            "sources": [s["id"] for s in SOURCES],
            "discovery": discovery,
            "note": "Top 20 策展 Skills，覆盖 GitHub Copilot / Cursor / Claude Code / Codex / OpenCode；description 从远程 SKILL.md 同步。",
        },
        "sdePhases": sorted({s["sdePhase"] for s in skills}),
        "platforms": all_platforms,
        "categories": sorted({s["category"] for s in skills}),
        "skills": skills,
    }

    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:4000], "...")
        return payload

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(SKILLS_PATH, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("\n已写入 {}（{} 条 skill）".format(SKILLS_PATH, len(skills)))
    return payload


def print_sources():
    for s in SOURCES:
        print("- {} ({})".format(s["primaryPlatform"], s["repo"]))
        if s.get("alsoOn"):
            print("  亦适用于: {}".format(", ".join(s["alsoOn"])))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sources", action="store_true")
    args = parser.parse_args()
    if args.sources:
        print_sources()
        return 0
    collect_skills(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
