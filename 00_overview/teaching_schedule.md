# 12 周教学节奏表

> 假设起点：会 Python，用过 LLM API，没做过微调。  
> 目标：12 周独立完成阶段 1-3，带基础 SFT + DPO 经验。

## Week 0 - 前置

**学**：
- LLM 推理基础：tokenizer / context / sampling (temp, top-p)
- LoRA 原理（[PEFT 官方文档首页](https://huggingface.co/docs/peft/conceptual_guides/lora)够用）
- SFT vs DPO vs RL 三句话区别
- 工具调用（Function Calling）格式

**做**：
- conda 环境搭建
- 本地跑通一个小模型推理
- LangSmith SDK 能列 10 条 trace

**产出**：`setup.md` 记录版本号

## Week 1 - 数据管线

**学**：
- Parquet / DuckDB 基础
- LangSmith 的 trace schema

**做**：
- Day 1-2：拉 V1 + V2 各 3-5k 条 trace（`01_data_pipeline/code/pull_traces.py`）
- Day 3-5：清洗规则（`clean.py`），每条规则独立函数 + 单测
- Day 6-7：字段抽取 → SFT 样本 schema（`extract_fields.py`）

**产出**：`data/datasets/v1_sft.jsonl`、`v2_sft.jsonl` 各数千条

## Week 2 - Benchmark Harness

**学**：
- 为什么 agent 评估不能用现成框架（多轮+工具调用）
- LLM-as-Judge 设计

**做**：
- Day 1-2：实现 `SuccessRate`、`LatencyP95` 两个最简单指标
- Day 3-4：实现 `ToolCallF1`（业务对齐：调错工具但结果对算不算）
- Day 5：实现 `OutputUsability`（LLM-as-Judge）
- Day 6-7：抽 100 条样本手动审，对齐自动指标和人工判断

**产出**：`benchmark/harness/` + `docs/eval-spec.md` v1

## Week 3 - 基线评估 + DP1

**做**：
- 跑 4-5 个候选：Claude / Gemma 9B IT / Gemma 2B IT / Qwen 7B IT
- 同一 benchmark、同一 prompt、同一 tool schema
- 写报告

**产出**：
- `reports/baseline.md`（V1+V2 各一份）
- `06_decisions/DP1_train_or_not.md` 填完

**DP1 决策**：是否训练？训练优先做什么？

---

## Week 4 - SFT 入门

**学**：
- TRL SFTTrainer
- Gemma 的 chat template
- Data collator: completion-only mask

**做**：
- 用 `timdettmers/openassistant-guanaco` 跑通 Gemma 2 2B 的最小 LoRA demo
- 看懂 loss 曲线

**产出**：`training/sft/minimal_demo.py` 能正常训练

## Week 5-6 - 真实数据 SFT

**做**：
- Day 5.1-5.2：格式转换（tool_call 序列化）
- Day 5.3-5.5：第一版训练（Gemma 2 9B + QLoRA）
- Week 6：超参扫描——每次只动一个
  - epoch (1/3/5)
  - lr (1e-4/2e-4/5e-4)
  - LoRA r (8/16/32)
  - 数据配比（是否混通用数据）

**产出**：`adapters/v2_sft_v{1..N}/` + 每个配一份 benchmark 报告

## Week 7 - SFT 优化 + DP2

**做**：
- 翻失败 case 100 条，分类
- 针对性数据增强
- 最终胜出 adapter

**产出**：
- 最佳 adapter
- `06_decisions/DP2_sft_enough.md` 填完

**DP2 决策**：SFT 是否达标？需不需要 DPO？

---

## Week 8 - 偏好数据

**学**：
- DPO 原理（Bradley-Terry + reference model）
- 偏好对来源的三种方法

**做**：
- 构造 1000-5000 对偏好数据
  - 方法 A：LangSmith 历史里挖
  - 方法 B：SFT 多次采样 + LLM 裁判排序
  - 方法 C：合规教师输出 chosen vs SFT 输出 rejected（慎用；Claude 仅限书面许可后）

**产出**：`datasets/dpo_v2.jsonl`

## Week 9 - DPO 训练

**学**：
- DPO 超参敏感度（lr 比 SFT 小 2-3 个量级）
- Reward hacking 识别

**做**：
- Day 1-3：起步配置训练
- Day 4-5：beta / lr 调参
- Day 6-7：防过拟合（early stop、1 epoch）

**产出**：DPO adapter

## Week 10 - DPO 评估 + DP3

**做**：
- 同一 benchmark 对比 SFT vs DPO
- 重点看人工评分

**产出**：
- 决策报告
- `06_decisions/DP3_dpo_value.md` 填完

**DP3 决策**：DPO 有收益吗？上线 SFT 还是 DPO 版本？

---

## Week 11 - 推理服务 + 路由

**做**：
- vLLM 部署 + LoRA adapter 挂载
- 路由中间件 + Claude fallback
- 监控 dashboard（成功率、p95、fallback 率、成本）

**产出**：`inference/serve.py` + `router.py` + dashboard

## Week 12 - 灰度 + DP4

**做**：
- 5% → 20% → 50% → 100% 灰度
- 每阶段守 3 天，看指标
- 异常回滚

**产出**：
- 线上稳定服务
- `06_decisions/DP4_full_rollout.md` 填完

---

## 时间缓冲建议

- 新手第一次做 ML 工程，**实际是 1.5x 预估**。
- Week 1-3 最容易超期（数据脏），可以多给 1 周。
- Week 5-6 如果第一次训练失败（OOM、loss 不降），可以多给 1 周。
- **不要压缩 Week 2 benchmark**——这是后续所有决策的地基。

## 验收门禁（不达标不能进下一周）

| 周 | 验收 |
|---|---|
| 0 | 能本地加载并推理 Gemma 2B |
| 1 | 样本 schema 通过 pydantic 校验；人工抽查 10 条结构正确 |
| 2 | harness 能对 Claude 跑出一份 benchmark 报告 |
| 3 | 报告被业务 lead 签字 |
| 4 | demo loss 曲线正常下降 |
| 5-6 | 至少有 3 个 adapter 版本和对应报告 |
| 7 | 最佳 adapter 在黄金集上的人工分 ≥ 3/5 |
| 8 | DPO 数据通过质检（≥90% 对分级人工复核通过） |
| 9 | DPO 训练收敛；reward margin 正向 |
| 10 | DPO 人工分 > SFT 人工分，或明确结论"不上" |
| 11 | router 能 fallback；超时可测试 |
| 12 | 灰度两周无重大事故 |
