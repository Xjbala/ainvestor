# AgentScope Spike Probe Report

- Generated (UTC): `2026-07-28T09:24:33.259253+00:00`
- Python: `3.13.9 | packaged by Anaconda, Inc. | (main, Oct 21 2025, 19:11:29) [Clang 20.1.8 ]`
- agentscope: `2.0.5`
- file: `/Users/aceplus/devlop/llm/ainvestor/.venv-as205-spike/lib/python3.13/site-packages/agentscope/__init__.py`

## Decision (heuristic)

**NO-GO** — P0 pass 6/8 (warn 0, fail 2)

- P0 fail=2, warn=0, pass=6/8
- Multiple critical API gaps — prefer stay on 1.x + self-built HITL
- MsgHub/conference primitive weak — Phase3 cost dominates

> Automated decision is advisory. Day1 PoC-A/B/C and human checklist override this.

## Checks

| ID | Sev | Status | Title | Detail |
|----|-----|--------|-------|--------|
| P0-01 | critical | **pass** | Import agentscope / version | version=2.0.5 |
| EXP-agent | info | **pass** | Import agentscope.agent | 5 public names |
| EXP-message | info | **pass** | Import agentscope.message | 17 public names |
| EXP-tool | info | **pass** | Import agentscope.tool | 27 public names |
| EXP-pipeline | critical | **fail** | Import agentscope.pipeline | agentscope.pipeline not importable |
| EXP-memory | critical | **fail** | Import agentscope.memory | agentscope.memory not importable |
| EXP-model | info | **pass** | Import agentscope.model | 15 public names |
| EXP-formatter | info | **pass** | Import agentscope.formatter | 19 public names |
| EXP-event | info | **pass** | Import agentscope.event | 34 public names |
| P0-02 | critical | **pass** | ReActAgent (or equivalent) available | using Agent; methods=['reply', 'reply_stream', '__call__', 'observe']; ReActAgent missing; Agent present (migration t... |
| P0-07 | critical | **pass** | reply() available for full-answer style calls | Class exposes reply(); runtime return type still needs PoC |
| P0-03 | critical | **pass** | Message construction (Msg / UserMsg) | constructed via UserMsg; extracted='hello spike' |
| P0-04 | critical | **pass** | Toolkit custom function registration | Registered via add_tool |
| P0-05 | critical | **pass** | ToolResponse / text return path | Constructed ToolResponse; paths=['ToolResponse(content=[TextBlock...])'] |
| P0-06 | critical | **fail** | MsgHub or multi-agent broadcast primitive | agentscope.pipeline missing |
| P0-08 | critical | **fail** | InMemoryMemory + clear | ModuleNotFoundError: No module named 'agentscope.memory' |
| P1-01 | high | **warn** | OpenAIChatModel present (base_url compatibility manual) | sig=(self, credential: agentscope.credential._openai.OpenAICredential, model: str, parameters: 'OpenAIChatModel.Param... |
| P1-02 | high | **pass** | DashScopeChatModel present |  |
| P1-03 | high | **pass** | Chat formatters present |  |
| P1-CRED | medium | **info** | agentscope.credential module present | 2.0-style credentials may be required |
| P1-06 | medium | **pass** | HITL / interrupt event symbols | found ['ConfirmResult', 'ExternalExecutionResultEvent', 'RequireExternalExecutionEvent', 'RequireUserConfirmEvent', '... |
| P1-08 | medium | **warn** | UserAgent present | UserAgent missing — human-as-participant needs alternate path |
| L-01 | high | **skip** | Live LLM smoke | Pass --live-llm to enable (needs API key) |

## Next actions

1. Keep `agentscope>=1.0.x,<2` pin
2. Build HITL on current pipeline/WebSocket
3. Archive this report under docs/spike-as205/

## Export snapshot

- `agent`: Agent, ContextConfig, InjectionConfig, ModelConfig, ReActConfig
- `agentscope`: exception, logger, set_id_factory, setup_logger, warnings
- `event`: AgentEvent, ConfirmResult, CustomEvent, DataBlockDeltaEvent, DataBlockEndEvent, DataBlockStartEvent, EventBase, EventType, ExceedMaxItersEvent, ExternalExecutionResultEvent, HintBlockEvent, ModelCallEndEvent, ModelCallStartEvent, ReplyEndEvent, ReplyEndReason, ReplyFinishedReason, ReplyStartEvent, RequireExternalExecutionEvent, RequireUserConfirmEvent, TextBlockDeltaEvent, TextBlockEndEvent, TextBlockStartEvent, ThinkingBlockDeltaEvent, ThinkingBlockEndEvent, ThinkingBlockStartEvent ...
- `formatter`: AnthropicChatFormatter, AnthropicMultiAgentFormatter, DashScopeChatFormatter, DashScopeMultiAgentFormatter, DeepSeekChatFormatter, DeepSeekMultiAgentFormatter, FormatterBase, GeminiChatFormatter, GeminiMultiAgentFormatter, MoonshotChatFormatter, MoonshotMultiAgentFormatter, OllamaChatFormatter, OllamaMultiAgentFormatter, OpenAIChatFormatter, OpenAIMultiAgentFormatter, OpenAIResponseFormatter, OpenAIResponseMultiAgentFormatter, XAIChatFormatter, XAIMultiAgentFormatter
- `memory`: 
- `message`: AssistantMsg, Base64Source, ContentBlock, ContentBlockTypes, DataBlock, HintBlock, Msg, SystemMsg, TextBlock, ThinkingBlock, ToolCallBlock, ToolCallState, ToolResultBlock, ToolResultState, URLSource, Usage, UserMsg
- `model`: AnthropicChatModel, ChatModelBase, ChatResponse, ChatUsage, DashScopeChatModel, DeepSeekChatModel, FinishedReason, GeminiChatModel, ModelCard, MoonshotChatModel, OllamaChatModel, OpenAIChatModel, OpenAIResponseModel, StructuredResponse, XAIChatModel
- `pipeline`: 
- `tool`: BackendBase, Bash, Edit, ExecResult, Function, FunctionTool, Glob, Grep, LocalBackend, MCPTool, ParamsBase, PowerShell, Read, RegisteredTool, ResetTools, TaskCreate, TaskGet, TaskList, TaskUpdate, ToolBase, ToolChoice, ToolChunk, ToolGroup, ToolMiddlewareBase, ToolResponse ...
