<div align="center">

# 🗺️ Weekend Planner · 周末活动规划 Agent

**美团 AI Hackathon 2026 参赛作品**

一个「人在回路」的周末出行规划智能体：你说需求，AI 结合**真实地理 / 天气 / POI 数据**生成可落地的活动方案，
在地图上可视化，并在你确认后自动完成「预订」。

LangGraph Plan-and-Execute · 确定性空间分析引擎 · DeepSeek 推理 · 高德地图可视化

</div>

---

## ✨ 功能特性

- **🧠 意图理解**：自然语言描述需求（"周末带娃在望京附近玩半天，要有公园和好吃的"），自动解析场景、出发点、偏好。
- **📍 确定性空间分析**：不靠 LLM 拍脑袋，而是用真实数据计算可达范围与候选场所——
  - 基于 **OpenRouteService** 等时圈（isochrone）算出"X 分钟可达"的真实多边形；
  - 用 **高德地图 POI** 检索候选场所，**Shapely 点在多边形内**判定过滤；
  - **和风天气**接入，雨天自动倾向室内活动；
  - 暴力 **TSP** 求解多点最优游览顺序。
- **✍️ LLM 叙事编排**：DeepSeek（思考模式）从候选集中挑选并串成有温度的方案文案。
- **🙋 人在回路（Human-in-the-loop）**：方案先呈现给你审阅，**你点确认后**才进入执行，基于 LangGraph `interrupt` 实现。
- **🤖 自动执行**：确认后调用预订 / 库存 / 配送等工具完成闭环，并生成可分享卡片。
- **🗺️ 实时地图可视化**：高德地图实时绘制家的位置、等时圈、候选场所、最终路线与活动点。
- **⚡ SSE 流式体验**：规划全过程（思考 / 调用工具 / 出结果）通过 Server-Sent Events 实时推送到前端。

---

## 🏗️ 系统架构

```
┌─────────────────────────────┐         SSE 流式         ┌──────────────────────────────────┐
│   前端  Next.js 16 + React   │ ◀──────────────────────  │       后端  FastAPI + LangGraph      │
│                             │   /api/plan/create        │                                    │
│  • 聊天交互 (useChat)        │   /api/plan/approve       │  ┌──────────────────────────────┐  │
│  • 高德地图可视化 (AMap)      │  ──────────────────────▶  │  │   Plan-and-Execute 状态图       │  │
│  • 方案卡片 / 审批           │                           │  └──────────────────────────────┘  │
└─────────────────────────────┘                           │                │                   │
                                                          │     ┌──────────┴───────────┐        │
                                                          │     ▼                      ▼        │
                                            ┌─────────────────────────┐   ┌──────────────────┐  │
                                            │  确定性空间分析引擎        │   │   DeepSeek LLM    │  │
                                            │  (services/spatial.py)   │   │   (叙事 / 编排)    │  │
                                            └─────────────────────────┘   └──────────────────┘  │
                                                          │                                      │
                                            外部 API ▼  高德 POI · ORS 等时圈/路径 · 和风天气          │
                                            └──────────────────────────────────────────────────┘
```

### 🧩 Agent 工作流（LangGraph 状态图）

```
parse_intent          解析自然语言 → 场景 / 出发点 / 偏好
      │
      ▼
spatial_analysis      ❶ ORS 等时圈  ❷ 高德 POI 检索  ❸ Shapely 可达过滤
（无 LLM，纯确定性）     ❹ 和风天气  ❺ 暴力 TSP 排序  → 候选场所 + 路线
      │
      ▼
select_and_narrate    DeepSeek 从候选集挑选并生成方案文案
      │
      ▼
present_plan ──────▶  ⏸ interrupt：呈现方案，等待用户确认 ───┐
      │                                                  │ 用户拒绝 → reset
      ▼ 用户确认 (Command resume=True)                      │
execute_steps         调用预订 / 库存 / 配送工具完成闭环        │
      │                                                  │
      ▼                                                  │
generate_share_card   生成可分享卡片  ◀────────────────────┘
```

---

## 🛠️ 技术栈

| 层 | 技术 |
|---|---|
| **后端框架** | FastAPI · Uvicorn · `sse-starlette`（SSE 流式） |
| **Agent 编排** | LangGraph 1.0（Plan-and-Execute + `interrupt` 人在回路） |
| **LLM** | DeepSeek · 通义千问 Qwen · Google Gemini · OpenAI（可插拔；默认 Qwen，fallback 优先级 Qwen → Gemini → DeepSeek → OpenAI，仅使用已配置 Key 的 provider） |
| **空间计算** | Shapely（点在多边形内）· 暴力 TSP 路径优化 |
| **外部数据** | 高德地图 POI · OpenRouteService 等时圈/路径 · 和风天气 |
| **日志 / 校验** | structlog · Pydantic v2 / pydantic-settings |
| **前端框架** | Next.js 16.2.6（Turbopack）· React 19 · TypeScript 5 |
| **样式 / 组件** | Tailwind CSS 4 · lucide-react |
| **地图** | 高德地图 JS API（`@uiw/react-amap` + 原生 loader） |
| **包管理** | 后端 `uv` · 前端 `npm` |

---

## 📁 目录结构

