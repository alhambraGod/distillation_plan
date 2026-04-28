# Benchmark 报告模板

> 每次跑完 benchmark 都复制这个模板，填空。存在 `benchmark/reports/<date>_<model>.md`。

---

# Benchmark Report: {{model_name}}

- **日期**：YYYY-MM-DD
- **Eval Spec 版本**：v1.0
- **基座模型** + **adapter hash**：
- **Benchmark 集**：v2/benchmark_golden.jsonl @ <git-hash>
- **Arch**：V1 / V2（选一个）
- **评估人**：

## 摘要（先写完整，高层读这段）

3 句话：
- 结果一句话：（比如："Qwen 2.5 7B SFT 在成功率上达到 Claude 的 87%，成本降低 93%"）
- 主要差距一句话：（比如："主要差距在长 horizon 任务和复杂工具调用"）
- 下一步建议一句话：（比如："建议进 DPO 阶段优化风格"）

## 1. 技术指标对比

对比至少一个 baseline（通常是 Claude）和候选模型。

| 指标 | Claude | {{model}} | 差异 |
|---|---|---|---|
| 成功率 | | | |
| 工具调用 F1 | | | |
| 工具调用 Exact Match | | | |
| JSON 有效率 | | | |
| Schema 有效率 | | | |
| 平均迭代次数 | | | |
| LatencyP50 / P95 | | | |
| Tokens / case | | | |
| Cost / case ($) | | | |

## 2. 业务指标（LLM-as-Judge）

| 维度 | Claude | {{model}} |
|---|---|---|
| Usability | | |
| Relevance | | |
| Completeness | | |
| StyleFit | | |

Judge 模型：
Judge prompt 版本：

## 3. 人工评估

- 黄金集人工分（均分）：Claude __ vs {{model}} __
- 采纳率：Claude __% vs {{model}} __%
- 主要失败码分布（F01-F10）：

## 4. 分 segment 指标（V2 额外）

| Segment | Claude 成功率 | {{model}} 成功率 | 差距 |
|---|---|---|---|
| 简单任务 | | | |
| 中等任务 | | | |
| 复杂任务 | | | |
| 长 horizon | | | |
| 未见 skill | | | |

## 5. 分节点指标（V1 额外）

| 节点 | 完成率 | 输出有效率 | p95 时延 |
|---|---|---|---|
| ... | | | |

## 6. Top 10 失败 case 示例

列出 10 条最差 case，每条：
- case_id
- user_input 摘要
- 实际输出摘要
- 失败原因（F01-F10）
- 备注

## 7. Judge vs 人工分歧样本（3 条）

每条：
- Judge 打分 vs 人工打分
- 分歧分析

## 8. 成本、时延分布图

- 时延直方图（附图或链接）
- 成本 vs 成功率散点图（附图或链接）

## 9. 分析 / Analysis

（工程 lead 填。结合指标数据回答：）
- 小模型的主要问题是"能力不足"还是"偏好不匹配"？（影响 DP2 决策）
- 哪些类型的任务小模型已经可用？
- 哪些类型必须保留 Claude？
- 成本收益是否达到阈值？

## 10. 下一步建议

- 建议决策：
  - [ ] 进 SFT 阶段
  - [ ] 进 DPO 阶段
  - [ ] 不训练，用 prompt 优化
  - [ ] 回炉数据清洗
- 具体动作：

## 11. 附录

- 完整 raw results：`reports/raw/{{date}}_{{model}}.jsonl`
- 复现命令：`python -m benchmark.harness.runner --cases ... --model ...`
- 相关 W&B run：
