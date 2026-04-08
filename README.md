# Deep Research MVP

这个仓库是对 `lib/deep-research` 主研究链路的重写版，技术栈改为 `FastAPI + LangGraph + Vue3`。目标不是 1:1 复刻原项目，而是先把“澄清问题 -> 生成研究计划 -> 搜索 -> 汇总最终报告”的核心体验落成一个可运行的 MVP。

## 当前结论

截至 `2026-04-01`，当前版本已经实现并验证了参考项目的主要研究主链路：

- 支持先生成澄清问题，再启动研究任务。
- 支持任务持久化、SSE 流式事件、任务历史列表和刷新后恢复最近一次任务。
- 支持 `OpenAI / Google / Anthropic` 三类 LLM 抽象。
- 支持 `Tavily / SearxNG` 两类搜索抽象。
- 支持研究计划、推理日志、最终 Markdown 报告、独立报告页和引用来源展示。
- 支持多轮 `re-research` 与可部署的 MCP Server。

但它仍然只是 `lib/deep-research` 的缩减版，不具备原项目全部能力。最重要的差异是：没有本地知识库、Artifact 编辑器、知识图谱、PWA 和阶段性局部再研究能力。

## 与参考项目的功能对照

| 功能 | `lib/deep-research` | 当前项目 |
| --- | --- | --- |
| 澄清问题后再研究 | 已实现 | 已实现 |
| 研究计划生成 | 已实现 | 已实现 |
| 搜索任务拆分 | 已实现 | 已实现 |
| 最终 Markdown 报告 | 已实现 | 已实现 |
| SSE 流式事件 | 已实现 | 已实现 |
| 任务结果持久化 | 浏览器本地持久化/服务模式 | PostgreSQL 持久化 |
| 刷新后恢复任务 | 已实现 | 已实现，恢复最近一次任务 |
| 多 LLM Provider | 很丰富 | 已实现，但只支持 `openai/google/anthropic` |
| 多搜索 Provider | 很丰富 | 已实现，但只支持 `tavily/searxng` |
| 阶段性继续研究 / re-research | 已实现 | 已实现，支持基于已完成任务发起下一轮研究 |
| 研究历史列表页 | 已实现 | 已实现，支持从后端任务列表加载历史 |
| 本地知识库 / 文件上传 | 已实现 | 未实现 |
| Artifact 编辑器 | 已实现 | 未实现 |
| 知识图谱 | 已实现 | 未实现 |
| MCP Server | 已实现 | 已实现，支持 `streamable-http` 和 `sse` transport |
| PWA | 已实现 | 未实现 |
| 多 Key payload | 已实现 | 未实现 |
| 多语言 UI | 已实现 | 部分实现，仅基础中英文参数切换 |

如果你的目标是“覆盖参考项目的主要研究能力”，当前版本已经达到。
如果你的目标是“产品功能接近原版完整体验”，当前版本还差一段距离。

## 项目结构

- `backend/`
  `FastAPI API`、`LangGraph` 研究流程、`SQLAlchemy/Alembic`、`PostgreSQL` 持久化、SSE 流。
- `frontend/`
  `Vue3 + Vite + TypeScript + Pinia + Vue Router + Element Plus` 单页工作台。
- `lib/deep-research/`
  原始参考项目，只读对照。

## 当前实现的核心流程

后端固定使用以下研究流程：

1. `clarify_questions`
2. `build_research_brief`
3. `write_report_plan`
4. `generate_search_queries`
5. `run_search_tasks`
6. `synthesize_final_report`
7. `finalize_task`

研究执行期间会同时做两件事：

- 把事件写入 PostgreSQL，支持断线恢复和页面刷新后回放。
- 把事件发布到进程内队列，供 SSE 实时消费。

前端是单页工作台，包含：

- API Base URL 和 Bearer Token 配置
- Provider / Model / Search Provider / Language / Max Results 配置
- 历史任务侧栏
- 研究主题输入
- 澄清问题回答
- 基于历史结果继续发起下一轮 `re-research`
- 流式进度、推理日志、报告计划、最终 Markdown 报告预览、引用来源展示
- 独立报告页 `reports/:taskId`

## 运行要求

### 后端

- Python `3.11+`
- `uv`
- PostgreSQL `16+`

### 前端

- Node.js `18.18+`
- npm

`uv` 统一负责 Python 侧依赖、命令和虚拟环境。Vue3 前端仍然使用 Node 生态安装依赖，这是 `uv` 目前不能替代的部分。

## 环境变量

先复制：

```bash
cp .env.example .env
```

最重要的变量如下：

| 变量 | 说明 |
| --- | --- |
| `API_BEARER_TOKEN` | 后端 Bearer Token，除 `/health` 外所有 `/api/v1/*` 请求都要带上 |
| `DATABASE_URL` | PostgreSQL 连接串 |
| `OPENAI_API_KEY` | OpenAI 或兼容网关 API Key |
| `OPENAI_BASE_URL` | OpenAI 兼容网关地址，可选 |
| `OPENAI_MODEL_LIST` | 前端可选 OpenAI 模型列表，逗号分隔 |
| `GOOGLE_API_KEY` | Google Gemini API Key |
| `GOOGLE_MODEL_LIST` | 前端可选 Gemini 模型列表，逗号分隔 |
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `ANTHROPIC_MODEL_LIST` | 前端可选 Anthropic 模型列表，逗号分隔 |
| `TAVILY_API_KEY` | Tavily 搜索 Key |
| `SEARXNG_BASE_URL` | SearxNG 服务地址 |
| `MCP_AI_PROVIDER` | MCP 默认 AI Provider |
| `MCP_THINKING_MODEL` | MCP 默认 Thinking Model |
| `MCP_TASK_MODEL` | MCP 默认 Task Model |
| `MCP_SEARCH_PROVIDER` | MCP 默认 Search Provider |
| `MCP_LANGUAGE` | MCP 默认输出语言 |
| `MCP_MAX_RESULTS` | MCP 默认搜索结果数 |

