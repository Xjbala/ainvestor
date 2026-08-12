# AI Investor → AgentScope 2.0.5 完整迁移方案

> **目标版本**: `agentscope==2.0.5`  
> **依据**: `docs/spike-as205/` 实测（2026-07-28）+ 当前仓库耦合面  
> **原则**: 保留 ainvestor 自建 FastAPI / WebSocket / RatingPipeline 业务语义；只替换 Agent 运行时与编排适配层。  
> **不在本期**: 用 `agentscope.app` 替换整个后端；投委会 HITL 产品（可在迁移后另开）。

---

## 0. 一页结论

| 项 | 内容 |
|----|------|
| 迁移性质 | **架构级 breaking**，不是改依赖版本 |
| 推荐策略 | **特性分支 + 适配层优先 + 分阶段可回滚** |
| 工期 | **约 24–36 人天**（1 人全职约 5–7 周；2 人可压到 3–4 周） |
| 最大风险 | 无 `MsgHub` → 会议层必须自建；默认 tool **ASK** 会卡住无人值守分析 |
| 成功标准 | CLI + Server 完整跑通一轮评级；WS 推送与报告格式不回归；工具可被模型调用 |

Spike 已证明：2.0.5 **可装、可 `Agent.reply`、可自定义 tool、可 live tool-call**；但 **无 pipeline/MsgHub、无 memory 模块、无 ReActAgent、Model/Toolkit API 全变**。

---

## 1. 范围与非范围

### 1.1 In Scope

- 依赖升级到 `agentscope==2.0.5`（建议 **精确钉死**，暂不用 `>=2`）
- Agent 基类、消息、工具、模型、短期记忆、会议广播、权限
- `backend/agents/*`、`backend/llm/models.py`、`backend/core/pipeline.py`、`main.py`、`server.py` 装配
- 回归：单 ticker / 多 ticker、fundamentals + valuation tools、会议多轮、报告落库、WS 事件
- 文档：`AGENTS.md`、README 中 AgentScope 版本与 API 说明

### 1.2 Out of Scope（本期不做，文档预留）

- 替换为官方 Agent as Service / multi-tenant session 托管
- Workspace 沙箱（Docker/E2B/K8s）全面落地
- 投委会人类 HITL 产品（可在 M5 后加）
- 前端大改（除非 WS 事件被迫变更）
- 评估模块、爬虫、估值纯算法（与 AS 无关）

### 1.3 明确保留

| 层 | 保留 |
|----|------|
| HTTP API | FastAPI routes |
| 实时 | 自建 WebSocket gateway + state_sync |
| 编排语义 | RatingPipeline Phase0–7 业务阶段名与顺序 |
| 领域工具 | fundamentals / valuation / qualitative 函数实现 |
| 持久化 | session / agent_outputs / rating_reports |
| Prompt | YAML `PromptLoader`（仅接入方式变） |

---

## 2. 目标架构（迁移后）

```text
┌─────────────────────────────────────────────────────────────┐
│  FastAPI + WebSocket (不变)                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  RatingPipeline (业务阶段保留)                                │
│  Phase0 clear state.context                                  │
│  Phase1–2/4–5 agent.reply(UserMsg|Msg)                       │
│  Phase3 ConferenceHub (自建，替代 MsgHub)                      │
│  Phase6 report (纯 Python)                                   │
│  Phase7 ReMeMiddleware / 可选                                │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   AnalystAgent        RiskAgent            PMAgent
   (extends Agent)     (extends Agent)      (extends Agent)
        │                   │                   │
        ▼                   ▼                   ▼
   Toolkit(FunctionTool...) + Permission BYPASS/allow_rules
        │
        ▼
   OpenAIChatModel / DashScopeChatModel + Credential
   (+ formatter 挂在 model 侧，不再独立塞进 Agent 构造)
```

### 2.1 新增内部模块（建议）

| 新文件 | 职责 |
|--------|------|
| `backend/agents/as2_compat.py` | 消息构造、文本抽取、Tool 包装、权限 state 工厂 |
| `backend/agents/toolkit_factory.py` | async 创建 Toolkit + `FunctionTool` 注册（统一 main/server） |
| `backend/core/conference_hub.py` | 替代 MsgHub：broadcast / observe / transcript |
| `backend/agents/base_agent.py` | 公共 `Agent` 子类：权限、reply 包装、context clear |
| `tests/agentscope2/*` | 适配层与冒烟测试 |