```
.
├── backend/                    # FastAPI + LangGraph 后端
│   ├── app/
│   │   ├── main.py             # FastAPI 应用入口 / CORS
│   │   ├── config.py           # pydantic-settings（读取 .env）
│   │   ├── api/routes.py       # /api/health · /api/plan/create · /api/plan/approve（SSE）
│   │   ├── agents/orchestrator.py   # LangGraph 状态图（核心编排）
│   │   ├── services/spatial.py      # 确定性空间分析引擎
│   │   ├── llm/                # provider 选择 / fallback / prompts
│   │   ├── tools/              # isochrone · poi_search · routing · weather · booking · availability · delivery
│   │   └── models/            # schemas（API）· state（图状态）· domain
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example           # ← 复制为 .env 填入真实 Key
│
├── frontend/                   # Next.js 16 前端
│   ├── app/page.tsx           # 主页面（左聊天 / 右地图）
│   ├── components/            # chat · plan · map(MapView) · ui
│   ├── hooks/useChat.ts       # 聊天状态机 + SSE 消费
│   ├── lib/api.ts             # SSE 解析（兼容 CRLF 分帧）
│   └── .env.example           # ← 复制为 .env.local 填入高德 JS Key
│
└── README.md
```

---

## 🚀 快速开始

### 前置要求

- **Python ≥ 3.11**（推荐 3.13）+ [`uv`](https://github.com/astral-sh/uv)
- **Node.js ≥ 20** + npm
- 各外部服务的 API Key（见下方[环境变量](#环境变量)）

### 1. 克隆

```bash
git clone https://github.com/Epawse/weekend-planner.git
cd weekend-planner
```

### 2. 启动后端（:8000）

```bash
cd backend
uv venv --python 3.13 .venv
VIRTUAL_ENV=$(pwd)/.venv uv pip install -e ".[dev]"

cp .env.example .env        # 填入真实 API Key
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

健康检查：`curl http://localhost:8000/api/health`

### 3. 启动前端（:3000）

```bash
cd frontend
npm install

cp .env.example .env.local  # 填入高德 JS API Key
npm run dev
```

打开 <http://localhost:3000>。

### 环境变量

**`backend/.env`**（复制自 `backend/.env.example`）：

| 变量 | 说明 |
|---|---|
| `DASHSCOPE_API_KEY` | 通义千问 Qwen（默认 LLM） |
| `DEEPSEEK_API_KEY` | DeepSeek（可选） |
| `GEMINI_API_KEY` | Google Gemini（可选，OpenAI 兼容端点） |
| `OPENAI_API_KEY` | OpenAI（可选） |
| `AMAP_API_KEY` | 高德 **Web 服务** Key（POI 检索） |
| `ORS_API_KEY` | OpenRouteService（等时圈 / 路径） |
| `QWEATHER_API_KEY` | 和风天气 |
| `THINKING_ENABLED` / `THINKING_EFFORT` | 思考模式开关 / 强度 |
| `DEFAULT_LLM_PROVIDER` | 默认 LLM 提供方（默认 `qwen`） |

> LLM fallback 优先级为 **Qwen → Gemini → DeepSeek → OpenAI**，仅使用已配置 Key 的 provider。
> 思考模式：DeepSeek 走 `thinking` flag，Gemini 3.x 则映射到 `reasoning_effort`（且无法完全关闭，思考会占用 `max_tokens` 预算）。

**`frontend/.env.local`**（复制自 `frontend/.env.example`）：

| 变量 | 说明 |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | 后端地址，默认 `http://localhost:8000` |
| `NEXT_PUBLIC_AMAP_KEY` | 高德 **JS API** Key（地图渲染，与后端 Web 服务 Key 不同） |

> ⚠️ 高德的 **JS API Key**（前端地图）和 **Web 服务 Key**（后端 POI）是两套不同的 Key，请分别申请。

---

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/health` | 健康检查 + 各 LLM provider 可用性 |
| `POST` | `/api/plan/create` | 启动规划，**SSE** 流式推送思考 / 工具 / 方案事件，到 `present_plan` 处中断等待确认 |
| `POST` | `/api/plan/approve` | 携带 `session_id` + `approved` 恢复图执行，**SSE** 流式推送执行进度 |

SSE 事件类型：`session` · `thinking` · `tool_calling` · `tool_result` · `node_complete` · `plan_ready` · `interrupted` · `step_start` · `step_complete` · `done` · `error`。

---

## 🧩 WSL2 / 跨平台说明

本项目可能在 macOS 与 Windows/WSL 之间迁移，已知注意事项：

- **跨平台依赖需重建**：从 macOS 拷贝来的 `backend/.venv`（含平台相关解释器）和 `frontend/node_modules`（含 `*-darwin-arm64` 原生包）在 Linux/WSL 上不可用，须按上面步骤**重新安装**。
- **WSL2 NAT 网络**：若 Windows 浏览器访问不到 WSL 内服务，前端需绑定 IPv4 通配地址，否则 `localhostForwarding` 不转发：
  ```bash
  npm run dev -- -H 0.0.0.0
  ```
- **行尾 / 权限**：仓库使用 `core.autocrlf=input`；若 `git status` 出现大量「仅权限位（mode）变化」，执行 `git config core.fileMode false` 即可消除（已是跨平台搬运噪声，非真实改动）。
- `*:Zone.Identifier`（Windows 隔离标记）与 `.DS_Store`（macOS）已在 `.gitignore` 中忽略。

---

## 🧪 开发

```bash
# 后端
cd backend
.venv/bin/ruff check app          # Lint
.venv/bin/pytest                  # 测试

# 前端
cd frontend
npm run lint
npm run build
```

---

## 📄 License

本项目为美团 AI Hackathon 2026 参赛 Demo，仅供学习与演示。
