# ProdFlow API 文档

> 本文档由后端代码自动分析生成，以代码为唯一事实来源。  
> 生成日期：2026-07-15  
> 后端框架：FastAPI  
> 数据库：PostgreSQL（生产）/ SQLite（开发）

---

## 1. 全局说明

### 1.1 Base URL

- 开发环境：`http://localhost:8000`
- 生产环境：由 nginx 反向代理，对外通过 Caddy 提供 HTTPS

### 1.2 认证机制

系统使用 **JWT Bearer Token**（OAuth2 Password Flow）进行身份认证。

- **登录接口**：`POST /api/auth/login`（表单格式 `username` + `password`）
- **Token 格式**：JWT，算法 HS256，默认有效期 12 小时（`access_token_expire_minutes=720`）
- **Token 传递**：请求头 `Authorization: Bearer <token>`
- **文件访问**：可通过 Query 参数 `?token=<token>` 或请求头传递 Token

### 1.3 角色体系

| 角色 | 说明 |
|------|------|
| `admin` | 管理员 — 用户管理、通知规则配置 |
| `supervisor` | 主管 — 通知规则配置 |
| `director` | 总监 |
| `staff` | 普通员工 |

### 1.4 权限分级

| 级别 | 说明 | 使用场景 |
|------|------|----------|
| 无需认证 | 公开接口 | 健康检查 |
| 需登录（`get_current_user`） | 任何有效 JWT Token 即可 | 大部分业务接口 |
| 需特定角色（`require_role(...)`） | Token 有效 + 角色匹配 | 用户管理（admin）、通知规则（admin/supervisor） |

### 1.5 通用错误响应

| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数错误（字段校验失败、外键引用不存在等） |
| 401 | 未认证 — Token 缺失、无效或已过期 |
| 403 | 权限不足 — 角色不满足要求 |
| 404 | 资源不存在 |
| 409 | 冲突 — 如订单号/PONo 并发冲突，需重试 |
| 500 | 服务器内部错误 |

### 1.6 CORS

开发环境下仅允许 `http://localhost:5173` 跨域访问。

### 1.7 TimestampMixin

大部分模型继承 `TimestampMixin`，自动包含：
- `created_at`: `datetime` — 创建时间
- `updated_at`: `datetime` — 最后更新时间

---

## 2. 健康检查

### GET /api/health

**功能**：服务健康检查。

- **认证**：不需要
- **请求参数**：无

**请求示例**：
```bash
curl http://localhost:8000/api/health
```

**返回示例**：
```json
{
  "status": "ok"
}
```

---

## 3. 认证模块 (Auth)

> Router 前缀：`/api/auth`  
> 代码位置：[routers/auth.py](backend/app/routers/auth.py)

### POST /api/auth/login

**功能**：用户登录，获取 JWT Token。

- **认证**：不需要
- **请求方式**：`POST`
- **Content-Type**：`application/x-www-form-urlencoded`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `username` | form | string | 是 | 用户名 |
| `password` | form | string | 是 | 密码 |

**请求示例**：
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=admin123"
```

**成功返回（200）**：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**错误返回**：
- `401` — `{"detail": "Incorrect username or password"}`

**注意事项**：
- 密码使用 bcrypt 哈希，比较时使用固定时间比较（用户不存在时也计算一次哈希，防止用户名枚举）。
- 用户需 `is_active=True` 才能登录。

---

### GET /api/auth/me

**功能**：获取当前登录用户信息。

- **认证**：需要登录（`get_current_user`）
- **请求方式**：`GET`
- **请求参数**：无

**请求示例**：
```bash
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <token>"
```

**成功返回（200）**：
```json
{
  "id": 1,
  "username": "admin",
  "full_name": "管理员",
  "role": "admin",
  "email": "",
  "phone": "",
  "is_active": true
}
```

---

## 4. 订单管理 (Orders)

> Router 前缀：`/api/orders`  
> 代码位置：[routers/orders.py](backend/app/routers/orders.py)

### 订单工作流

订单创建后自动生成 5 个进度步骤（`ORDER_WORKFLOW_STEPS`）：
1. 样品制作
2. 采购备料
3. 生产
4. 包装
5. 出货

订单状态：`in_progress` → `paused` / `cancelled` / `completed`

---

### POST /api/orders

**功能**：创建订单，自动生成订单号和 5 个进度步骤。

- **认证**：需要登录
- **请求方式**：`POST`

**请求体 JSON**（`OrderCreate`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `customer_name` | string | 是 | — | 客户名称 |
| `product_name` | string | 否 | 默认 `""` | 产品名称 |
| `quantity` | integer | 否 | `>= 0`，默认 `0` | 订单数量 |
| `delivery_date` | string(date) | 否 | — | 交付日期，格式 `YYYY-MM-DD` |
| `notes` | string | 否 | 默认 `""` | 备注 |

**请求示例**：
```bash
curl -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "XX公司",
    "product_name": "零件A",
    "quantity": 1000,
    "delivery_date": "2026-08-01",
    "notes": "加急"
  }'
