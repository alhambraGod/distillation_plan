# V2 DeerFlow / MarketingAI Benchmark 专项设计

> 对应 V2 架构：单循环 Agent + Middleware。  
> 本文档是 `eval_spec.md` 的 V2 专属补充。

## V2 特点（影响评估方式）

- **单循环 agent**：一个主 agent 通过 tool-call 循环完成任务
- **Middleware**：横向注入的中间件（鉴权、限流、skill 加载、报告进度等）
- **Skill 加载机制**：不同任务加载不同 skill 集，影响可调工具
- **业务领域**：营销 AI、深度研究等

## 关键指标（V2 专属扩展）

在通用 metrics 基础上加：

| 指标 | 口径 |
|---|---|
| **ReportProgressCoverage** | agent 是否在关键步骤调了 `report_progress` |
| **SubmitFinalReportValid** | 最终 `submit_final_report` 是否符合 schema |
| **SkillUsageRate** | 加载的 skill 里被用到的比例（太低说明 skill 选择浪费） |
| **IterationCount** | 完成任务需要的 agent 循环轮数（反映效率） |
| **ToolRedundancy** | 同一工具被重复调用且参数几乎相同的次数（死循环嫌疑） |

## Benchmark case 扩展字段

```json
{
  "case_id": "v2_bench_001",
  ...（通用字段）,
  "expected_report_progress_count": 3,
  "final_report_schema": {
    "type": "object",
    "required": ["summary", "sections"],
    ...
  },
  "max_iterations": 20
}
```

## V2 的核心挑战

### 1. 工具调用循环稳定性

V2 是单循环，模型要自己决定"何时停"。小模型最容易在这里翻车：
- 早停：没调够工具就 submit
- 死循环：重复调同一工具
- 漂移：中途忘了目标

benchmark 必须重点测这三种失败。

### 2. Skill 兼容性

模型训练时见过 skill A，推理时如果业务方新加了 skill B，可能不会用。
- benchmark 集要**包含训练集里没见过的 skill 组合**测泛化
- 或者上线前强制"已见 skill 白名单路由"

### 3. report_progress 习惯

这是 V2 的 UX 关键——用户靠这个看进度。小模型经常忘了调。
- 训练数据里要显式保留 `report_progress` 轨迹
- benchmark 单独统计覆盖率

### 4. 长对话上下文

V2 可能跑十几轮才结束，上下文积累快。
- benchmark 集要包含几条"长 horizon"case（10+ 轮）
- 小模型可能在长上下文下崩，特别关注

## 小模型在 V2 上的替代策略

**不建议直接全盘替代。** 按风险分层：

| 任务类型 | 替代策略 |
|---|---|
| 简单查询 + 简单回答 | 小模型 SFT 足够 |
| 中等复杂度 + 工具调用 1-3 次 | 小模型 SFT + DPO |
| 高复杂度 + 多工具多轮 | 保留 Claude，或小模型+Claude fallback |
| 关键决策（发布、扣费等） | 必须 Claude |

## Router 策略示例（V2）

```python
def route_v2(task_meta):
    if task_meta.complexity == "simple":
        return "local-qwen2.5-7b-sft"
    if task_meta.requires_skills in TRAINED_SKILLS:
        return "local-qwen2.5-7b-sft"
    if task_meta.is_critical:
        return "claude-3-5-sonnet"
    # 保守策略：用小模型，fallback 到 Claude
    return RouterWithFallback("local-qwen2.5-7b-sft", fallback="claude-3-5-sonnet")
```

## 推荐 benchmark 集规模（V2）

- 黄金集：200 条（分层：简单 80 / 中等 80 / 复杂 40）
- 回放集：1000 条（按月从历史 trace 抽）
- 长 horizon 集：50 条（10+ 轮对话）
- Skill 泛化集：100 条（训练集未见的 skill 组合）

## V2 benchmark 报告模板额外看什么

除了通用指标，单独列：
```
| 长 horizon 成功率 | XX% |
| 未见 skill 成功率 | XX% |
| 平均迭代次数 | XX |
| report_progress 覆盖率 | XX% |
```

这几项低了就不能上。
