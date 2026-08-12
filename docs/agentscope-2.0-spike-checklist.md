# AgentScope 2.0.5 升级 Spike Checklist（2 天）

> 目标：用 **2 个工作日** 验证 ainvestor 能否以可接受成本迁到 `agentscope==2.0.5`，并给出 **GO / CONDITIONAL / NO-GO**。  
> 本 spike **不改主工程依赖**，不在 `main` 上直接升级。

## 背景约束（来自当前仓库）

| 项 | 现状 |
|----|------|
| 锁定版本 | `uv.lock` → **1.0.13**（`pyproject`: `>=1.0.13`） |
| 核心用法 | `ReActAgent` 子类、`Msg`、`Toolkit.register_tool_function`、`ToolResponse`+`TextBlock`、`MsgHub`、`InMemoryMemory` / ReMe、model+formatter 工厂 |
| 编排 | `backend/core/pipeline.py` 固定 Phase0–7 + 会议多轮 |
| 实时通道 | 自建 WebSocket（以下行为主） |
| 后续诉求 | 投资会议 HITL：人类插话 → Agent 判断是否采数 |

**重要：** 2.0 官方 HITL 偏 **工具确认 / 外部执行暂停**，不等于投委会人类发言。即便 API 全绿，HITL 产品仍要自建会议闸门。

---

## 日程总览

| 时间 | 焦点 | 产出 |
|------|------|------|
| Day 1 上午 | 隔离环境 + 静态 API 探针 | `spike-report.json` / 初版 markdown |
| Day 1 下午 | 最小运行时（无/弱 LLM）+ 工具/消息/MsgHub | 6 门关键题 yes/no |
| Day 2 上午 | 可选 live LLM 冒烟 + 与 pipeline 映射 | 风险清单 |
| Day 2 下午 | 估时校准 + GO/NO-GO 决议 | 决议记录、是否启动迁移 |

---

## Day 0 准备（30–60 分钟，可前一晚做）

- [ ] 确认本机 Python `>=3.11`（2.0 要求；项目已是 `>=3.12`）
- [ ] 网络可访问 PyPI（或已有 `agentscope-2.0.5` wheel 离线包）
- [ ] 准备隔离目录（**不要**污染项目 `.venv`）：

```bash
cd /path/to/ainvestor
python3 -m venv .venv-as205-spike
source .venv-as205-spike/bin/activate
pip install -U pip
pip install "agentscope==2.0.5"
# 若探针需要异步 SQL / 你们常用 provider 客户端，可按需追加：
# pip install openai httpx
python scripts/agentscope_2_spike_probe.py --out docs/spike-as205
```

- [ ] （可选）复制一份最小 `.env` 到 spike 环境，仅当要跑 live LLM：
  - `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `MODEL_NAME`
  - 或 `DASHSCOPE_API_KEY`
- [ ] 约定：spike 分支名建议 `spike/agentscope-2.0.5`（只提交报告与脚本，不改 `uv.lock`）

---

## Day 1 — API 存活与最小编排

### 上午：自动探针（必须）

- [ ] 运行：

```bash
source .venv-as205-spike/bin/activate
python scripts/agentscope_2_spike_probe.py \
  --expected-version 2.0.5 \
  --out docs/spike-as205 \
  --fail-on critical
