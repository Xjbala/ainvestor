# 💎 AI Investor - 多Agent价值投资分析系统

> **AI Investor** is a multi-agent value investing analysis system for A-share stocks, powered by AgentScope. It combines LLM-driven fundamental analysis, professional valuation modeling (DCF / Residual Income / Relative / SOTP / WACC / Triangulation), and real-time multi-agent collaboration to generate structured investment ratings.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-19.2-61dafb.svg)](https://react.dev/)
[![AgentScope](https://img.shields.io/badge/AgentScope-1.0.13+-green.svg)](https://github.com/modelscope/agentscope)

**关键词 / Keywords / Tags:** `价值投资` `量化投资` `A股分析` `股票估值` `DCF估值` `剩余收益模型` `RIM` `相对估值` `SOTP分部加总` `WACC` `CAPM` `三角验证` `多智能体` `Multi-Agent` `LLM` `AgentScope` `基本面分析` `财务分析` `风险管理` `投资组合` `年报解析` `MD&A` `新闻舆情` `情绪分析` `FastAPI` `React` `TypeScript` `WebSocket` `value investing` `stock valuation` `DCF` `residual income` `relative valuation` `SOTP` `financial analysis` `investment rating` `A-share` `Chinese stock market`

基于 [AgentScope](https://github.com/modelscope/agentscope) 框架的多智能体价值投资分析系统，采用前后端分离架构，通过多个专业AI智能体协作，对A股股票进行基本面分析、风险评估、估值建模和投资建议生成。

## ✨ 核心特性

- 🤖 **多Agent协作系统** - 基本面分析师、估值分析师、风险管理、投资组合管理四个专业角色
- 💬 **投资委员会会议** - 多轮讨论机制，形成投资共识和综合分析
- 📊 **实时状态同步** - WebSocket推送Agent执行进度和中间结果
- 📋 **结构化评级报告** - 自动生成包含分析师观点、风险评估、会议摘要和投资建议的完整报告
- 🧠 **长期记忆支持** - 可选的ReMe长期记忆功能，支持经验积累和反思学习
- 🎯 **五级评级体系** - 强烈推荐、推荐、中性、谨慎、回避
- 📐 **专业估值建模** - DCF、剩余收益、相对估值、SOTP 分部加总、多方法三角验证
- 📰 **定性数据采集** - 巨潮年报PDF解析、MD&A结构化提取、新闻舆情情绪分析

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

欢迎贡献代码、报告问题或提出建议！

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

⭐ 如果这个项目对你有帮助，欢迎给个 Star！