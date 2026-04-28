# Benchmark Harness 设计

## 为什么要自己写

现成框架（lm-eval-harness、HELM 等）**假设单轮 QA**，不适合我们的场景：
- 多轮对话
- 工具调用序列
- 中间状态（report_progress）
- 最终 submit_final_report

所以必须自研。但我们不造轮子——复用 `trl` / `datasets` / `langsmith` 等。

## 架构

```
┌──────────────────────────────────────────┐
│  Runner                                   │
│  - 加载 cases                             │
│  - 对每个 case 调用 ModelClient.run()    │
│  - 收集 Trace                             │
└───────────────┬──────────────────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌──────────────┐   ┌──────────────────┐
│ ModelClient  │   │  MetricSuite     │
│ - Claude     │   │ - SuccessRate    │
│ - vLLM       │   │ - ToolCallF1     │
│ - Ollama     │   │ - JSONValid      │
└──────────────┘   │ - Latency        │
                   │ - LLMJudge       │
                   └──────────────────┘
                           │
                           ▼
                   ┌──────────────┐
                   │ Reporter     │
                   │ - Markdown   │
                   │ - JSON raw   │
                   └──────────────┘
```

## 文件组织

```
02_benchmark/harness/
├── __init__.py
├── case.py          # BenchmarkCase / Trace 数据类
├── model_client.py  # 统一 LLM 接口
├── runner.py        # 跑 benchmark 的主循环
├── metrics.py       # 5 类指标实现
├── judge.py         # LLM-as-Judge
└── reporter.py      # 报告生成
```

## 扩展点

### 加新模型
实现 `ModelClient` 协议：
```python
class ModelClient(Protocol):
    def run(self, case: BenchmarkCase) -> Trace: ...
```

### 加新指标
继承 `Metric`：
```python
class MyMetric(Metric):
    name = "my_metric"
    def compute(self, case, trace) -> float: ...
```

## 使用示例

```bash
python -m benchmark.harness.runner \
    --cases ../../data/datasets/v2/benchmark_golden.jsonl \
    --model claude-sonnet \
    --spec eval-spec-v2.md \
    --spec-version v1.0 \
    --out reports/v2_claude_baseline.md
```

## 注意事项

1. **复现性**：每次 run 都记录 seed、model SHA、prompt hash、tool schema。
2. **限流**：对 Claude / OpenAI API 加 semaphore（默认 5 并发）。
3. **超时**：单 case 默认 120s，超时标记为 error 而不是死住。
4. **失败保留**：即使某个 case 报错，其他 case 继续跑；报错 case 单独落 error log。
5. **增量**：支持 `--resume`，跳过已跑完的 case（按 case_id 查 result 文件）。