```

**成功返回（200）**：
```json
{
  "id": 1,
  "order_no": "ORD202607150001",
  "customer_name": "XX公司",
  "product_name": "零件A",
  "quantity": 1000,
  "delivery_date": "2026-08-01",
  "status": "in_progress",
  "notes": "加急",
  "created_at": "2026-07-15T10:30:00",
  "updated_at": "2026-07-15T10:30:00",
  "attachments": [],
  "progress_steps": [
    {
      "id": 1,
      "step_name": "样品制作",
      "sequence": 0,
      "status": "in_progress",
      "started_at": "2026-07-15T10:30:00",
      "completed_at": null,
      "due_at": null,
      "is_overdue": false
    }
  ],
  "change_logs": []
}
```

**错误返回**：
- `409` — 订单号分配冲突，需重试（最多重试 3 次后返回此错误）

**注意事项**：
- 订单号格式：`ORD` + 日期（`YYYYMMDD`）+ 4 位递增序号，如 `ORD202607150001`
- 创建时使用 savepoint 重试机制处理并发订单号冲突
- 订单创建时第 1 个步骤自动设为 `in_progress`，其余为 `pending`
- 步骤的 `due_at` 根据 `TimeoutRule` 中配置自动计算

---

### POST /api/orders/bulk-import

**功能**：从 Excel 文件批量导入订单。

- **认证**：需要登录
- **请求方式**：`POST`
- **Content-Type**：`multipart/form-data`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `file` | form | file (.xlsx) | 是 | Excel 文件 |

**Excel 模板列**（第 1 行为表头，数据从第 2 行开始）：

| 列 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `customer_name` | string | 是 | 客户名称 |
| `product_name` | string | 否 | 产品名称 |
| `quantity` | integer | 否 | 数量（>= 0） |
| `delivery_date` | date | 否 | 交付日期，格式 `YYYY-MM-DD` |
| `notes` | string | 否 | 备注 |

**请求示例**：
```bash
curl -X POST http://localhost:8000/api/orders/bulk-import \
  -H "Authorization: Bearer <token>" \
  -F "file=@orders.xlsx"
```

**成功返回（200）**：
```json
{
  "created": ["ORD202607150001", "ORD202607150002"],
  "errors": [
    {"row": 5, "error": "customer_name is required"}
  ]
}
```

**注意事项**：
- 每行使用 savepoint 隔离——某行失败不影响其他行
- 只支持 `.xlsx` 格式
- 空行自动跳过

---

### GET /api/orders

**功能**：搜索/列表订单。

- **认证**：需要登录
- **请求方式**：`GET`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `keyword` | query | string | 否 | 搜索关键词，匹配客户名称或订单号（模糊匹配） |
| `status` | query | string | 否 | 按订单状态筛选 |

**请求示例**：
```bash
curl "http://localhost:8000/api/orders?keyword=XX公司&status=in_progress" \
  -H "Authorization: Bearer <token>"
```

**成功返回（200）**：
```json
[
  {
    "id": 1,
    "order_no": "ORD202607150001",
    "customer_name": "XX公司",
    "product_name": "零件A",
    "quantity": 1000,
    "delivery_date": "2026-08-01",
    "status": "in_progress",
    "notes": "加急",
    "created_at": "2026-07-15T10:30:00",
    "updated_at": "2026-07-15T10:30:00"
  }
]
```

**注意事项**：
- 结果按 `created_at` 降序排列
- 列表接口不返回关联数据（附件、进度步骤、变更日志）

---

### GET /api/orders/stats

**功能**：订单统计面板。

- **认证**：需要登录
- **请求方式**：`GET`
- **请求参数**：无

**请求示例**：
```bash
curl http://localhost:8000/api/orders/stats \
  -H "Authorization: Bearer <token>"
```

**成功返回（200）**（`OrderStatsOut`）：
```json
{
  "total_orders": 100,
  "on_time_rate": 85.5,
  "delay_ranking": [
    {"order_no": "ORD202606010001", "customer_name": "XX公司", "delay_days": 10}
  ],
  "step_duration_avg_hours": [
    {"step_name": "样品制作", "avg_hours": 24.5}
  ],
  "product_quantity_totals": [
    {"product_name": "零件A", "total_quantity": 50000}
  ]
}
```

**字段说明**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `total_orders` | int | 订单总数 |
| `on_time_rate` | float | 准时交付率（%） |
| `delay_ranking` | list | 延迟排名，按 delay_days 降序 |
| `step_duration_avg_hours` | list | 每个步骤平均耗时（小时） |
| `product_quantity_totals` | list | 按产品名称汇总的订单总量 |

---

### GET /api/orders/{order_id}

**功能**：获取订单详情（含附件、进度步骤、变更日志）。

- **认证**：需要登录
- **请求方式**：`GET`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `order_id` | path | integer | 是 | 订单 ID |

**请求示例**：
```bash
curl http://localhost:8000/api/orders/1 \
  -H "Authorization: Bearer <token>"
```

**成功返回（200）**：返回 `OrderDetailOut` 结构，与 [POST /api/orders](#post-apiorders) 返回结构相同。

**错误返回**：
- `404` — `{"detail": "Order not found"}`

---

### PATCH /api/orders/{order_id}

**功能**：更新订单基本信息。

- **认证**：需要登录
- **请求方式**：`PATCH`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `order_id` | path | integer | 是 | 订单 ID |

**请求体 JSON**（`OrderUpdate`，所有字段可选）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `customer_name` | string | 否 | — | 客户名称 |
| `product_name` | string | 否 | — | 产品名称 |
| `quantity` | integer | 否 | `>= 0` | 数量 |
| `notes` | string | 否 | — | 备注 |

**请求示例**：
```bash
curl -X PATCH http://localhost:8000/api/orders/1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"notes": "更新备注"}'
```

**成功返回（200）**：返回 `OrderDetailOut` 结构。

**注意事项**：
- 使用 `exclude_unset=True`，仅更新传入的字段
- 不支持更新 `delivery_date`——请使用变更接口（`/change`）

---

### POST /api/orders/{order_id}/change

**功能**：订单变更操作（修改交期、取消、暂停、恢复）。

- **认证**：需要登录
- **请求方式**：`POST`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `order_id` | path | integer | 是 | 订单 ID |

**请求体 JSON**（`OrderChangeAction`）：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `change_type` | string | 是 | 变更类型：`delivery_date` / `cancel` / `pause` / `resume` |
| `new_delivery_date` | string(date) | 条件必填 | 当 `change_type=delivery_date` 时必填 |

**变更类型规则**：

| change_type | 前置条件 | 效果 |
|-------------|----------|------|
| `delivery_date` | 无 | 修改交付日期 |
| `cancel` | 订单状态不能是 `cancelled` 或 `completed` | 订单状态 → `cancelled` |
| `pause` | 订单状态必须是 `in_progress` | 订单状态 → `paused` |
| `resume` | 订单状态必须是 `paused` | 订单状态 → `in_progress` |

**请求示例**：
```bash
# 暂停订单
curl -X POST http://localhost:8000/api/orders/1/change \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"change_type": "pause"}'

