# API 约定

## 1. 基础规则

- API 版本前缀：`/api/v1`。
- 数据格式：UTF-8 JSON。
- 字段命名：`snake_case`，与 FastAPI Schema 保持一致。
- 认证方式：`Authorization: Bearer <access_token>`。
- HTTP 状态码表示传输与请求结果，响应体中的 `code` 表示统一业务结果。
- Swagger 文档默认地址：`/docs`。

除健康检查和登录外，业务接口默认需要登录。前端使用 `frontend/src/api/http.ts` 的 Axios 实例统一附加令牌，不应在页面中重复实现请求拦截器。

## 2. 统一响应

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

无返回数据时，`data` 为 `null`。具体成功消息可以是“登录成功”“反馈提交成功”“分配成功”或“状态更新成功”。

业务错误：

```json
{
  "code": 40300,
  "message": "当前角色无权执行此操作",
  "data": null
}
```

当前错误码约定：

| HTTP 状态 | `code` | 使用场景 |
|---:|---:|---|
| 400 | `40000` | 请求业务参数不合法 |
| 401 | `40100` | 未登录、令牌无效或登录过期 |
| 403 | `40300` | 已登录但角色无权操作 |
| 404 | `40400` | 资源不存在或当前用户不可见 |
| 409 | `40900` | 工单状态转换冲突 |
| 422 | `42200` | Pydantic 参数校验失败 |
| 500 | `50000` | 未处理的服务端异常 |
| 503 | `50300` | 智能分析未配置密钥或已关闭（`ANALYSIS_PROVIDER=off`） |

参数校验失败时，`data.errors` 包含每项错误的 `loc`（字段位置）、`msg`（错误描述）和 `type`（类型），不返回用户的原始输入。前端提示用户时优先读取 `message`。

## 3. 当前端点

| 方法 | 路径 | 认证与权限 | 说明 |
|---|---|---|---|
| `GET` | `/api/v1/health` | 公开 | 健康检查 |
| `POST` | `/api/v1/auth/login` | 公开 | 用户名密码登录 |
| `GET` | `/api/v1/auth/me` | 登录 | 获取当前用户 |
| `POST` | `/api/v1/auth/logout` | 登录 | 无状态退出确认；客户端删除令牌 |
| `GET` | `/api/v1/users` | `ADMIN` | 列出用户，供分配负责人使用 |
| `POST` | `/api/v1/tickets` | `USER`、`ADMIN` | 创建工单 |
| `GET` | `/api/v1/tickets` | 登录 | 按角色返回可见工单 |
| `GET` | `/api/v1/tickets/{ticket_id}` | 登录且可见 | 获取工单详情 |
| `PATCH` | `/api/v1/tickets/{ticket_id}/assign` | `ADMIN` | 分配或重新分配负责人 |
| `PATCH` | `/api/v1/tickets/{ticket_id}/status` | 登录且可见 | 按角色和状态机更新状态 |

当前列表接口直接返回数组，尚未实现分页、筛选和排序参数。后续新增分页时应先统一分页 Schema，再同步修改前端类型，不能让不同列表使用不同结构。

## 4. 请求示例

登录：

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user001",
  "password": "Demo123!"
}
```

创建工单：

```http
POST /api/v1/tickets
Authorization: Bearer <token>
Content-Type: application/json

