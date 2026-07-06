---
name: trellis-prototype
description: "Use when a new project or a major UI direction change needs visual direction before planning — runs the prototype gate: read atlas references, produce ≥3 divergent style prototypes, iterate with the user, freeze one into DECISION.md before Phase 1 planning starts."
---

# Prototype Gate（Phase 0.5 原型门）

在 planning 之前把「长什么样」定下来：产 ≥3 个**分歧**风格原型 → 用户挑选/混合/否决 →
迭代 → 冻结一稿 → 冻结稿成为 Phase 1 的设计输入。目标是把视觉方向的发散收敛在写产品代
码之前，而不是让第一版实现顺便决定风格。

## 适用边界

- ✅ 新项目 bootstrap 后、首个 planning 前（greenfield UI）
- ✅ 既有项目的大型 UI 方向变更（换设计语言级别）
- ❌ 纯后端任务；❌ 设计体系内的增量 UI 改动（走项目既有 spec/design-system）

## 流程

### 1. 取参考（先读再画）

- `~/projects/trellis-workspace/my-trellis-marketplace/atlas/frontend-taste/`（展柜与引擎现状）
- `~/projects/trellis-workspace/my-trellis-marketplace/atlas/anti-patterns/`（自检行）
- 用户点名的参考物（截图/链接/竞品）

### 2. 产 ≥3 个分歧原型

- **分歧**指风格方向不同（如极简克制 / 数据密集工作台 / 品牌表现型），不是同一风格的三个
  微调；每个原型一句定位写在文件头注释。
- 载体：**单文件自包含 HTML**（内联 CSS/JS、无外部依赖、双击可开）；除非项目已定栈且用户
  要求栈内载体。
- 引擎解析（发散期）：① 仓内 `huashu-design`（本 profile vendored，双镜像故 Codex 亦可见；
  40 风格库+顾问模式，默认主力；来源与 refresh 见其 IMPORTED.md）→ ② 不可用时降级为读
  atlas frontend-taste 参考自由发挥，产物头注明 engine=none。
- 人工 lane：也可在 Claude Design（官方 GUI）自行探索，导出的独立 HTML 放入 `prototypes/`
  即参与挑选——冻结点与流程不变。
- 落盘：`prototypes/<MM-DD>-<style-slug>.html`，全部可运行——不给半成品。

### 3. 呈现与迭代

一次性并排交付全部原型 + 每个一句定位，让用户挑选/混合/否决。按反馈出新变体或修选中稿；
每轮产物同样全量可运行。不追问偏好细节——用变体回答问题。

### 4. 冻结

用户拍板后写 `prototypes/DECISION.md`：选中稿、被否原型的一句否决理由、从选中稿提炼的风
格要点（配色/字体/密度/组件语言），以及一行实现期纪律：**greenfield UI 实现载入仓内
`frontend-design`（官方 skill vendored，单方向收敛：signature element 唯一、token 两阶段、反默认风格）**。
冻结稿 + DECISION.md 即 Phase 1 PRD 的设计输入（复杂任务的 design.md 引用它）。

## 硬规则

- 原型期零后端、零构建、零外部依赖——纯静态。
- **未冻结不进 planning gate**：greenfield UI 项目的 `task.py start` 前提是 DECISION.md 存在。
- 交付前对照 anti-patterns 的 AI-slop 特征行自检（随机抽象、半成品、能跑就行）。
- 原型是探索产物，冻结后旧原型保留在 prototypes/ 供回溯，不删。