# 变更交期
curl -X POST http://localhost:8000/api/orders/1/change \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"change_type": "delivery_date", "new_delivery_date": "2026-09-01"}'
```

**成功返回（200）**：返回 `OrderDetailOut` 结构。

**注意事项**：
- 所有变更会写入 `OrderChangeLog` 和 `OperationLog`

---

### POST /api/orders/{order_id}/progress/{step_id}/advance

**功能**：推进订单进度步骤——标记当前步骤完成，开始下一步。

- **认证**：需要登录
- **请求方式**：`POST`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `order_id` | path | integer | 是 | 订单 ID |
| `step_id` | path | integer | 是 | 进度步骤 ID |

**请求示例**：
```bash
curl -X POST http://localhost:8000/api/orders/1/progress/5/advance \
  -H "Authorization: Bearer <token>"
```

**成功返回（200）**：返回 `OrderDetailOut` 结构。

**规则**：
- 仅 `in_progress` 状态的订单可以推进步骤
- 仅 `in_progress` 状态的步骤可以推进（确保步骤按顺序执行）
- 推进后：当前步骤 → `done`，下一步骤 → `in_progress`
- 如果是最后一个步骤，订单状态 → `completed`
- 每一步的 `due_at` 根据 `TimeoutRule` 配置计算

**错误返回**：
- `400` — 订单不在 `in_progress` 状态；步骤不在 `in_progress` 状态
- `404` — 订单或步骤不存在

---

### POST /api/orders/{order_id}/attachments

**功能**：上传订单附件。

- **认证**：需要登录
- **请求方式**：`POST`
- **Content-Type**：`multipart/form-data`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `order_id` | path | integer | 是 | 订单 ID |
| `file` | form | file | 是 | 附件文件 |

**请求示例**：
```bash
curl -X POST http://localhost:8000/api/orders/1/attachments \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf"
```

**成功返回（200）**：返回 `OrderDetailOut` 结构。

**注意事项**：
- 文件存储在 `uploads/orders/{order_id}/` 下
- 文件名自动添加 8 位随机前缀防止重名覆盖

---

## 5. 文件服务

### GET /uploads/{file_path:path}

**功能**：访问上传的文件（附件、样品照片等）。

- **认证**：需要登录（支持 Query 参数 `?token=` 或 `Authorization` 请求头）
- **请求方式**：`GET`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `file_path` | path | string | 是 | 文件路径 |
| `token` | query | string | 否 | JWT Token（用于 `<a>` / `<img>` 标签直接访问） |

**请求示例**：
```bash
curl "http://localhost:8000/uploads/orders/1/a1b2c3d4_document.pdf?token=<token>"
```

**注意事项**：
- 路径遍历攻击受防护（`os.path.realpath` 校验）
- 商业敏感文件，不充当公开静态资源

---

## 6. 样品管理 (Samples)

> Router 前缀：`/api/samples`  
> 代码位置：[routers/samples.py](backend/app/routers/samples.py)

### 样品状态流转

```
assigned → produced → shipped → confirmed/returned
```

---

### GET /api/samples

**功能**：列表所有样品。

- **认证**：需要登录
- **请求方式**：`GET`
- **请求参数**：无

**返回**：`list[SampleOut]`，按 `id` 降序

```json
[
  {
    "id": 1,
    "order_id": 1,
    "assigned_to": 2,
    "deadline": "2026-07-20",
    "status": "assigned"
  }
]
```

---

### POST /api/samples

**功能**：创建样品任务。

- **认证**：需要登录
- **请求方式**：`POST`

**请求体 JSON**（`SampleCreate`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `order_id` | integer | 否 | 存在性校验（FK） | 关联订单 ID |
| `assigned_to` | integer | 否 | 存在性校验（FK） | 指派给的用户 ID |
| `deadline` | string(date) | 否 | — | 截止日期 |

**请求示例**：
```bash
curl -X POST http://localhost:8000/api/samples \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"order_id": 1, "assigned_to": 2, "deadline": "2026-07-20"}'
```

**成功返回（200）**：返回 `SampleOut`，`status` 创建时固定为 `assigned`。

**错误返回**：
- `400` — `order_id` 或 `assigned_to` 引用的记录不存在

---

### GET /api/samples/{sample_id}

**功能**：获取样品详情（含照片、发货、确认、物料清单）。

- **认证**：需要登录
- **请求方式**：`GET`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `sample_id` | path | integer | 是 | 样品 ID |

**成功返回（200）**（`SampleDetailOut`）：
```json
{
  "id": 1,
  "order_id": 1,
  "assigned_to": 2,
  "deadline": "2026-07-20",
  "status": "produced",
  "photos": [
    {"id": 1, "photo_path": "uploads/samples/1/xxx_photo.jpg", "uploaded_at": "2026-07-15T14:00:00"}
  ],
  "shipments": [
    {"id": 1, "tracking_no": "SF1234567890", "shipped_at": "2026-07-16T10:00:00"}
  ],
  "confirmations": [
    {"id": 1, "result": "pass", "proof_path": "", "confirmed_at": "2026-07-18T12:00:00"}
  ],
  "materials": [
    {"id": 1, "material_name": "ABS塑料", "spec": "A级", "unit": "kg", "qty_per_unit": 0.5, "notes": ""}
  ]
}
```

---

### POST /api/samples/{sample_id}/photos

**功能**：上传样品照片。

- **认证**：需要登录
- **请求方式**：`POST`
- **Content-Type**：`multipart/form-data`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `sample_id` | path | integer | 是 | 样品 ID |
| `file` | form | file | 是 | 照片文件 |

**注意事项**：
- 首次上传照片时，样品状态自动从 `assigned` → `produced`
- 之后的上传不会改变样品状态（避免状态回退）

---

### POST /api/samples/{sample_id}/shipments

**功能**：添加样品发货信息。

- **认证**：需要登录
- **请求方式**：`POST`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `sample_id` | path | integer | 是 | 样品 ID |

**请求体 JSON**（`SampleShipmentIn`）：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tracking_no` | string | 是 | 快递单号 |