---

## 3. API 对照表（必须全部落地）

| # | 1.x 现状 | 2.0.5 目标 | 改造点 |
|---|----------|------------|--------|
| 1 | `ReActAgent` | `Agent` | 三 Agent 基类 |
| 2 | `sys_prompt=` | `system_prompt=` | 构造参数 |
| 3 | `formatter=` 传 Agent | formatter 给 **Model** 或默认 | `models.py` |
| 4 | `memory=InMemoryMemory()` | `state=AgentState(...)` | Phase0 / 构造 |
| 5 | `max_iters=10` | `react_config=ReActConfig(max_iters=10)` | 构造 |
| 6 | `long_term_memory=` + mode | `middlewares=[ReMeMiddleware/Mem0Middleware]` | main 可选路径 |
| 7 | `Msg(name, str, role)` | `UserMsg(name, content)` 或 `Msg(name=..., role=..., content=[TextBlock...])` | pipeline 全量 |
| 8 | `Toolkit.register_tool_function(fn)` | `await toolkit.add_tool(FunctionTool(fn))` | 装配异步 |
| 9 | 同步创建 toolkit | **async factory** | server/main 启动路径 |
| 10 | `MsgHub` | `ConferenceHub` 自建 | pipeline Phase3 |
| 11 | `await agent.memory.clear()` | `agent.state.context = []`（或重建 state 保留 permission） | Phase0 |
| 12 | `OpenAIChatModel(model_name, api_key, base_url=)` | `OpenAIChatModel(credential=OpenAICredential(api_key=...), model=..., client_kwargs={base_url})` | models |
| 13 | 无 tool 权限 | 默认 ASK → 生产 **`PermissionMode.BYPASS`** 或按 tool allow_rules | **必做** |
| 14 | `await agent.reply(msg)` | 仍可用；返回 `Msg` content 为 blocks | 抽取逻辑加强 |
| 15 | 子类 `async def reply(self, x: Msg)` | `async def reply(self, inputs=..., structured_schema=...)` | 签名对齐 |

---

## 4. 分阶段实施计划

### 总览

| 阶段 | 名称 | 人天 | 出口标准 |
|------|------|------|----------|
| **M0** | 分支/依赖/脚手架 | 1–2 | 2.0.5 装进项目 venv；compat 空壳；CI 可 import |
| **M1** | 模型 + 消息 + 工具适配层 | 4–6 | 无 Agent 也能单测消息/Toolkit/Model 构造 |
| **M2** | 三 Agent 重写 | 5–7 | 单 Agent + 一 tool live 成功 |
| **M3** | ConferenceHub + Pipeline | 6–9 | 完整 Phase0–7 无 WS 跑通 |
| **M4** | Server/CLI/WS 集成 | 3–5 | `server.py` + 前端看完一轮分析 |
| **M5** | 回归、文档、收尾 | 3–5 | 验收清单全绿；可合并 |
| **缓冲** | 隐藏 breaking | 2–4 | — |
| **合计** | | **24–36** | |

---

### M0 — 工程脚手架（1–2d）

**动作**

1. 分支：`feat/agentscope-2.0.5`
2. `pyproject.toml`：
   ```toml
   "agentscope==2.0.5",
   ```
   暂时 **精确版本**；lock 用 `uv lock` / `uv sync`（pip 易 resolution-too-deep）。
3. 确认 Python `>=3.12`（已满足；2.0 要求 `>=3.11`）。
4. 新增：
   - `backend/agents/as2_compat.py`
   - `backend/agents/toolkit_factory.py`
   - `backend/core/conference_hub.py`
   - `backend/agents/base_agent.py`
5. 保留 spike 目录作对照，不删。
6. 可选：双版本兼容开关 **不推荐**长期维护；以 clean break 为准，git 回滚即可。

**验收**

```bash
uv sync
uv run python -c "import agentscope; assert agentscope.__version__=='2.0.5'"
uv run python scripts/agentscope_2_spike_probe.py --expected-version 2.0.5 --out /tmp/as205-proj --fail-on none
```

**回滚**: 切回 `main`，`uv.lock` 恢复。

