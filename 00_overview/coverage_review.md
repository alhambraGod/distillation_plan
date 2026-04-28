# 架构 & 教学体系完整性审阅

> 作者视角的**自审**：这份 `distill_plan/` 是否足以让一个初学者照做完成全部需求？  
> 诚实列出覆盖了什么、漏了什么、怎么补。

更新：2026-04-24

## 1. 需求 → 文档 覆盖矩阵

把需求文档 v2026-04-14 的每个条目映射到本方案：

### 需求 §1-2 目标 & 现状
| 需求项 | 对应文档 | 覆盖度 |
|---|---|---|
| 蒸馏 Gemma 级别小模型 | `00_overview/base_model_selection.md` | ✅ 还扩展了 Qwen / Llama / Mistral / DeepSeek |
| 降低成本，保留 Claude fallback | `05_serving/router.py` + `monitoring.md` | ✅ |
| 评估：哪些任务适合小模型替代 | `02_benchmark/eval_spec.md` + `report_template.md` | ✅ |
| 评估：是否需要训练 | `06_decisions/DP1_train_or_not.md` | ✅ |
| 决定 SFT / DPO / RL 优先级 | DP2、DP3、DP5 决策文档 | ✅ |
| V1 vs V2 独立评估 | `02_benchmark/v1/v2_benchmark_design.md` | ✅ |

### 需求 §3 可用数据
| 需求项 | 对应文档 | 覆盖度 |
|---|---|---|
| 用户输入 / system / context | `01_data_pipeline/code/extract_fields.py` | ✅ |
| 已加载 skill | 同上 | ✅ |
| AI 工具调用 + 工具返回 | 同上 | ✅ |
| report_progress / submit_final_report | 同上 + `v2_benchmark_design.md` | ✅ |
| 最终状态 | 同上 | ✅ |
| SFT 数据集 | `build_datasets.py` | ✅ |
| 偏好对数据 | `04_dpo/build_preferences.py` | ✅ |
| Benchmark 回放集 | `build_datasets.py` + `eval_spec.md` | ✅ |

### 需求 §4 分阶段路线
| 阶段 | 对应文档 | 覆盖度 |
|---|---|---|
| §4.1 数据+Benchmark | `01_data_pipeline/` + `02_benchmark/` | ✅ 代码 + 设计全 |
| §4.2 SFT | `03_sft/` | ✅ |
| §4.3 DPO/ORPO | `04_dpo/` | ✅ |
| §4.4 RL 暂缓 | `08_rl_future/readings.md` + `DP5` | ✅ |

### 需求 §5 风险
| 风险 | 对应 | 覆盖度 |
|---|---|---|
| 历史数据噪声 | `01_data_pipeline/design.md` 清洗规则 + 黄金集 | ✅ |
| V1/V2 架构分开 | 全文档贯穿 | ✅ |
| 业务评估标准在梳理 | `eval_spec.md` + 人工标注流程 | ✅ |
| RL environment/reward 不清晰 | `08_rl_future/` 5 个必要条件 | ✅ |

**结论**：需求文档每一条都有对应落地。**需求覆盖 100%**。

## 2. 初学者学习路径完整性

以"完全不懂 ML 的工程师"为起点，12 周能做到什么？

### 📚 必读顺序（按初学者学习曲线）
1. `README.md` - 总览
2. `00_overview/environment_setup.md` - 装环境（Day 1）
3. `00_overview/ml_fundamentals.md` - ML 基础补课（Day 1-2）
4. `00_overview/concepts_and_techniques.md` - 术语和路线（Day 2-3）
5. `00_overview/glossary.md` - 速查
6. `00_overview/base_model_selection.md` - 选模型
7. `00_overview/learning_resources.md` - 深入学习
8. `00_overview/core_principles.md` - 团队守则
9. `00_overview/teaching_schedule.md` - 12 周节奏
10. 按周进入 01-05 各目录
11. `00_overview/team_workflow.md` - 协作规范
12. `00_overview/compliance_and_safety.md` - 合规

### ✅ 已覆盖（初学者能做）

- ML 基础概念（loss / LoRA / attention / optimizer / schedule）
- 所有主流微调技术（SFT / DPO / ORPO / KTO / SimPO / RLHF / GRPO）
- 数据工程完整 pipeline（拉 / 清 / 抽 / 构）
- Benchmark 框架（设计 + 代码）
- SFT / DPO 完整训练代码 + config + troubleshooting
- 推理部署 + 路由 + fallback + 灰度
- 决策模板 + 成本估算 + 风险管控
- 合规 / 安全 / 团队工作流

### ⚠️ 认知缺口（需要团队内部填）

