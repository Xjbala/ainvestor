# AI Investor - 项目上下文文档

## 项目概述

**AI Investor** 是一个基于 **AgentScope** 框架的多智能体价值投资分析系统。该系统采用前后端分离架构，通过多个专业AI智能体协作，对A股股票进行基本面分析、风险评估、估值建模和投资建议生成，并通过WebSocket实时推送分析过程到前端界面。

### 核心特性

- 🤖 **多Agent协作系统** - 基本面分析师、估值分析师、风险管理、投资组合管理四个专业角色
- 💬 **投资委员会会议** - 多轮讨论机制，形成投资共识和综合分析
- 📊 **实时状态同步** - WebSocket推送Agent执行进度和中间结果
- 📋 **结构化评级报告** - 自动生成包含分析师观点、风险评估、会议摘要和投资建议的完整报告
- 🧠 **长期记忆支持** - 可选的ReMe长期记忆功能，支持经验积累和反思学习
- 🎯 **五级评级体系** - 强烈推荐、推荐、中性、谨慎、回避

## 技术架构

### 后端技术栈

- **AI框架**: AgentScope 1.0.13+（多智能体协作框架）
- **Web框架**: FastAPI 0.115.0+ + Uvicorn
- **WebSocket**: websockets 14.0+
- **数据库**: SQLite（开发） / MySQL（生产，使用aiomysql + SQLAlchemy）
- **认证**: passlib[bcrypt] + python-jose[cryptography]
- **依赖管理**: uv（Python >= 3.12）

### 前端技术栈

- **框架**: React 19.2.0 + TypeScript 5.9.3
- **构建工具**: Vite 7.2.4
- **状态管理**: Zustand 5.0.10
- **Markdown渲染**: react-markdown 10.1.0
- **开发环境**: Node.js >= 18

## 目录结构

```
ainvestor/
├── backend/                    # Python后端
│   ├── agents/                # AI智能体实现
│   │   ├── analyst.py        # 基本面/估值分析师
│   │   ├── risk_agent.py     # 风险管理Agent
│   │   ├── pm_agent.py       # 投资组合管理Agent
│   │   ├── prompt_loader.py  # 提示词加载器
│   │   └── prompts/          # YAML配置的提示词模板
│   ├── analysis/             # 财务分析模块
│   │   ├── growth.py         # 增长能力分析
│   │   ├── operating.py      # 营运能力分析
│   │   ├── profitability.py  # 盈利能力分析
│   │   └── solvency.py       # 偿债能力分析
│   ├── api/                  # REST API路由
│   │   ├── routes.py         # 主路由
│   │   ├── auth.py           # 认证API
│   │   ├── users.py          # 用户管理
│   │   ├── crawler.py        # 数据爬取
│   │   ├── analysis.py       # 分析API
│   │   ├── valuation.py      # 估值API
│   │   ├── companies.py      # 公司信息
│   │   └── exchanges.py      # 交易所信息
│   ├── config/               # 配置管理
│   │   ├── constants.py      # Agent常量配置
│   │   └── env_config.py     # 环境变量配置
│   ├── core/                 # 核心模块
│   │   ├── pipeline.py       # 评级Pipeline（多Agent协作流程）
│   │   ├── auth.py           # 认证逻辑
│   │   └── dependencies.py   # FastAPI依赖
│   ├── crawler/              # 数据爬虫
│   │   ├── base.py           # 基础爬虫
│   │   ├── crawler_engine.py # 爬虫引擎
│   │   ├── exchange_crawler.py # 交易所爬虫
│   │   └── sina_crawler.py   # 新浪财经爬虫
│   ├── llm/                  # LLM模型配置
│   │   └── models.py         # 模型工厂和格式化器
│   ├── persistence/          # 数据持久化
│   │   ├── database.py       # 数据库操作（aiosqlite）
│   │   ├── models.py         # 数据模型定义
│   │   ├── orm_models.py     # ORM模型
│   │   ├── repository.py     # 数据仓库
│   │   └── financial_models.py # 财务模型
│   ├── valuation/            # 估值模块
│   │   ├── dcf.py            # DCF估值
│   │   └── residual_income.py # 剩余收益估值
│   ├── websocket/            # WebSocket服务
│   │   ├── gateway.py        # WebSocket网关
│   │   ├── state_sync.py     # 状态同步器
│   │   └── message.py        # 消息定义
│   └── server.py             # 后端服务入口
├── frontend/                 # React前端
│   └── src/
│       ├── components/       # UI组件
│       ├── hooks/            # React Hooks（WebSocket等）
│       ├── services/         # API服务
│       ├── stores/           # Zustand状态管理
│       ├── types/            # TypeScript类型定义
│       └── utils/            # 工具函数
├── data/                     # 数据目录
│   └── ainvestor.db         # SQLite数据库
├── main.py                   # CLI入口（命令行模式）
├── pyproject.toml           # Python项目配置
├── .env                     # 环境变量
└── README.md                # 项目说明
```