**注意事项**：
- 添加后样品状态自动变为 `shipped`

---

### POST /api/samples/{sample_id}/confirmation

**功能**：客户确认样品结果。

- **认证**：需要登录
- **请求方式**：`POST`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `sample_id` | path | integer | 是 | 样品 ID |

**请求体 JSON**（`SampleConfirmationIn`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `result` | string | 是 | `"pass"` 或 `"fail"` | 确认结果 |
| `proof_path` | string | 否 | 默认 `""` | 确认凭证路径 |

**注意事项**：
- `pass` → 状态变为 `confirmed`；`fail` → 状态变为 `returned`

---

### POST /api/samples/{sample_id}/materials

**功能**：添加样品物料清单。

- **认证**：需要登录
- **请求方式**：`POST`

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `sample_id` | path | integer | 是 | 样品 ID |

**请求体 JSON**（`SampleMaterialIn`）：
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `material_name` | string | 是 | — | 物料名称 |
| `spec` | string | 否 | `""` | 规格 |
| `unit` | string | 否 | `""` | 单位 |
| `qty_per_unit` | float | 否 | `0` | 单件用量 |
| `notes` | string | 否 | `""` | 备注 |

---

## 7. 采购/物料管理 (Procurement)

> Router 前缀：`/api/procurement`  
> 代码位置：[routers/procurement.py](backend/app/routers/procurement.py)

### 7.1 供应商 (Suppliers)

#### GET /api/procurement/suppliers

**功能**：列表所有供应商。

- **认证**：需要登录
- **返回**：`list[SupplierOut]`，按 `id` 升序

```json
[
  {
    "id": 1,
    "name": "XX材料有限公司",
    "contact_name": "张三",
    "phone": "13800138000",
    "address": "XX市XX区",
    "notes": ""
  }
]
```

---

#### POST /api/procurement/suppliers

**功能**：创建供应商。

- **认证**：需要登录

**请求体 JSON**（`SupplierIn`）：
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `name` | string | 是 | — | 供应商名称 |
| `contact_name` | string | 否 | `""` | 联系人 |
| `phone` | string | 否 | `""` | 电话 |
| `address` | string | 否 | `""` | 地址 |
| `notes` | string | 否 | `""` | 备注 |

---

#### PATCH /api/procurement/suppliers/{supplier_id}

**功能**：更新供应商信息。

- **认证**：需要登录
- **请求体**：`SupplierIn`（全字段更新）

---

#### DELETE /api/procurement/suppliers/{supplier_id}

**功能**：删除供应商。

- **认证**：需要登录

**注意事项**：
- 删除前会自动将该供应商的采购订单 `supplier_id` 置为 `NULL`，避免 FK 约束冲突

---

### 7.2 采购需求 (Requirements)

#### POST /api/procurement/requirements/generate/{order_id}

**功能**：根据订单的样品物料清单自动生成采购需求。  
计算方式：`required_qty = sample_material.qty_per_unit × order.quantity`

- **认证**：需要登录

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `order_id` | path | integer | 是 | 订单 ID |

**注意事项**：
- 重新生成时，已完成的采购需求（`fulfilled=true`）保留不重复添加
- 未完成的需求先删除再重新生成

---

#### GET /api/procurement/requirements

**功能**：列表所有采购需求。

- **认证**：需要登录
- **返回**：`list[PurchaseRequirementOut]`，按 `id` 降序

```json
[
  {
    "id": 1,
    "order_id": 1,
    "material_name": "ABS塑料",
    "required_qty": 500,
    "unit": "kg",
    "fulfilled": false
  }
]
```

---

### 7.3 采购订单 (Purchase Orders)

#### GET /api/procurement/purchase-orders

**功能**：列表所有采购订单（含明细）。

- **认证**：需要登录
- **返回**：`list[PurchaseOrderOut]`，按 `id` 降序

```json
[
  {
    "id": 1,
    "po_no": "PO202607150001",
    "supplier_id": 1,
    "planned_arrival_date": "2026-07-25",
    "status": "open",
    "items": [
      {"id": 1, "material_name": "ABS塑料", "qty": 500, "unit_price": 12.5}
    ]
  }
]
```

---

#### POST /api/procurement/purchase-orders

**功能**：创建采购订单。

- **认证**：需要登录

**请求体 JSON**（`PurchaseOrderCreate`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `supplier_id` | integer | 否 | 存在性校验 | 供应商 ID |
| `planned_arrival_date` | string(date) | 否 | — | 预计到货日期 |
| `items` | list | 否 | — | 采购明细列表 |

`items` 中每项（`PurchaseOrderItemIn`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `material_name` | string | 是 | — | 物料名称 |
| `qty` | float | 是 | `> 0` | 采购数量 |
| `unit_price` | float | 否 | `>= 0`，默认 `0` | 单价 |

**注意事项**：
- PONo 格式：`PO` + 日期（`YYYYMMDD`）+ 4 位序号
- 使用 savepoint 重试处理并发 PONo 冲突

---

### 7.4 物料入库 (Inbound)

#### POST /api/procurement/inbound

**功能**：登记物料入库，记录数量和 QC 结果。入库后自动计算采购需求完成度及 PO 状态。

- **认证**：需要登录

**请求体 JSON**（`MaterialInboundIn`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `purchase_order_item_id` | integer | 是 | — | 采购订单明细 ID |
| `qty_received` | float | 是 | `> 0` | 实收数量 |
| `qc_result` | string | 否 | `"pass"` / `"fail"` / `"pending"`，默认 `"pending"` | QC 结果 |

**返回**（`MaterialInboundOut`）：
```json
{
  "id": 1,
  "purchase_order_item_id": 1,
  "qty_received": 500,
  "qc_result": "pass",
  "received_at": "2026-07-20T15:00:00"
}
```

