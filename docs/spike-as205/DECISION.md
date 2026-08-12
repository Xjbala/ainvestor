# AgentScope 2.0.5 Spike 决议

- **日期**: 2026-07-28
- **探针版本**: `agentscope==2.0.5`（隔离 `.venv-as205-spike`，`uv pip install`）
- **环境**: Python 3.13.9 / darwin arm64
- **Live LLM**: SiliconFlow `Pro/MiniMaxAI/MiniMax-M2.5`（`OPENAI_*` 兼容）— **通过**（需 `PermissionMode.BYPASS`）

## 决议

# **NO-GO（当前不为 HITL / 主路径升级 2.0.5）**

| 项 | 结果 |
|----|------|
| 自动探针 P0 | **6/8 pass，2 fail**（MsgHub / InMemoryMemory）→ 启发式 **NO-GO** |
| Offline PoC | A/B/C/D/MEM 核心通过；**1.x `register_tool_function` 已删除** |
| Live PoC | tool calling 成功返回 `42`，但默认权限会 **ASK 暂停** |
| 与 HITL 关系 | 2.0 HITL = 工具确认/外部执行；**≠ 投委会人类插话** |

### 理由（3 条）

1. **`agentscope.pipeline` / `MsgHub` 不存在** — `RatingPipeline` Phase3 会议编排无 drop-in 等价物，必须自建 ManualHub / `Agent.observe` / 重写会议层（高成本）。
2. **短期记忆与 Agent 构造全面 breaking** — 无 `InMemoryMemory`；`ReActAgent` 消失，仅 `Agent`；`sys_prompt`→`system_prompt`；`formatter`/`memory` 构造参数移除；model 改为 **Credential 必填**。
3. **为 HITL 升级不划算** — 官方 pause 解决的是 tool permission，不是会议闸门；自建 HITL on 1.x 仍更短。升 2.0 还要额外处理 permission 默认 ASK、tools 全改 `FunctionTool`。

### 下一步（已建议执行）

- [x] 完成本 spike 报告归档于 `docs/spike-as205/`
- [ ] **维持 1.x**，`pyproject` pin：`agentscope>=1.0.19,<2`（或 `>=1.0.13,<2` 后升到 1.0.21）
- [ ] **HITL MVP 做在 1.x pipeline + WebSocket**（`waiting_human` / `human_opinion` / fetch_data）
- [ ] **不**启动 2.0 全量迁移分支（除非未来强需求：沙箱 / 官方 multi-tenant agent service）

---

## 自动探针摘要

详见 `spike-report.md` / `spike-report.json`。

| ID | 结果 | 说明 |
|----|------|------|
| P0-01 版本 2.0.5 | PASS | |
| P0-02 Agent 基类 | PASS | **仅 `Agent`**，无 `ReActAgent`；可 subclass |
| P0-03 消息 | PASS | **`UserMsg` 可用**；`Msg(content=str)` **非法**，必须 `content=[TextBlock...]` |
| P0-04 Toolkit | PASS* | 无 `register_tool_function`；用 **`FunctionTool` + await `add_tool`** |
| P0-05 ToolResponse | PASS | `ToolResponse(content=[TextBlock...])` 仍可用 |
| P0-06 MsgHub | **FAIL** | **`agentscope.pipeline` 整模块不存在** |
| P0-07 reply | PASS | `reply` 仍返回 `Msg`；另有 `reply_stream` 事件 |
| P0-08 InMemoryMemory | **FAIL** | **`agentscope.memory` 不存在**；改用 `AgentState.context` |
| P1 models | WARN/PASS | `OpenAIChatModel(credential=..., model=..., client_kwargs=)` |
| P1 HITL events | PASS | `RequireUserConfirmEvent` 等存在 |
| P1 UserAgent | WARN | **不存在** |

\* 初版探针曾对 `add_tool` 未 await，已在 PoC 中确认必须 `await toolkit.add_tool(...)`。

---

## Offline / Live PoC

| 用例 | 结果 | 证据 |
|------|------|------|
| PoC-A FunctionTool 注册 | PASS | `schemas names=['spike_add']` |
| PoC-A2 register_tool_function | **FAIL**（预期） | API 删除 |
| PoC-B 文本抽取 | PASS | UserMsg / Msg+TextBlock OK；1.x 字符串 content 失败 |
| PoC-C 无 MsgHub 会议 | PASS | ManualHub + `AgentState.context` 广播 |
| PoC-C2 observe | PASS | `Agent.observe(msgs)` 存在 |
| PoC-D 子类 | PASS | `class Spike(Agent)` 可定义；构造必须新签名 |
| PoC-MEM Phase0 | PASS | `state.context = []` |
| Live 17+25 tool | PASS | 返回 `42`；**必须 BYPASS/ALLOW 规则**，否则文案 *waiting for your permission* |

报告文件：

