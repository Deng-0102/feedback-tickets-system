# 测试集评测、模块对接与 GitHub 上传

> 面向 3 号：怎么用测试集量化效果、在哪里接 2/4/5/6/7 号的代码、怎么把成果推到 GitHub。

---

## 1. 先纠正：你发的不是 API Key

截图里的 `421d415d-ed9c-4de0-b947-874093213483` 是 **Tracking ID**（表格里 "Tracking ID" 那一列），不是密钥。

DeepSeek（以及绝大多数平台）的 API Key 有两个特征：

- 以 `sk-` 开头，例如 `sk-3f8a...`（长度 30 位以上）；
- **只在创建时显示一次**，关闭弹窗后无法再查看完整值。

你这个页面右上角有「创建 API key」按钮，正确做法：

1. 点「创建 API key」；
2. 名称填 `feedback-ticket-3`（方便以后区分和吊销）；
3. 创建后**立刻复制**，粘贴到项目根目录 `.env`：

```dotenv
ANALYSIS_PROVIDER=deepseek
ANALYSIS_API_KEY=sk-你复制的密钥
ANALYSIS_BASE_URL=https://api.deepseek.com/v1
ANALYSIS_MODEL=deepseek-chat
```

4. **完全重启后端**（`Ctrl+C` 再 `.\start-backend.cmd`，`--reload` 不会重读 `.env`）。

⚠️ 不要用截图里那把标着 **App-managed / 由 Harness 管理** 的 key：它是 DeepSeek Harness 应用自己创建的，额度与管理都归那个应用，可能随时被轮换，混用后账单也分不清。单独建一把课程专用 key。

⚠️ 密钥只放 `.env`，不要写进代码、文档、GitHub、聊天或截图。`.gitignore` 已经忽略 `.env`，但仍要自己确认 `git status` 里没有它。

**验证密钥是否生效**（不启动服务也能测）：

```powershell
cd "D:\inteligent feedback system\feedback-ticket-system-main\backend"
..\.venv\Scripts\python.exe -m scripts.try_analysis "修改密码后一直无法登录，重新安装也没用" --module 账号中心
```

看到 `模型：deepseek-chat`、`状态：SUCCESS`、耗时 1~3 秒，说明接好了。如果报：

| 现象 | 原因 |
|---|---|
| `AUTH: 模型服务认证失败` | key 复制不全、有空格、或已删除 |
| `HTTP 402` / 余额不足 | 没充值，充 10 元即可 |
| `TIMEOUT` | 网络问题，或需要代理；先重试一次 |
| `HTTP 404` | `ANALYSIS_MODEL` 名字写错 |

---

## 2. 用测试集跑出准确率（完整步骤）

测试集文件：`docs/member3/测试集-模板.csv`，25 条，五类各 5 条，含 2 条边界样本（“咨询+权限”“抱怨+建议”）。

### 2.1 先检查文件格式（0 成本）

```powershell
cd "D:\inteligent feedback system\feedback-ticket-system-main\backend"
..\.venv\Scripts\python.exe -m scripts.eval_analysis --dry-run
```

输出 `测试集共 25 条，列名检查通过` 即可。列名必须是：`编号、用户描述、功能模块、人工标准分类`（其余列可留空）。

### 2.2 先用 mock 跑通流程（0 成本）

```powershell
..\.venv\Scripts\python.exe -m scripts.eval_analysis --provider mock --limit 5 --sleep 0
```

它会在 `docs/member3/` 生成 `测试结果.csv` 和 `测试结果-汇总.md`。这一步只证明脚本、CSV、输出都正常，**数字没有意义**（mock 是关键词规则）。

### 2.3 用真实模型跑全量

```powershell
..\.venv\Scripts\python.exe -m scripts.eval_analysis
```

- 默认每条间隔 0.8 秒，25 条约 1~2 分钟；
- 25 次调用约 2.5 万 tokens，费用不到 0.5 元；
- 中途断了加 `--resume`，会按“编号”跳过已有结果。