```

- [ ] 打开 `docs/spike-as205/spike-report.md`，确认下列 **P0** 结果：

| ID | 探测项 | 你们 1.x 依赖 | 通过标准 |
|----|--------|---------------|----------|
| P0-01 | 版本 == 2.0.5 | lock 迁移前提 | exact 或兼容 |
| P0-02 | `ReActAgent` 可 import | 3 个 Agent 子类 | 存在且可子类化，或文档给出等价基类 |
| P0-03 | `Msg`（或等价消息构造） | pipeline 全链路 | 能构造 user/system/assistant 并读出文本 |
| P0-04 | `Toolkit` + 注册自定义函数 | fundamentals/valuation tools | 不用重写为 class 也能挂 Python 函数 |
| P0-05 | `ToolResponse` / 文本块返回 | 所有 tools | tool 能把结果返回给 agent 循环 |
| P0-06 | `MsgHub` 或等价多 agent 广播 | 会议 Phase3 | 存在语义清晰的多参与者共享消息机制 |
| P0-07 | `reply` 可拿到完整答案 | 报告/WS 抽取 | 非仅 stream；或有稳定的 drain-to-Msg 方式 |
| P0-08 | `InMemoryMemory` + `memory.clear` | Phase0 | 可清空短期记忆 |

- [ ] 记录 P1（可 workaround）：

| ID | 探测项 | 影响 |
|----|--------|------|
| P1-01 | `OpenAIChatModel` + 自定义 `base_url` | DeepSeek/硅基等 |
| P1-02 | `DashScopeChatModel` | 国内主路径 |
| P1-03 | `*ChatFormatter` / multi-agent formatter | `get_agent_formatter` |
| P1-04 | `ReMeTaskLongTermMemory` | `--enable-memory` |
| P1-05 | `long_term_memory_mode` 参数 | analyst/pm 构造 |
| P1-06 | HITL 事件：`RequireUserConfirmEvent` 等 | 仅当想用官方 tool-HITL |
| P1-07 | Interrupt：`UserInterruptEvent` / cancel 语义 | 长任务打断 |
| P1-08 | `UserAgent` / 人类参会入口 | 投委会真人 |

### 下午：手写最小 PoC（必须，即便自动探针全绿）

在 spike venv 中新建临时文件（可放 `docs/spike-as205/poc/`，**勿接入 server**）：

- [ ] **PoC-A 单 Agent + 自定义 tool**
  - 注册一个纯函数 tool：`add(a,b)` 或 `echo_ticker(ticker)`
  - `await agent.reply(...)`（或 drain stream）得到含 tool 结果的最终文本
  - 验收：不靠官方 Bash/Grep 工具，**业务 Python 函数**可用

- [ ] **PoC-B 消息文本抽取**
  - 用与 `RatingPipeline._extract_text_content` 同类逻辑解析 2.0 返回
  - 验收：能稳定得到 `str`，忽略 thinking/tool 中间块（若有）

- [ ] **PoC-C 双 Agent + 共享上下文**
  - 优先复现 `MsgHub`：PM 发言后分析师能读到
  - 若无 MsgHub：用官方 Team / 手动 memory 注入做等价
  - 验收：写出「ainvestor 会议」映射方案（保留 MsgHub / 替换为 X）

- [ ] **PoC-D 子类化**
  - `class SpikeAnalyst(ReActAgent或等价): async def reply...`
  - 验收：可 override 并调用 `super()`，或明确「禁止子类、改用 middleware」

### Day 1 结束门禁

填写：

```text
P0 通过数:  _ / 8
MsgHub 策略:  保留 / 替换为 ______ / 未知
Tool 注册策略: register_function / ToolBase class / 其它
reply 策略:   一次性 Msg / 必须 event drain
Day1 结论:    继续 Day2 live / 已可 NO-GO
```

**提前 NO-GO 条件（满足任 2 条可直接停）：**

1. 无法注册普通 Python tool 函数（必须大改 tools 层）
2. 无任何可用的多 Agent 共享消息原语，且 Team 无法表达「同轮广播会议」
3. 无法在非 UI 场景得到完整最终文本（只能碎事件且无官方聚合）
4. 不能子类化/扩展 Agent，导致 3 个业务 Agent 模式推倒

---

## Day 2 — 运行时真实度 + 成本校准

### 上午：Live 冒烟（有 Key 才做；无 Key 则标 N/A，不阻塞决议）

```bash
source .venv-as205-spike/bin/activate
python scripts/agentscope_2_spike_probe.py \
  --expected-version 2.0.5 \
  --out docs/spike-as205 \
  --live-llm \
  --live-timeout 90
