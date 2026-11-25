# 团队开发与模块交付规则

## 1. 分支策略

建议使用以下长期分支：

- `main`：可演示、可提交的稳定版本。
- `develop`：日常集成分支，合并后必须能够启动并通过测试。

每项任务从 `develop` 创建短期分支：

```text
feature/1-auth-permission
feature/2-ticket-backend
feature/3-ai-analysis
feature/4-similarity-search
feature/5-user-pages
feature/6-admin-dashboard
test/7-integration
docs/1-report-outline
fix/ticket-status-check
```

禁止直接在 `main` 上开发。跨模块修改需要先通知相关负责人，避免两个人同时改同一个枚举、Schema 或接口。

## 2. 提交信息

提交应小而完整，推荐格式：

```text
feat(auth): 完成三角色登录权限校验
feat(ticket): 增加工单分配接口
fix(workflow): 拒绝非法状态转换
test(auth): 补充越权访问用例
docs(api): 更新工单状态接口说明
refactor(search): 拆分文本预处理逻辑
```

一个提交只处理一类问题。不要提交 `.env`、数据库文件、虚拟环境、`node_modules`、真实反馈、真实密码或访问令牌。

## 3. 合并前检查

提交合并请求前，开发者至少完成：

- 后端：在 `backend/` 运行 `pytest`。
- 前端：在 `frontend/` 运行 `pnpm run type-check` 和 `pnpm run build`。
- 手工验证本模块主流程和一个失败场景。
- 检查角色权限和数据归属，而不只是页面按钮是否隐藏。
- 接口变化已经同步更新 Schema、前端类型、测试和 `docs/`。
- 新配置只写入 `.env.example` 的安全示例，不提交真实值。

## 4. 模块负责人和协作边界

| 成员 | 主要代码范围 | 必须参与确认的共享内容 |
|---|---|---|
| 1 号 | 项目基础、认证、角色权限、总体结构 | 角色、公共配置、编码规范、跨模块集成 |
| 2 号 | 工单后端、数据库、处理记录 | 表结构、状态字段、事务和数据口径 |
| 3 号 | 标题、摘要、分类与报告生成 | 智能结果 Schema、失败降级、模型配置 |
| 4 号 | 文本处理和相似问题检索 | 检索输入输出、排序规则、测试集 |
| 5 号 | 用户端页面 | 用户操作流程、表单和用户权限 |
| 6 号 | 管理端、统计看板和报告展示 | 管理操作、统计口径、导出格式 |
| 7 号 | 测试、部署和缺陷跟踪 | 测试环境、演示数据、发布检查 |

负责人拥有模块实现责任，但不能单方面改变共享协议。下列文件或概念属于共享边界：

- 角色、工单分类和状态枚举。
- 数据库主外键和字段含义。
- API 路径、请求/响应字段及错误码。
- 状态转换、解决率和处理时长的计算口径。
- 登录令牌、环境变量和部署方式。

## 5. 每项模块的交付物

每个人的模块都必须同时交付：

1. **可运行代码**：入口清楚，配置示例完整，不依赖个人电脑的绝对路径。
2. **报告材料**：需求、设计、关键实现和当前限制，与实际代码一致。
3. **图表或截图**：使用测试数据，能够证明功能真实运行。
4. **自测记录**：记录输入、步骤、预期结果、实际结果和是否通过。

如果功能没有完成，应明确标记“未完成”或“后续计划”，不得用静态截图或模拟文本冒充实际运行结果。

## 6. 接口协作流程

涉及前后端或两个后端模块时，先确定接口合同再编码：

1. 提交接口路径、请求 JSON、响应 JSON 和错误场景。
2. 相关负责人确认字段、枚举和权限。
3. 后端实现 Schema 和测试；前端按同一合同实现类型与调用。
4. 完成联调，记录至少一个成功和一个失败场景。
5. 更新 `docs/api-conventions.md` 和报告材料。

智能分析与相似检索必须允许失败降级：原始反馈先可靠保存，分析失败时保留错误信息并允许人工分类，不能阻塞工单创建。

## 7. 第一阶段完成标准

第一阶段只有同时满足以下条件才算完成：

- 所有成员能按 README 启动后端并获得演示账号。
- 三种角色能登录并进入对应首页。
- 未登录、越权访问和登录失败都有明确响应。
- 用户、处理人员和管理员只能看到权限范围内的工单。
- 工单可完成创建、分配、处理、解决、确认或重新打开的合法流程。
- 非法状态转换被后端拒绝并有自动测试。
- 文档、枚举、API 和页面使用相同术语。

智能分类、相似检索、统计看板和报告生成不属于第一阶段验收条件；它们是下一阶段的独立模块，完成后再加入总体演示流程。

## 8. 周期性同步

建议每次短会只同步四项：

- 上次承诺是否完成，能否现场运行。
- 当前接口或数据结构是否影响别人。
- 下一步具体交付物和完成时间。
- 是否存在需要组长协调的阻塞。

1 号负责维护共同约定和全文一致性；各模块负责人对自己提供的代码、截图、数据和报告材料真实性负责。

## 9. GitHub 首次协作

1 号在 GitHub 创建一个空的私有仓库。已有本地提交时，创建仓库不要勾选初始化 README、`.gitignore` 或许可证。复制仓库页面的 HTTPS 地址并替换以下示例地址，在项目根目录运行：

```powershell
git remote add origin https://github.com/YOUR-ACCOUNT/feedback-ticket-system.git
git push -u origin main
git push -u origin develop
```

推送后，在 GitHub 仓库进入 **Settings → Collaborators → Add people**，按 GitHub 用户名邀请组员。组员接受邀请后，在保存项目的上一级目录克隆仓库：

```powershell
git clone https://github.com/YOUR-ACCOUNT/feedback-ticket-system.git
cd feedback-ticket-system
git switch develop
```

每项任务先同步 `develop`，再创建自己的功能分支。以下以 2 号为例：

```powershell
git switch develop
git pull --ff-only
git switch -c feature/2-ticket-backend
```

修改并自测后，运行 `git status` 检查文件，用 `git add -- 文件路径` 暂存本次改动，提交并推送分支：

```powershell
git commit -m "feat(ticket): 完善工单处理"
git push -u origin feature/2-ticket-backend
```

在 GitHub 上创建 Pull Request，将目标分支（base）选为 `develop`，来源分支（compare）选为自己的功能分支。1 号检查改动与自测结果后合并。