---

### M1 — 适配层：消息 / 工具 / 模型 / 权限（4–6d）

#### 1.1 `as2_compat.py`（核心）

实现至少：

```python
# 伪代码 — 实施时按 2.0.5 实测签名

def user_msg(name: str, text: str, metadata: dict | None = None) -> Msg:
    return UserMsg(name=name, content=text)  # 或显式 TextBlock

def system_user_msg(text: str, metadata: dict | None = None) -> Msg:
    """pipeline 里大量 role=user 的 system 提示"""
    return user_msg("system", text, metadata)

def extract_text(content_or_msg) -> str:
    """升级现有 RatingPipeline._extract_text_content
    - 跳过 thinking / tool_call 块（按产品决定）
    - 拼接 text blocks
    """

def make_tool_response(text: str) -> ToolResponse:
    return ToolResponse(content=[TextBlock(type="text", text=text)])

def make_agent_state(*, bypass: bool = True, allow_tools: list[str] | None = None) -> AgentState:
    """无人值守分析默认 BYPASS 或 allow_rules 全开业务工具"""

def wrap_function_tool(fn) -> FunctionTool:
    return FunctionTool(fn)
```

#### 1.2 `toolkit_factory.py`

```python
async def build_toolkit(analyst_type: str) -> Toolkit:
    toolkit = Toolkit()
    for fn in TOOLS_BY_TYPE[analyst_type]:
        await toolkit.add_tool(FunctionTool(fn))
    return toolkit
```

- **删除**所有 `register_tool_function`
- `main.py` / `server.py` 创建 agent 前必须 `await build_toolkit(...)`
- risk/pm 内置 tool 方法同样 `FunctionTool(self._tool_...)`（注意 bound method）

#### 1.3 `models.py` 重写

| Provider | 2.0 路径 |
|----------|----------|
| OPENAI / SILICONFLOW / DEEPSEEK / GROQ / OPENROUTER | `OpenAICredential` + `OpenAIChatModel(credential, model=..., client_kwargs={base_url})` |
| DASHSCOPE / ALIBABA | `DashScopeCredential` + `DashScopeChatModel` |
| ANTHROPIC / GEMINI / OLLAMA | 对应 Credential + Model（逐个验） |

要点：

- 参数名：`model_name` → 多为 **`model`**
- **Formatter**：优先 `OpenAIChatModel(..., formatter=OpenAIChatFormatter())`；Agent 不再收 formatter
- `get_agent_formatter()`：可改为 `get_model_formatter(provider)` 仅供 model 工厂使用，或内联进 `get_agent_model`
- 环境变量映射尽量保持 `MODEL_PROVIDER` / `OPENAI_BASE_URL` 等不变，降低运维成本

#### 1.4 权限策略（生产默认）

**推荐默认（分析流水线）**：

```python
PermissionContext(mode=PermissionMode.BYPASS)
```

或对业务 tool 名逐个 `PermissionRule(tool_name=..., behavior=ALLOW, rule_content=None, source="ainvestor")`。

| 场景 | 模式 |
|------|------|
| 自动评级 / CI / 服务端 | BYPASS 或全 ALLOW |
| 将来人工审批高危工具 | DEFAULT + allow 名单 |
| 切勿 | 默认 DEFAULT 却无人确认 → 卡死在 “waiting for permission” |

#### 1.5 tools 返回值

- 保持 `ToolResponse(content=[TextBlock(type="text", text=...)])`（spike 已通）
- **修复** `risk_agent.py` 中不存在的 `ToolResponse.text(...)`（1.x 已有隐患，2.0 一并清）
- 纯 `str` 返回：FunctionTool 可能接受，但统一 `ToolResponse` 更稳

**M1 验收**

```bash
uv run python -c "from backend.agents.as2_compat import user_msg, extract_text; m=user_msg('u','hi'); assert 'hi' in extract_text(m)"
uv run python - <<'PY'
import asyncio
from backend.agents.toolkit_factory import build_toolkit
async def main():
    tk = await build_toolkit("fundamentals_analyst")
    schemas = await tk.get_tool_schemas()
    assert schemas
asyncio.run(main())
PY
uv run python -c "from backend.llm.models import get_agent_model; m=get_agent_model('fundamentals_analyst'); print(type(m))"
```

