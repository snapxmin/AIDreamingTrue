#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业界 Top Agent Skills 采集脚本 — 从 GitHub Copilot、Cursor 等生态抓取 Skill 元数据，
合并策展内容与远程 SKILL.md 描述，输出 data/skills.json。

用法:
  python3 scripts/collect_skills.py              # 抓取并写入 data/skills.json
  python3 scripts/collect_skills.py --dry-run    # 仅预览，不写入
  python3 scripts/collect_skills.py --sources    # 列出监控来源
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

USER_AGENT = "AIDreamingTrue-SkillsCollector/1.0"

SOURCES = [
    {
        "id": "awesome-copilot",
        "platform": "GitHub Copilot",
        "repo": "github/awesome-copilot",
        "skillsPath": "skills",
        "installPrefix": "gh skill install github/awesome-copilot",
        "docsUrl": "https://awesome-copilot.github.com/skills/",
    },
    {
        "id": "cursor-superpowers",
        "platform": "Cursor",
        "repo": "obra/superpowers",
        "skillsPath": "skills",
        "installPrefix": "Cursor Plugin: superpowers",
        "docsUrl": "https://github.com/obra/superpowers",
    },
]

# 策展 Top Skills — 围绕 AI 软件工程全链路
CURATED_SKILLS = [
    {
        "slug": "ai-ready",
        "sourceId": "awesome-copilot",
        "displayName": "AI Ready",
        "rank": 1,
        "sdePhase": "环境准备",
        "category": "仓库初始化",
        "featured": True,
        "tags": ["AGENTS.md", "copilot-instructions", "CI"],
        "introduction": (
            "将任意代码仓库一键「AI 化」：分析技术栈与 PR 审查模式，自动生成 AGENTS.md、"
            "copilot-instructions.md、CI 工作流、Issue 模板等配置文件。"
            "这是 AI 辅助开发前的基础设施步骤，显著降低 Agent 进入陌生仓库时的理解成本。"
        ),
        "useCases": [
            {
                "title": "新项目接入 Copilot Agent",
                "scenario": "团队刚 fork 一个开源项目，希望 Copilot 能按项目规范写代码。",
                "prompt": "make this repo ai-ready",
                "expected": "生成 AGENTS.md 与 .github/copilot-instructions.md，并针对技术栈定制规则。",
            },
            {
                "title": "Monorepo 多包规范",
                "scenario": "仓库含前端、后端、基础设施多个子目录，需要分区 instructions。",
                "prompt": "set up AI config for this monorepo with per-area instructions",
                "expected": "为各子目录生成带 applyTo glob 的 instructions 文件。",
            },
        ],
    },
    {
        "slug": "acquire-codebase-knowledge",
        "sourceId": "awesome-copilot",
        "displayName": "Acquire Codebase Knowledge",
        "rank": 2,
        "sdePhase": "代码理解",
        "category": "代码库分析",
        "featured": True,
        "tags": ["onboarding", "architecture", "documentation"],
        "introduction": (
            "对现有代码库做系统性测绘，产出 7 份结构化文档（STACK、ARCHITECTURE、TESTING 等），"
            "附带 scan.py 可执行扫描脚本。每条结论要求有文件证据，适合 Agent 或新人快速建立心智模型。"
        ),
        "useCases": [
            {
                "title": "接手遗留系统",
                "scenario": "开发者加入项目，需要在两周内理解 10 万行代码的架构。",
                "prompt": "map this codebase and document the architecture",
                "expected": "在 docs/codebase/ 下生成 7 份带证据链的 Markdown 文档。",
            },
            {
                "title": "PR 前影响面评估",
                "scenario": "大功能改动前，需要弄清模块边界与集成点。",
                "prompt": "create codebase docs focusing on integrations and testing",
                "expected": "INTEGRATIONS.md 与 TESTING.md 标注关键依赖与测试策略。",
            },
        ],
    },
    {
        "slug": "brainstorming",
        "sourceId": "cursor-superpowers",
        "displayName": "Brainstorming",
        "rank": 3,
        "sdePhase": "需求设计",
        "category": "创意与方案",
        "featured": True,
        "tags": ["design", "requirements", "superpowers"],
        "introduction": (
            "在写任何功能代码之前，强制进入结构化头脑风暴：澄清意图、探索 2–3 种方案、"
            "分段展示设计并逐段获得用户确认。防止 AI「一上来就写代码」导致方向跑偏。"
        ),
        "useCases": [
            {
                "title": "新功能立项",
                "scenario": "产品提出模糊需求「加个导出功能」，实现路径不明确。",
                "prompt": "I want to add an export feature for user data",
                "expected": "Skill 引导追问格式、权限、数据量，输出分段设计文档供确认后再实现。",
            },
            {
                "title": "重构方案选型",
                "scenario": "单体服务需要拆分，有多种架构选项。",
                "prompt": "help me brainstorm how to split this monolith",
                "expected": "列出多种方案及权衡，用户选定后再进入实现阶段。",
            },
        ],
    },
    {
        "slug": "structured-autonomy-plan",
        "sourceId": "awesome-copilot",
        "displayName": "Structured Autonomy Plan",
        "rank": 4,
        "sdePhase": "规划拆解",
        "category": "实现规划",
        "featured": True,
        "tags": ["planning", "commits", "PR"],
        "introduction": (
            "将用户需求拆解为可提交的实现计划：研究代码上下文 → 按 commit 粒度拆分步骤 → "
            "写入 plans/{feature}/plan.md。与 implement skill 配对，实现 Plan/Implement 两阶段自治。"
        ),
        "useCases": [
            {
                "title": "复杂功能多 commit 交付",
                "scenario": "需要在单个 PR 内分 5 个可独立验证的 commit 完成支付模块。",
                "prompt": "plan the payment integration feature",
                "expected": "生成含 Branch、Steps、Testing 字段的 plan.md，每步对应一个 commit。",
            },
        ],
    },
    {
        "slug": "create-implementation-plan",
        "sourceId": "awesome-copilot",
        "displayName": "Create Implementation Plan",
        "rank": 5,
        "sdePhase": "规划拆解",
        "category": "实现规划",
        "featured": True,
        "tags": ["spec", "refactor", "upgrade"],
        "introduction": (
            "为新建功能、重构或依赖升级创建正式实现计划文件，明确范围、风险与验证方式。"
            "属于 project-planning 插件核心 skill，适合企业级规范流程。"
        ),
        "useCases": [
            {
                "title": "框架大版本升级",
                "scenario": "React 17 → 19 升级，需要分阶段计划。",
                "prompt": "create an implementation plan for upgrading React to 19",
                "expected": "输出分阶段计划，含影响文件、回滚策略与测试检查点。",
            },
        ],
    },
    {
        "slug": "test-driven-development",
        "sourceId": "cursor-superpowers",
        "displayName": "Test-Driven Development",
        "rank": 6,
        "sdePhase": "实现",
        "category": "测试驱动",
        "featured": True,
        "tags": ["TDD", "red-green-refactor", "superpowers"],
        "introduction": (
            "强制执行红-绿-重构循环：先写失败测试 → 最小实现通过 → 重构。"
            "对抗 AI 编码最常见的「看起来对、实际错」问题，是 Cursor Superpowers 生态的核心纪律 skill。"
        ),
        "useCases": [
            {
                "title": "新 API 端点开发",
                "scenario": "需要为 /api/users 添加分页查询接口。",
                "prompt": "implement paginated user list endpoint using TDD",
                "expected": "先输出失败测试，再写最小实现，最后重构并确认全部测试通过。",
            },
        ],
    },
    {
        "slug": "eval-driven-dev",
        "sourceId": "awesome-copilot",
        "displayName": "Eval-Driven Development",
        "rank": 7,
        "sdePhase": "测试评估",
        "category": "LLM 应用 QA",
        "featured": True,
        "tags": ["eval", "LLM", "pixie", "golden-dataset"],
        "introduction": (
            "面向 Python LLM 应用的评估驱动开发：定义 eval 标准 → 插桩 → 构建 golden dataset → "
            "运行 pixie test → 分析结果。解决传统单元测试无法覆盖的非确定性 AI 输出质量问题。"
        ),
        "useCases": [
            {
                "title": "RAG 问答质量回归",
                "scenario": "知识库问答机器人回答偶尔幻觉，需要可重复评估。",
                "prompt": "set up evals for our RAG chatbot to catch hallucinations",
                "expected": "建立 eval criteria、测试数据集与 LLM-as-judge 评分流水线。",
            },
        ],
    },
    {
        "slug": "security-review",
        "sourceId": "awesome-copilot",
        "displayName": "Security Review",
        "rank": 8,
        "sdePhase": "安全审查",
        "category": "应用安全",
        "featured": True,
        "tags": ["SAST", "OWASP", "secrets", "CVE"],
        "introduction": (
            "AI 驱动的代码安全审查：追踪数据流、审计依赖 CVE、扫描硬编码密钥，"
            "按 CRITICAL/HIGH/MEDIUM 分级并给出修复补丁建议。附带语言特定漏洞模式参考库。"
        ),
        "useCases": [
            {
                "title": "合并前安全门禁",
                "scenario": "PR 涉及认证模块改动，需在 merge 前做安全扫描。",
                "prompt": "run security review on src/auth/",
                "expected": "输出分级漏洞清单，每项含文件位置、类型与具体修复建议。",
            },
        ],
    },
    {
        "slug": "systematic-debugging",
        "sourceId": "cursor-superpowers",
        "displayName": "Systematic Debugging",
        "rank": 9,
        "sdePhase": "调试排错",
        "category": "问题定位",
        "featured": True,
        "tags": ["debug", "root-cause", "superpowers"],
        "introduction": (
            "系统化调试流程：先复现 → 收集 runtime 证据 → 定位根因 → 再修复。"
            "禁止无证据的猜测性修复，专门针对 AI Agent 常见的「试一把」式 debug 坏习惯。"
        ),
        "useCases": [
            {
                "title": "间歇性 500 错误",
                "scenario": "生产环境 API 偶发 500，日志信息不足。",
                "prompt": "debug intermittent 500 errors on /api/checkout",
                "expected": "要求复现步骤与日志证据，形成假设树并逐一验证后再改代码。",
            },
        ],
    },
    {
        "slug": "doublecheck",
        "sourceId": "awesome-copilot",
        "displayName": "Doublecheck",
        "rank": 10,
        "sdePhase": "输出验证",
        "category": "防幻觉",
        "featured": True,
        "tags": ["verification", "hallucination", "fact-check"],
        "introduction": (
            "三层验证流水线：提取可验证声明 → 网络搜索佐证/反驳 → 对抗性审查幻觉模式。"
            "输出带来源链接的验证报告，适合架构决策、合规分析等高风险 AI 输出场景。"
        ),
        "useCases": [
            {
                "title": "技术选型报告核验",
                "scenario": "Agent 生成数据库选型对比，需确认引用数据真实。",
                "prompt": "doublecheck the database comparison you just wrote",
                "expected": "逐条标注 VERIFIED / PLAUSIBLE / FABRICATION RISK 及来源 URL。",
            },
        ],
    },
    {
        "slug": "harness-engineering",
        "sourceId": "awesome-copilot",
        "displayName": "Harness Engineering",
        "rank": 11,
        "sdePhase": "持续治理",
        "category": "Agent 治理",
        "featured": True,
        "tags": ["governance", "drift-check", "regression"],
        "introduction": (
            "将 Agent 反复犯的错误沉淀为仓库级治理资产：instructions、约束、反馈回路、"
            "失败记忆、评估与漂移检查。Harness = Instructions + Constraints + Feedback + "
            "Memory + Evaluation + Governance。"
        ),
        "useCases": [
            {
                "title": "Agent 反复犯同一错误",
                "scenario": "Copilot 总在错误目录创建测试文件。",
                "prompt": "improve the agent harness so tests always go in tests/",
                "expected": "更新 instructions、添加 drift 检查或 CI 规则防止复发。",
            },
        ],
    },
    {
        "slug": "ai-team-orchestration",
        "sourceId": "awesome-copilot",
        "displayName": "AI Team Orchestration",
        "rank": 12,
        "sdePhase": "多 Agent 协作",
        "category": "团队编排",
        "featured": True,
        "tags": ["multi-agent", "sprint", "parallel"],
        "introduction": (
            "启动多 Agent AI 开发团队：定义 Producer/Dev/QA 角色、编写 sprint 计划、"
            "生成带 distinct voices 的 brainstorm prompt，支持并行开发与跨会话上下文延续。"
        ),
        "useCases": [
            {
                "title": "Greenfield 项目启动",
                "scenario": "从零开始用多个 Agent 并行开发 Web 应用。",
                "prompt": "bootstrap an AI dev team for a new todo app",
                "expected": "输出 project brief、sprint plan 与角色分工模板。",
            },
        ],
    },
    {
        "slug": "verification-before-completion",
        "sourceId": "cursor-superpowers",
        "displayName": "Verification Before Completion",
        "rank": 13,
        "sdePhase": "输出验证",
        "category": "完成前验证",
        "featured": False,
        "tags": ["verification", "evidence", "superpowers"],
        "introduction": (
            "在声称任务完成、测试通过或 bug 已修复之前，必须运行验证命令并确认输出。"
            "Evidence before assertions — 防止 AI 未跑测试就宣布「已修复」。"
        ),
        "useCases": [
            {
                "title": "修复后确认",
                "scenario": "Agent 声称修复了 lint 错误。",
                "prompt": "fix the lint errors and verify",
                "expected": "实际运行 linter，展示通过输出后才标记完成。",
            },
        ],
    },
    {
        "slug": "agentic-eval",
        "sourceId": "awesome-copilot",
        "displayName": "Agentic Eval",
        "rank": 14,
        "sdePhase": "测试评估",
        "category": "Agent 质量",
        "featured": False,
        "tags": ["self-critique", "reflection", "rubric"],
        "introduction": (
            "Agent 输出自我评估与迭代改进模式：Generate → Evaluate → Critique → Refine 循环，"
            "支持 rubric 评分与 LLM-as-judge，适合质量敏感的分析与代码生成任务。"
        ),
        "useCases": [
            {
                "title": "报告质量提升",
                "scenario": "自动生成的架构报告需要二次润色达到发布标准。",
                "prompt": "generate architecture report with self-critique loop",
                "expected": "首轮草稿后经自评迭代，按 rubric 打分直至达标。",
            },
        ],
    },
    {
        "slug": "context-map",
        "sourceId": "awesome-copilot",
        "displayName": "Context Map",
        "rank": 15,
        "sdePhase": "代码理解",
        "category": "上下文管理",
        "featured": False,
        "tags": ["context", "refactor", "impact"],
        "introduction": (
            "在动手改代码前，生成与任务相关的文件地图，明确影响范围与依赖关系。"
            "属于 context-engineering 插件，最大化 Copilot 上下文效率。"
        ),
        "useCases": [
            {
                "title": "大重构前摸底",
                "scenario": "重命名核心模块前需弄清所有引用点。",
                "prompt": "map all files relevant to renaming AuthService",
                "expected": "列出直接/间接相关文件及修改优先级。",
            },
        ],
    },
]


