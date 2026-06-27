# AI Coding 信息平台（MVP）

一个面向开发者、技术管理者与创业者的 AI Coding 资讯平台原型，用于快速查看近期重要事件（产品、商业、用户故事、技术突破）。

## 已实现内容

- 首页信息流（今日/本周重点）
- 分类导航（产品、商业、用户故事、工具生态、投融资）
- 专题筛选（Agent、IDE、代码评审、自动化测试）
- 事件详情（摘要、来源、影响分析、为什么重要）
- 搜索与多维筛选（关键词、时间窗口、类型、公司、热度）
- 趋势榜单（按热度与增长排序）
- 内容生产链路、质量机制、分阶段路线图展示

## 本地使用

这是一个纯静态 MVP，无需安装依赖。  
直接打开以下文件即可：

- `./index.html`

## 目录

- `./index.html`：页面结构
- `./styles.css`：样式
- `./app.js`：交互逻辑
- `./data/events.json`：示例事件数据

## 部署到 GitHub Pages

仓库已添加 GitHub Pages 自动部署工作流：

- 工作流文件：`./.github/workflows/deploy-pages.yml`
- 触发方式：推送到 `main` 分支，或手动运行工作流

启用方式：

1. 进入 GitHub 仓库 **Settings > Pages**
2. 在 **Build and deployment** 中将 **Source** 设为 **GitHub Actions**
3. 推送到 `main` 分支后，等待 `Deploy static site to Pages` 工作流完成

部署完成后，站点会发布到 GitHub Pages 提供的公开地址。