---

### M2 — 三 Agent 重写（5–7d）

#### 2.1 `base_agent.py`

```text
InvestorAgent(Agent):
  - 统一 system_prompt / model / toolkit / state / react_config / middlewares
  - clear_short_memory()
  - reply 包装：兼容旧调用方传入 str → 转 UserMsg
  - 可选：把 metadata.tickers 写入日志（原 analyst.reply 进度逻辑）
```

构造对齐 2.0：

```python
Agent(
  name=agent_id,
  system_prompt=sys_prompt,
  model=model,
  toolkit=toolkit,
  state=make_agent_state(bypass=True, allow_tools=tool_names),
  react_config=ReActConfig(max_iters=10),
  middlewares=middlewares or None,
)
```

#### 2.2 `AnalystAgent` / `RiskAgent` / `PMAgent`

| 改动 | 说明 |
|------|------|
| 基类 | `ReActAgent` → `InvestorAgent` / `Agent` |
| 删除 | `InMemoryMemory`、`formatter` 入参（若保留入参仅忽略并 warn） |
| Prompt | 仍用 `PromptLoader`，得到 string 后作 `system_prompt` |
| 内置 tools | pm/risk 的 `register_tool_function(self._xxx)` → 构造 toolkit 时 `FunctionTool` |
| `reply` 签名 | 对齐 `inputs` / `structured_schema`；内部 `return await super().reply(...)` |

#### 2.3 长期记忆（可第二迭代，但接口要留）

- 1.x：`ReMeTaskLongTermMemory` + `long_term_memory_mode`
- 2.0：`ReMeMiddleware(workspace_dir=..., config=...)` 或 `Mem0Middleware`
- M2 最低：`enable_memory=False` 主路径全绿；memory 开关在 M5 前接通或明确文档为实验特性

**M2 验收**

- 单 Agent live：`UserMsg` 要求调用 `analyze_profitability` 或 spike 级 add tool，返回非 permission 等待文案
- 单元：Agent 可实例化；`clear_short_memory` 后 `state.context == []`

---

### M3 — ConferenceHub + RatingPipeline（6–9d）

#### 3.1 `conference_hub.py` 设计

替代：

```python
async with MsgHub(participants=..., announcement=Msg(...)):
    ...
```

建议接口：

```python
class ConferenceHub:
    def __init__(self, agents: list[Agent]): ...
    async def __aenter__/__aexit__:  # 可选，保持 pipeline 结构相似
    async def announce(self, text: str): ...
    async def broadcast(self, speaker: str, msg: Msg): 
        """写入 transcript；对其他 agent 调用 observe 或 append state.context"""
    async def speak(self, agent, prompt_msg: Msg) -> Msg:
        """agent.reply → broadcast 结果"""
    @property
    def transcript(self) -> list[tuple[str, str]]: ...
```

**语义对齐 1.x MsgHub 的要点**：

1. 同轮内后发言者应能看到先发言者内容（via `observe` 或共享 context 注入）
2. announcement 进入全员 context
3. 不依赖已删除的 pipeline 包
4. 与 StateSync 解耦：仍由 pipeline 调 `on_conference_message`

Spike PoC-C 已验证：`AgentState.context` 列表追加 + `Agent.observe` 可行。

#### 3.2 `pipeline.py` 改造清单

| 位置 | 改动 |
|------|------|
| import | 删 `MsgHub`；改用 `ConferenceHub` + `as2_compat` |
| Phase0 | `await agent.memory.clear()` → `agent.clear_short_memory()` |
| 所有 `Msg(name="system", content=prompt, role="user")` | `system_user_msg(prompt)` / `user_msg(...)` |
| `async with MsgHub(...)` | `async with ConferenceHub(participants) as hub:` 或显式 start/stop |
| `_run_conference_cycles` | `hub.speak(pm, ...)` / `hub.speak(analyst, ...)` |
| `_extract_text_content` | 委托 `as2_compat.extract_text`，过滤 thinking |
| reflection / predictions | 同样改消息构造 |
| 错误处理 | 若 reply 返回 permission 等待文案，视为失败并打明确日志 |

#### 3.3 会议内工具

分析师在会议轮若仍带 toolkit，BYPASS 下可继续调 tool（可能变慢）。可选策略：