**自动触发的副作用**：
1. 计算物料累计入库量（仅 `qc_result=pass`），按最早优先顺序标记采购需求为已完成（`fulfilled=true`）
2. 检查 PO 下所有物料是否已收齐 → 自动更新 PO 状态为 `received`（准时）或 `late`（逾期）

---

### 7.5 短缺预警 (Shortages)

#### GET /api/procurement/shortages

**功能**：列出所有未完成的采购需求。

- **认证**：需要登录
- **返回**：`list[PurchaseRequirementOut]`（仅 `fulfilled=false` 的记录）

---

### 7.6 采购报告 (Report)

#### GET /api/procurement/report/on-time-rate

**功能**：采购准时率统计。

- **认证**：需要登录

**返回**：
```json
{
  "on_time_rate": 80.0,
  "sample_size": 10
}
```

- `on_time_rate`：关闭状态中 `received`（准时）占比（%）
- `sample_size`：已关闭的 PO 总数

---

## 8. 物料准备 (Prep)

> Router 前缀：`/api/prep`  
> 代码位置：[routers/prep.py](backend/app/routers/prep.py)

### GET /api/prep

**功能**：列表所有物料准备任务。

- **认证**：需要登录
- **返回**：`list[PrepTaskOut]`，按 `id` 降序

---

### POST /api/prep

**功能**：创建物料准备任务。

- **认证**：需要登录

**请求体 JSON**（`PrepTaskCreate`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `order_id` | integer | 否 | 存在性校验 | 关联订单 |
| `process_name` | string | 是 | — | 工序名称 |
| `assigned_worker_id` | integer | 否 | 存在性校验 | 指派人员 |
| `due_date` | string(date) | 否 | — | 截止日期 |

**注意事项**：
- 状态初始为 `pending`

---

### GET /api/prep/{task_id}

**功能**：获取物料准备任务详情（含子任务列表）。

- **认证**：需要登录
- **返回**：`PrepTaskDetailOut`（含 `subtasks`）

---

### POST /api/prep/{task_id}/subtasks

**功能**：添加子任务。

- **认证**：需要登录

**请求体 JSON**（`PrepSubtaskIn`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `name` | string | 是 | — | 子任务名称 |
| `percent_complete` | integer | 否 | `0-100`，默认 `0` | 完成百分比 |

**注意事项**：
- 添加子任务后自动刷新父任务状态：所有子任务 ≥ 100% 时 → 父任务 `done`，否则 → `in_progress`

---

### PATCH /api/prep/{task_id}/subtasks/{subtask_id}

**功能**：更新子任务进度。

- **认证**：需要登录

**请求体 JSON**（`PrepSubtaskUpdate`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `name` | string | 否 | — | 子任务名称 |
| `percent_complete` | integer | 否 | `0-100` | 完成百分比 |

**注意事项**：
- 更新后自动刷新父任务状态

---

### GET /api/prep/{task_id}/completion

**功能**：子任务完成度面板。

- **认证**：需要登录

**返回**：
```json
{
  "percent_complete": 75.0,
  "is_overdue": false
}
```

- `percent_complete`：所有子任务 `percent_complete` 的平均值
- `is_overdue`：`due_date` 已过且平均进度 < 100%

---

## 9. 生产管理 (Production)

> Router 前缀：`/api/production`  
> 代码位置：[routers/production.py](backend/app/routers/production.py)

### 9.1 生产记录 (Records)

#### GET /api/production/records

**功能**：列表所有生产记录。

- **认证**：需要登录
- **返回**：`list[ProductionRecordOut]`，按 `id` 降序

```json
[
  {
    "id": 1,
    "order_id": 1,
    "launch_time": "2026-07-16T08:00:00",
    "pre_production_sample_time": "2026-07-16T09:00:00",
    "estimated_ship_time": "2026-07-30T18:00:00",
    "completed_time": null
  }
]
```

---

#### POST /api/production/records

**功能**：创建生产记录（关键时间节点）。

- **认证**：需要登录

**请求体 JSON**（`ProductionRecordIn`，全部字段可选）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `order_id` | integer | 否 | 存在性校验 | 订单 ID |
| `launch_time` | datetime | 否 | — | 上线时间 |
| `pre_production_sample_time` | datetime | 否 | — | 产前样时间 |
| `estimated_ship_time` | datetime | 否 | — | 预计出货时间 |
| `completed_time` | datetime | 否 | — | 完成时间 |

---

#### PATCH /api/production/records/{record_id}

**功能**：更新生产记录。

- **认证**：需要登录
- **请求体**：`ProductionRecordIn`（传哪些字段更新哪些）

---

### 9.2 日进度 (Progress)

#### GET /api/production/progress

**功能**：列表生产日进度记录。

- **认证**：需要登录
- **返回**：`list[ProductionProgressOut]`，按 `record_date` 降序

---

#### POST /api/production/progress

**功能**：添加日进度记录。

- **认证**：需要登录

**请求体 JSON**（`ProductionProgressIn`）：
| 字段 | 类型 | 必填 | 校验 | 默认 | 说明 |
|------|------|------|------|------|------|
| `order_id` | integer | 否 | 存在性校验 | — | 订单 ID |
| `process_step` | string | 是 | — | — | 当前工序名称 |
| `record_date` | string(date) | 否 | — | 当天 | 记录日期 |
| `status` | string | 否 | — | `"in_progress"` | 状态 |

---

### 9.3 物料异常 (Material Issues)

#### GET /api/production/material-issues

**功能**：列表生产物料异常。

- **认证**：需要登录
- **返回**：`list[MaterialIssueOut]`，按 `reported_at` 降序

---

#### POST /api/production/material-issues

**功能**：上报物料异常。

- **认证**：需要登录

**请求体 JSON**（`MaterialIssueIn`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `order_id` | integer | 否 | 存在性校验 | 订单 ID |
| `description` | string | 是 | — | 异常描述 |

