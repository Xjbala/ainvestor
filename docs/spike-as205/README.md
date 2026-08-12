# Spike 输出目录（AgentScope 2.0.5）

本目录存放 **隔离 spike venv** 跑探针后的报告，不要用手改 JSON。

## 生成方式

```bash
# 在仓库根目录
python3 -m venv .venv-as205-spike
source .venv-as205-spike/bin/activate
pip install -U pip
pip install "agentscope==2.0.5"

python scripts/agentscope_2_spike_probe.py \
  --expected-version 2.0.5 \
  --out docs/spike-as205 \
  --fail-on critical

# 可选 live（需 API Key）
python scripts/agentscope_2_spike_probe.py \
  --expected-version 2.0.5 \
  --out docs/spike-as205 \
  --live-llm \
  --live-timeout 90
```

## 产出文件

| 文件 | 说明 |
|------|------|
| `spike-report.md` | 人读摘要 + 启发式 GO/CONDITIONAL/NO-GO |
| `spike-report.json` | 全量机器可读结果 |
| `spike-raw-exports.json` | 各子模块 export 快照，便于和 1.x diff |

清单与两日流程见：[`../agentscope-2.0-spike-checklist.md`](../agentscope-2.0-spike-checklist.md)

## 注意

- 必须在 **安装了 2.0.5 的 spike venv** 里跑；用项目 `.venv`（1.0.13）或系统 1.x 会得到错误基线。
- 启发式决策不能替代 Day1 手工 PoC-A/B/C。
- `.venv-as205-spike` 不要提交到 git。
