# 基座选型 Pilot 方法论

> 对应 `project_critique_and_fixes.md` 问题 4。
> **不预设 Gemma**，用小规模实验横向对比，数据说话。

---

## 1. 为什么要做 Pilot

- 需求文档说"Gemma 级别"，但具体多大、什么基座没锁
- 不同基座在中文 / tool-calling / 格式稳定性上差异巨大
- 直接选 Gemma 可能踩坑（tool-calling 原生不支持）

**Pilot 目标**：用 500-1000 条样本 + 500 条 benchmark，3-5 个候选基座做横向对比，**用真实业务数据**决策。

---

## 2. 候选基座（按优先级）

| 候选 | 量级 | 为什么选 |
|---|---|---|
| **Qwen 2.5 7B Instruct** | 7B | 中文强 + tool-call 原生 + Apache 2.0 |
| **DeepSeek-R1-Distill-Qwen-7B** | 7B | 已经蒸馏过，可能直接够用 |
| **Qwen 2.5 14B Instruct** | 14B | 上一档能力 |
| **Llama 3.1 8B Instruct** | 8B | 英文强 / 生态活跃 |
| Gemma 2 9B IT | 9B | 原需求指定，作为参考 |
| Qwen 3 8B（新） | 8B | 新版，如已发布测试 |

**至少选 4 个**对比。

---

## 3. Pilot 评估维度

### 3.1 Zero-shot 能力（快速筛）

对每个候选跑 benchmark（无训练），看：
- 成功率
- Tool call F1
- JSON 合法率
- 中文输出质量

**目的**：看哪个基座**未训都已经接近**需求，省训练。

### 3.2 Few-shot 能力

给 3-5 个业务示例 in-context，再测：
- 学习效率：few-shot 后指标提升多少
- 格式遵循

### 3.3 LoRA 小规模训练

**每个候选**用同样 500 条金数据训 LoRA（1 epoch，r=16）：
- 训练稳定性（loss 是否降）
- 训练后 benchmark 指标
- GPU 显存需求

### 3.4 综合评分

```
基座得分 = 0.3 × zero_shot_success
       + 0.2 × few_shot_uplift
       + 0.3 × lora_trained_success
       + 0.1 × latency_score
       + 0.1 × license_and_cost_score
```

---

## 4. Pilot 执行计划（2 周）

### Week 1：准备 + Zero/Few-shot 测

**Day 1-2**：
- 准备 500 条 Pilot benchmark（从金 benchmark 抽 500）
- 准备 500 条 Pilot 训练集（从金数据抽 500）

**Day 3-5**：
- 下载所有候选基座
- 跑 zero-shot benchmark
- 产出对比表

### Week 2：LoRA 训练 + 决策

**Day 6-9**：
- 每基座跑 1 epoch LoRA（~1 天/基座）
- 产出每基座的训练后 benchmark

**Day 10**：
- 写 Pilot 报告
- 决策会议

---

## 5. Pilot 决策矩阵

| 基座 | Zero-shot | Few-shot | LoRA 后 | 时延 P95 | 显存 | License | 综合 |
|---|---|---|---|---|---|---|---|
| Qwen 2.5 7B | 70% | 78% | 85% | 8s | 16GB | Apache | **A+** |
| R1-Distill-Qwen-7B | 80% | 82% | 85% | 10s | 16GB | Apache | **A+** |
| Qwen 2.5 14B | 78% | 85% | 90% | 14s | 30GB | 自有 | B |
| Llama 3.1 8B | 60% | 70% | 78% | 8s | 16GB | Community | C |
| Gemma 2 9B | 62% | 72% | 80% | 9s | 20GB | Gemma | C |

**决策**（示例）：
- 🥇 **主选 R1-Distill-Qwen-7B**：zero-shot 就接近需求，训练增益明显
- 🥈 备选 Qwen 2.5 7B：更通用，训练后接近
- 其他淘汰

---

## 6. Pilot 脚本

### 6.1 统一 benchmark 跑脚本

复用 `02_benchmark/harness/runner.py`：

```bash
for model in Qwen2.5-7B-Instruct DeepSeek-R1-Distill-Qwen-7B Qwen2.5-14B Llama-3.1-8B Gemma-2-9B; do
  python -m benchmark.harness.runner \
    --cases data/pilot_bench.jsonl \
    --model local-$model \
    --out-dir reports/pilot/ \
    --spec-version v1.0
done
```

### 6.2 统一 LoRA 训练脚本

```bash
for model in "Qwen/Qwen2.5-7B-Instruct" "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B" "..."; do
  python 03_sft/train.py \
    --config configs/pilot_${model//\//_}.yaml
done
```

每个 config 基于 `sft_v2_base.yaml` 改基座名。

---

## 7. Pilot 预算

| 项 | 成本 |
|---|---|
| GPU 时长（5 基座 × 1 天 A100） | ~$500 |
| 数据准备（500 条 × 2 tier） | 人力 2-3 天 |
| Benchmark 跑（5 × 30 分钟） | $100 |
| API 费用（judge） | $50 |
| **合计** | **~$650 + 3-5 人天** |

**收益**：避免后续 3 个月用错基座返工，ROI 极高。

---

## 8. Pilot 常见坑

### ❌ "用太少数据 pilot 不代表真实"
500 条虽然少，但**用于选基座足够**。大模型训练增益曲线前期就能看出差距。

### ❌ "基座选型一次定终身"
一般 1 年会有 2-3 次基座升级（Qwen 2.5 → Qwen 3），要**保留升级能力**。训练 config 和 adapter 结构要和基座解耦。

### ❌ "看 leaderboard 选就行"
公开 benchmark（MMLU / HumanEval）和**业务场景**差距很大。必须用**你们自己的 500 条**测。

### ❌ "zero-shot 差就淘汰"
有些基座**很能训**（提升空间大），zero-shot 差但 LoRA 后反而最好。要看综合得分。

---

## 9. Pilot 产出文档

必须产出：
- [ ] `reports/pilot/comparison_matrix.md` - 打分矩阵
- [ ] `reports/pilot/top3_analysis.md` - 前 3 名详细分析
- [ ] `reports/pilot/decision.md` - 选型决策书（签字）
- [ ] `06_decisions/DP1_train_or_not.md` 更新

---

## 10. 与 DP1 决策的关系

DP1 的核心决策之一就是"选哪个基座"。Pilot 报告是 DP1 决策书的**必备附件**。

```
DP1 输入：
  - Pilot 报告（基座选型）
  - Teacher 对比（教师选型）
  - 基线 benchmark（量化空间）

DP1 输出：
  - 是否训练
  - 训练什么基座
  - 用什么教师 + 蒸馏方法
```

---

## 变更记录
- 2026-04-24：首版