- **会议轮**：临时换“无工具 / 只读 tool 组”（若 Toolkit 支持 group）  
- 或接受与 1.x 相同可调工具行为  

在 M3 文档写死默认策略，避免扯皮。

**M3 验收**

```bash
uv run python main.py --tickers 600519 --date 2026-07-28
# 或项目现有 CLI 参数
```

- 日志出现 Phase0–7
- 会议至少 1 轮 PM + 分析师文本
- 生成 rating_report 结构字段完整
- 无 “waiting for your permission”

---

### M4 — Server / CLI / WebSocket 集成（3–5d）

| 文件 | 改动 |
|------|------|
| `main.py` | async toolkit；agent 构造去 formatter；memory middleware 可选 |
| `server.py` | `_create_analyst_toolkit` → await factory；分析 handler 里创建 agents |
| `websocket/*` | **尽量不动**事件名；若 extract 文本变空再修 |
| 前端 | 冒烟即可 |

注意：

- 创建 Toolkit/Agent 的路径必须在 async 上下文
- 生命周期：每个 session 新建 agents 还是复用？保持 1.x 行为（通常每任务一套或按 server 现逻辑）
- 并发两个 session：AgentState 不可跨 session 共享

**M4 验收**

1. `uv run python backend/server.py`（或项目入口）
2. 前端连 WS → `start_analysis`
3. 看到 agent / conference / report 事件
4. DB 有 session completed + report

---

### M5 — 测试、文档、收尾（3–5d）

#### 5.1 测试矩阵

| 用例 | 级别 | 说明 |
|------|------|------|
| compat 消息/抽取 | 单元 | 无网络 |
| toolkit 注册 schemas | 单元 | |
| model 工厂各 provider 构造 | 单元 | 不真调 API 也可 |
| 单 Agent tool call | 集成 | 需 Key |
| 全 pipeline 1 ticker | 集成 | 需 Key |
| 2 tickers + 2 conference cycles | 集成 | |
| enable-memory 开/关 | 集成 | 可 xfail 若 M5 未完成 |
| WS 一轮 | 手工/脚本 | |
| 权限未 BYPASS 时失败可读 | 单元/集成 | 防止静默挂起 |

现有 `tests/` 几乎不覆盖 Agent — **必须新建** `tests/agentscope2/`。

#### 5.2 文档

- `AGENTS.md`：版本改为 2.0.5；ReActAgent/MsgHub 描述更新
- `README.md`：依赖与最小示例
- `docs/spike-as205/DECISION.md` 顶部加注：「项目已决定迁移，见 migration-plan」
- Changelog / PR 描述：breaking 列表

#### 5.3 清理

- 删除一切 `register_tool_function`、`InMemoryMemory`、`MsgHub` 残留
- `get_agent_formatter` 若无外部用处则废弃
- `.venv-as205-spike` 仅本地，已 gitignore

---

## 5. 文件级工作分解（WBS）

| 文件 | 动作 | 阶段 | 预估 |
|------|------|------|------|
| `pyproject.toml` / `uv.lock` | 钉 `agentscope==2.0.5` | M0 | 0.5d |
| `backend/agents/as2_compat.py` | **新建** | M1 | 1.5d |
| `backend/agents/toolkit_factory.py` | **新建** | M1 | 1d |
| `backend/agents/base_agent.py` | **新建** | M2 | 1d |
| `backend/llm/models.py` | 重写 | M1 | 2d |
| `backend/agents/tools/*.py` | 统一 ToolResponse；小改 | M1 | 1d |
| `backend/agents/analyst.py` | 重写构造/基类 | M2 | 1d |
| `backend/agents/risk_agent.py` | 重写 + 修 ToolResponse | M2 | 1.5d |
| `backend/agents/pm_agent.py` | 重写 | M2 | 1d |
| `backend/core/conference_hub.py` | **新建** | M3 | 2d |
| `backend/core/pipeline.py` | 大改消息/会议/Phase0 | M3 | 4–6d |
| `main.py` | 装配 | M4 | 1d |
| `server.py` | 装配 | M4 | 1d |
| `tests/agentscope2/*` | 新建 | M1–M5 | 3d |
| 文档 | 更新 | M5 | 1d |
| 联调缓冲 | | | 2–4d |

