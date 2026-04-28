# 小模型蒸馏替代 Claude - 完整实施方案

更新：2026-04-24

基于需求文档《小模型替代 Claude 需求简版》v2026-04-14 展开的工程实施 + 教学方案。

## 阅读顺序

### 🚀 第一天（所有人）
1. **[README.md](./README.md)** - 本文件
2. **[finetune_vs_distill.md](./00_overview/finetune_vs_distill.md) - 🆕 蒸馏 vs 微调（最重要）**
3. **[methods_deep_dive.md](./00_overview/methods_deep_dive.md) - 🆕 SFT/DPO/RL 深度对比**
4. **[environment_setup.md](./00_overview/environment_setup.md)** - 装环境
5. **[ml_fundamentals.md](./00_overview/ml_fundamentals.md)** - ML 基础
6. **[concepts_and_techniques.md](./00_overview/concepts_and_techniques.md)** - 术语 + 路线
7. **[glossary.md](./00_overview/glossary.md)** - 速查词汇表

### 📋 第一周（开工前）
- [implementation_plan.md](./00_overview/implementation_plan.md) - 系统架构 + 路线
- [teaching_schedule.md](./00_overview/teaching_schedule.md) - 12 周节奏
- [core_principles.md](./00_overview/core_principles.md) - 5 条核心原则
- **[project_critique_and_fixes.md](./00_overview/project_critique_and_fixes.md) - 🆕 6 大问题反思对策**
- [base_model_selection.md](./00_overview/base_model_selection.md) - 学生基座选型
- **[base_model_pilot.md](./00_overview/base_model_pilot.md) - 🆕 基座 Pilot 方法**
- [teacher_model_comparison.md](./00_overview/teacher_model_comparison.md) - 教师模型选型（10 款对比）
- [03_sft/distillation_techniques.md](./03_sft/distillation_techniques.md) - 7 种蒸馏方法
- **[anthropic_tos_compliance.md](./00_overview/anthropic_tos_compliance.md) - 🆕 Claude 蒸馏合规**
- **[08_rl_future/rl_in_current_business.md](./08_rl_future/rl_in_current_business.md) - 🆕 RL 在本项目的三档落地**
- [learning_resources.md](./00_overview/learning_resources.md) - 学习资源索引
- [team_workflow.md](./00_overview/team_workflow.md) - 团队协作
- [compliance_and_safety.md](./00_overview/compliance_and_safety.md) - 合规
- [coverage_review.md](./00_overview/coverage_review.md) - 架构完整性审阅

### ⚙️ 按阶段进入

| 目录 | 内容 | 入口文件 | 受众 |
|---|---|---|---|
| `01_data_pipeline/` | trace 拉取、清洗、数据集构建 | `design.md` | 数据工程师 |
| `02_benchmark/` | 评估口径 + harness 代码 + V1/V2 专项设计 | `eval_spec.md` | 工程师 + 业务 |
| `03_sft/` | SFT 全流程 + 训练脚本 + 配置 | `sft_guide.md` | 训练工程师 |
| `04_dpo/` | DPO / ORPO 流程 + 偏好对构造 | `dpo_guide.md` | 训练工程师 |
| `05_serving/` | vLLM 推理 + 路由 + fallback + 灰度 | `rollout_plan.md` | SRE + 工程师 |
| `06_decisions/` | 5 个关键决策点的一页纸模板 | `DP1_train_or_not.md` | 负责人 |
| `07_budget/` | 算力估算 + 成本对比 | `compute_estimate.md` | 负责人 + 财务 |
| `08_rl_future/` | RL 前置调研（暂缓） | `readings.md` | 研究方向 |

## 关键时间线

```
Week 0         Week 1-3          Week 4-7         Week 8-10        Week 11-12
环境+学习  →   数据+Benchmark  →  SFT（条件）  →   DPO（条件）  →   灰度上线
              【DP1 决策】      【DP2 决策】     【DP3 决策】     【DP4 决策】
```

## 最重要的 3 条

1. **没有 Benchmark 不要训练**——先做阶段 1，DP1 决定是否需要训练。
2. **V1 / V2 物理隔离**——数据集、benchmark、报告都分开，不混测。
3. **每次实验只动一个变量**——否则无法归因。

## 如何使用这套文档

- **初学者**：按上面"第一天 → 第一周 → 按阶段"顺序读。
- **工程 lead**：直接看 `06_decisions/` 里 5 个决策点模板。
- **架构师**：`01`~`05` 每个目录下的 `*_guide.md` 和 `design.md`。
- **业务方**：`implementation_plan.md` + `eval_spec.md` §3（评估维度）。
- **合规 / 法务**：`compliance_and_safety.md`。

## 文档完整清单（47 个文件）