模型列表示例：

```env
OPENAI_MODEL_LIST=gpt-5.4-mini,gpt-5.4,gpt-5
GOOGLE_MODEL_LIST=gemini-2.5-flash,gemini-2.5-pro
ANTHROPIC_MODEL_LIST=claude-3-5-sonnet-latest,claude-3-7-sonnet-latest
```

`/api/v1/providers` 会直接把这些模型列表返回给前端，所以你可以通过 `.env` 控制下拉项。

## MCP Server

当前后端支持两种 MCP transport：

- `streamable-http`：`POST /api/v1/mcp`
- `sse`：`GET /api/v1/mcp/sse`，消息发送到 `POST /api/v1/mcp/sse/messages?sessionId=...`

示例配置：

```json
{
  "mcpServers": {
    "deep-research": {
      "url": "http://127.0.0.1:8000/api/v1/mcp",
      "transportType": "streamable-http",
      "timeout": 600,
      "headers": {
        "Authorization": "Bearer change-me"
      }
    }
  }
}
```

当前暴露的工具：

- `deep-research.run`
- `deep-research.follow-up`
- `deep-research.get-task`
- `deep-research.list-tasks`
- `deep-research.clarify`

## 快速启动

### 使用 Docker Compose

```bash
docker compose up --build
```

启动后访问：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`

### 后端本地开发

```bash
cd backend
uv python install 3.11
uv venv --python 3.11
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### 前端本地开发

```bash
cd frontend
npm install
npm run dev
```

## 使用方式

1. 在顶部填入 `API Base URL` 和 `Bearer Token`。
2. 选择 `Provider`、`Thinking Model`、`Task Model`、`Search Provider`、`Language`。
3. 输入研究主题。
4. 点击“生成澄清问题”。
5. 填写补充说明后点击“启动研究”。
6. 在左侧历史区查看历史任务，在右侧查看进度、推理日志、最终报告预览和引用来源。
7. 点击“打开独立报告页”或历史中的“报告”进入单独报告视图。

如果页面刷新，前端会尝试恢复最近一次任务并重新连接 SSE。

## API

### `GET /api/v1/health`

健康检查，不需要 Bearer Token。

### `GET /api/v1/providers`

返回当前允许的 LLM Provider、模型列表和搜索 Provider。

### `POST /api/v1/research/clarify`

请求体：

```json
{
  "query": "研究主题",
  "provider": "openai",
  "thinking_model": "gpt-5.4",
  "language": "zh-CN"
}
```

响应体：

```json
{
  "questions": ["问题 1", "问题 2"]
}
```

### `POST /api/v1/research/tasks`

请求体：

```json
{
  "query": "研究主题",
  "answers": ["补充说明 1", "补充说明 2"],
  "provider": "openai",
  "thinking_model": "gpt-5.4",
  "task_model": "gpt-5",
  "search_provider": "tavily",
  "language": "zh-CN",
  "max_results": 5
}
```

响应体：

```json
{
  "task_id": "uuid",
  "status": "queued"
}
```

### `GET /api/v1/research/tasks`

返回最近的任务列表，用于前端历史记录界面。

### `GET /api/v1/research/tasks/{task_id}`

返回任务状态、当前步骤、报告计划、最终报告、来源和历史事件。

### `GET /api/v1/research/tasks/{task_id}/stream`

SSE 事件流。连接建立后会先回放数据库中的历史事件，再继续输出实时事件。

## SSE 事件语义

当前后端支持这些事件类型：

- `infor`
- `progress`
- `message`
- `reasoning`
- `error`
- `done`

其中：

- `progress.step` 可能是 `report-plan`、`serp-query`、`search-task`、`final-report`
- `progress.status` 可能是 `start` 或 `end`
- `message` 用于输出报告正文流
- `reasoning` 用于输出中间分析
- `done` 表示任务结束

## 测试

### 后端

```bash
cd backend
uv run pytest
```

### 前端

```bash
cd frontend
npm test
npm run build
npm run test:e2e
```

## 已验证的内容

截至 `2026-04-01`，已经验证：

- `uv run pytest` 通过
- `npm test` 通过
- `npm run build` 通过
- `/api/v1/health` 正常
- `/api/v1/providers` 能返回 `.env` 中配置的模型列表
- 真实 `clarify` 请求可返回澄清问题
- 真实研究任务可以从创建、搜索、汇总一直完成到 `completed`
- 完成后的 `report_plan`、`final_report`、`research_events`、`research_sources` 会落库

## 已知限制

- 这不是原项目的全量复刻，只覆盖 Deep Research 主链路。
- 当前搜索阶段为了避免异步数据库会话冲突，采用顺序执行，不是并发搜索。
- 当前前端已补上历史侧栏和独立报告页，但仍没有 Artifact 编辑器和知识图谱视图。
- 不支持文件上传、本地知识库、MCP、PWA、多 Key 轮转。
- 如果你接的是 OpenAI 兼容网关，最终报告阶段的耗时会高度依赖该网关对长文本生成的稳定性。
- 后端建议统一使用 Python `3.11+`，避免 Python 3.9 带来的 Google 依赖 EOL warning。