---

#### POST /api/production/material-issues/{issue_id}/resolve

**功能**：标记物料异常已解决。

- **认证**：需要登录
- **返回**：`MaterialIssueOut`（`resolved=true`）

---

## 10. 包装管理 (Packaging)

> Router 前缀：`/api/packaging`  
> 代码位置：[routers/packaging.py](backend/app/routers/packaging.py)

### GET /api/packaging

**功能**：列表所有包装任务。

- **认证**：需要登录
- **返回**：`list[PackagingTaskOut]`，按 `id` 降序

---

### POST /api/packaging

**功能**：创建包装任务。

- **认证**：需要登录

**请求体 JSON**（`PackagingTaskCreate`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `order_id` | integer | 否 | 存在性校验 | 订单 ID |

**注意事项**：
- 状态初始为 `pending`

---

### POST /api/packaging/{task_id}/pack

**功能**：标记已打包。

- **认证**：需要登录

**前置条件**：任务状态必须为 `pending`

**错误返回**：
- `400` — 任务状态非 `pending`
- `404` — 任务不存在

---

### POST /api/packaging/{task_id}/qc

**功能**：登记 QC 检验结果。

- **认证**：需要登录

**请求体 JSON**（`PackagingQCIn`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `quantity_checked` | integer | 是 | `>= 0` | 检验数量 |
| `result` | string | 是 | `"pass"` 或 `"fail"` | 检验结果 |

**前置条件**：任务状态必须为 `packed` 或 `qc_done`

**注意事项**：
- 登记后任务状态变为 `qc_done`

---

## 11. 通知规则与超时提醒 (Notifications)

> Router 前缀：`/api/notification-rules`  
> 代码位置：[routers/notifications.py](backend/app/routers/notifications.py)

### 11.1 超时规则 (Timeout Rules)

#### GET /api/notification-rules/timeout

**功能**：列表所有超时规则。

- **认证**：需要登录
- **返回**：`list[TimeoutRuleOut]`

```json
[
  {
    "id": 1,
    "step_name": "样品制作",
    "days_allowed": 7,
    "warning_threshold_days": 1
  }
]
```

---

#### POST /api/notification-rules/timeout

**功能**：创建超时规则。

- **认证**：需要 `admin` 或 `supervisor` 角色

**请求体 JSON**（`TimeoutRuleIn`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `step_name` | string | 是 | — | 步骤名称（如 `样品制作`） |
| `days_allowed` | integer | 是 | `>= 1` | 允许天数 |
| `warning_threshold_days` | integer | 否 | `>= 0`，默认 `1` | 预警提前天数 |

---

#### PATCH /api/notification-rules/timeout/{rule_id}

**功能**：更新超时规则。

- **认证**：需要 `admin` 或 `supervisor` 角色
- **请求体**：`TimeoutRuleIn`（全字段更新）

---

### 11.2 升级规则 (Escalation Rules)

#### GET /api/notification-rules/escalation

**功能**：列表所有升级规则。

- **认证**：需要登录
- **返回**：`list[EscalationRuleOut]`，按 `overdue_days` 升序

---

#### POST /api/notification-rules/escalation

**功能**：创建升级规则。

- **认证**：需要 `admin` 或 `supervisor` 角色

**请求体 JSON**（`EscalationRuleIn`）：
| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| `step_name` | string | 是 | — | 步骤名称 |
| `overdue_days` | integer | 是 | `>= 0` | 超期天数阈值 |
| `notify_role` | string | 是 | — | 通知的角色（如 `supervisor`、`director`） |

---

### 11.3 扫描通知 (Scan)

#### POST /api/notification-rules/scan

**功能**：触发式扫描——对当前所有 `in_progress` 订单步骤评估超时/升级规则，生成通知。

- **认证**：需要登录
- **请求参数**：无

**返回**：
```json
{
  "notifications_created": 3,
  "steps_checked": 25
}
```

**触发逻辑**（代码中实现，非 cron 自动触发）：
1. 遍历所有 `in_progress` 步骤
2. 如果步骤无 `due_at` 但有超时规则 → 回填 `due_at`
3. 如果已超期 → 创建 `warning` 级别通知（通知 `StepOwner` 或广播）
4. 根据 `EscalationRule` 匹配超期天数 → 向对应角色的活跃用户发送 `critical` 级别通知
5. 如果距离到期在预警阈值内 → 创建 `info` 级别通知

**注意事项**：
- 该接口设计为按需调用（页面加载或 cron job），代码中未实现自动定时触发

---

## 12. 系统管理 (System)

> Router 前缀：`/api/system`  
> 代码位置：[routers/system.py](backend/app/routers/system.py)

### 12.1 用户管理 (Users)

#### GET /api/system/users

**功能**：列表所有用户。

- **认证**：需要登录（任何角色均可）
- **返回**：`list[UserOut]`，按 `id` 升序

---

#### POST /api/system/users

**功能**：创建用户。

- **认证**：需要 `admin` 角色

**请求体 JSON**（`UserCreate`）：
| 字段 | 类型 | 必填 | 默认 | 校验 | 说明 |
|------|------|------|------|------|------|
| `username` | string | 是 | — | 唯一 | 用户名 |
| `password` | string | 是 | — | — | 密码（明文，后端 bcrypt 哈希存储） |
| `full_name` | string | 否 | `""` | — | 全名 |
| `role` | string | 否 | `"staff"` | 必须是 `admin`/`supervisor`/`director`/`staff` | 角色 |
| `email` | string | 否 | `""` | — | 邮箱 |
| `phone` | string | 否 | `""` | — | 电话 |

**错误返回**：
- `400` — 角色不合法；用户名已存在

---

#### PATCH /api/system/users/{user_id}

**功能**：更新用户信息。

- **认证**：需要 `admin` 角色