```
distill_plan/
├── README.md
├── 00_overview/                   # 总览 + 新人培训
│   ├── implementation_plan.md     # 系统架构 + 路线图
│   ├── teaching_schedule.md       # 12 周节奏表
│   ├── core_principles.md         # 5 条核心原则
│   ├── finetune_vs_distill.md     # 🆕 蒸馏 vs 微调（客户最困惑的澄清）
│   ├── methods_deep_dive.md       # 🆕 SFT/DPO/RL 深度对比与坑
│   ├── project_critique_and_fixes.md # 🆕 方案 6 大问题对策
│   ├── base_model_selection.md    # 学生基座对比 (Gemma/Qwen/Llama/DeepSeek)
│   ├── base_model_pilot.md        # 🆕 基座 Pilot 横向对比方法
│   ├── teacher_model_comparison.md # 教师模型对比 (10 款大模型深度评估)
│   ├── anthropic_tos_compliance.md # 🆕 Claude 蒸馏 ToS 合规专题
│   ├── concepts_and_techniques.md # SFT/DPO/ORPO/RL 等术语深度
│   ├── learning_resources.md      # 100+ 带链接资源索引
│   ├── environment_setup.md       # 新人环境搭建
│   ├── ml_fundamentals.md         # ML 基础回顾
│   ├── team_workflow.md           # PR / review / 事故响应
│   ├── compliance_and_safety.md   # License / PII / 安全
│   ├── glossary.md                # 一页速查术语表
│   └── coverage_review.md         # 架构完整性审阅
├── 01_data_pipeline/              # 数据管线
│   ├── design.md
│   ├── data_quality_tiers.md      # 🆕 金/银/铜/黑分级防幸存者偏差
│   └── code/
│       ├── pull_traces.py
│       ├── clean.py
│       ├── extract_fields.py
│       └── build_datasets.py
├── 02_benchmark/                  # 评估
│   ├── eval_spec.md               # 唯一真源
│   ├── harness_design.md
│   ├── v1_benchmark_design.md     # V1 专项
│   ├── v2_benchmark_design.md     # V2 专项
│   ├── report_template.md
│   └── harness/                   # 评估框架代码
│       ├── __init__.py
│       ├── case.py
│       ├── model_client.py
│       ├── metrics.py
│       ├── judge.py
│       ├── runner.py
│       └── reporter.py
├── 03_sft/                        # 监督微调 + 蒸馏
│   ├── sft_guide.md
│   ├── distillation_techniques.md # 7 种蒸馏方法分类对比
│   ├── format.py
│   ├── train.py                   # 黑盒 SFT 训练
│   ├── train_kd.py                # 白盒 KL 蒸馏训练
│   ├── train_rl_grpo.py           # 🆕 RL GRPO POC 起步脚本
│   ├── precompute_teacher_logits.py # 教师 logits 预计算
│   ├── build_cot_data.py          # CoT 思维链合成
│   ├── troubleshooting.md
│   └── configs/
│       ├── sft_v2_base.yaml       # Qwen 2.5 7B 起步配置
│       ├── sft_v2_gemma.yaml      # Gemma 2 9B 备选
│       ├── blackbox_claude_to_qwen7b.yaml  # 黑盒 Claude→Qwen
│       ├── kd_qwen72b_to_7b.yaml  # 白盒 Qwen 72B→7B
│       └── grpo_tool_params.yaml  # 🆕 RL POC 配置
├── 04_dpo/                        # DPO 偏好对齐
│   ├── dpo_guide.md
│   ├── build_preferences.py
│   ├── train_dpo.py
│   ├── troubleshooting.md
│   └── configs/
│       └── dpo_v2.yaml
├── 05_serving/                    # 推理 + 上线
│   ├── serve.sh
│   ├── router.py
│   ├── fallback_engineering.md    # 🆕 回退工程化（5 触发器 + 熔断器）
│   ├── monitoring.md
│   └── rollout_plan.md
├── 06_decisions/                  # 5 个关键决策点
│   ├── DP1_train_or_not.md
│   ├── DP2_sft_enough.md
│   ├── DP3_dpo_value.md
│   ├── DP4_full_rollout.md
│   └── DP5_rl_evaluation.md
├── 07_budget/                     # 成本与算力
│   ├── compute_estimate.md
│   └── cost_breakdown.md
├── 08_rl_future/                  # RL 调研（暂缓）
│   ├── readings.md
│   └── rl_in_current_business.md  # 🆕 RL 三档落地 + POC 计划
└── curriculum/                    # 🆕 培训课程大纲
    ├── README.md                  # 三版选择指南
    ├── curriculum_full.md         # 推荐版 18 课时
    ├── curriculum_12class.md      # 12 节版
    └── curriculum_8class.md       # 8 节版
```

## 文档自评

**覆盖率**：需求文档 v2026-04-14 每一条均有对应落地。

**适用对象**：0 基础 ML 工程师 12 周内能独立完成阶段 1-3。

**深度/广度**：
- 深度：每个核心技术都给出原理+代码+超参+troubleshooting
- 广度：基座对比 5 类、微调方法 8 种、推理优化、合规、团队协作全覆盖

**已知局限**：
- V1/V2 架构内部的具体字段结构需要团队 walkthrough 补齐
- 第一次 OOM / loss 不降的实操经验只能在实验中踩到

**更新计划**：
- 新基座发布 → 更新 `base_model_selection.md`
- 新工具 / 方法 → 更新 `learning_resources.md`
- 踩坑 → 更新 `troubleshooting.md`
- 决策 → 填 `06_decisions/`

详见 [`00_overview/coverage_review.md`](./00_overview/coverage_review.md)。
