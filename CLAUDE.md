# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 项目概述

VibeHub 是一个 AI 驱动的全栈应用生成平台。用户用自然语言描述需求，系统按阶段生成代码、在 E2B 云沙箱中执行并提供实时预览。会话完整持久化，支持增量迭代。

## 架构

双进程应用：React SPA 前端 + FastAPI 后端，通过 REST（会话 CRUD）和 WebSocket（实时生成事件）通信。

**AI 流水线（LangGraph 状态机）：**
`blueprint_generation → phase_implementation → pre_validation（最多 2 次重试）→ sandbox_execution ↔ sandbox_fix（最多 3 次重试）→ finalizing`

> **注意：** `pre_validation` 节点在 2025-03-02 添加，用于在沙箱执行前捕获常见 TypeScript 错误。详见 [docs/ai-code-quality.md](docs/ai-code-quality.md) 和 [docs/ai-code-quality-plan.md](docs/ai-code-quality-plan.md)。

所有节点通过 `callback_registry`（按 `session_id` 索引）发射实时 WebSocket 事件。

**前端状态：** 无全局状态库。所有会话状态集中在 `useChat` hook 中（`messages`、`files`、`phases`、`blueprint`、`previewUrl` 等），由 WebSocket 事件驱动更新。

**数据库：** SQLite + async SQLAlchemy。表：`sessions`、`generated_files`、`phases`、`messages`。

**模板系统：** `/templates/{name}/` 提供初始代码、提示词注入文件（`prompts/usage.md`、`prompts/selection.md`）和元数据（`meta.json`）。由 `backend/services/template_service.py` 加载。

## 开发命令

### 前端（在 `frontend/` 目录下）
```bash
npm install          # 安装依赖
npm run dev          # 开发服务器 http://localhost:5173
npm run build        # 类型检查 (tsc -b) + 生产构建
npm run lint         # ESLint 检查
```

### 后端（在 `backend/` 目录下）
```bash
uv venv && uv pip install -e .    # 创建虚拟环境并安装依赖
cp .env.example .env              # 然后填写 GOOGLE_API_KEY、E2B_API_KEY
uvicorn main:app --reload --port 8000   # 开发服务器 http://localhost:8000
```

前后端需同时运行。Vite 会将 `/api` 和 `/ws` 请求代理到 `localhost:8000`。

## 关键技术细节

- **前端：** React 19、TypeScript 5.9（严格模式）、Vite 7、TailwindCSS v4（CSS 原生配置，无 `tailwind.config.js`）、react-router v7
- **后端：** Python 3.11+、FastAPI、LangGraph、Google Gemini（主力 LLM，通过 `langchain-google-genai`）、E2B 沙箱
- **路径别名：** `@/` 解析到 `frontend/src/`
- **TypeScript 配置：** 严格模式，启用 `noUnusedLocals`、`noUnusedParameters`、`noFallthroughCasesInSwitch`、`erasableSyntaxOnly`
- **前端路由：** `/`（首页）和 `/chat/:chatId`（聊天页，含编辑器/预览/蓝图标签页）
- **WebSocket 协议：** 客户端发送 `session_init`、`generate_all`、`user_suggestion`、`stop_generation`；服务端推送蓝图、阶段、文件、沙箱及生成生命周期等类型化事件
- **E2B 沙箱验证：** react-vite 执行 `tsc --noEmit → npm run lint → npm run build`；nextjs 执行 `tsc --noEmit → npx next build`
- **后端配置：** Pydantic Settings 从 `backend/.env` 加载（所有变量见 `backend/.env.example`）
- **包管理器：** Python 用 `uv`，前端用 `npm`
