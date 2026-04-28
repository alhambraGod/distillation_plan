# 数据管线设计

## 目标

把 LangSmith 里的 trace 变成三种产物：
1. **SFT 数据集**（多轮对话 + 工具调用）
2. **偏好对数据集**（DPO 用，阶段 3 才用到）
3. **Benchmark 回放集**（固定样本，跨版本对比）

## 原则

- **V1 / V2 物理隔离**：两套独立的 pipeline，从拉数据到产出数据集不混。
- **按时间窗口拉**：避免一次拉全库，按周/月增量。
- **每一步可重放**：原始数据落 Parquet，下游可从任一中间态重跑。
- **脱敏前置**：敏感字段（邮箱、手机、API key）在清洗阶段就去掉，不等到训练发现。

## 阶段拆解

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 1. pull      │ → │ 2. clean     │ → │ 3. extract   │ → │ 4. build     │
│   拉原始     │   │   清洗+脱敏  │   │   抽字段     │   │   建数据集   │
│   parquet    │   │   分 V1/V2   │   │   成标准样本 │   │   train/val/test │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

## 产出 schema

### SFT 样本（jsonl 一行）
```json
{
  "sample_id": "v2_20260301_000123",
  "task_type": "marketing_ai_v2",
  "system": "You are a marketing agent...",
  "skills_loaded": ["skill_a", "skill_b"],
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "tool_calls": [
      {"id": "call_1", "name": "search", "arguments": {"q": "..."}}
    ]},
    {"role": "tool", "tool_call_id": "call_1", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "final_status": "success",
  "metadata": {
    "run_id": "uuid",
    "start_time": "2026-03-01T...",
    "duration_ms": 12345,
    "token_usage": {"prompt": 2000, "completion": 500}
  }
}
```

### 偏好对样本
```json
{
  "pair_id": "v2_pref_000001",
  "context": {
    "system": "...",
    "messages_prefix": [...]
  },
  "chosen": {
    "content": "...",
    "tool_calls": [...]
  },
  "rejected": {
    "content": "...",
    "tool_calls": [...]
  },
  "source": "sampled_v1_vs_v2" | "llm_judge" | "human_rank"
}
```

### Benchmark case
```json
{
  "case_id": "v2_bench_001",
  "task_type": "marketing_ai_v2",
  "initial_input": {...},
  "expected_status": "success",
  "expected_tools": ["search", "summarize"],
  "expected_tools_strict": false,
  "golden_output": "..." 
}
```

## 清洗规则一览

| ID | 规则 | 处理方式 |
|---|---|---|
| R01 | `run.error != null` | 标记，不进 SFT；进 benchmark（复现用） |
| R02 | `final_status == "cancelled"` | 丢弃 |
| R03 | tool_call JSON 无法 parse | 丢弃 |
| R04 | prompt 或 output 含 email/phone/API key | 正则脱敏替换 |
| R05 | 内容长度 < 50 token 或 > 32k | 丢弃（极短或超长） |
| R06 | 同一 prompt 多次出现 | 保留最新的一次 |
| R07 | 工具返回包含 stack trace 错误 | 保留但打 tag `tool_error` |
| R08 | 无 assistant 消息 | 丢弃（空对话） |

## 下一步

- 代码示例见 `code/`：
  - `pull_traces.py` - 拉 trace
  - `clean.py` - 清洗 + 脱敏
  - `extract_fields.py` - 字段抽取
  - `build_datasets.py` - train/val/test 切分

## 注意事项

1. **LangSmith 流量配额**：一次拉取 5000 条以内；分页+重试；记录 last_run_id 支持断点续传。
2. **PII 脱敏**：至少覆盖 email、手机、身份证、信用卡、常见 API key 前缀（sk-、ghp_ 等）。
3. **去重算法**：用 prompt 的 normalized hash（去除空格和标点后的 sha256）。
4. **数据血缘**：每条样本记录 `source_run_id`，遇到异常能回溯原始 trace。