### 2.4 看结果

打开 `docs/member3/测试结果-汇总.md`，里面有：

- 总体分类准确率；
- 每个分类的准确率（哪一类最差一目了然）；
- 状态分布（SUCCESS / DEGRADED / FAILED 各多少）；
- 平均耗时。

再打开 `测试结果.csv`，人工看一遍“标题”列：

1. 标题能不能直接当工单标题用？能就填“是”，不能填“否”；
2. 标题可用率 = 填“是”的条数 ÷ 25；
3. 把填“否”的行和分类错误的行单独标黄，分析原因。

### 2.5 回填报告

报告 4.4.9 节两个“待填”替换成真实数字，并写一句方法：

> 测试集共 25 条，覆盖五类各 5 条，另含 2 条多意图边界样本。分类准确率 __%（__/25），标题可用率 __%（__/25），平均耗时 __ ms。错误集中在“建议类被判为功能异常”，在提示词中补充判定要点后，v1.1 准确率由 __% 提升到 __%。

### 2.6 参数速查

| 参数 | 作用 |
|---|---|
| `--file 路径` | 换测试集文件 |
| `--output 路径` | 换结果输出位置 |
| `--provider mock` | 强制离线演示，不花钱 |
| `--limit N` | 只跑前 N 条 |
| `--sleep 0.8` | 每条间隔，防限流；mock 可设 0 |
| `--resume` | 跳过已有结果，续跑 |
| `--dry-run` | 只校验 CSV，不调模型 |

---

## 3. 在哪里接别人的代码（接口位置清单）

你的模块已经按“可替换”设计，接入点都在下面这些位置，**不需要改核心算法**。

### 3.1 数据库（2 号 / 7 号）

| 项 | 位置 |
|---|---|
| 连接串 | 项目根目录 `.env` 的 `DATABASE_URL` |
| 引擎与会话 | `backend/app/db/session.py` |
| 你的表 | `backend/app/models/analysis.py`（`analysis_results`） |

换 MySQL 的步骤（开发阶段）：

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -e '.[dev,mysql]'
```

```dotenv
DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/feedback_ticket?charset=utf8mb4
```

重启后 `Base.metadata.create_all` 会在空库建表。**注意**：`create_all` 只建缺失的表，不会改字段；正式部署要换 Alembic 迁移（7 号负责）。

你的代码没有裸 SQL，全部走 SQLAlchemy `Session`，所以换库不用改分析模块。

### 3.2 工单字段（2 号）

你依赖的字段只有 6 个，集中在 `analysis_service.py`：

| 字段 | 用途 | 出现位置 |
|---|---|---|
| `Ticket.description` | 模型输入 | `analyse_ticket()` 调用 `run_analysis` |
| `Ticket.feature_module` | 模型输入 | 同上 |
| `Ticket.title` | 写回标题 | `apply` 分支 |
| `Ticket.summary` | 写回摘要 | 同上 |
| `Ticket.category` | 写回分类 | 同上 |
| `Ticket.submitter_id` / `assignee_id` | 可见性判断 | `routes/analysis.py` 的 `_visible_ticket_or_404` |

如果 2 号改了字段名或加了 `deleted_at` 软删除，改这 2 个文件即可。**约定**：分析只写 title/summary/category，不碰状态、不碰负责人。

### 3.3 相似问题检索（4 号）——已留扩展点

位置：`backend/app/services/analysis_events.py`。

分析成功、事务提交后，会依次调用注册的回调；单个回调失败只记日志，不影响分析结果。4 号只需要新增自己的模块并注册一次：

```python
# backend/app/services/similarity.py（4 号写）
from app.services.analysis_events import register_post_analysis_hook

def index_for_search(db, ticket, view):
    # view.title / view.summary / view.keywords 就是整理后的文本
    # 这里做 TF-IDF 建索引或写检索表
    ...