## 核心智能体系统

### Agent类型

系统包含以下智能体（在 `backend/config/constants.py` 中定义）：

1. **基本面分析师** (`fundamentals_analyst`)
   - 角色：财务健康度分析、盈利能力评估、增长质量判断
   - 关注点：资产负债表、利润表、现金流量表分析

2. **估值分析师** (`valuation_analyst`)
   - 角色：公司估值和价值评估
   - 关注点：DCF估值、剩余收益估值、EV/EBITDA等估值方法

3. **风险管理** (`risk_manager`)
   - 角色：投资风险评估和警示
   - 关注点：市场风险、信用风险、流动性风险

4. **投资组合管理** (`portfolio_manager`)
   - 角色：投资决策和组合管理
   - 关注点：投资建议、评级生成、会议主持

### Agent基类

- **AnalystAgent** (`backend/agents/analyst.py`): 继承自 `AgentScope.ReActAgent`，支持工具调用和长期记忆
- **RiskAgent** (`backend/agents/risk_agent.py`): 风险评估专用Agent
- **PMAgent** (`backend/agents/pm_agent.py`): 投资组合管理专用Agent

### 提示词系统

提示词采用YAML配置方式存储在 `backend/agents/prompts/` 目录：
- `analyst/personas.yaml`: Agent角色定义和关注点
- `analyst/system.yaml`: 系统提示词模板

通过 `PromptLoader` 类加载和渲染提示词。

## 核心业务流程

### RatingPipeline 评级流程

核心流程定义在 `backend/core/pipeline.py` 中的 `RatingPipeline` 类：

```
Phase 0: 清空短期记忆（避免跨日上下文污染）
  ↓
Phase 1: 分析师评估
  - 基本面分析师分析财务数据
  - 估值分析师进行估值建模
  ↓
Phase 2: 风险评估
  - 风险管理Agent提供风险警示
  ↓
Phase 3: 会议讨论（多轮）
  - PM提出议程和问题
  - 分析师分享观点和见解
  - 可配置最大轮次（MAX_COMM_CYCLES）
  ↓
Phase 4: 生成最终预测
  - 分析师提供结构化预测（方向 + 置信度）
  ↓
Phase 5: 投资建议生成
  - PM生成投资评级和建议
  ↓
Phase 6: 生成评级报告
  - 汇总分析师评估、风险评估、会议讨论、投资建议
  ↓
Phase 7: 反思与记忆
  - 将经验记录到长期记忆（如启用）
```

### 实时状态同步

通过 `WebSocketStateSync` 实现Pipeline执行过程中的实时状态推送：
- `on_agent_complete`: Agent完成分析时
- `on_conference_start`: 会议开始时
- `on_conference_cycle_start/end`: 会议轮次开始/结束时
- `on_conference_message`: 会议消息时
- `on_conference_end`: 会议结束时

## 数据库设计

### 数据表

数据库使用 `aiosqlite` 进行异步操作（`backend/persistence/database.py`）：

1. **analysis_sessions**: 分析会话
   - id, tickers, date, status, created_at, updated_at, completed_at

2. **agent_outputs**: Agent输出
   - id, session_id, agent_id, agent_type, phase, content, created_at

3. **rating_reports**: 评级报告
   - id, session_id, report_content, recommendations, created_at

### 数据模型

数据模型定义在 `backend/persistence/models.py`：
- `AnalysisSession`: 分析会话模型
- `AgentOutput`: Agent输出模型
- `RatingReport`: 评级报告模型

## API接口

### REST API

- `GET /` - API根路径
- `GET /api/health` - 健康检查
- `GET /api/sessions` - 获取分析会话列表
- `GET /api/sessions/{id}` - 获取会话详情
- `GET /api/sessions/{id}/report` - 获取评级报告
- `POST /api/auth/*` - 认证相关
- `POST /api/users/*` - 用户管理
- `POST /api/crawler/*` - 数据爬取
- `POST /api/analysis/*` - 分析API
- `POST /api/valuation/*` - 估值API
- `GET /api/companies/*` - 公司信息
- `GET /api/exchanges/*` - 交易所信息

### WebSocket

- **连接地址**: `ws://localhost:8765`
- **消息格式**: JSON

