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
views/        每个模块一个文件夹（orders/ 包含 OrderList、OrderDetail、OrderStats）
layouts/      MainLayout.vue — 已认证用户的壳布局，含侧边导航（全部 8 个模块）+ 顶栏
stores/       Pinia 认证存储 — JWT 存储在 localStorage，登录/登出，用户信息
api/client.js Axios 实例 — 自动附加 Bearer token，401 时重定向到 /login
router/       Vue Router — /login 公开；其他所有路由都是 MainLayout 的子路由
```

关键模式：
- **Auth 守卫**：`router.beforeEach` 检查 `auth.isAuthenticated`；未认证用户重定向到 `/login`。
- **API 调用**：视图从 `api/client.js` 导入 `client`，调用 `client.get('/orders')`、`client.post(...)` 等。`client` 的基础 URL 是 `/api` — 开发环境由 Vite 代理，生产环境由 nginx 代理。
- **布局**：`MainLayout.vue` 渲染 `el-menu`（含全部 8 个模块路由）、`el-header`（显示用户信息和登出按钮）、以及 `el-main` 中的 `<router-view />`。
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