def fetch_url(url, timeout=20):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
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


def fetch_skill_description(repo, skills_path, slug):
    for branch in ("main", "master"):
        url = "https://raw.githubusercontent.com/{}/{}/{}/{}/SKILL.md".format(
            repo, branch, skills_path, slug
        )
        content = fetch_url(url)
        if content:
            meta = parse_frontmatter(content)
            desc = meta.get("description", "")
            if desc.startswith(">"):
                desc = desc[1:].strip()
            base_url = "https://github.com/{}/tree/{}/{}/{}".format(
                repo, branch, skills_path, slug
            )
            return desc, base_url
    return "", ""


def discover_repo_skills(repo, skills_path):
    api_url = "https://api.github.com/repos/{}/contents/{}".format(repo, skills_path)
    content = fetch_url(api_url)
    if not content:
        return []
    try:
        entries = json.loads(content)
    except ValueError:
        return []
    return sorted(
        item["name"]
        for item in entries
        if item.get("type") == "dir" and not item["name"].startswith(".")
    )


def build_skill_record(curated, source, remote_desc, repo_base_url):
    slug = curated["slug"]
    install = source["installPrefix"]
    if source["id"] == "awesome-copilot":
        install_cmd = "{} {}".format(install, slug)
    else:
        install_cmd = install

    source_url = repo_base_url or "https://github.com/{}/tree/main/{}/{}".format(
        source["repo"], source["skillsPath"], slug
    )

    description = remote_desc or curated.get("description", "")

    return {
        "id": "skill-{:03d}".format(curated["rank"]),
        "slug": slug,
        "name": slug,
        "displayName": curated["displayName"],
        "platform": source["platform"],
        "ecosystem": source["id"],
        "category": curated["category"],
        "sdePhase": curated["sdePhase"],
        "rank": curated["rank"],
        "featured": curated.get("featured", False),
        "description": description,
        "introduction": curated["introduction"],
        "useCases": curated["useCases"],
        "installCommand": install_cmd,
        "sourceUrl": source_url,
        "docsUrl": source.get("docsUrl", ""),
        "tags": curated.get("tags", []),
        "triggers": curated.get("triggers", []),
        "remoteSynced": bool(remote_desc),
    }


