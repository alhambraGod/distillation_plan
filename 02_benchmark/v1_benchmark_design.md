# V1 Agent-Service Benchmark 专项设计

> 对应 V1 架构：多节点流程 agent-service。  
> 本文档是 `eval_spec.md` 的 V1 专属补充。

## V1 特点（影响评估方式）

- **多节点**：每个节点可能是独立 LLM 调用
- **节点之间有明确的数据流**（节点 A 产出 → 节点 B 消费）
- **失败可能发生在任一节点**
- **业务领域**：（按实际填；示例：客户分析、渠道分析、文案生成）

## 节点级评估（V1 特有）

相比 V2 的"整个 agent 一起看"，V1 需要能定位**是哪个节点失败**：

| 节点失败模式 | 评估指标 |
|---|---|
| 节点提前终止 | 节点完成率 = 实际完成节点数 / 期望节点数 |
| 节点输入格式错 | 节点输入有效率 |
| 节点输出格式错 | 节点输出有效率 |
| 节点超时 | 节点 p95 时延 |

### 实现思路

benchmark case 扩展字段：
```json
{
  "case_id": "v1_bench_001",
  ...（通用字段）,
  "expected_nodes": ["classifier", "retriever", "writer", "reviewer"],
  "node_specs": {
    "classifier": {"expected_output_schema": {...}},
    "retriever": {"expected_sources_min": 3},
    ...
  }
}
```

harness 针对 V1 case 额外跑 `NodeCompletionRate`、`NodeOutputValid` 等指标。

## 小模型替代粒度

V1 架构里，**不是每个节点都要上小模型**。可分三类：

| 节点类型 | 建议模型 |
|---|---|
| 结构化抽取/分类（短输入短输出） | 小模型（最省钱，最好训） |
| 长文本生成（marketing copy） | 中等规模，可能需要 SFT + DPO |
| 最终审核/关键决策 | 保留 Claude |

benchmark 要能支持"某几个节点换成小模型，其他保留线上教师"的混合评估。

## 节点路由建议

在 `05_serving/router.py` 里加一层节点级路由：
```python
NODE_ROUTING = {
    "classifier": "local-qwen-classifier-lora",   # 最容易替代
    "retriever": "approved-teacher",              # 保留线上教师
    "writer": "local-qwen-writer-sft",             # SFT 训练
    "reviewer": "approved-teacher",               # 保留线上教师
}
```

## V1 evaluation 的坑

1. **节点间依赖**：某节点挂了，下游全挂——要区分"下游自己不行"和"上游没给好输入"。harness 跑 benchmark 时给下游**固定输入**测能力，跑真实 e2e 测协同。
2. **V1 日志 schema 可能不规整**：如果历史 trace 没有明确的节点标记，需要先做一轮"节点边界识别"才能抽 per-node 数据。
3. **节点粒度 vs 整体指标**：两个都要报。节点 F1 高但整体成功率低，说明协同出问题。

## 推荐 benchmark 集规模（V1）

- 黄金集：200 条（整体 e2e）
- 节点级回放集：每节点 200-500 条（独立测该节点能力）
- 压测集：50 条长输入