**请求体 JSON**（`UserUpdate`，全部可选）：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `full_name` | string | 否 | 全名 |
| `role` | string | 否 | 角色 |
| `email` | string | 否 | 邮箱 |
| `phone` | string | 否 | 电话 |
| `is_active` | bool | 否 | 是否启用 |
| `password` | string | 否 | 新密码（非空时更新） |

**防护规则**：
- 不允许将最后一个活跃管理员降级或停用
- 密码字段特殊处理：`password` 被 pop 出来单独哈希后赋值给 `hashed_password`

---

#### DELETE /api/system/users/{user_id}

**功能**：删除用户。

- **认证**：需要 `admin` 角色

**防护规则**：
- 不允许删除自己的账号
- 不允许删除最后一个活跃管理员
- 删除前自动将引用该用户的外键字段置为 `NULL`（操作日志、步骤负责人、通知、变更日志、样品指派、备料任务指派）

---

### 12.2 基础数据 (Base Data)

以下三个资源使用统一的 CRUD 模式（`_named_item_crud`），结构为 `{id, name, notes}`。

#### 产品类别

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/system/product-categories` | 列表 |
| `POST` | `/api/system/product-categories` | 创建 |
| `DELETE` | `/api/system/product-categories/{item_id}` | 删除 |

#### 物料类别

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/system/material-categories` | 列表 |
| `POST` | `/api/system/material-categories` | 创建 |
| `DELETE` | `/api/system/material-categories/{item_id}` | 删除 |

**请求体**（`NamedItemIn`）：
```json
{
  "name": "类别名称",
  "notes": ""
}
```

**注意事项**：
- 所有操作需要登录即可（无角色限制）
- **未实现 PATCH 更新接口**——仅支持创建和删除

---

### 12.3 工序库 (Process Library)

#### GET /api/system/process-library

**功能**：列表工序库。

- **认证**：需要登录
- **返回**：`list[ProcessLibraryOut]`

```json
[
  {"id": 1, "name": "切割", "description": "板材切割工序"}
]
```

---

#### POST /api/system/process-library

**功能**：添加工序。

- **认证**：需要登录

**请求体 JSON**（`ProcessLibraryIn`）：
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `name` | string | 是 | — | 工序名称 |
| `description` | string | 否 | `""` | 描述 |

---

### 12.4 操作日志 (Operation Logs)

#### GET /api/system/operation-logs

**功能**：查看操作日志。

- **认证**：需要登录
- **返回**：`list[OperationLogOut]`，按 `created_at` 降序，**最多 500 条**

```json
[
  {
    "id": 1,
    "user_id": 1,
    "action": "create_order",
    "target": "ORD202607150001",
    "created_at": "2026-07-15T10:30:00"
  }
]
```

**注意事项**：
- 只读，无创建/删除接口
- 硬限制 500 条，无分页参数

---

### 12.5 通知中心 (Notifications)

#### GET /api/system/notifications

**功能**：获取当前用户的通知（含广播通知）。

- **认证**：需要登录

**过滤逻辑**：`user_id = 当前用户` 或 `user_id IS NULL`（广播）

---

#### POST /api/system/notifications/{notification_id}/read

**功能**：标记通知已读。

- **认证**：需要登录

**安全设计**：
- 只能标记自己的通知或广播通知
- 其他人的通知返回 404（而非 403，防止通过状态码推断通知是否存在）

---

### 12.6 步骤负责人 (Step Owners)

#### GET /api/system/step-owners

**功能**：列表所有步骤负责人配置。

- **认证**：需要登录
- **返回**：`list[StepOwnerOut]`

---

#### POST /api/system/step-owners

**功能**：配置步骤负责人（用于超时通知路由）。

- **认证**：需要登录

**请求体 JSON**（`StepOwnerIn`）：
| 字段 | 类型 | 必填 | 默认 | 校验 | 说明 |
|------|------|------|------|------|------|
| `step_name` | string | 是 | — | — | 步骤名称 |
| `user_id` | integer | 否 | `null` | 存在性校验 | 用户 ID |
| `contact_name` | string | 否 | `""` | — | 联系人姓名 |
| `contact_phone` | string | 否 | `""` | — | 联系电话 |

---

## 附录 A：API 索引总表