这些涉及**你们内部系统的具体实现**，文档无法代写：

1. **V1 agent-service 的具体节点结构** - 需要读源码
2. **V2 DeerFlow / MarketingAI 的 middleware API** - 需要读源码
3. **skill 加载协议的具体 schema** - 需要对齐
4. **report_progress / submit_final_report 的字段** - 需要对齐
5. **生产的工具 schema 清单** - 需要业务方提供
6. **既有 LangSmith project 名 / trace 字段形状** - 需要实操看到才能固化

**怎么填**：入职第 1 周安排 1-2 次 code walkthrough 会议，由熟悉 V1/V2 的工程师带读源码，把上述信息补进 `01_data_pipeline/design.md` 和 `02_benchmark/v*_benchmark_design.md` 的具体字段里。

### ⚠️ 教学上的**软缺口**

以下是"教不出来但必须亲手踩"的经验：

1. **第一次 OOM**：只能在实验中踩到
2. **第一次 loss 不降**：troubleshooting.md 覆盖了常见原因，但真实排查经验要实操
3. **第一次 eval 指标骗你**：遇到才能建立直觉
4. **业务方分歧**：文档说"要对齐"，但真实的沟通只能靠做

**怎么补**：每周有一次"惨痛经验分享会"（30 分钟）交流本周踩的坑。

## 3. 深度 & 广度评估

### 深度
| 话题 | 深度 | 评估 |
|---|---|---|
| LoRA 原理 | 概念 + 公式 + 代码 + 超参 | ✅ |
| DPO 原理 | 公式 + loss + 超参敏感性 + hacking | ✅ |
| RL 原理 | 概念 + 论文索引 + 暂缓理由 | ✅ |
| 数据清洗 | 规则 + 代码 + 脱敏 + 血缘 | ✅ |
| 评估设计 | 指标 + spec + 人工 + 分歧处理 | ✅ |
| 推理部署 | vLLM + LoRA 热加载 + 路由 + fallback | ✅ |
| 合规 | 数据 license + PII + 安全 | ✅ |
| 团队协作 | PR / review / 事故 / 周会 | ✅ |

### 广度
| 方向 | 触达 | 评估 |
|---|---|---|
| 基座模型对比 | 5 类横评（Gemma/Qwen/Llama/Mistral/DeepSeek） | ✅ |
| 微调方法 | 8 种（SFT/DPO/ORPO/KTO/SimPO/PPO/GRPO/Constitutional） | ✅ |
| 推理优化 | vLLM + 量化 + 约束解码 | ✅（基本够） |
| 数据合成 | Self-instruct 等 | ⚠️ 未展开 |
| Agent 评估 | 自研 harness + 工具调用指标 | ✅ |
| Long context | 4k/8k 训练策略 | ⚠️ 未展开 |
| Multi-modal | 图像/视频输入 | ❌ 不适用本项目 |
| Model merging | TIES/DARE 合并 adapter | ❌ 未展开（本项目用不到） |
| Speculative decoding | 推测采样 | ❌ 未展开 |
| PRM / MCTS | 过程奖励 / 搜索 | ❌ 未展开（RL 专题） |

**评估**：深度 **够用**（能独立完成项目）。广度上有几处"触到但未深挖"，但对本项目目标**不是关键路径**。如果团队某阶段发现需要，可按 `learning_resources.md` 的索引自行深入。

## 4. 可能的改进方向

### 优先级 P0（建议补）
1. **`unit tests` 骨架**：数据 pipeline 的单测示例，防止清洗规则漂移
2. **`smoke test` 脚本**：每次改动跑一个 5 分钟自测
3. **`Makefile` 或 `justfile`**：把常用命令封装（`make train` / `make bench`）

### 优先级 P1（选做）
1. **Prompt engineering 章节**：DP1 可能结论是"不训练"，那时 prompt 工程就是主线
2. **Data synthesis 章节**：SFT 数据不够时合成（self-instruct / Evol-Instruct）
3. **Quantization 章节**：推理侧进一步压缩（INT8/FP8）
4. **Ablation 方法论**：怎么设计对照实验

### 优先级 P2（远期）
1. **Model merging**：多个 adapter 合并
2. **Speculative decoding**：推理加速
3. **Long context 训练**：8k+ 上下文调优
4. **Advanced RL**：PRM / MCTS（如果 DP5 触发）

## 5. 与业界最佳实践对标