def collect_skills(dry_run=False):
    source_by_id = {s["id"]: s for s in SOURCES}
    skills = []
    discovery_stats = {}

    print("采集业界 Top Agent Skills...")
    for curated in CURATED_SKILLS:
        source = source_by_id.get(curated["sourceId"])
        if not source:
            print("  [WARN] 未知来源: {}".format(curated["sourceId"]), file=sys.stderr)
            continue

        print("  → {} ({})".format(curated["slug"], source["platform"]))
        remote_desc, repo_base = fetch_skill_description(
            source["repo"], source["skillsPath"], curated["slug"]
        )
        record = build_skill_record(curated, source, remote_desc, repo_base)
        skills.append(record)

    for source in SOURCES:
        discovered = discover_repo_skills(source["repo"], source["skillsPath"])
        discovery_stats[source["id"]] = {
            "platform": source["platform"],
            "repo": source["repo"],
            "totalInRepo": len(discovered),
            "curatedCount": sum(1 for s in skills if s["ecosystem"] == source["id"]),
        }
        print(
            "  [DISCOVER] {} — 仓库共 {} 个 skill，策展收录 {} 个".format(
                source["platform"],
                len(discovered),
                discovery_stats[source["id"]]["curatedCount"],
            )
        )

    skills.sort(key=lambda s: s["rank"])

    phases = sorted({s["sdePhase"] for s in skills})
    platforms = sorted({s["platform"] for s in skills})
    categories = sorted({s["category"] for s in skills})

    payload = {
        "meta": {
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "totalCount": len(skills),
            "featuredCount": sum(1 for s in skills if s["featured"]),
            "sources": [s["id"] for s in SOURCES],
            "discovery": discovery_stats,
            "note": (
                "策展 Top Skills 围绕 AI 软件工程全链路；"
                "description 字段从远程 SKILL.md 自动同步，introduction/useCases 为门户策展内容。"
            ),
        },
        "sdePhases": phases,
        "platforms": platforms,
        "categories": categories,
        "skills": skills,
    }

    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:3000], "...")
        print("\n[DRY-RUN] 共 {} 条 skill，未写入文件。".format(len(skills)))
        return payload

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(SKILLS_PATH, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("\n已写入 {}（{} 条 skill）".format(SKILLS_PATH, len(skills)))
    return payload


def print_sources():
    print("监控来源:")
    for source in SOURCES:
        print("  - {} ({})".format(source["platform"], source["repo"]))
        print("    路径: {}/{}".format(source["repo"], source["skillsPath"]))
        print("    文档: {}".format(source["docsUrl"]))


def main():
    parser = argparse.ArgumentParser(description="采集业界 Top Agent Skills")
    parser.add_argument("--dry-run", action="store_true", help="预览，不写入文件")
    parser.add_argument("--sources", action="store_true", help="列出监控来源")
    args = parser.parse_args()

    if args.sources:
        print_sources()
        return 0

    collect_skills(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
