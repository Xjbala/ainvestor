# 💎 AI Investor - 多Agent价值投资分析系统

> **AI Investor** is a multi-agent value investing analysis system for A-share stocks, powered by AgentScope. It combines LLM-driven fundamental analysis, professional valuation modeling (DCF / Residual Income / Relative / SOTP / WACC / Triangulation), and real-time multi-agent collaboration to generate structured investment ratings.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-19.2-61dafb.svg)](https://react.dev/)
[![AgentScope](https://img.shields.io/badge/AgentScope-1.0.13+-green.svg)](https://github.com/modelscope/agentscope)

**关键词 / Keywords / Tags:** `价值投资` `量化投资` `A股分析` `股票估值` `DCF估值` `剩余收益模型` `RIM` `相对估值` `SOTP分部加总` `WACC` `CAPM` `三角验证` `多智能体` `Multi-Agent` `LLM` `AgentScope` `基本面分析` `财务分析` `风险管理` `投资组合` `年报解析` `MD&A` `新闻舆情` `情绪分析` `FastAPI` `React` `TypeScript` `WebSocket` `value investing` `stock valuation` `DCF` `residual income` `relative valuation` `SOTP` `financial analysis` `investment rating` `A-share` `Chinese stock market`

基于 [AgentScope](https://github.com/modelscope/agentscope) 框架的多智能体价值投资分析系统，采用前后端分离架构，通过多个专业AI智能体协作，对A股股票进行基本面分析、风险评估、估值建模和投资建议生成。

> 面向 A 股研究者的可计算、可追溯 AI 投研工作台：从数据采集和校验，到多模型估值、专家协作与评级报告，完整保留每一步分析依据。

> 本项目真正想强调的不是“多 Agent 聊天”，而是：
>
> **结构化数据底座 → 可计算的分析/估值引擎 → Agent 工具真实读库算数 → 投资委员会共识 → 可追溯评级报告。**
>
> 有可复用的基础数据，Agent 才有可信的判断；没有数据底座，LLM 只会在幻觉上辩论。

## ✨ 核心特性

- 🧱 **结构化数据底座** - 交易所名单、财务三大表、行情、年报 MD&A、分部数据、新闻舆情统一落库复用
- 🤖 **多Agent协作系统** - 基本面分析师、估值分析师、风险管理、投资组合管理四个专业角色
- 🛠️ **Agent 真读库算数** - ReAct Toolkit 调用财务分析与估值服务，而不是空口生成结论
- 💬 **投资委员会会议** - 多轮讨论机制，形成投资共识和综合分析
- 📊 **实时状态同步** - WebSocket推送Agent执行进度和中间结果
- 📋 **结构化评级报告** - 自动生成包含分析师观点、风险评估、会议摘要和投资建议的完整报告
- 🧠 **长期记忆支持** - 可选的ReMe长期记忆功能，支持经验积累和反思学习
- 🎯 **五级评级体系** - 强烈推荐、推荐、中性、谨慎、回避
- 📐 **专业估值建模** - DCF、剩余收益、相对估值、SOTP 分部加总、多方法三角验证
- 📰 **定性 + 定量双底座** - 定量回答“值多少钱”，定性补足护城河、风险、展望与分部结构

## 🖥️ 系统界面

系统把数据准备、分析推理和最终决策放在同一条可回溯的工作流中。研究者既能查看 Agent 正在使用的分析结果，也能回到原始财务、年报和新闻数据核对结论。

### 实时多 Agent 投资分析

分析任务通过 WebSocket 实时同步。基本面、估值、风控与投资顾问依次完成职责，前端集中展示当前进度、工具计算结果与每位专家的结构化观点。

**基本面分析师：从真实财务数据识别经营质量与关键变化**

![基本面分析师实时分析界面](docs/系统截图/AI分析-基本面分析师.png)

**估值分析师：整合 DCF、剩余收益及相对估值，输出内在价值与置信度**

![估值分析师实时分析界面](docs/系统截图/AI分析-估值分析师.png)

**风险管理师：将盈利、估值、现金流和成长性风险结构化呈现**

![风险管理师实时分析界面](docs/系统截图/AI分析-风险管理师.png)

### 可核验的数据底座

在分析之前，系统会将交易所名单、三大财务报表等数据统一沉淀，并将覆盖情况和勾稽关系直接暴露给研究者。数据问题可定位、可追踪，避免模型在不完整或矛盾的数据上生成结论。

**数据覆盖总览：按公司、报表类型和报告期跟踪数据准备状态**

![数据覆盖总览](docs/系统截图/数据查看-数据覆盖.png)

**财务报表校验：检查核心科目与会计恒等式，展示完整度和异常项**

![财务报表校验](docs/系统截图/数据查看-财务报表校验.png)

### 定性研究与市场信息

除数值模型外，系统也把年报内容和新闻舆情接入研究流程，使 Agent 能结合经营叙事、业务分部和市场情绪形成判断。

**年报内容：按报告期浏览经营概述、收入分析和管理层讨论**

![年报内容查看器](docs/系统截图/数据查看-年度报告.png)

**新闻舆情：聚合相关新闻并保留情绪标签与评分**

![新闻舆情查看器](docs/系统截图/数据查看-新闻舆情.png)

## 🧠 设计理念：数据底座优先

很多 AI 投研项目把重点放在“多角色对话”，本项目更强调把 A 股基础数据做成可计算资产：

| 层级 | 做什么 | 为什么重要 |
|------|--------|------------|
| **数据采集** | 交易所名单、新浪三大表、行情、巨潮年报、新闻舆情、分部 | 没有稳定输入，后续分析无法复现 |
| **结构化存储** | 标准科目编码、ORM 模型、可查询财务/定性表 | 同一套数据可被 API、专家模式、Agent 共用 |
| **计算引擎** | 四维财务分析 + DCF/RIM/Relative/SOTP/WACC/三角验证 | 先算出可核对数字，再让模型解释 |
| **Agent 协作** | 工具调用 → 风控 → 会议 → PM 决策 → 报告 | Agent 是编排层，不是唯一真相来源 |

### 数据如何被应用

```text
交易所名单 / 新浪三表 / 行情
        +
巨潮年报 PDF / MD&A / 分部
        +
新闻舆情情绪
        │
        ▼
   结构化落库（可复用）
        │
        ├─► 四维财务分析 API
        ├─► DCF / RIM / Relative / SOTP / WACC / Triangulate
        └─► Agent Toolkit（fundamentals / valuation / qualitative / risk）
                │
                ▼
        RatingPipeline 会议共识
                │
                ▼
        五级评级 + 结构化报告 + 前端回放
```

一句话总结：**先把基础数据做成资产，再让 Agent 在真实数字上协作。**

## 🏗️ 系统架构

```
ainvestor/
├── backend/                    # Python后端
│   ├── agents/                # AI智能体实现
│   │   ├── analyst.py        # 基本面/估值分析师
│   │   ├── risk_agent.py     # 风险管理Agent
│   │   ├── pm_agent.py       # 投资组合管理Agent
│   │   ├── tools/            # Agent工具（基本面/估值/定性）
│   │   └── prompts/          # 提示词模板（YAML配置）
│   ├── analysis/             # 财务分析（偿债/盈利/增长/营运）
│   ├── api/                  # REST API路由（9个模块）
│   │   ├── routes.py         # 通用API（会话/报告）
│   │   ├── auth.py           # 认证（JWT）
│   │   ├── users.py          # 用户管理
│   │   ├── crawler.py        # 数据采集任务
│   │   ├── analysis.py       # 财务分析
│   │   ├── valuation.py      # 估值分析
│   │   ├── companies.py      # 公司管理
│   │   ├── exchanges.py      # 交易所
│   │   └── segments.py       # 分部数据
│   ├── core/                 # 核心模块（Pipeline评级流程）
│   ├── crawler/              # 数据爬虫
│   │   ├── sina_crawler.py   # 新浪财经爬虫
│   │   ├── exchange_crawler.py # 交易所爬虫
│   │   ├── qualitative/      # 定性数据采集
│   │   │   ├── cninfo_crawler.py  # 巨潮资讯网
│   │   │   ├── mineru_client.py  # MinerU PDF解析
│   │   │   ├── mdpa_extractor.py # MD&A结构化提取
│   │   │   └── segment_extractor.py # 分部抽取
│   │   ├── qualitative_service.py # 定性采集服务
│   │   └── news_service.py   # 新闻舆情采集
│   ├── valuation/            # 估值模块（6种方法）
│   │   ├── dcf.py            # DCF估值
│   │   ├── residual_income.py # 剩余收益估值
│   │   ├── relative.py      # 相对估值
│   │   ├── sotp.py           # 分部加总估值
│   │   ├── wacc.py           # WACC/CAPM
│   │   ├── triangulate.py   # 多方法三角验证
│   │   ├── industry_profiles.py # 行业画像
│   │   └── scenarios.py      # 情景与敏感性
│   ├── websocket/            # WebSocket服务
│   └── persistence/          # 数据持久化（SQLAlchemy ORM）
├── frontend/                 # React前端
│   └── src/
│       ├── components/       # UI组件
│       │   ├── AIMode/       # AI分析模式
│       │   ├── ExpertMode/   # 专家估值实验室
│       │   ├── DataManagement/ # 数据采集管理
│       │   ├── DataViewer/   # 数据查看器
│       │   ├── StockList/    # 股票列表
│       │   ├── Reports/      # 报告库
│       │   └── Common/       # 通用组件
│       ├── hooks/            # React Hooks（WebSocket）
│       ├── services/         # API服务
│       └── stores/           # Zustand状态管理
├── tests/                    # 单元测试（纯逻辑）
└── main.py                   # CLI入口
```

## 🚀 快速开始

### 环境要求

- Python >= 3.12
- Node.js >= 18
- [uv](https://docs.astral.sh/uv/) (Python包管理器)

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/Xjbala/ainvestor.git
cd ainvestor

# 2. 安装Python依赖
uv sync

# 3. 安装前端依赖
cd frontend && npm install && cd ..

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置你的 LLM API Key
```

### 配置说明

编辑 `.env` 文件，配置以下必要参数：

```bash
# LLM API配置 (必填)
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4

# 或使用其他兼容OpenAI API的服务
# OPENAI_BASE_URL=https://api.siliconflow.cn/v1
# MODEL_NAME=Pro/MiniMaxAI/MiniMax-M2.5

# 数据库配置 (生产环境使用MySQL)
# 开发环境默认使用SQLite，自动创建 data/ainvestor.db
DATABASE_URL=mysql+aiomysql://user:password@127.0.0.1:3306/ainvestor

# 估值参数 (可选，有默认值)
RISK_FREE_RATE=0.025
EQUITY_RISK_PREMIUM=0.065
DEFAULT_COST_OF_DEBT=0.055
VALUATION_V2=true

# 年报PDF解析 (定性数据采集需要)
MINERU_API_KEY=your-mineru-api-key
```

### 初始化基础数据（生产环境必做）

首次部署或连接全新数据库时，必须初始化系统运行所需的基础参考数据（标准财务科目、数据源、交易所、新浪科目映射、银行扩展科目）。一条命令即可完成：

```bash
# 1. 先审计（不写库），确认无冲突
uv run python -m backend.scripts.bootstrap_reference_data --dry-run

# 2. 确认无误后执行写入
uv run python -m backend.scripts.bootstrap_reference_data
```

该脚本按依赖顺序幂等执行以下步骤，每一步都是安全的重复操作：

| 步骤 | 说明 |
|------|------|
| 1. 创建数据库表 | `create_all`，表已存在则跳过 |
| 2. 初始化标准科目 | 完整利润表/资产负债表/现金流量表科目（ISF001-ISF028 等） |
| 3. 初始化数据源与交易所 | 新浪财经、交易所官方API、巨潮资讯网、新浪新闻；上交所/深交所/北交所 |
| 4. 补录新浪科目映射 | 人工审核的主名称与来源别名（幂等，不覆盖已有） |
| 5. 补录银行扩展科目 | 000001 平安银行等专业科目及映射 |

> 脚本可安全重复执行：已存在的行自动跳过，不会覆盖已有定义。如果新浪/银行映射 dry-run 发现冲突，会跳过该步写入并提示单独排查。

### 启动服务

**方式1: 完整服务模式 (推荐)**

```bash
# 启动后端 (HTTP: 8000, WebSocket: 8765)
uv run python backend/server.py

# 新终端启动前端 (http://localhost:5173)
cd frontend && npm run dev
```

**方式2: 命令行模式**

```bash
# 直接运行分析
uv run python main.py --tickers 600519,000858 --date 2026-01-28

# 启用长期记忆
uv run python main.py --tickers 600519 --enable-memory
```

### 可选：集成 AgentScope Studio 追踪

AgentScope Studio 用于查看每次分析的 Agent 调用轨迹。它是一个独立服务，默认不启动、不导出追踪，也不会在前端显示入口。启用后仍通过主站同域名访问，例如 `https://your-domain.example/agent-studio/`，而不是新增子域名。

> Studio 会保存提示词、模型回复、工具入参/结果及相关上下文。它没有内置的生产级鉴权，必须在 Nginx、VPN、SSO 或 IP 白名单层保护 `/agent-studio/`，不要公开暴露。

1. 启动独立的 Studio 服务。Compose 仅将端口暴露给本机，数据保存在 Docker named volume：

```bash
docker compose -f deploy/agentscope-studio/docker-compose.yml up -d
```

2. 在运行 Python 后端的 `.env` 中启用导出。`AGENTSCOPE_STUDIO_ENDPOINT` 是后端可达的内部地址，不是浏览器 URL；后端与 Compose 服务位于同一主机时使用 `http://127.0.0.1:3000`：

```env
AGENTSCOPE_STUDIO_ENABLED=true
AGENTSCOPE_STUDIO_ENDPOINT=http://127.0.0.1:3000
AGENTSCOPE_STUDIO_PROJECT=AI Investor
```

3. 在构建前端的 `frontend/.env.production` 中启用侧边栏入口。此变量是浏览器 URL，应使用同域路径：

```env
VITE_AGENTSCOPE_STUDIO_URL=/agent-studio/
```

4. 创建 Studio 访问凭据，再将 [`deploy/agentscope-studio/nginx.conf`](deploy/agentscope-studio/nginx.conf) 的 location 块加入现有 HTTPS 虚拟主机。模板会同时保护页面、tRPC API 与实时连接；若改用 VPN、SSO 或 IP 白名单，必须在这三个 location 上同时生效。完整说明见 [`docs/production-websocket-proxy.md`](docs/production-websocket-proxy.md)。

```bash
sudo htpasswd -c /etc/nginx/.htpasswd-agent-studio <studio-user>
sudo nginx -t
sudo systemctl reload nginx
cd frontend && npm run build
```

该 Nginx 模板固定适配 `@agentscope/studio@1.0.9`。该版本的前端假设它部署在域名根路径，模板通过 `sub_filter` 将资源、tRPC、Socket.IO 和浏览器路由改写到 `/agent-studio/`。升级 Studio 前必须重新验证该模板，并确认 Nginx 包含 `ngx_http_sub_module`：

```bash
nginx -V 2>&1 | grep -- --with-http_sub_module
```

Studio 不可用时，AI 分析会继续执行，仅在后端日志中记录追踪初始化失败。当前实现仅导出 trace，不安装 AgentScope 的全局 Studio hooks，因此 Studio 中的运行记录会直接显示为已完成；请以 trace 内容定位单次分析过程。当前 WebSocket 状态保存在后端进程内，生产环境请保持单 worker（不要为该服务配置多个 Gunicorn worker）。

## 📐 估值模型

系统提供 6 种估值方法，支持按行业画像加权融合：

| 方法 | 文件 | 说明 |
|------|------|------|
| **DCF** | `valuation/dcf.py` | 自由现金流折现，双终值（Gordon + Exit Multiple），三情景，自动 WACC，5×5 敏感性矩阵，质量 gates |
| **剩余收益** | `valuation/residual_income.py` | 每股口径，内在价值 = 每股净资产 + RI现值 + 终值现值，适合 ROE > Ke 的公司 |
| **相对估值** | `valuation/relative.py` | 同业 PE/PB/PS 中位数 + ROE 调整，按行业画像选主倍数 |
| **SOTP** | `valuation/sotp.py` | 分部加总，支持 EV/EBITDA 与 EV/Revenue，扣除总部费用，检测集团折扣 |
| **WACC** | `valuation/wacc.py` | CAPM 驱动，Ke = rf + β×ERP + size_premium，行业区间校验 |
| **三角验证** | `valuation/triangulate.py` | 融合 DCF+RI+Relative+SOTP，按行业画像加权，输出综合公允价、分歧度、置信度 |

## 📊 投资评级体系

| 评级 | 含义 | 建议 |
|------|------|------|
| **强烈推荐** | 预期涨幅 > 15% | 重点配置 |
| **推荐** | 跑赢大盘 | 适度配置 |
| **中性** | 与大市同步 | 持有观望 |
| **谨慎** | 跑输大盘 | 减少配置 |
| **回避** | 预期下跌/风险高 | 暂不参与 |

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| AI框架 | AgentScope 1.0.13+ |
| 前端 | React 19.2 + TypeScript 5.9 + Vite 7.2 |
| 状态管理 | Zustand 5.0 |
| 后端 | FastAPI 0.115+ + Uvicorn |
| WebSocket | websockets 14.0+ |
| 数据库 | SQLite (开发) / MySQL (生产，aiomysql + SQLAlchemy) |
| 认证 | passlib[bcrypt] + python-jose (JWT) |

## 📡 API文档

启动后端后访问 `http://localhost:8000/docs` 查看完整 Swagger 文档。主要端点：

### 估值分析

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/valuation/dcf/{stock_code}` | DCF 估值 |
| GET | `/api/valuation/residual-income/{stock_code}` | 剩余收益估值 |
| GET | `/api/valuation/relative/{stock_code}` | 相对估值 |
| GET | `/api/valuation/wacc/{stock_code}` | WACC/CAPM 拆解 |
| GET | `/api/valuation/triangulate/{stock_code}` | 多方法三角验证综合估值 |
| GET | `/api/valuation/sotp/{stock_code}` | 分部加总估值 |
| GET | `/api/valuation/compare/{stock_code}` | 估值对比 |

### 数据采集

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/crawler/tasks` | 创建爬虫任务 |
| POST | `/api/crawler/tasks/batch-financial` | 全量财务数据批量采集 |
| POST | `/api/crawler/tasks/qualitative` | 定性数据采集（年报PDF） |
| POST | `/api/crawler/tasks/news` | 新闻舆情采集 |
| GET | `/api/crawler/news/{stock_code}` | 新闻情绪数据 |

### 财务分析

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/analysis/solvency/{stock_code}` | 偿债能力 |
| GET | `/api/analysis/profitability/{stock_code}` | 盈利能力 |
| GET | `/api/analysis/growth/{stock_code}` | 发展能力 |
| GET | `/api/analysis/operating/{stock_code}` | 营运能力 |
| GET | `/api/analysis/summary/{stock_code}` | 四维综合分析 |

### WebSocket

连接地址: `ws://localhost:8765`

```json
// 发送分析请求
{
  "type": "command",
  "event": "start_analysis",
  "data": {
    "tickers": ["600519", "000858"],
    "date": "2026-01-28"
  }
}
```

## 🧪 测试

```bash
# 运行纯逻辑单元测试（无需数据库/网络/LLM）
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！完整流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

你可以从这些方向参与：
- 数据源 / 科目映射 / 爬虫稳定性
- 财务分析与估值模型
- Agent 提示词、工具与 Pipeline
- 前端可视化与专家模式体验
- 测试、文档、Issue / PR 模板


1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范

- **Python**: 遵循 PEP8，使用类型注解，异步编程（async/await）
- **TypeScript/React**: 使用 ESLint，函数式组件 + Hooks，严格模式
- **提交信息**: 使用清晰的描述性信息

## ⚠️ 免责声明

本项目仅供学习和研究目的，不构成任何投资建议。投资有风险，入市需谨慎。使用本系统进行的任何投资决策，风险自负。

## 📄 License

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- [AgentScope](https://github.com/modelscope/agentscope) - 多智能体框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Python Web框架
- [React](https://react.dev/) - 前端UI框架

---

最新版本：[v0.1.0 Release](https://github.com/Xjbala/ainvestor/releases/tag/v0.1.0)

⭐ 如果这个项目对你有帮助，欢迎给个 Star！