| # | 方法 | 路径 | 认证 | 角色要求 | 所属模块 |
|---|------|------|------|----------|----------|
| 1 | `GET` | `/api/health` | 否 | — | 系统 |
| 2 | `POST` | `/api/auth/login` | 否 | — | 认证 |
| 3 | `GET` | `/api/auth/me` | 是 | — | 认证 |
| 4 | `POST` | `/api/orders` | 是 | — | 订单 |
| 5 | `POST` | `/api/orders/bulk-import` | 是 | — | 订单 |
| 6 | `GET` | `/api/orders` | 是 | — | 订单 |
| 7 | `GET` | `/api/orders/stats` | 是 | — | 订单 |
| 8 | `GET` | `/api/orders/{order_id}` | 是 | — | 订单 |
| 9 | `PATCH` | `/api/orders/{order_id}` | 是 | — | 订单 |
| 10 | `POST` | `/api/orders/{order_id}/change` | 是 | — | 订单 |
| 11 | `POST` | `/api/orders/{order_id}/progress/{step_id}/advance` | 是 | — | 订单 |
| 12 | `POST` | `/api/orders/{order_id}/attachments` | 是 | — | 订单 |
| 13 | `GET` | `/uploads/{file_path}` | 是 | — | 文件 |
| 14 | `GET` | `/api/samples` | 是 | — | 样品 |
| 15 | `POST` | `/api/samples` | 是 | — | 样品 |
| 16 | `GET` | `/api/samples/{sample_id}` | 是 | — | 样品 |
| 17 | `POST` | `/api/samples/{sample_id}/photos` | 是 | — | 样品 |
| 18 | `POST` | `/api/samples/{sample_id}/shipments` | 是 | — | 样品 |
| 19 | `POST` | `/api/samples/{sample_id}/confirmation` | 是 | — | 样品 |
| 20 | `POST` | `/api/samples/{sample_id}/materials` | 是 | — | 样品 |
| 21 | `GET` | `/api/procurement/suppliers` | 是 | — | 采购 |
| 22 | `POST` | `/api/procurement/suppliers` | 是 | — | 采购 |
| 23 | `PATCH` | `/api/procurement/suppliers/{supplier_id}` | 是 | — | 采购 |
| 24 | `DELETE` | `/api/procurement/suppliers/{supplier_id}` | 是 | — | 采购 |
| 25 | `POST` | `/api/procurement/requirements/generate/{order_id}` | 是 | — | 采购 |
| 26 | `GET` | `/api/procurement/requirements` | 是 | — | 采购 |
| 27 | `GET` | `/api/procurement/purchase-orders` | 是 | — | 采购 |
| 28 | `POST` | `/api/procurement/purchase-orders` | 是 | — | 采购 |
| 29 | `POST` | `/api/procurement/inbound` | 是 | — | 采购 |
| 30 | `GET` | `/api/procurement/shortages` | 是 | — | 采购 |
| 31 | `GET` | `/api/procurement/report/on-time-rate` | 是 | — | 采购 |
| 32 | `GET` | `/api/prep` | 是 | — | 备料 |
| 33 | `POST` | `/api/prep` | 是 | — | 备料 |
| 34 | `GET` | `/api/prep/{task_id}` | 是 | — | 备料 |
| 35 | `POST` | `/api/prep/{task_id}/subtasks` | 是 | — | 备料 |
| 36 | `PATCH` | `/api/prep/{task_id}/subtasks/{subtask_id}` | 是 | — | 备料 |
| 37 | `GET` | `/api/prep/{task_id}/completion` | 是 | — | 备料 |
| 38 | `GET` | `/api/production/records` | 是 | — | 生产 |
| 39 | `POST` | `/api/production/records` | 是 | — | 生产 |
| 40 | `PATCH` | `/api/production/records/{record_id}` | 是 | — | 生产 |
| 41 | `GET` | `/api/production/progress` | 是 | — | 生产 |
| 42 | `POST` | `/api/production/progress` | 是 | — | 生产 |
| 43 | `GET` | `/api/production/material-issues` | 是 | — | 生产 |
| 44 | `POST` | `/api/production/material-issues` | 是 | — | 生产 |
| 45 | `POST` | `/api/production/material-issues/{issue_id}/resolve` | 是 | — | 生产 |
| 46 | `GET` | `/api/packaging` | 是 | — | 包装 |
| 47 | `POST` | `/api/packaging` | 是 | — | 包装 |
| 48 | `POST` | `/api/packaging/{task_id}/pack` | 是 | — | 包装 |
| 49 | `POST` | `/api/packaging/{task_id}/qc` | 是 | — | 包装 |
| 50 | `GET` | `/api/notification-rules/timeout` | 是 | — | 通知 |
| 51 | `POST` | `/api/notification-rules/timeout` | 是 | admin/supervisor | 通知 |
| 52 | `PATCH` | `/api/notification-rules/timeout/{rule_id}` | 是 | admin/supervisor | 通知 |
| 53 | `GET` | `/api/notification-rules/escalation` | 是 | — | 通知 |
| 54 | `POST` | `/api/notification-rules/escalation` | 是 | admin/supervisor | 通知 |
| 55 | `POST` | `/api/notification-rules/scan` | 是 | — | 通知 |
| 56 | `GET` | `/api/system/users` | 是 | — | 系统 |
| 57 | `POST` | `/api/system/users` | 是 | admin | 系统 |
| 58 | `PATCH` | `/api/system/users/{user_id}` | 是 | admin | 系统 |
| 59 | `DELETE` | `/api/system/users/{user_id}` | 是 | admin | 系统 |
| 60 | `GET` | `/api/system/product-categories` | 是 | — | 系统 |
| 61 | `POST` | `/api/system/product-categories` | 是 | — | 系统 |
| 62 | `DELETE` | `/api/system/product-categories/{item_id}` | 是 | — | 系统 |
| 63 | `GET` | `/api/system/material-categories` | 是 | — | 系统 |
| 64 | `POST` | `/api/system/material-categories` | 是 | — | 系统 |
| 65 | `DELETE` | `/api/system/material-categories/{item_id}` | 是 | — | 系统 |
| 66 | `GET` | `/api/system/process-library` | 是 | — | 系统 |
| 67 | `POST` | `/api/system/process-library` | 是 | — | 系统 |
| 68 | `GET` | `/api/system/operation-logs` | 是 | — | 系统 |
| 69 | `GET` | `/api/system/notifications` | 是 | — | 系统 |
| 70 | `POST` | `/api/system/notifications/{notification_id}/read` | 是 | — | 系统 |
| 71 | `GET` | `/api/system/step-owners` | 是 | — | 系统 |
| 72 | `POST` | `/api/system/step-owners` | 是 | — | 系统 |

**总计：72 个 API 端点**

## 附录 B：代码中已知但未实现的功能

以下功能在模型/代码注释中提及但**未提供对应 API 接口**：

1. **EscalationRule 的 PATCH/DELETE**：模型已定义，但 router 中仅实现了 `GET` 列表和 `POST` 创建
2. **ProcessLibraryItem 的 PATCH/DELETE**：仅实现了 `GET` 列表和 `POST` 创建
3. **OrderAttachment 的 DELETE**：可以上传附件，但无删除附件接口
4. **Sample 的 PATCH/DELETE**：样品创建后不可修改基本信息
5. **PurchaseOrder 的 PATCH**：PO 创建后无更新接口
6. **PrepTask 的 PATCH**：备料任务创建后基本信息不可修改
7. **PackagingTask 的 GET 详情**：无单独获取包装任务详情（含 QC 记录）的接口，列表只返回基本信息
8. **定时任务**：`scan_and_notify` 设计为被定时调用，但代码中未内置 cron 调度器
9. **Alembic 数据库迁移**：已在 `requirements.txt` 中，但当前使用 `Base.metadata.create_all` 方案