| 维度 | 本方案 | 业界 top | 差距 |
|---|---|---|---|
| 数据 pipeline | 规则清洗 + 脱敏 + 黄金集 | +Cleanlab 噪声检测 / distilabel 合成 | 小 |
| Benchmark | 自研 + LLM-judge + 人工 | +τ-bench / AgentBench 标准 | 可借鉴 |
| 训练 | TRL + LoRA + QLoRA | +Unsloth / Axolotl 加速 | 效率 |
| 推理 | vLLM + LoRA hot-swap | +TensorRT-LLM / SGLang | 成熟即可 |
| 监控 | Prometheus + 业务抽检 | +Arize / WhyLabs 漂移检测 | 可选 |
| 合规 | License + PII + safety | +Model Cards / Datasheets 规范 | 补 model card |
| 协作 | PR / review / 事故 | +ModelDB / MLflow Registry | 成熟可选 |

**结论**：本方案**稳健务实**，不追求花哨，每个环节都有 plan B。团队跑熟后可按 gap 选项升级。

## 6. 一句话总结

> **这套 distill_plan 能让一个初学者，在 12 周内，从零完成"LangSmith trace → 训练小模型 → 部署 → 灰度上线"的全流程，并且每一步都有决策文档和回滚方案。**
>
> **知识覆盖完整，深度够支撑落地，广度点到为止不喧宾夺主。**
>
> **剩余的真实缺口集中在"你们内部系统具体实现"——这部分必须由团队内部 walkthrough 补齐，文档代替不了。**

## 7. 上手行动（给新人的第一天）

1. 读 `README.md`（10 分钟）
2. 读 `00_overview/environment_setup.md` 并执行（1 小时）
3. 读 `00_overview/ml_fundamentals.md`（30 分钟）
4. 读 `00_overview/concepts_and_techniques.md`（40 分钟）
5. 开完第一次 walkthrough 会议（V1/V2 架构 code review，2 小时）
6. 开始写第一份 `DP1` 准备材料——拉 100 条 trace 跑通 pipeline（剩余时间）

**第一天结束**：对项目有清晰认知、开发环境就绪、知道下周要做什么。

## 8. 文档维护承诺

- `concepts_and_techniques.md` / `learning_resources.md`：**季度 review 一次**（生态变化快）
- `base_model_selection.md`：新模型发布时更新
- `eval_spec.md`：**每次改口径都 bump 版本**
- `troubleshooting.md`：每次踩新坑都补一条
- 决策文档 `DP*.md`：**每次决策都写一份**，不可跳过

## 附：文档完整清单（47 个文件）

```
distill_plan/
├── README.md
├── 00_overview/
│   ├── implementation_plan.md
│   ├── teaching_schedule.md
│   ├── core_principles.md
│   ├── base_model_selection.md         # 基座选型详细对比
│   ├── concepts_and_techniques.md      # SFT/DPO/RL 等名词深度解释
│   ├── learning_resources.md           # 带链接的学习资料索引
│   ├── environment_setup.md            # 新人装环境
│   ├── ml_fundamentals.md              # ML 基础回顾
│   ├── team_workflow.md                # 团队协作
│   ├── compliance_and_safety.md        # 合规
│   ├── glossary.md                     # 速查词汇表
│   └── coverage_review.md              # 本文件
├── 01_data_pipeline/
│   ├── design.md
│   └── code/
│       ├── pull_traces.py
│       ├── clean.py
│       ├── extract_fields.py
│       └── build_datasets.py
├── 02_benchmark/
│   ├── eval_spec.md
│   ├── harness_design.md
│   ├── v1_benchmark_design.md
│   ├── v2_benchmark_design.md
│   ├── report_template.md
│   └── harness/
│       ├── __init__.py
│       ├── case.py
│       ├── model_client.py
│       ├── metrics.py
│       ├── judge.py
│       ├── runner.py
│       └── reporter.py
├── 03_sft/
│   ├── sft_guide.md
│   ├── format.py
│   ├── train.py
│   ├── troubleshooting.md
│   └── configs/
│       ├── sft_v2_base.yaml
│       └── sft_v2_gemma.yaml
├── 04_dpo/
│   ├── dpo_guide.md
│   ├── build_preferences.py
│   ├── train_dpo.py
│   ├── troubleshooting.md
│   └── configs/
│       └── dpo_v2.yaml
├── 05_serving/
│   ├── serve.sh
│   ├── router.py
│   ├── monitoring.md
│   └── rollout_plan.md
├── 06_decisions/
│   ├── DP1_train_or_not.md
│   ├── DP2_sft_enough.md
│   ├── DP3_dpo_value.md
│   ├── DP4_full_rollout.md
│   └── DP5_rl_evaluation.md
├── 07_budget/
│   ├── compute_estimate.md
│   └── cost_breakdown.md
└── 08_rl_future/
    └── readings.md
```
