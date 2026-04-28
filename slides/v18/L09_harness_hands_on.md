---
marp: true
theme: default
paginate: true
header: 'L09 · Harness 实操'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #7E22CE; border-bottom: 4px solid #7E22CE; padding-bottom: 8px; }
  h2 { color: #9333EA; }
  section.cover { background: linear-gradient(135deg, #7E22CE 0%, #9333EA 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #7E22CE; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  .big { font-size: 44px; text-align: center; color: #7E22CE; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L09 · Harness 实操

## 评估框架代码走读 + 跑基线

<br>

📅 **第 9 课 · 60 分钟**
📚 教材：`harness_design.md` + `02_benchmark/harness/*.py`

---

## 🎯 本课目标

- 理解 Harness 架构
- 掌握 7 种指标实现
- 能加新指标
- **动手**：对 Claude + Qwen base 跑一次基线

---

## 🏗️ Harness 架构

```
Runner（主循环）
  │
  ├── ModelClient（统一 LLM 接口）
  │     ├── ClaudeClient
  │     └── OpenAICompatClient (vLLM / Ollama)
  │
  ├── MetricSuite
  │     ├── SuccessRate
  │     ├── ToolCallF1
  │     ├── JSONValidRate
  │     ├── LatencyMs (P50/P95)
  │     └── LLMJudge
  │
  └── Reporter（markdown + raw JSON）
```

---

## 📐 BenchmarkCase 数据结构

```python
@dataclass
class BenchmarkCase:
    case_id: str
    task_type: str              # v1 / v2
    system: str
    skills_loaded: list[str]
    initial_input: dict
    expected_status: str
    expected_tools: list[str]
    golden_output: str
```

<br>

一条 case = 一次 agent 的完整执行。

---

## 🔧 ModelClient 统一接口

```python
class ModelClient(Protocol):
    name: str
    def run(
        self,
        case: BenchmarkCase,
        tools: list[dict] | None = None,
        timeout: float = 120.0,
    ) -> Trace: ...
```

<br>

**扩展点**：加新 LLM 只需实现这个协议。

---

## 📊 7 种指标

| 指标 | 实现 | 用途 |
|---|---|---|
| SuccessRate | 1 if status 对 | 总体 |
| ToolCallExactMatch | 序列完全一致 | 严格 |
| ToolCallF1 | 集合 F1（容忍顺序） | 宽松 |
| JSONValidRate | tc.arguments 能 parse | 格式 |
| SchemaValidRate | jsonschema.validate | 结构 |
| LatencyMs | P50/P95 | 性能 |
| TokensPerCase | prompt + completion | 成本 |

---

## 🧑‍⚖️ LLM-as-Judge 实现

```python
class LLMJudge:
    def score(self, case, trace) -> JudgeScore:
        prompt = JUDGE_PROMPT.format(
            user_input=case.initial_input,
            ai_output=trace.final_output,
            golden_output=case.golden_output,
        )
        resp = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": prompt}],
        )
        return parse_json(resp.content[0].text)
```

<br>

**关键**：Judge prompt **版本化**，跨批次才可比。

---

## 🎯 Judge Prompt 模板

```
你是严格的营销内容评估专家。

用户输入：{user_input}
AI 输出：{ai_output}
标准参考：{golden_output}

评估维度（1-5 分）：
1. 可用性 (Usability)
2. 相关性 (Relevance)
3. 完整性 (Completeness)
4. 风格一致性 (StyleFit)

严格要求：
- 每项必须附一句话理由
- 严重问题可用性 ≤ 2

只输出 JSON：{...}
```

---

## 🏃 跑基线示例

```bash
# Step 1: Claude 基线
python -m benchmark.harness.runner \
  --cases data/datasets/v2/benchmark_golden.jsonl \
  --model claude-3-5-sonnet \
  --out-dir reports/baseline_v2/

# Step 2: Qwen 7B zero-shot
python -m benchmark.harness.runner \
  --cases data/datasets/v2/benchmark_golden.jsonl \
  --model local-qwen2.5-7b \
  --out-dir reports/baseline_v2/

# 自动输出 report.md + raw.jsonl
```

---

## 📊 Reporter 输出

```markdown
# Benchmark Report: local-qwen2.5-7b

- Eval Spec: v1.0
- Total cases: 200

## Metrics
| success_rate     | 72.3% |
| tool_f1          | 84.5% |
| json_valid_rate  | 96.1% |
| avg_tokens       | 2450  |
| latency_p50_ms   | 3200  |
| latency_p95_ms   | 8900  |

## Top Failures
...
```

---

## 🔬 加新指标的步骤

```python
# 1. 新建 metric
class FirstTokenLatency(Metric):
    name = "first_token_latency_ms"
    def compute_single(self, case, trace) -> float:
        return trace.metadata["first_token_ms"]

# 2. 加到 DEFAULT_METRICS
DEFAULT_METRICS = [..., FirstTokenLatency()]
```

<br>

**Harness 设计**：指标独立 class，可插拔。

---

## 🧪 单元测试

harness 每个 metric 应有单测：

```python
def test_tool_f1():
    case = BenchmarkCase(
        expected_tools=["search", "analyze"],
        ...
    )
    trace = Trace(
        tool_calls=[
            ToolCall(name="search", arguments={}),
        ],
    )
    assert ToolCallF1().compute_single(case, trace) == 2/3
```

---

## ⚠️ 常见坑

1. **并发太高**：Claude API 限流 → 起步 5 并发
2. **超时太短**：长任务挂 → 默认 120s
3. **无断点续传**：跑一半崩要重来 → `--resume`
4. **Judge 用了最贵模型**：每条 case $$$ → 用 Haiku 或降频
5. **没版本化 eval_spec** → 跨版本不可比

---

## 🏋️ 实操（25 分钟）

```bash
# 拉 50 条黄金集样本
# 跑 Claude + Qwen 2.5-7B 双组
# 打印对比表

python scripts/compare_models.py \
  --cases data/pilot_50.jsonl \
  --models claude-3-5-sonnet local-qwen2.5-7b
```

现场讨论：
- 两个差距多大？
- 哪类任务差距大？
- 值得训练吗？

---

## 🏠 课后作业

1. 加一个新 metric：`HallucinationRate`
2. 写单测
3. 对 50 条样本跑 Claude + 1 个 open model

<br>

**下节课**：L10 SFT 原理 + demo

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: Benchmark 要跑多久？→ A: 200 条 × 5s/case × 5 并发 ≈ 3-5 分钟
- Q: Judge 是不是慢？→ A: 是，建议先跑技术指标，Judge 每天定时跑
- Q: 能不能用现成框架？→ A: Agent 多轮 + 工具调用现成的不适配