约 **212 处** agentscope 相关触点（rg 统计），集中在上表文件。

---

## 6. 关键实现草图（可直接当 coding 规格）

### 6.1 消息

```python
# 旧
Msg(name="system", content=prompt, role="user")

# 新
from backend.agents.as2_compat import system_user_msg
system_user_msg(prompt, metadata={"tickers": tickers})
```

### 6.2 工具注册

```python
# 旧
toolkit = Toolkit()
toolkit.register_tool_function(analyze_growth)

# 新
toolkit = Toolkit()
await toolkit.add_tool(FunctionTool(analyze_growth))
```

### 6.3 Agent

```python
# 旧
ReActAgent(name=..., sys_prompt=..., model=..., formatter=..., toolkit=..., memory=InMemoryMemory(), max_iters=10)

# 新
Agent(
  name=...,
  system_prompt=...,
  model=model,  # 内部已带 credential/formatter
  toolkit=toolkit,
  state=make_agent_state(bypass=True),
  react_config=ReActConfig(max_iters=10),
)
```

### 6.4 Phase0

```python
# 旧
await analyst.memory.clear()

# 新
st = analyst.state
# 保留 permission_context，只清对话
st.context = []
# 如有 middle_context 等短时字段，按需一并清（实施时读 AgentState 字段）
```

### 6.5 会议

```python
hub = ConferenceHub([*self.analysts, self.risk_manager, self.pm])
await hub.announce(f"Starting investment analysis cycle for {date}...")
# Phase1–2 仍可直接 reply；若需全员可见，reply 后 hub.broadcast
pm_resp = await hub.speak(self.pm, system_user_msg(pm_prompt))
```

### 6.6 模型（OpenAI 兼容）

```python
cred = OpenAICredential(api_key=api_key)
model = OpenAIChatModel(
    credential=cred,
    model=model_name,
    stream=False,  # 或 True + 仍用 reply() 聚合
    client_kwargs={"base_url": base_url} if base_url else None,
    formatter=OpenAIChatFormatter(),  # 若构造支持
)
```

---

## 7. 风险登记与缓解

| ID | 风险 | 影响 | 缓解 |
|----|------|------|------|
| R1 | ConferenceHub 语义 ≠ 旧 MsgHub | 会议质量/上下文丢失 | 对照 1.x 同 ticker 各跑 1 次人工 diff transcript |
| R2 | 默认 permission ASK | 生产假死 | 强制 BYPASS/allow；启动时 assert |
| R3 | Provider Credential 差异 | 部分供应商挂 | M1 按 `.env` 实际 provider 优先；其它标 known issue |
| R4 | `add_tool` 异步遗漏 | 空 toolkit | factory 统一 await；测试 schemas 非空 |
| R5 | 文本抽取漏块/混 thinking | 报告垃圾 | 单测 blocks；过滤 thinking |
| R6 | bound method → FunctionTool | risk/pm 工具失败 | 实测 schema 与 live call |
| R7 | ReMe 行为变化 | enable-memory 挂 | M2 主路径关 memory；M5 专项 |
| R8 | 依赖解析/锁文件 | 安装失败 | 统一 **uv**；文档写明 |
| R9 | 一次大 PR 难审 | 回滚难 | 按 M0–M5 多 PR 或同一分支多 commit 可 cherry-pick |
| R10 | 无 Agent 测试家底 | 回归靠人 | 先写 compat 单测再改 pipeline |

---

## 8. 回滚方案

| 层级 | 方法 |
|------|------|
| Git | `main` 不合并直到 M5；`feat/agentscope-2.0.5` 可弃 |
| 依赖 | 恢复 `uv.lock` 中 1.0.13/1.x |
| 数据 | 无 schema 强依赖 AS 版本；DB 一般不用迁 |
| 运行 | 生产未切流量前仅开发环境验 |

**不做**长期 1.x/2.0 运行时双栈（成本高于分支回滚）。

---

## 9. PR / Commit 建议切片