- `poc/poc_offline_report.json`
- `poc/poc_live_report.json`

---

## 1.x → 2.0.5 API 对照（ainvestor 相关）

| 1.x（当前工程） | 2.0.5 | 迁移动作 |
|-----------------|-------|----------|
| `from agentscope.agent import ReActAgent` | `from agentscope.agent import Agent` | 改基类；无 `ReActAgentBase` 继承链 |
| `sys_prompt=` | `system_prompt=` | 全量改名 |
| `formatter=` / `memory=InMemoryMemory()` | 构造器无此参数 | formatter 挂 model；记忆→middleware/`AgentState` |
| `max_iters=` | `react_config=ReActConfig(...)`（需再确认字段） | 查 `ReActConfig` |
| `long_term_memory=` / `long_term_memory_mode=` | `ReMeMiddleware` / `Mem0Middleware` | 重接可选记忆路径 |
| `Msg(name, content:str, role)` | `UserMsg(name, content:str\|blocks)` 或 `Msg(..., content=[TextBlock...])` | **全 pipeline 消息构造** |
| `Toolkit(); register_tool_function(fn)` | `Toolkit(); await add_tool(FunctionTool(fn))` | **所有 tools 装配异步化** |
| `ToolResponse` + `TextBlock` | 基本仍可用 | 小改 |
| `async with MsgHub(participants=...)` | **无** | 自建广播 + `observe` / 共享 state |
| `await memory.clear()` | `agent.state.context = []`（或重建 state） | Phase0 改写 |
| `OpenAIChatModel(model_name, api_key, stream, base_url=)` | `OpenAIChatModel(credential=OpenAICredential(...), model=..., client_kwargs={base_url})` | `models.py` 重写 |
| 无默认 tool 权限 | **DEFAULT=每工具 ASK** | 生产需 `BYPASS` 或 allow_rules，否则会议/分析会挂起等人 |
| 自建 FastAPI+WS | 另有 `agentscope.app`（重依赖） | **不必替换** |

### 模块级 Reuse / Adapter / Rewrite

| 模块 | 判定 | 说明 |
|------|------|------|
| `backend/agents/analyst.py` | **Rewrite** | 基类/构造/reply 签名 |
| `backend/agents/risk_agent.py` | **Rewrite** | 同上 + 内置 tools |
| `backend/agents/pm_agent.py` | **Rewrite** | 同上 |
| `backend/agents/tools/*` | **Adapter** | 返回值大体可留，注册方式变 |
| `backend/llm/models.py` | **Rewrite** | Credential + 新 model API |
| `backend/core/pipeline.py` | **Rewrite（会议）/ Adapter（其它）** | MsgHub 没了；Msg 构造全改；Phase0 记忆改 |
| `main.py` / `server.py` | **Adapter** | 装配 Toolkit/Agent |
| ReMe 路径 | **Rewrite** | middleware 化 |
| WebSocket | **Reuse**（纯升 2.0） | HITL 另做 |
| 前端 | **Reuse** | |

---

## 人天校准（基于实测）

| 方案 | 原估 | **Spike 后** | 说明 |
|------|------|--------------|------|
| A 最小兼容升 2.0 | 16–29 | **→ 按 B 计 24–36** | MsgHub/Memory/Agent 均非兼容，「最小兼容」不存在 |
| B 按 2.0 惯用重写 | 21–34 | **24–36** | 会议层+三 Agent+models+tools 注册+permission |
| C 1.x 只做 HITL | 8–14 | **8–14（不变）** | 仍是推荐路径 |
| 1.x 小升 pin `<2` | 0.5–1.5 | **0.5–1.5** | 建议立刻做 |

**HITL 若强行先升 2.0：**  
迁移 24–36d + HITL 仍 6–12d ≈ **30–45 人天**，对比 1.x HITL **8–14 人天**。

---

## 安装笔记（可复现）

```bash
# pip 曾 resolution-too-deep / 镜像缺 anthropic；改用 uv 成功
python3 -m venv .venv-as205-spike
uv pip install "agentscope==2.0.5" --python .venv-as205-spike/bin/python

source .venv-as205-spike/bin/activate
python scripts/agentscope_2_spike_probe.py --expected-version 2.0.5 --out docs/spike-as205 --fail-on critical
python docs/spike-as205/poc/poc_offline.py
python docs/spike-as205/poc/poc_live_llm.py   # 需 .env 中 OPENAI_*
```

`.venv-as205-spike/` 仅本地 spike，**勿提交**。

---

## 结论一句话

**2.0.5 可跑、可 tool call，但对 ainvestor 是架构级 breaking（无 MsgHub、无 memory 模块、Agent/Model/Toolkit 全换皮）。**  
为投资会议 HITL **没有升级必要**；决议 **NO-GO**，在 1.x 上做 human gate，并把依赖钉在 `<2`。
