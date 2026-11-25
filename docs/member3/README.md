# 3 号智能分析模块：文档与使用入口

本目录只放 3 号（智能分类 / 标题摘要 / 模型接口 / 异常处理）的说明、报告素材和测试记录。代码在 `backend/`，不在这里。

## 先读哪一篇

| 顺序 | 文档 | 什么时候看 |
|---|---|---|
| 1 | [01-全流程实施指南.md](01-全流程实施指南.md) | **第一次接手时从头读**：软件清单、30 分钟跑通、8 步开发流程、时间计划、FAQ |
| 2 | [03-模型接口与提示词契约.md](03-模型接口与提示词契约.md) | 联调前看：接口 JSON、提示词全文、校验规则、错误码 |
| 3 | [04-测试用例与自测记录.md](04-测试用例与自测记录.md) | 写报告第 5 章、准备答辩前看：9 个自动测试、手工用例、失败场景怎么造 |
| 4 | [02-第4章详细设计-统稿提纲与3号章节.md](02-第4章详细设计-统稿提纲与3号章节.md) | 写报告时看：第 4 章结构 + 4.4 节正文（可直接粘贴） |
| 5 | [05-答辩演示脚本.md](05-答辩演示脚本.md) | 答辩前一周看：8 分钟流程、演示命令、9 个常见提问回答 |
| — | [测试集-模板.csv](测试集-模板.csv) | 量化模型效果时用：25 条覆盖五类的反馈，填模型结果和准确率 |

## 当前状态（2026-11-17）

| 项目 | 状态 |
|---|---|
| 后端代码 | 已完成：配置、提示词、模型客户端、分析服务、3 个接口、命令行工具 |
| 自动测试 | `pytest` 18 passed（本模块 9 个） |
| 本地环境 | `.venv` 已创建，依赖已装；`.env` 已生成，当前 `ANALYSIS_PROVIDER=mock` |
| 演示数据 | 已初始化 `user001` / `agent001` / `admin`，密码 `Demo123!` |
| 真实模型 | **未接入**（需要你申请 Key 并改 `.env`） |
| 测试集指标 | **未测**（用模板跑 25 条后回填报告） |
| 第 4 章统稿 | 4.4、4.7 已写；4.1/4.2/4.3/4.5/4.6 待收队友素材 |

## 30 秒验证

```powershell
cd "D:\inteligent feedback system\feedback-ticket-system-main"
.\start-backend.cmd                 # 启动后端（免激活虚拟环境）
cd backend
..\.venv\Scripts\python.exe -m pytest
```

> 不要用 `Activate.ps1` 后再敲 `python`：本机 PowerShell 默认禁止运行脚本，激活失败后 `python` 会指向全局解释器，报 `No module named uvicorn`。

浏览器打开 <http://127.0.0.1:8000/docs>，用 `user001 / Demo123!` 登录后按 01 文档 3.2 节走 6 步。

## 文件与代码的对应关系

| 你想改什么 | 改哪里 |
|---|---|
| 分类定义、提示词、输出字段说明 | `backend/app/services/analysis_prompts.py` |
| 超时、重试、错误类型、模型请求格式 | `backend/app/services/llm_client.py` |
| 校验、截断、别名映射、置信度、降级、写库 | `backend/app/services/analysis_service.py` |
| 新增/修改接口路径与权限 | `backend/app/api/routes/analysis.py` |
| 接口字段（前端要的类型） | `backend/app/schemas/analysis.py` |
| 测试 | `backend/tests/test_analysis.py` |

改完记得三件事：跑 `pytest`、同步 `docs/api-conventions.md` 第 7 节、在 PR 里 @ 受影响的人。
