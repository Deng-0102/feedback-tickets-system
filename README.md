# 智能用户反馈分析与工单管理系统

这是课程项目的第一阶段基础框架。当前版本用于统一团队的开发环境、认证方式、角色权限和工单状态规则，后续成员可在此基础上继续实现智能分类、相似问题检索、统计看板和分析报告。

## 当前已完成

- FastAPI 后端基础结构、SQLite 开发数据库和自动建表。
- `USER`、`AGENT`、`ADMIN` 三类角色的登录认证与后端权限校验。
- Vue 3 登录页、角色首页、路由守卫和令牌存储。
- 工单创建、按角色查询、详情查看、管理员分配和合法状态流转。
- 统一成功/失败响应格式、参数校验和基础自动测试。
- 三个演示账号的初始化脚本。

第一阶段不包含截图上传、智能分类与摘要、相似问题检索、处理记录展示、统计看板和分析报告生成。这些能力的接口与页面应在后续阶段按文档约定扩展，不能把模拟数据当作真实实现。

## 项目结构

```text
project/
├─ backend/                   # FastAPI、SQLAlchemy、测试和演示数据脚本
│  ├─ app/
│  ├─ scripts/
│  ├─ tests/
│  └─ pyproject.toml
├─ frontend/                  # Vue 3、Vite、Pinia、Vue Router
│  ├─ src/
│  └─ package.json
├─ docs/                      # 架构、权限、接口和团队协作约定
├─ .env.example
└─ README.md
```

更详细的说明见：

- [系统架构](docs/architecture.md)
- [角色权限与工单流程](docs/permissions-and-workflow.md)
- [API 约定](docs/api-conventions.md)
- [团队协作规则](docs/team-workflow.md)

## 环境要求

- Python 3.11 或更高版本。
- Node.js 24 和 pnpm 11。团队使用 `frontend/pnpm-lock.yaml` 统一依赖版本。
- Git。

## Windows PowerShell 启动后端

以下命令均从项目根目录开始执行。

1. 创建并启用虚拟环境：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 阻止当前窗口执行激活脚本，可以只为本进程放宽策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

2. 安装后端及开发依赖：

```powershell
Set-Location .\backend
python -m pip install --upgrade pip
pip install -e '.[dev]'
```

3. 返回项目根目录并创建本地配置：

```powershell
Set-Location ..
Copy-Item .env.example .env
```

开发环境默认使用 SQLite。开发时可将 `SECRET_KEY` 留空，服务重启后原令牌失效；共享部署时需设置 `APP_ENV=production` 和至少 32 字符的随机签名密钥。如需 MySQL，请安装可选依赖并更新 `DATABASE_URL`：

```powershell
Set-Location .\backend
pip install -e '.[dev,mysql]'
Set-Location ..
```

4. 初始化演示账号：

```powershell
Set-Location .\backend
python -m scripts.seed_demo
```

演示账号如下，初始密码均为 `Demo123!`：

| 账号 | 角色 |
|---|---|
| `user001` | 普通用户 `USER` |
| `agent001` | 处理人员 `AGENT` |
| `admin` | 管理员 `ADMIN` |

可在执行 seed 前设置临时环境变量覆盖演示密码：

```powershell
$env:DEMO_PASSWORD = 'YourStrongDemoPassword'
python -m scripts.seed_demo
```

演示密码只用于本地开发，不得用于共享测试或正式部署。

5. 启动 API：

```powershell
python -m uvicorn app.main:app --reload
```

启动后可访问：

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>

6. 运行测试：

```powershell
python -m pytest
```

## Windows PowerShell 启动前端

打开另一个 PowerShell 窗口，在项目根目录执行：

```powershell
Set-Location .\frontend
pnpm.cmd install --frozen-lockfile
pnpm.cmd run dev
```

如果依赖已安装，但 PowerShell 提示找不到 `pnpm.cmd`，可以在 `frontend` 目录直接启动：

```powershell
.\start-dev.cmd
```

这个入口直接运行已安装的 Vite，会优先使用系统的 Node.js，其次尝试使用本机缓存的 Codex Node.js。

默认页面地址为 <http://127.0.0.1:5173>。开发服务器会把 `/api` 请求代理到本地后端；也可以通过 `VITE_API_BASE_URL` 指定其他 API 地址。

提交代码前建议执行：

```powershell
pnpm.cmd run type-check
pnpm.cmd run build
```

本阶段页面可演示三角色登录、进入各自工作台和退出。工单流转目前通过 [API 接口约定](docs/api-conventions.md) 和本地 Swagger 文档验证；工作台里的业务入口留给后续模块接入。

## 开发入口

- 后端 API 前缀：`/api/v1`
- 前端角色首页：`/user`、`/agent`、`/admin`
- 后端角色和状态枚举：`backend/app/models/enums.py`
- 状态流转规则：`backend/app/services/ticket_workflow.py`
- 前端路由权限：`frontend/src/router/index.ts`

涉及角色、状态、接口字段或数据库结构的修改属于跨模块变更，必须先在团队内确认并同步更新代码、测试和 `docs/` 文档。