register_post_analysis_hook(index_for_search)
```

注册位置建议放在 4 号模块被导入的地方（例如 `app/api/router.py` 里 `import app.services.similarity`），避免循环导入。

另一种更松的耦合方式：4 号直接调 `GET /api/v1/tickets/{id}/analysis` 拿 `title/summary`，不依赖 Python 回调。

### 3.4 用户端 / 管理端（5、6 号）

| 需求 | 接口 | 关键字段 |
|---|---|---|
| 提交前预览 | `POST /api/v1/analysis/preview` | `title/category/summary/confidence` |
| 提交后展示结果 | `GET /api/v1/tickets/{id}/analysis` | 同上 + `status` |
| 手动重新整理 | `POST /api/v1/tickets/{id}/analysis?force=true` | 需要 ADMIN 或工单可见 |
| 看板“待人工确认” | 列表数据 + `needs_manual_review` | 也可用 `GET` 结果的 `status=DEGRADED` |

前端文案严格按 `status` 区分：`SUCCESS`“已自动整理”、`DEGRADED`“请确认分类”、`FAILED`“请手动选择分类”。

### 3.5 权限与配置（1 号）

- 权限：`routes/analysis.py` 用 `get_current_user` + 本地 `_visible_ticket_or_404`。如果 1 号抽了统一的 `get_visible_ticket` 依赖，替换这个函数即可（只有一处调用点）。
- 配置：`analysis_config.py` 独立读 `ANALYSIS_*`。如果团队要求所有配置统一到 `core/config.py`，把 `get_analysis_settings()` 改成从 `Settings` 取值即可，其他文件不用动。

### 3.6 统计口径（6 号 / 报告）

- 数字一律由 SQL 统计，模型只写文字；
- 建议口径：解决率 = `RESOLVED + CLOSED` / 总数；平均处理时长 = `resolved_at - created_at`；
- 你的模块只提供 `analysis_results`（分类建议、置信度）和 `AI_ANALYSIS` 处理记录，不参与统计计算。

---

## 4. 上传到 GitHub（awqssl/feedback-ticket-system）

当前状态：本地目录**没有 `.git`**（1 号的压缩包不带版本库）。远程仓库已存在，但你本地不是从它 clone 的，两者历史无关。

### 4.1 先配好网络（国内常见）

```powershell
# 如果你用 Clash，默认混合端口 7890
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
# 取消代理
# git config --global --unset http.proxy
```

测试：`git ls-remote https://github.com/awqssl/feedback-ticket-system.git`，能列出分支即通。

### 4.2 路线 A（推荐，最干净）：clone 新目录，把 3 号文件拷进去

```powershell
cd D:\
git clone https://github.com/awqssl/feedback-ticket-system.git feedback-repo
cd feedback-repo
git branch -a          # 看有哪些分支，通常有 main/develop
git switch develop     # 没有 develop 就用 main
git switch -c feature/3-ai-analysis
```

然后把**新增文件**从 `D:\inteligent feedback system\feedback-ticket-system-main` 拷过来（目录结构一致）：

```text
backend/app/services/analysis_config.py
backend/app/services/analysis_prompts.py
backend/app/services/analysis_events.py
backend/app/services/llm_client.py
backend/app/services/analysis_service.py
backend/app/schemas/analysis.py
backend/app/api/routes/analysis.py
backend/tests/test_analysis.py
backend/scripts/try_analysis.py
backend/scripts/eval_analysis.py
docs/member3/            （整个目录：5 篇文档 + 测试集 + 测试结果）
start-backend.cmd
```

再对**共享文件**做 4 处小改（建议在 GitHub 网页或 VS Code 里逐处改，不要整文件覆盖，避免盖掉 1 号的新改动）：

| 文件 | 改什么 |
|---|---|
| `backend/app/api/router.py` | 导入 `analysis`，加 2 行 `include_router` |
| `backend/pyproject.toml` | `dependencies` 里加 `"httpx>=0.28,<1.0"` |
| `.env.example` | 末尾加 `ANALYSIS_*` 配置块 |
| `docs/api-conventions.md` | 加第 7 节（智能分析接口）和 50300 错误码 |