**发送分析请求**:
```json
{
  "type": "command",
  "event": "start_analysis",
  "data": {
    "tickers": ["600519", "000858"],
    "date": "2026-01-28"
  }
}
```

## 环境配置

### 环境变量 (.env)

```bash
# API配置
API_HOST=0.0.0.0
API_PORT=8000
WS_PORT=8765

# LLM配置
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4

# 长期记忆配置（可选）
MEMORY_API_KEY=your_memory_api_key
MEMORY_MODEL_NAME=qwen3-max
MEMORY_EMBEDDING_MODEL=text-embedding-v4

# 分析配置
CONFIG_NAME=default
MAX_COMM_CYCLES=2
TICKERS=000001,600519
```

## 构建与运行

### 安装依赖

```bash
# 安装Python依赖（使用uv）
uv sync

# 安装前端依赖
cd frontend && npm install
```

### 启动开发服务器

**方式1: 启动完整服务（HTTP + WebSocket）**
```bash
# 后端
uv run python backend/server.py
# 或使用CLI
uv run python main.py --server

# 前端（新终端）
cd frontend && npm run dev
```

**方式2: 命令行模式（不启动服务器）**
```bash
# 基础分析
uv run python main.py --tickers 600519,000858 --date 2026-01-28

# 启用长期记忆
uv run python main.py --tickers 600519 --enable-memory
```

### 构建生产版本

```bash
# 前端构建
cd frontend && npm run build

# 后端运行
gunicorn backend.server:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 开发约定

### 代码规范

1. **Python代码**:
   - 遵循 PEP8 规范
   - 使用类型注解（Type Hints）
   - 文件头部包含编码声明和作者信息
   - 使用异步编程（async/await）

2. **TypeScript/React代码**:
   - 使用 ESLint + Prettier 格式化
   - 使用函数式组件和 Hooks
   - TypeScript 严格模式

3. **Agent开发**:
   - 继承相应的Agent基类
   - 使用PromptLoader加载提示词
   - 支持工具调用和长期记忆
   - 返回Msg对象

### Git工作流

- 主分支：`main`
- 功能开发：创建特性分支
- 提交信息：使用清晰的描述性信息

### 数据库变更

- 使用migration管理数据库变更（待实现）
- 当前版本：直接修改 `database.py` 中的表结构

## 投资评级体系

| 评级 | 含义 | 建议 |
|------|------|------|
| **强烈推荐** | 预期涨幅 > 15% | 重点配置 |
| **推荐** | 跑赢大盘 | 适度配置 |
| **中性** | 与大市同步 | 持有观望 |
| **谨慎** | 跑输大盘 | 减少配置 |
| **回避** | 预期下跌/风险高 | 暂不参与 |

## 扩展与定制

### 添加新的分析师

1. 在 `backend/config/constants.py` 的 `ANALYST_TYPES` 中定义新分析师类型
2. 在 `backend/agents/prompts/analyst/personas.yaml` 中添加角色配置
3. 在 `backend/agents/prompts/analyst/system.yaml` 中添加系统提示词
4. 创建相应的工具函数（可选）

### 添加新的分析工具

1. 在 `backend/analysis/` 或相关模块中实现工具函数
2. 在Agent初始化时通过 `toolkit` 参数传入
3. AgentScope的ReActAgent会自动选择和使用工具

### 自定义估值模型

1. 在 `backend/valuation/` 中实现新的估值类
2. 继承或参考 `dcf.py` / `residual_income.py` 的实现
3. 在API路由中添加新的估值端点

## 常见问题

### Q: 如何切换不同的LLM模型？
A: 修改 `.env` 文件中的 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `MODEL_NAME`，或在 `backend/llm/models.py` 中配置不同的模型工厂。

### Q: 如何启用MySQL数据库？
A: 修改 `.env` 文件添加MySQL连接配置，并在 `backend/persistence/database.py` 中使用 `aiomysql` 替代 `aiosqlite`。

### Q: WebSocket连接失败怎么办？
A: 检查 `WS_PORT` 配置是否正确，确保防火墙允许该端口，并查看后端日志中的WebSocket启动信息。

### Q: 如何调试Agent执行过程？
A: 启用详细日志级别，或在 `pipeline.py` 的关键位置添加日志输出。WebSocket状态同步也会在前端显示Agent执行进度。

## 相关资源

- **AgentScope文档**: https://github.com/modelscope/agentscope
- **FastAPI文档**: https://fastapi.tiangolo.com/
- **React文档**: https://react.dev/
- **前端地址**: http://localhost:5173
- **API文档**: http://localhost:8000/docs

## License

MIT