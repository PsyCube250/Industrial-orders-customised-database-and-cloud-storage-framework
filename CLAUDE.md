# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概览

ProdFlow — 制造订单与生产管理系统。共 8 个模块：订单管理、样品管理、采购/物料、物料准备、生产、包装、消息与超时提醒、系统管理。

技术栈：**Vue 3 + Element Plus**（前端），**FastAPI + SQLAlchemy**（后端），**PostgreSQL**（生产环境）或 SQLite（开发环境）。

## 命令

### Docker（推荐全栈运行）
```bash
docker compose up --build         # 启动所有服务（db、backend、frontend、caddy）
docker compose up --build -d      # 后台模式
```

### 后端（本地开发，不使用 Docker）
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.seed                # 创建 dev.db + 管理员用户（admin/admin123）
uvicorn app.main:app --reload --port 8000
```

### 前端（本地开发，另开终端）
```bash
cd frontend
npm install
npm run dev                       # Vite 运行在 :5173，代理 /api 和 /uploads 到 :8000
npm run build                     # 生产构建
```

## 架构

### 后端（`backend/app/`）

```
models/       SQLAlchemy ORM 模型，每个模块一个文件 — 全部通过 models/__init__.py 注册
schemas/      Pydantic 请求/响应模型
routers/      FastAPI APIRouter，每个模块一个 — 基于前缀（如 /api/orders、/api/auth）
auth.py       JWT 创建/验证（python-jose）、bcrypt 密码哈希、基于角色的守卫
database.py   SQLAlchemy 引擎 + 会话工厂 — 根据 DATABASE_URL 适配 SQLite 或 Postgres
config.py     Pydantic Settings — 读取 .env，默认使用 SQLite
main.py       应用组装：CORS（localhost:5173）、StaticFiles 挂载 /uploads、路由注册
seed.py       建表并初始化管理员用户和基础参考数据（类别、工序）
```

关键模式：
- **TimestampMixin**（`models/mixins.py`）：为模型添加 `created_at`/`updated_at` 字段。大部分模型类都引入该混入。
- **Auth 依赖链**：`get_current_user` → 验证 JWT，返回 `User`。`require_role(*roles)` → 包裹 `get_current_user` 并实施角色校验（使用方法：`Depends(require_role("admin", "supervisor"))`）。
- **订单流程**：固定 5 步流程，定义在 `ORDER_WORKFLOW_STEPS`（`样品制作`、`采购备料`、`生产`、`包装`、`出货`）。每个订单创建时会生成对应 `OrderProgressStep` 记录。通过 `POST /api/orders/{id}/progress/{step_id}/advance` 手动推进 — 标记当前步骤完成，开始下一步，或完成订单。
- **文件上传**：存储在 `backend/uploads/`（或 Docker 卷 `uploads_data`）下。订单附件存放于 `uploads/orders/{order_id}/`。
- **批量导入**：`POST /api/orders/bulk-import` 接收 Excel 文件，列包含：customer_name、product_name、quantity、delivery_date、notes。

### 前端（`frontend/src/`）

```
styles/       tokens.css（Design Token CSS 变量）+ global.css（全局重置）
data/         modules.js — 7 大模块 + 子功能定义
api/          client.js — Axios 实例，自动附加 Bearer token，401 时重定向到 /login
stores/       auth.js — Pinia 认证存储，JWT 存入 localStorage，login/logout/fetchUser
router/       index.js — /login 公开，其余路由 MainLayout 子路由 + beforeEach 守卫
layouts/      MainLayout.vue — 侧边导航（8 模块）+ 顶栏（用户信息、登出）+ <router-view>
views/        Login.vue（登录页）/ Home.vue（模块总览首页）/ Placeholder.vue（未开发模块占位）
```

关键模式：
- **Design Token**：`tokens.css` 定义 CSS 变量（色彩、字体、间距、圆角、阴影、布局），`global.css` 全局重置。小程序端对应 `miniprogram/constants/tokens.js`。
- **Docker 多阶段构建**：`frontend/Dockerfile`（Node 构建 → Nginx 托管），`nginx.conf` 代理 `/api` 和 `/uploads` 到后端。
- **Auth 守卫**：`router.beforeEach` 检查 `auth.isAuthenticated`；未认证用户重定向到 `/login`。
- **API 调用**：视图从 `api/client.js` 导入 `client`，调用 `client.get('/orders')`、`client.post(...)` 等。`client` 的基础 URL 是 `/api` — 开发环境由 Vite 代理，生产环境由 nginx 代理。
- **布局**：`MainLayout.vue` 渲染 `el-menu`（含全部 8 个模块路由，支持折叠）、`el-header`（显示用户信息和登出按钮）、以及 `el-main` 中的 `<router-view />`。
- 所有 Element Plus 图标在 `main.js` 中全局注册。

### 部署拓扑

```
                       +---------+
                       |  Caddy  |  :80/:443 → 自动 HTTPS（Let's Encrypt）
                       +----+----+
                            |
                       +----+----+
                       |  nginx  |  :80 — 提供 Vue SPA，代理 /api 和 /uploads → 后端
                       +----+----+
                            |
                       +----+----+
                       | FastAPI |  :8000 — 仅 Docker 网络内可访问
                       +----+----+
                            |
                       +----+----+
                       |Postgres |  :5432 — 仅 Docker 内部网络
                       +---------+
```

Caddy 使用 `sslip.io` 作为主机名，以便 Let's Encrypt 能为裸 IP 颁发证书。`Caddyfile` 反向代理到 `frontend:80`（nginx）。

## 认证与角色

- 登录：`POST /api/auth/login`（form 编码的 `username` + `password`）
- Token：JWT（HS256）— 默认 12 小时过期
- 角色：`admin`、`supervisor`、`director`、`staff`
- 默认管理员：`admin` / `admin123`（启动时初始化）
- 角色强制：路由在受保护端点上使用 `Depends(require_role("admin", "supervisor"))`（如用户管理、通知规则 CRUD）

## 数据库

- 本地开发使用 SQLite（首次运行自动创建为 `backend/prodflow.db`）
- Docker 中使用 PostgreSQL 16（主机 `db`、数据库 `prodflow`、用户名/密码 `prodflow`）
- FastAPI 启动时自动建表（`main.py` 的 `on_startup` 中 `Base.metadata.create_all`）
- 暂未使用 Alembic 迁移（尽管已存在于 requirements.txt 中 — 每次启动时重新建表）

## 环境变量

| 变量 | 默认值 | 用途 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./prodflow.db` | 数据库连接字符串 |
| `SECRET_KEY` | `dev-secret-change-me` | JWT 签名密钥 |
| `UPLOAD_DIR` | `./uploads` | 文件上传存储路径 |

使用本地 Postgres 时，复制 `backend/.env.example` 到 `backend/.env` 并设置 `DATABASE_URL`。

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发，或在执行实现计划之前使用——通过原生工具或 git worktree 回退机制确保隔离工作区存在
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