改完自测：

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

> 新 clone 的仓库没有 `.venv`。要么把旧项目的 `.venv` 复制过来（路径会变，建议重建），要么重新建：`py -m venv .venv` 再 `..\.venv\Scripts\python.exe -m pip install -e '.[dev]'`。

提交并推送：

```powershell
cd D:\feedback-repo
git status                       # 确认没有 .env、.venv、*.db
git add backend docs .env.example start-backend.cmd
git commit -m "feat(analysis): 智能分类摘要、模型异常处理与失败降级"
git push -u origin feature/3-ai-analysis
```

然后在 GitHub 网页上点 **Compare & pull request**，base 选 `develop`，填 PR 描述（见 4.4），@1 号 review。

### 4.3 路线 B：保留现有目录，直接接远程

适合你不想再拷文件：

```powershell
cd "D:\inteligent feedback system\feedback-ticket-system-main"
git init
git add .
git commit -m "feat(analysis): 智能分析模块与文档"
git remote add origin https://github.com/awqssl/feedback-ticket-system.git
git fetch origin
git switch -c feature/3-ai-analysis
git merge origin/main --allow-unrelated-histories   # 有 develop 就 merge origin/develop
```

两段历史无关，`merge` 时共享文件（README、router.py、pyproject.toml）大概率冲突：

- `git status` 看冲突文件；
- 打开文件搜 `<<<<<<<`，保留双方内容并手动合并；
- `git add 文件` → `git commit`；
- `git push -u origin feature/3-ai-analysis`。

> 路线 B 容易出现“把 1 号的新代码盖掉”的问题，**新手优先用路线 A**。无论哪条路线，`.env`、`.venv`、`feedback_ticket.db` 都被 `.gitignore` 忽略，不会上传；提交前用 `git status` 再确认一次。

### 4.4 PR 描述模板

```markdown
## 做了什么
- 新增智能分析服务（提示词、模型客户端、结构化校验、失败降级）
- 新增 3 个接口：工单分析 / 读取结果 / 提交页预览
- 新增 10 个自动测试，pytest 19 passed
- 新增测试集评测脚本与 25 条测试集，分类准确率 __%

## 改了哪些共享文件
- router.py：注册 2 个路由
- pyproject.toml：httpx 提为运行依赖
- .env.example：新增 ANALYSIS_* 配置
- docs/api-conventions.md：第 7 节

## 自测
- pytest 19 passed
- 真实模型：25 条测试集，准确率 __%，标题可用率 __%
- 失败场景：错 Key / 超时 / 非 JSON 均降级为 FAILED，工单未被修改

## 需要谁确认
@1号 共享文件；@5号 预览字段；@2号 写回方式
```

### 4.5 常见错误

| 报错 | 原因 / 解决 |
|---|---|
| `Authentication failed` | GitHub 不再支持密码；用 Personal Access Token 当密码，或安装 Git Credential Manager 走浏览器登录 |
| `Connection was reset` | 网络问题，配 4.1 的代理 |
| `rejected (non-fast-forward)` | 远程有你的新提交，先 `git pull --rebase origin 分支名` |
| `fatal: refusing to merge unrelated histories` | 路线 B 忘加 `--allow-unrelated-histories` |
| 提交里出现 `.env` | 立刻 `git rm --cached .env` 并提交；**如果已经 push，去平台吊销密钥** |
| 文件太大（>100MB） | 不要提交 `.venv`、数据库、截图原图；用 `.gitignore` |

---

## 5. 交付前检查清单

- [ ] `.env` 里有真实 key，且 `git status` 看不到 `.env`
- [ ] `pytest` 19 passed
- [ ] 25 条测试集跑完，`测试结果-汇总.md` 有真实准确率
- [ ] 报告 4.4.9 的“待填”已替换
- [ ] 失败场景截图：错 Key、超时、非 JSON
- [ ] 分支名 `feature/3-ai-analysis`，PR 指向 `develop`
- [ ] PR 里 @ 了 1、2、5 号
