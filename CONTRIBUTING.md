# 贡献指南 / Contributing

感谢你对 **AI Investor** 的兴趣！

本项目欢迎各种形式的贡献：修 bug、补数据源、完善估值模型、优化 Agent 协作、改进前端体验、补充测试与文档。

> 核心原则：  
> **数据底座优先，Agent 协作其次。**  
> 请尽量让改动可复现、可核对，而不是只增加“看起来更聪明”的提示词。

---

## 适合从哪里开始

### 高价值方向
1. **数据底座**
   - 爬虫稳定性（新浪 / 交易所 / 巨潮）
   - 科目映射与缺失数据处理
   - 年报 MD&A / 分部抽取质量
2. **分析与估值**
   - 四维财务分析指标
   - DCF / RIM / Relative / SOTP / WACC / 三角验证
   - 行业画像与默认参数
3. **Agent 协作**
   - 工具调用边界与错误提示
   - Pipeline 阶段串联
   - 报告结构化输出
4. **产品体验**
   - 数据管理页
   - 专家估值实验室
   - AI 模式过程展示
5. **工程化**
   - 单测 / 集成测
   - 文档
   - CI / 发布流程

### 不太建议的起步方式
- 只改提示词、不验证是否读到真实数据
- 大范围重构却没有对应测试
- 引入重依赖但没有明确收益

---

## 本地开发

### 环境要求
- Python >= 3.12
- Node.js >= 18
- [uv](https://docs.astral.sh/uv/)

### 安装

```bash
git clone https://github.com/Xjbala/ainvestor.git
cd ainvestor
uv sync
cd frontend && npm install && cd ..
cp .env.example .env
```

至少配置：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
MODEL_NAME=...
```

如需定性年报解析，再配置：

```bash
MINERU_API_KEY=...
```

### 启动

```bash
# 后端
uv run python backend/server.py

# 前端
cd frontend && npm run dev
```

- 前端：http://localhost:5173
- API Docs：http://localhost:8000/docs
- WebSocket：ws://localhost:8765

### 测试

```bash
# 后端纯逻辑单测（无需数据库/网络/LLM）
uv run python -m unittest discover -s tests -p "test_*.py" -v

# 前端
cd frontend
npm run lint
npm run build
```

---

## 贡献流程

1. Fork 仓库并创建分支  
   ```bash
   git checkout -b feature/your-feature
   # 或
   git checkout -b fix/your-bug
   ```
2. 做最小可验证改动
3. 补充/更新测试与文档
4. 提交 PR，说明：
   - 解决了什么问题
   - 如何验证
   - 是否影响数据模型 / API / Agent 行为

### Commit 建议
- `feat: ...` 新功能
- `fix: ...` 修复
- `docs: ...` 文档
- `refactor: ...` 重构
- `test: ...` 测试
- `chore: ...` 工程杂项

---

## 代码约定

### Python
- Python 3.12+
- 尽量使用类型注解
- 异步代码优先 `async/await`
- 数据访问走 repository / service，避免在 Agent 提示词里硬编码业务逻辑
- 财务/估值改动尽量补充纯逻辑测试

### TypeScript / React
- 函数式组件 + Hooks
- 保持现有目录与命名风格
- 改动后至少保证 `npm run build` 通过

### Agent / 数据相关改动
请特别说明：
1. 数据从哪里来
2. 如何进入分析/估值/Agent 工具
3. 缺数据时如何提示，而不是静默编造

---

## Issue 怎么提

请尽量使用 Issue 模板：
- **Bug report**：可复现问题
- **Feature request**：新能力建议
- **Data source / valuation discussion**：数据源、科目、估值方法讨论

一个好 Issue 通常包含：
- 期望行为
- 实际行为
- 复现步骤
- 环境信息
- 相关日志 / 截图 / 股票代码

---

## PR 审查关注点

维护者会重点看：
1. 是否破坏现有数据模型与 API
2. 是否真正复用数据底座，而不是旁路造一套逻辑
3. 是否有最小验证路径
4. 文档是否同步
5. 是否引入不必要复杂度

---

## 社区协作原则

- 默认善意，先讨论清楚再大改
- 小步提交，便于 review
- 承认边界：本项目是研究/学习向工具，不提供投资建议
- 对外部数据源保持克制，遵守网站条款与频率限制

---

## 许可证

贡献代码即表示你同意以项目当前 [MIT License](LICENSE) 授权。

再次感谢你的参与。  
如果你也认同“**先把 A 股基础数据做成可计算资产，再谈 Agent 协作**”，欢迎一起来打磨。