{
  "description": "修改密码后一直无法登录，重新安装后仍未解决。",
  "feature_module": "账号中心"
}
```

`description` 长度为 10 到 5000 个字符，`feature_module` 长度为 1 到 100 个字符。

管理员分配负责人：

```http
PATCH /api/v1/tickets/1/assign
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "assignee_id": 2
}
```

更新状态：

```http
PATCH /api/v1/tickets/1/status
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "IN_PROGRESS",
  "content": "开始检查用户账号状态和登录日志。"
}
```

状态值必须使用 `PENDING_ASSIGNMENT`、`PENDING`、`IN_PROGRESS`、`RESOLVED`、`CLOSED`、`REOPENED` 之一，并符合角色和状态转换规则。

## 5. 认证约定

登录成功返回 `access_token`、`token_type` 和用户信息。当前后端签发带 `sub`、`role`、`iat`、`exp` 的 HMAC-SHA256 令牌；默认有效期为 120 分钟，可通过环境变量调整。

前端把令牌和用户信息保存在 `localStorage`，重新打开页面时通过 `/auth/me` 确认登录状态。已认证的请求收到 HTTP `401` 时，前端清除本地会话并返回登录页。后端退出接口采用无状态模式，不维护令牌黑名单，已签发令牌在过期前不会因单次退出自动作废。

共享部署必须设置新的高强度 `SECRET_KEY`。不得把令牌、密码、`.env` 内容或真实用户反馈写入日志、截图和 Git 提交。

## 6. 接口变更规则

- 新接口放在 `/api/v1` 下，并使用统一 `ApiResponse`。
- 请求和响应必须定义 Pydantic Schema，不能直接返回 ORM 对象或临时字典。
- 修改枚举、字段或错误码时，必须同步更新前端类型和自动测试。
- 模型生成结果必须经过 Schema 校验；模型超时或格式错误不能导致原始反馈丢失。
- 统计接口只返回程序计算的真实值，分析报告模块不得自行猜测数量或解决率。
- 破坏兼容性的改动需要团队确认；必要时新增 API 版本，不能静默改变旧字段含义。

## 7. 智能分析接口（3 号，第二阶段新增）

对应代码：`backend/app/api/routes/analysis.py`、`backend/app/services/analysis_service.py`。
分类枚举、`title`、`summary` 等字段仍以 `Ticket` 为准，本节只新增“整理建议”的读写能力。

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| `POST` | `/api/v1/tickets/{ticket_id}/analysis?force=false&apply=true` | 登录且可见该工单 | 对已有工单执行整理；默认复用历史结果，`force=true` 重新调用模型；`apply=false` 只出建议不写回工单 |
| `GET` | `/api/v1/tickets/{ticket_id}/analysis` | 登录且可见该工单 | 读取该工单最近一次成功的分析结果，没有则返回 `40400` |
| `POST` | `/api/v1/analysis/preview` | 登录 | 提交页预览，不创建工单、不写库 |

`POST /tickets/{id}/analysis` 成功响应（`status=DEGRADED` 表示置信度低或分类被归一化，需要人工确认）：

```json
{
  "code": 0,
  "message": "智能整理完成，但置信度不高，请人工确认分类",
  "data": {
    "ticket_id": 12,
    "result_id": 5,
    "status": "DEGRADED",
    "title": "修改密码后无法登录",
    "category": "ACCOUNT_LOGIN",
    "category_label": "账号登录",
    "summary": "用户修改密码后无法登录，重装后仍未解决，影响正常使用。",
    "keywords": ["密码修改", "无法登录"],
    "confidence": 0.55,
    "reason": "故障发生在修改密码之后",
    "model_name": "deepseek-chat",
    "prompt_version": "v1.0",
    "needs_manual_review": true,
    "fallback_used": false,
    "applied": true,
    "cached": false,
    "error": null,
    "elapsed_ms": 2380
  }
}
```

模型失败时**不返回 5xx**：接口仍返回 `200`，`data.status` 为 `FAILED`，`data.error` 以错误类型开头（如 `TIMEOUT:`、`BAD_FORMAT:`、`AUTH:`），`data.applied` 为 `false`，工单标题、分类、摘要保持不变，同时写入一条 `action=AI_ANALYSIS_FAILED` 的处理记录。这样 5、6 号页面可以“先保存反馈、再提示人工分类”，不会因模型故障丢失用户提交的内容。

`POST /analysis/preview` 请求体：

```json
{ "description": "修改密码后一直无法登录，重新安装也没有解决。", "feature_module": "账号中心" }
```

响应 `data` 与上表结构一致，但 `ticket_id`、`result_id` 为 `null`，`applied` 恒为 `false`。

其他约定：

- `keywords` 最多 6 个，单个不超过 20 字；`title` 不超过 40 字；`summary` 不超过 200 字，超长由服务端截断并在 `issues` 中记录。
- `confidence` 缺失或低于 `0.6` 时 `needs_manual_review=true`，管理员可人工修改分类，人工结果以 `Ticket.category` 为准。
- 复用历史结果时 `cached=true` 且不产生新的模型调用与费用；需要重新整理必须显式传 `force=true`。
- 真实模型由 `ANALYSIS_PROVIDER`、`ANALYSIS_API_KEY`、`ANALYSIS_BASE_URL`、`ANALYSIS_MODEL` 配置；`ANALYSIS_PROVIDER=mock` 为离线演示，结果中 `model_name=mock-demo-v1`，不得作为真实模型效果写进报告。
