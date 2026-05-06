# DP1：是否进入训练阶段？

> 阶段 1 结束时填。一页纸，结论明确。
>
> 与 `06_decisions/DP2_sft_enough.md` ~ `DP5_rl_evaluation.md`（5 份决策书）配套使用。
> 决策依据见 `00_overview/concepts_and_techniques.md`（蒸馏方法选型）+ `02_benchmark/eval_spec.md`（评估口径）。

## 基本信息
- **决策日期**：YYYY-MM-DD
- **责任人**：
- **评审人**（至少含业务 lead）：
- **依据报告**：`benchmark/reports/baseline_v1.md` 和 `baseline_v2.md`

## 背景摘要（3 句话）

（比如：阶段 1 跑完了 V1 + V2 各 200 条黄金集的基线评估，候选模型 4 个，最终结论如下……）

## 关键指标对比

### V1
| 模型 | SuccessRate | ToolF1 | 人工分 | P95 时延 | 单次成本 $ |
|---|---|---|---|---|---|
| Claude (baseline) | | | | | |
| Qwen 2.5 7B Instruct | | | | | |
| Gemma 2 9B IT | | | | | |
| Qwen 3 7B | | | | | |

### V2
| 模型 | SuccessRate | ToolF1 | 人工分 | P95 时延 | 单次成本 $ |
|---|---|---|---|---|---|
| 同上结构 | | | | | |

## 判断（必选其一）

### Option A：不训练，用 prompt engineering + 路由
- 条件：小模型和 Claude 差距 ≤ 15%，成本降低 ≥ 50%
- 理由：
- 实施：路由 + Claude fallback 即可，跳过阶段 2-3

### Option B：进 SFT 阶段
- 条件：差距 15-40%，且主要问题是"格式/流程/未见模式"
- 理由：
- 优先级任务：
- 预计 3-4 周

### Option C：暂不训练，数据回炉
- 条件：数据质量问题导致无法评估（脏数据 > 30% / benchmark 集不平衡）
- 理由：
- 补救动作：

### Option D：换基座
- 条件：当前候选模型和 Claude 差距 > 50%，不是靠微调能弥补
- 候选：更大模型 / 不同基座
- 理由：

## 教师模型选择（如果训练）

> 配套 `00_overview/teacher_model_comparison.md` + `03_sft/distillation_techniques.md`

- 教师模型候选：__
- 蒸馏类型：
  - [ ] 黑盒 SFT（已授权/人工批准 trace）
  - [ ] 白盒 KL（同家族大模型作教师）
  - [ ] CoT 合成（教师生成思维链）
  - [ ] 混合（多种叠加）
- Tokenizer 同源？Y / N
- 教师推理成本评估：__
- License legal 已确认？Y / N

## 本次决策选择

- [ ] Option A
- [ ] Option B
- [ ] Option C
- [ ] Option D

**理由（3 句话）**：

## 下一阶段目标（Option B/D 时填）

- 目标成功率：
- 目标成本：
- 目标人工分：
- Deadline：

## 风险备忘

（列 2-3 条需要持续关注的）

## 签字

- 工程 lead：
- 业务 lead：
- 日期：
