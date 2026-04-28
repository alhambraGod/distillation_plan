---
marp: true
theme: default
paginate: true
header: 'L06 · 学生基座 + Pilot'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #1E3A8A; border-bottom: 4px solid #1E3A8A; padding-bottom: 8px; }
  h2 { color: #2563EB; }
  section.cover { background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #1E40AF; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 16px; }
  .big { font-size: 44px; text-align: center; color: #1E3A8A; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L06 · 学生基座 + Pilot

## 不预设 Gemma，用数据说话

<br>

📅 **第 6 课 · 60 分钟**
📚 教材：`base_model_selection.md` + `base_model_pilot.md`

---

## 🎯 本课目标

- 理解基座选型维度
- 掌握 Pilot 横评方法（zero / few / LoRA 三步）
- 能判断本项目选哪个基座
- **动手**：跑 1 个基座的 zero-shot 评估

---

## 🧩 选基座是"三轴决策"

<div class="big">
能力 × 成本 × License
</div>

<br>

任何单维度最优都不一定合适：
- 能力最强 → 可能 license 贵 / 跑不起
- 最便宜 → 可能能力不够
- License 最宽 → 可能中文弱

---

## 📊 5 候选横评

| 基座 | 量级 | 中文 | Tool Call | License | 推荐 |
|---|:---:|:---:|:---:|:---:|:---:|
| **Qwen 2.5 7B** | 7B | ⭐⭐⭐ | ⭐⭐⭐ | Apache 2.0 | 🥇 |
| **R1-Distill-Qwen-7B** | 7B | ⭐⭐⭐ | ⭐⭐⭐ | Apache 2.0 | 🥇 已蒸馏 |
| Qwen 2.5 14B | 14B | ⭐⭐⭐ | ⭐⭐⭐ | 自有 | 🥈 |
| Llama 3.1 8B | 8B | ⭐⭐ | ⭐⭐⭐ | Community | 英文 |
| Gemma 2 9B | 9B | ⭐⭐ | ⭐ | Gemma | 参考 |

---

## 🏁 DeepSeek-R1-Distill-Qwen-7B 特殊

DeepSeek 已经**蒸馏好的 Qwen 7B 学生**：
- 继承了 R1 的推理能力
- Apache 2.0 商用无忧
- 可能 **zero-shot 就接近需求**

<br>

<div class="highlight">
💡 阶段 1 benchmark 必测这个 —— 如果够用，可以省掉整个 SFT 阶段
</div>

---

## 🔬 Pilot 方法：三步横评

```
Step 1: Zero-shot benchmark
  └── 未训的基座在 500 条黄金集上表现

Step 2: Few-shot benchmark
  └── 加 3-5 个 in-context 示例后表现

Step 3: 500 条 LoRA 小实验
  └── 每基座训 1 epoch 后再 benchmark
```

**三个数据点**：
- Zero = 基座本身能力
- Few = 能否从示例学
- LoRA = 训练潜力

---

## 📋 Pilot 评分公式

```
总分 = 0.3 × zero_shot_success
     + 0.2 × few_shot_uplift
     + 0.3 × lora_trained_success
     + 0.1 × latency_score
     + 0.1 × license_and_cost_score
```

<br>

**关键**：**不只看 zero-shot**，有些基座 zero 差但很能训。

---

## 📊 Pilot 示例结果（假设）

| 基座 | Zero | Few | LoRA | P95 | 显存 | License | 综合 |
|---|---|---|---|---|---|---|---|
| Qwen 2.5 7B | 70% | 78% | 85% | 8s | 16G | Apache | **A+** |
| R1-Distill-Qwen-7B | 80% | 82% | 85% | 10s | 16G | Apache | **A+** |
| Qwen 2.5 14B | 78% | 85% | 90% | 14s | 30G | 自有 | B |
| Llama 3.1 8B | 60% | 70% | 78% | 8s | 16G | Community | C |
| Gemma 2 9B | 62% | 72% | 80% | 9s | 20G | Gemma | C |

<br>

**决策**：主选 R1-Distill-Qwen-7B，备选 Qwen 2.5 7B

---

## ⏱️ Pilot 耗时预算

| 阶段 | 天数 |
|---|---|
| 准备 500 条 pilot benchmark | 1-2 |
| Zero-shot 5 基座 | 1 |
| Few-shot 5 基座 | 1 |
| LoRA 小训 5 基座（每个 ~1 天 A100） | 5 |
| 写 Pilot 报告 | 1 |
| **合计** | **~2 周** |

**成本**：约 $650 + 3-5 人天

---

## 🛠️ Pilot 实操命令

```bash
# 跑 5 个基座的 zero-shot
for model in Qwen2.5-7B-Instruct \
             DeepSeek-R1-Distill-Qwen-7B \
             Qwen2.5-14B-Instruct \
             Llama-3.1-8B-Instruct \
             gemma-2-9b-it; do
  python -m benchmark.harness.runner \
    --cases data/pilot_bench.jsonl \
    --model local-$model \
    --out-dir reports/pilot/
done
```

---

## 📝 Pilot 产出文档

必须有：
- [ ] `reports/pilot/comparison_matrix.md`
- [ ] `reports/pilot/top3_analysis.md`
- [ ] `reports/pilot/decision.md`（签字）
- [ ] 更新 `DP1_train_or_not.md`

<br>

**签字流程**：技术负责人 + 业务 lead + 架构师

---

## ⚠️ 常见坑

1. **预设 Gemma 跳过 Pilot** → 可能选错
2. **只看 zero-shot 就淘汰** → 漏掉"能训"的
3. **Pilot 数据不够多样** → 结论不可信（至少 500 条覆盖关键场景）
4. **不记录 License** → 后期发现不能商用
5. **不看 Tokenizer** → 影响白盒蒸馏选项

---

## 🏋️ 实操（课堂 15 分钟）

**任务**：用本地小基座跑 zero-shot

```bash
python -m benchmark.harness.runner \
  --cases data/pilot_bench_mini.jsonl \
  --model local-Qwen2.5-1.5B-Instruct \
  --out-dir reports/pilot_demo/ \
  --concurrency 5
```

看：
- 成功率多少？
- 哪些 case 失败了？
- 你会淘汰这个基座吗？

---

## 🏠 课后作业

1. 读完 `base_model_pilot.md`
2. 讨论：如果预算只够跑 3 个基座，选哪 3 个？为什么？
3. 为下节课做准备：思考"我们应该用什么教师"

<br>

**下节课**：L07 教师 + 蒸馏技术

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: Pilot 能不能跳过直接选？→ A: 不能，后期换基座成本远大于 Pilot 成本
- Q: 我们数据少，500 条 Pilot 能代表吗？→ A: 能排前 3 名，但精细选型还要大规模训练
- Q: 基座升级（Qwen 2.5 → 3）要重 Pilot 吗？→ A: 要，每年都可能有更好的
