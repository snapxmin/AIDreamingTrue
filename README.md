# AI Coding 信息平台（MVP）

一个面向开发者、技术管理者与创业者的 AI Coding 资讯平台原型，用于快速查看近期重要事件（产品、商业、用户故事、技术突破）。

## 已实现内容

- 首页信息流（今日/本周重点）
- 分类导航（产品、商业、用户故事、工具生态、投融资）
- 专题筛选（Agent、IDE、代码评审、自动化测试）
- 事件详情（摘要、来源、影响分析、为什么重要）
- 搜索与多维筛选（关键词、时间窗口、类型、公司、热度）
- 趋势榜单（按热度与增长排序）
- **Skill 库**（业界 Top Agent Skills 策展、详细介绍、使用案例）
- 竞品演进历史时间线
- 内容生产链路、质量机制、分阶段路线图展示

## 本地使用

这是一个纯静态 MVP，无需安装依赖。  
直接打开以下文件即可：

- `./index.html` — 门户首页
- `./skills.html` — Skill 库
- `./evolution.html` — 竞品演进历史

## 目录

- `./index.html`：门户首页
- `./skills.html`：Skill 库页面
- `./skills.js` / `./skills.css`：Skill 库交互与样式
- `./evolution.html`：竞品演进页面
- `./styles.css`：全局样式
- `./app.js`：首页交互逻辑
- `./data/events.json`：竞品事件数据（25 条真实动态）
- `./data/skills.json`：策展 Top Agent Skills（自动采集）
- `./data/competitors.json`：竞品监控列表（7 家）
- `./scripts/collect_events.py`：事件数据采集脚本
- `./scripts/collect_skills.py`：Skill 数据采集脚本

## 数据来源

事件数据来自以下公开来源的人工整理与脚本辅助采集：

| 类型 | 来源 |
|------|------|
| 产品 Release Notes | [Cursor Changelog](https://cursor.com/changelog)、[Claude Code Releases](https://github.com/anthropics/claude-code/releases)、[GitHub Changelog](https://github.blog/changelog/)、[Devin Blog](https://devin.ai/blog)、[Replit Blog](https://replit.com/blog) |
| 投融资/商业 | TechCrunch、Bloomberg、SiliconANGLE |
| 用户论坛反馈 | Hacker News 讨论帖、社区对比评测 |
| 行业分析 | Analysis Atlas、社区开发者报告 |

### 监控竞品

Cursor、GitHub Copilot、Devin Desktop (Cognition)、Claude Code (Anthropic)、Replit Agent、Google Jules、AWS Kiro

### 更新数据

```bash
# 查看监控来源
python3 scripts/collect_events.py --sources

# 抓取新数据并合并（支持 GitHub Releases、RSS）
python3 scripts/collect_events.py

# 预览模式，不写入文件
python3 scripts/collect_events.py --dry-run
```

### Skill 库数据

Skill 库策展收录 GitHub Copilot（awesome-copilot）与 Cursor（superpowers）等生态的 Top Skills，并自动同步远程 `SKILL.md` 描述。

```bash
# 查看监控来源
python3 scripts/collect_skills.py --sources

# 抓取 Skill 元数据并写入 data/skills.json
python3 scripts/collect_skills.py

# 预览模式
python3 scripts/collect_skills.py --dry-run
```

监控来源：

| 平台 | 仓库 | 说明 |
|------|------|------|
| GitHub Copilot | [github/awesome-copilot](https://github.com/github/awesome-copilot) | 365+ community skills |
| Cursor | [obra/superpowers](https://github.com/obra/superpowers) | Superpowers 工程纪律 skills |

## 部署到 GitHub Pages

仓库已添加 GitHub Pages 自动部署工作流：

- 推送部署：`./.github/workflows/deploy-pages.yml`（推送到 `main` 时触发）
- 定时采集发布：`./.github/workflows/daily-collect-and-publish.yml`（每天 08:30 北京时间：事件 + Skills 采集并发布）
- Skill 专项采集：`./.github/workflows/collect-skills-and-deploy.yml`（每周一 09:00 北京时间，可手动触发）

### 定时任务

每天 **08:30（北京时间 UTC+8）** 自动执行：

1. 运行 `scripts/collect_events.py` 抓取竞品最新动态
2. 运行 `scripts/collect_skills.py` 同步 Skill 远程描述
3. 将更新写入 `data/events.json` / `data/skills.json` 并提交到 `main`
4. 部署更新后的门户到 GitHub Pages

每周一 **09:00（北京时间）** 额外执行 Skill 专项采集工作流（可手动触发）。

也可在 GitHub Actions 页面手动触发 **Daily collect and publish** 工作流。

启用方式：

1. 进入 GitHub 仓库 **Settings > Pages**
2. 在 **Build and deployment** 中将 **Source** 设为 **GitHub Actions**
3. 推送到 `main` 分支后，等待 `Deploy static site to Pages` 工作流完成

部署完成后，站点会发布到 GitHub Pages 提供的公开地址。
