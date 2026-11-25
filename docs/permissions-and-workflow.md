# 角色权限与工单流程

## 1. 统一角色

角色值以 `backend/app/models/enums.py` 为准：

| 角色 | 枚举 | 职责 |
|---|---|---|
| 普通用户 | `USER` | 提交反馈、查看和操作自己的工单 |
| 处理人员 | `AGENT` | 查看并处理分配给自己的工单 |
| 管理员 | `ADMIN` | 查看全部工单、分配负责人、管理流程 |

前端已经为三个角色提供 `/user`、`/agent`、`/admin` 首页和路由守卫。前端拦截不是安全措施，所有敏感接口仍须使用后端的 `get_current_user` 或 `require_roles` 校验。

## 2. 第一阶段权限矩阵

| 操作 | `USER` | `AGENT` | `ADMIN` |
|---|---|---|---|
| 登录、查看当前身份 | 是 | 是 | 是 |
| 创建工单 | 是 | 否 | 是 |
| 列出工单 | 仅本人提交 | 仅分配给本人 | 全部 |
| 查看工单详情 | 仅本人提交 | 仅分配给本人 | 全部 |
| 查看用户列表 | 否 | 否 | 是 |
| 分配或重新分配负责人 | 否 | 否 | 是 |
| 开始处理 | 否 | 仅本人负责 | 是 |
| 标记已解决 | 否 | 仅本人负责 | 是 |
| 确认关闭 | 仅本人提交 | 否 | 是 |
| 重新打开已解决工单 | 仅本人提交 | 否 | 是 |

为了避免通过工单编号推测其他人的数据，当前详情接口对不可见工单统一返回“工单不存在”。

管理员分配时，负责人必须是处于启用状态的 `AGENT`。重新分配会更新负责人；只有工单处于 `PENDING_ASSIGNMENT` 时，分配操作才同时把状态改为 `PENDING`，其他状态保持不变。

## 3. 状态定义

| 状态 | 中文名称 | 含义 |
|---|---|---|
| `PENDING_ASSIGNMENT` | 待分配 | 新工单已保存，尚未确定负责人 |
| `PENDING` | 待处理 | 已分配负责人，等待开始处理 |
| `IN_PROGRESS` | 处理中 | 负责人已经开始调查或处理 |
| `RESOLVED` | 已解决 | 负责人提交了解决结果，等待用户确认 |
| `CLOSED` | 已关闭 | 用户或管理员确认问题已解决，流程结束 |
| `REOPENED` | 已重新打开 | 用户或管理员认为问题仍未解决，需继续处理 |

## 4. 合法状态转换

当前代码中的唯一合法转换如下：

| 原状态 | 操作角色 | 目标状态 | 典型动作 |
|---|---|---|---|
| `PENDING_ASSIGNMENT` | `ADMIN` | `PENDING` | 分配有效处理人员 |
| `PENDING` | `AGENT`、`ADMIN` | `IN_PROGRESS` | 开始处理 |
| `IN_PROGRESS` | `AGENT`、`ADMIN` | `RESOLVED` | 提交处理结果 |
| `RESOLVED` | `USER`、`ADMIN` | `CLOSED` | 确认解决 |
| `RESOLVED` | `USER`、`ADMIN` | `REOPENED` | 问题未解决，重新打开 |
| `REOPENED` | `AGENT`、`ADMIN` | `IN_PROGRESS` | 继续处理 |

其中 `AGENT` 只能操作分配给自己的工单，`USER` 只能操作自己提交的工单。`CLOSED` 在第一阶段是终态，不能再次打开；若团队希望支持“关闭后重新打开”，必须先修改状态机、测试和本文档，再开放页面操作。

流程可表示为：

```text
PENDING_ASSIGNMENT
  └─ ADMIN 分配 → PENDING
                       └─ AGENT/ADMIN 开始 → IN_PROGRESS
                                                └─ AGENT/ADMIN 解决 → RESOLVED
                                                                            ├─ USER/ADMIN 确认 → CLOSED
                                                                            └─ USER/ADMIN 重开 → REOPENED
                                                                                                      └─ AGENT/ADMIN 继续 → IN_PROGRESS
```

`PENDING_ASSIGNMENT → PENDING` 只能通过分配接口完成，确保负责人和状态同时更新。状态接口会执行角色和转换校验，非法转换返回 HTTP `409`。工单重新打开时会清空当前的 `resolved_at`，先前的解决操作仍保留在处理记录中。

## 5. 状态变更记录

创建、分配和状态变更都应写入 `TicketRecord`：

- `operator_id`：操作者。
- `action`：例如 `CREATE`、`ASSIGN`、`STATUS_CHANGE`。
- `content`：处理说明或补充信息。
- `from_status`、`to_status`：转换前后的状态。
- `created_at`：操作时间。

后续实现页面时，解决说明和重新打开原因应设为必填；当前第一阶段 Schema 仍允许状态说明为空，这是后续需要收紧的业务校验点。

## 6. 权限修改流程

新增角色、权限或状态时，负责人必须同步完成：

1. 修改后端枚举、依赖或状态机。
2. 更新 API 测试，至少包含允许和拒绝两类用例。
3. 更新前端 TypeScript 类型、路由和按钮可见性。
4. 更新本文档与相关报告图表。
5. 通知受影响的模块负责人后再合并。