```

- [ ] **L-01** 单轮 chat：模型能回复
- [ ] **L-02** tool calling：模型主动调自定义 tool 并给出最终回答
- [ ] **L-03**（可选）OpenAI-compatible `base_url` 通
- [ ] **L-04**（可选）DashScope 通
- [ ] 记录：token/延迟/报错类型（鉴权、formatter、tool schema）

### 上午：与 ainvestor 模块映射

对每个模块标 `Reuse / Adapter / Rewrite`：

| 模块 | 1.x 依赖 | 2.0 结论 | 人天初估 |
|------|----------|----------|----------|
| `backend/agents/analyst.py` | ReActAgent 子类 | | |
| `backend/agents/risk_agent.py` | 子类 + 内置 tools | | |
| `backend/agents/pm_agent.py` | 子类 + decision tool | | |
| `backend/agents/tools/*` | ToolResponse/TextBlock | | |
| `backend/llm/models.py` | model+formatter 工厂 | | |
| `backend/core/pipeline.py` | MsgHub+reply 编排 | | |
| `main.py` / `server.py` | 装配 | | |
| ReMe 路径 | 可选 | | |
| WebSocket | 间接 | 升 2.0 本身可不改 | |
| HITL 会议闸门 | 无 | 2.0 不能替代产品设计 | |

### 下午：估时校准与决议

- [ ] 用探针失败项刷新此前区间：
  - 方案 A 最小兼容：原估 16–29 人天 → 本次 **\_\_** 人天
  - 方案 B 惯用重写：原估 21–34 人天 → 本次 **\_\_** 人天
  - 方案 C 仅 1.x HITL：8–14 人天（对照）
- [ ] 明确 HITL：升 2.0 后是否仍要自建 `waiting_human`？
  - 预期答案：**是**（官方 HITL ≠ 投委会插话）
- [ ] 写出决议（三选一）：

| 决议 | 含义 |
|------|------|
| **GO** | P0 全过，MsgHub/Tool/reply 有清晰适配，方案 A ≤ 15 人天可接受 |
| **CONDITIONAL** | 可迁，但会议或 tool 需 Rewrite；仅当业务强依赖 2.0 沙箱/托管时启动 |
| **NO-GO** | P0 多处红灯，或迁移人天 ≥ 直接自建 HITL 的 2×；维持 1.x 并 pin `<2` |

### 决议记录模板

```markdown
## Spike 决议
- 日期:
- 探针版本:
- P0: x/8
- Live LLM: 通过 / 失败 / N/A
- 决议: GO | CONDITIONAL | NO-GO
- 理由（3 条内）:
  1.
  2.
  3.
- 下一步:
  - [ ] 维持 1.x，执行 HITL MVP
  - [ ] pin agentscope>=1.0.19,<2
  - [ ] 启动迁移分支（仅 GO/CONDITIONAL）
- 报告路径: docs/spike-as205/
```

---

## 验收脚本说明

脚本：`scripts/agentscope_2_spike_probe.py`

| 模式 | 命令 | 作用 |
|------|------|------|
| 静态+构造探测 | 默认 | import、签名、最小对象、MsgHub/Toolkit |
| 严格门禁 | `--fail-on critical` | P0 失败则 exit 2 |
| Live LLM | `--live-llm` | 真实模型+tool（需 Key） |
| 对比安装 | 在 spike venv 跑 | 避免误测项目 1.0.13 |

**退出码：**

| Code | 含义 |
|------|------|
| 0 | 无 critical 失败（或未启用 fail-on） |
| 1 | 脚本自身错误（环境/参数） |
| 2 | 存在 critical 探测失败（`--fail-on critical`） |
| 3 | 存在 high 失败（`--fail-on high`） |

**产出文件（`--out DIR`）：**

- `spike-report.json` — 机器可读全量结果  
- `spike-report.md` — 人读摘要 + GO 建议  
- `spike-raw-exports.json` — 各模块 export 列表（便于 diff 1.x）

---

## 与 HITL 的关系（避免 spike 目标漂移）

| 问题 | Spike 应回答 |
|------|----------------|
| 2.0 能不能少写 pause/resume？ | 对 **tool 审批** 可能；对 **会议插话** 基本不能 |
| 要不要为 HITL 升 2.0？ | 仅当 P0 全绿 **且** 迁移人天明显小于自建，或还要沙箱/多租户托管 |
| 推荐默认路径 | **1.x + 自建 human gate**；本 spike 用于给「将来迁 2.0」定价 |

---

## 清理

```bash
deactivate
rm -rf .venv-as205-spike
# 保留 docs/spike-as205/ 报告作决策附件
```

勿将 spike venv、临时 PoC 密钥提交进 git。