1. `chore: pin agentscope 2.0.5 and add as2 compat scaffolds`
2. `feat(llm): credential-based model factory for agentscope 2`
3. `feat(agents): toolkit factory + tool response fixes`
4. `feat(agents): port Analyst/Risk/PM to Agent base`
5. `feat(pipeline): ConferenceHub replace MsgHub + message migration`
6. `feat(server): async agent wiring for 2.0`
7. `test: agentscope2 smoke and unit tests`
8. `docs: AGENTS/README migration notes`

每片可独立 review；**从第 5 片起功能才闭环**。

---

## 10. 验收清单（Definition of Done）

### 10.1 功能

- [ ] `agentscope.__version__ == "2.0.5"`
- [ ] CLI 单票完整评级报告
- [ ] CLI 双票 + `MAX_COMM_CYCLES>=1` 会议摘要非空
- [ ] fundamentals / valuation 工具至少各 1 次真实 tool call（日志或 transcript 可见）
- [ ] Server + WS 前端完整一轮，`session=completed`
- [ ] 报告落库可 `GET /api/sessions/{id}/report`
- [ ] 无 permission 等待假死
- [ ] Phase0 后第二轮分析不泄漏上一票 context（同进程连续两次）

### 10.2 工程

- [ ] 无 `MsgHub` / `InMemoryMemory` / `register_tool_function` / `ReActAgent` 引用
- [ ] `uv lock` 可复现安装
- [ ] `tests/agentscope2` 在 CI 可跑（live 标 optional）
- [ ] AGENTS.md 与版本一致

### 10.3 性能/体验（基线记录即可）

- [ ] 记录 1 ticker 端到端耗时 vs 1.x（允许变慢，需无数量级回退）
- [ ] WS 事件顺序与 1.x 基本一致

---

## 11. 迁移后可选增强（Backlog，非本期门禁）

1. **投委会 HITL**：`waiting_human` + 人类意见注入 ConferenceHub（用 2.0 事件或自建 Future）  
2. 高危 tool 用 `DEFAULT`+确认，分析 tool 保持 ALLOW  
3. `reply_stream` 推 token 级 WS（前端打字机）  
4. `LocalWorkspace` / Docker 跑代码类工具  
5. `ReplyBudgetControlMiddleware` 控成本  
6. 评估是否采用官方 `agentscope.app` 多 session（大决策，另开 RFC）

---

## 12. 执行顺序（给你直接开工用）

```text
Day 1–2    M0 分支 + 依赖 + 空壳模块
Day 3–7    M1 compat + models + toolkit_factory
Day 8–14   M2 三 Agent
Day 15–23  M3 ConferenceHub + pipeline
Day 24–28  M4 server/cli/ws
Day 29–35  M5 测试文档缓冲
```

**第一个编码任务（M0+M1 启动）建议：**

1. 建分支，钉 `agentscope==2.0.5`，`uv sync`  
2. 实现 `as2_compat.user_msg` / `extract_text` / `make_agent_state`  
3. 实现 `toolkit_factory.build_toolkit`  
4. 重写 `get_agent_model` 对 SILICONFLOW/OPENAI 路径  
5. 写 3 个单元测试再动 Agent 类  

---

## 13. 参考材料（仓库内）

| 路径 | 用途 |
|------|------|
| `docs/spike-as205/DECISION.md` | 实测 breaking 清单 |
| `docs/spike-as205/spike-report.md` | 自动探针 |
| `docs/spike-as205/poc/poc_offline.py` | FunctionTool / ManualHub / 子类样例 |
| `docs/spike-as205/poc/poc_live_llm.py` | Credential + BYPASS + live tool |
| `docs/agentscope-2.0-spike-checklist.md` | 原 spike 过程 |
| 官方文档 | https://docs.agentscope.io/ （2.0.x） |

---

## 14. 签署式摘要

| 决策 | 内容 |
|------|------|
| 升到 | **2.0.5 精确版本** |
| 方式 | **适配层 + 自建 ConferenceHub + 重写 Agent/Model/Toolkit 装配** |
| 不替换 | FastAPI / WS / 业务 Phase 语义 / 领域工具算法 |
| 默认权限 | **BYPASS 或业务 tool 全 ALLOW** |
| 工期 | **24–36 人天** |
| 完成标志 | CLI+Server 全链路评级与 1.x 能力对齐，无 MsgHub/1.x API 残留 |

---

*本文是实施规格，不是再评估“要不要升”。下一步从 M0 建分支改依赖开始即可。*
