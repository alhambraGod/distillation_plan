---
marp: true
theme: default
paginate: true
header: '小模型蒸馏项目 · Day 2 · 技术专题'
footer: '© 2026 · 基于 distill_plan/'
size: 16:9
style: |
  section {
    font-family: 'PingFang SC', 'Helvetica Neue', sans-serif;
    font-size: 24px;
  }
  h1 {
    color: #7C2D12;
    border-bottom: 4px solid #7C2D12;
    padding-bottom: 8px;
  }
  h2 {
    color: #B45309;
  }
  section.cover {
    background: linear-gradient(135deg, #7C2D12 0%, #B45309 100%);
    color: white;
  }
  section.cover h1 {
    color: white;
    border-bottom: 4px solid white;
    font-size: 56px;
  }
  section.cover h2 {
    color: #FED7AA;
    font-size: 28px;
  }
  section.section-divider {
    background: #FFF7ED;
    text-align: center;
  }
  section.section-divider h1 {
    font-size: 64px;
    border: none;
    color: #7C2D12;
  }
  section.summary {
    background: #FFFBEB;
  }
  table {
    margin: 0 auto;
    font-size: 20px;
    border-collapse: collapse;
  }
  th {
    background: #7C2D12;
    color: white;
    padding: 6px 10px;
  }
  td {
    padding: 6px 10px;
    border-bottom: 1px solid #E5E7EB;
  }
  code {
    background: #FEF3C7;
    padding: 2px 6px;
    border-radius: 4px;
    color: #7C2D12;
  }
  pre {
    background: #1E293B;
    color: #E2E8F0;
    border-radius: 8px;
    padding: 14px;
    font-size: 16px;
  }
  .highlight {
    background: #FED7AA;
    padding: 2px 6px;
    border-radius: 4px;
  }
  .big {
    font-size: 48px;
    text-align: center;
    color: #7C2D12;
  }
  .center {
    text-align: center;
  }
  .green { color: #059669; font-weight: bold; }
  .red { color: #DC2626; font-weight: bold; }
  .gold { background: #FEF3C7; padding: 12px; border-left: 4px solid #B45309; border-radius: 4px; }
---

<!-- _class: cover -->

# 蒸馏技术全景

## 教师模型 × 蒸馏方法 × 学生模型

<br>

📅 **Day 2 / 技术专题**
🎯 **理解 7 种蒸馏 + 10 款教师**
🛠️ **选对组合，事半功倍**

---

## 📋 今天讲什么

<br>

| 段 | 内容 | 时长 |
|:---|:---|:---:|
| 1️⃣ 蒸馏到底是什么 | 概念 + 类比 | 10 min |
| 2️⃣ 7 种蒸馏方法 | 黑盒/白盒/CoT/On-policy | 25 min |
| 3️⃣ 10 款教师模型 | DeepSeek/Qwen/Llama 横评 | 20 min |
| 4️⃣ 怎么组合 | 三套推荐方案 | 10 min |
| 5️⃣ 本项目落地 | 起步 → 进阶路径 | 10 min |
| 6️⃣ Q&A | | 10 min |

---

<!-- _class: section-divider -->

# 1️⃣ 蒸馏是什么？

---

## 🎓 三句话理解蒸馏

<br>

<div class="gold">

**1. 大模型贵 / 慢 / 强**，小模型便宜 / 快 / 弱

**2. 用大模型当"老师"教小模型**，让小模型学会做大模型擅长的事

**3. 学生 ≤ 教师**——学生不会超越教师，但会更便宜

</div>

<br>

<div class="big">
🎓 → 📚 → 👶
</div>

---

## 🧩 蒸馏的三个独立选择

<br>

<div class="big">
教师 × 方法 × 学生
</div>

<br>

```
教师（学谁）        方法（怎么学）         学生（训谁）
─────────         ─────────          ─────────
Claude API         黑盒 SFT            Qwen 7B
Qwen 72B           白盒 KL             Gemma 9B
DeepSeek V3        CoT 合成            Llama 8B
Llama 70B          On-policy           Yi 9B
...                ...                 ...
```

<br>

**误区**：不是只有"SFT" 一种训法。
**正解**：方法 / 教师 / 学生**三轴独立**，自由组合。

---

## 🤔 我们项目的现状

<br>

```
教师：Claude  ─────────▶  方法：黑盒 SFT  ─────────▶  学生：Qwen 7B
                          (用 Claude 历史
                           trace 直接训)
```

<br>

**这是最简单的一种组合**。
但还有 **6 种方法 + 9 种其他教师**可以选 / 叠加。

<br>

<div class="center">
👇 接下来讲全景
</div>

---

<!-- _class: section-divider -->

# 2️⃣ 7 种蒸馏方法

---

## 🗺️ 蒸馏方法全景图

<br>

```
                  ┌─────────────────┐
                  │   Teacher LLM   │
                  └────────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  只看输出文字         看输出+概率         看输出+中间态
   (Black-box)       (White-box logits)  (White-box hidden)
        │                  │                  │
        ▼                  ▼                  ▼
   方法 1: SFT        方法 2-3: KL/序列   方法 7: Feature
   方法 4: CoT        方法 6: Reverse KL
   方法 5: On-policy
```

<br>

**轴 1**：信号粒度 — 文本 / 概率 / 隐状态
**轴 2**：数据来源 — 历史已有 / 实时合成 / 学生采样

---

## 🥇 方法 1：Black-box SFT（黑盒输出蒸馏）

<br>

```
教师 API → (prompt, output) 配对 → 学生 SFT
```

<br>

| 维度 | 评价 |
|:---|:---|
| 信号粒度 | 粗（只学最终 token） |
| 实施难度 | 🟢 简单 |
| 数据成本 | 已有 trace = $0 |
| 训练速度 | 1x 基准 |
| 适用 | 只能 API 调用的教师（Claude） |

<br>

<div class="gold">
✅ <span class="highlight">本项目当前主线</span>。 trade-off：简单，但收益有上限。
</div>

---

## 🥈 方法 2：White-box KL（白盒概率蒸馏）

<br>

教师吐出每个 token 的**概率分布**，学生学概率（不只学"对/错"）：

```python
loss = α * CE(student, label)     # 硬标签
     + β * KL(student || teacher) # 软标签：每个 token 的整个概率分布
```

<br>

| 维度 | 评价 |
|:---|:---|
| 信号粒度 | 🌟 富 |
| 实施难度 | 🟡 中（需教师权重 + 同 tokenizer） |
| 数据成本 | 跑教师推理一遍 |
| 训练速度 | 1.5x |
| 适用 | 同家族大→小（Qwen 72B → Qwen 7B） |

<br>

<div class="center">
🎯 <span class="highlight">本项目阶段 2.5 强推</span>
</div>

---

## 🎨 KL 蒸馏直觉图

<br>

```
教师对 token "猫" 的预测分布：

  狗 ████ 0.15
  猫 ████████████████ 0.65
  鼠 █ 0.05
  虎 ██ 0.10
  其他 █ 0.05

学生学的不是"答案是猫"，
而是"狗 0.15、猫 0.65、虎 0.10..."
   ↑
   这个完整分布
```

<br>

教师"模糊"的判断（不只是 1 个答案，是一组概率）= 更丰富的信号。

---

## 🧠 方法 3：CoT 思维链合成

<br>

```python
教师对每条 case 输出：
  <think>
    步骤 1: 识别用户意图...
    步骤 2: 拆分子任务...
    步骤 3: 选择工具 search...
  </think>
  最终答案: ...
```

<br>

学生学**完整思考过程**，不只学最终答案。

| 适用 | 不适用 |
|:---|:---|
| 复杂多步推理 | 简单格式化输出 |
| 长 horizon agent | 单工具查询 |
| 数学/逻辑分析 | tool 参数填充 |

<br>

<div class="gold">
💡 DeepSeek R1 的看家技术 → R1-Distill-Qwen-7B 就是这么训的
</div>

---

## 🎯 方法 4：On-Policy 蒸馏

<br>

**洞察**：传统蒸馏让学生学"教师的对答案"，但**学生实际会犯的错**没暴露给教师。

```
传统:  教师 → 答案 → 学生学
       (学生没参与)

On-policy:  学生先答 → 教师批改 / 排序 → 学生再学
            (从学生的实际错误出发)
```

<br>

| 优点 | 缺点 |
|:---|:---|
| 训练分布 = 实际分布 | 实施复杂 |
| 偏好对齐效果好 | 成本高（每条样本要 K 次学生 + 1 次教师） |
| 接近 RLHF 效果 | 需要 reward / judge |

<br>

**本项目位置**：阶段 3 DPO 的进阶实现

---

## 🔬 方法 5-7：进阶/不推荐

<br>

| 方法 | 简述 | 本项目 |
|:---|:---|:---:|
| **Sequence-Level KD** | 整 sequence 级别 KL | ⚠️ 进阶 |
| **Reverse KL (MiniLLM)** | KL 方向反过来 | ⚠️ 进阶 |
| **Feature Matching** | 对齐 hidden states | ❌ 学生教师层数不同 |

<br>

<div class="center">
本项目 <span class="highlight">不实施</span>，留作未来研究方向
</div>

---

## 📊 7 种方法对比一览

<br>

| 方法 | 难度 | 成本 | 收益 | 本项目 |
|:---|:---:|:---:|:---:|:---:|
| 1. Black-box SFT | 🟢 | 1x | ⭐⭐⭐ | ✅ 主线 |
| 2. White-box KL | 🟡 | 3-4x | ⭐⭐⭐⭐ | ✅ 增强 |
| 3. CoT 合成 | 🟡 | 2-3x | ⭐⭐⭐⭐ | ✅ 选用 |
| 4. On-policy | 🔴 | 5-10x | ⭐⭐⭐⭐⭐ | ⚠️ DPO 阶段 |
| 5. Sequence KD | 🔴 | 高 | ⭐⭐⭐ | ❌ |
| 6. Reverse KL | 🔴 | 10x+ | ⭐⭐⭐⭐ | ❌ |
| 7. Feature Match | 🔴 | 高 | ⭐⭐⭐ | ❌ |

<br>

<div class="center">
🎯 <span class="highlight">先 1，必要时叠 2、3、4</span>
</div>

---

<!-- _class: section-divider -->

# 3️⃣ 10 款教师模型

---

## 🏆 教师模型选型 8 个维度

<br>

| 维度 | 含义 |
|:---|:---|
| 综合能力 | MMLU / HumanEval / GSM8K 等 |
| 中文能力 | CMMLU / C-Eval / AlignBench |
| 工具调用 | function call 原生支持 |
| **同家族下探** | 是否有同 tokenizer 小学生 |
| **白盒友好** | 开源权重 + 可推理 |
| License | 商用 + 蒸馏许可 |
| 推理成本 | 自托管 GPU 需求 |
| 稳定性 | 生态成熟度 |

---

## 🥇 候选 1-3：DeepSeek 家族

<br>

| 维度 | DeepSeek V3 | DeepSeek R1 |
|:---|:---:|:---:|
| 综合能力 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 中文 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 工具调用 | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 同家族下探 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 推理成本 | 🚨 671B MoE | 🚨 同 |
| License | ✅ 允许蒸馏 | ✅ 允许蒸馏 |

<br>

<div class="gold">
🎁 <strong>R1 已发布 R1-Distill-Qwen-7B/14B/32B</strong>
建议直接当起点 benchmark，看能否免训
</div>

---

## 🥈 候选 4-5：Qwen 家族（推荐！）

<br>

| 维度 | Qwen 2.5 72B | Qwen 3 32B |
|:---|:---:|:---:|
| 综合能力 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 中文 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 工具调用 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 同家族下探 | ⭐⭐⭐⭐⭐ Qwen 7B | ⭐⭐⭐⭐⭐ Qwen 3 8B |
| 白盒友好 | ⭐⭐⭐⭐ 4×A100 80G | ⭐⭐⭐⭐ 单卡可推 |
| License | ✅ Apache 2.0 (≤7B) | ✅ Apache 2.0 |

<br>

<div class="gold">
🥇 <strong>Qwen 2.5 72B → Qwen 2.5 7B</strong>：
教科书级白盒蒸馏配对 — 同 tokenizer + 强中文 + 商用无忧
</div>

---

## 🥉 候选 6-7：Llama 家族

<br>

| 维度 | Llama 3.1 405B | Llama 3.3 70B |
|:---|:---:|:---:|
| 综合能力 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 中文 | ⭐⭐ | ⭐⭐⭐ |
| 工具调用 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 同家族下探 | ⭐⭐⭐⭐ Llama 8B | ⭐⭐⭐⭐ |
| 推理成本 | 🚨 极高 | ⚠️ 中等 |
| License | ⚠️ Community | ⚠️ Community |

<br>

<div class="center">
⚠️ <strong>英文场景优选；中文场景</strong>不如 Qwen
</div>

---

## 候选 8-10：其他国产 / 国际

<br>

| 模型 | 中文 | 工具 | License | 适用 |
|:---|:---:|:---:|:---:|:---|
| GLM-4.5 / GLM-4-32B | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⚠️ 自有 | 中文备选 |
| Yi-1.5-34B | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ Apache 2.0 | 轻量备选 |
| Mistral Large 2 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ 商用付费 | 不推荐 |
| Command R+ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⚠️ 研究 | 不推荐 |
| **豆包 (字节)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ 闭源 API | 不适合做开源教师 |
| Kimi K2 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 🆕 看发布 | 观望 |

---

## 📊 总评分（综合排序）

<br>

| 排名 | 教师 | 推荐度 |
|:---:|:---|:---|
| 🥇 | **Qwen 2.5 72B** | 白盒首选，同家族下探无痛 |
| 🥈 | **Qwen 3 32B / 235B** | Qwen 升级版，能力更强 |
| 🥉 | DeepSeek R1（直接用 R1-Distill 学生） | 免训捷径 |
| 4 | DeepSeek V3 | API 黑盒 |
| 5 | Llama 3.3 70B | 英文场景 |
| 6 | GLM-4.5 / Yi-1.5-34B | 中文备选 |
| ❌ | Mistral / Command R+ / 豆包 | 不推荐 |

---

## ⚠️ 重要约束

<br>

<div class="gold">

**1. 白盒蒸馏：教师和学生必须同 tokenizer**
- Qwen 72B → Qwen 7B ✅
- Llama 70B → Qwen 7B ❌

**2. License 必须 Legal 确认**
- 关键问题：教师输出**是否允许用于训练第三方模型**
- 不同 vendor 条款差异大

**3. 学生 ≤ 教师**
- 教师本身不行 → 蒸馏救不了
- 业务上限 = 教师能力上限

</div>

---

<!-- _class: section-divider -->

# 4️⃣ 推荐组合

---

## 🎯 三套推荐方案

<br>

<div class="gold">

**方案 A 主推**：Qwen 72B → Qwen 7B 白盒
适合：算力充裕，追求最佳效果

**方案 B 兜底**：Claude trace → Qwen 7B 黑盒
适合：算力紧张，最快验证（**当前现状**）

**方案 C 最强**：方案 B + 方案 A + CoT 合成
适合：成本不敏感，业务关键

</div>

---

## 🛠️ 方案 A：白盒 KL（Qwen 72B → 7B）

<br>

```
1. precompute_teacher_logits.py
   ├── 加载 Qwen 2.5 72B
   ├── 跑训练集，每 token 存 top-64 logits
   └── 输出：sft_train_with_teacher.jsonl

2. train_kd.py
   ├── 学生：Qwen 2.5 7B
   ├── Loss = 0.5 * CE + 0.5 * KL
   └── 输出：v2_kd_v1 adapter
```

<br>

**预期收益**：比纯 SFT 提升 **5-15% 成功率**
**成本**：教师推理一遍训练集（一次性）+ 训练时长 1.5x

📁 配置：`configs/kd_qwen72b_to_7b.yaml`

---

## 🛠️ 方案 B：黑盒 SFT（Claude trace）

<br>

```
1. 用现有 LangSmith trace
2. 直接 train.py SFT
3. 产出 v2_sft adapter
```

<br>

| 维度 | 数值 |
|:---|:---|
| 数据成本 | $0（已有） |
| 训练成本 | 1x |
| 实施时间 | 1-2 周 |
| 预期成功率 | Claude × 70-85% |

<br>

📁 配置：`configs/blackbox_claude_to_qwen7b.yaml`

---

## 🛠️ 方案 C：组合最强

<br>

```
阶段 2.0: 黑盒 SFT (Claude trace)         ──▶ v2_sft
阶段 2.5: + 白盒 KL (Qwen 72B logits)     ──▶ v2_kd
阶段 2.6: + CoT 合成 (复杂 case)          ──▶ v2_cot
阶段 3:   + DPO (on-policy 偏好对齐)      ──▶ v2_dpo
```

<br>

**预期收益**：纯 SFT 基础上**叠加 10-20% 提升**

**成本**：4-5x 单 SFT 时间 + 多次教师推理

**适用**：DP2 后发现 SFT 不够，但希望避开 RL 复杂度

---

## 💰 成本对比

<br>

| 方案 | GPU 时长 | 教师推理成本 | 总相对成本 |
|:---|:---:|:---:|:---:|
| 黑盒 SFT | 1x | $0 | **1x** |
| + 白盒 KL | 1.5x | + 72B 跑一遍 | 3-4x |
| + CoT | 1x | + 72B CoT 生成 | 2-3x |
| + On-policy DPO | 2-3x | + K 采样+judge | 5-10x |
| 全组合 (C) | — | — | **6-8x** |

<br>

<div class="center">
💡 <span class="highlight">先 1x 看效果，不行再加</span>
</div>

---

<!-- _class: section-divider -->

# 5️⃣ 本项目落地

---

## 🗺️ 落地路线（更新版）

<br>

```
W0      W1-3            W4-7           W8-10        W11-12
环境  ─▶ 数据+评估  ──▶  SFT       ──▶ DPO     ──▶ 灰度
              │           │           │
              │           ├ 2.0 黑盒（必做）
              │           ├ 2.5 白盒（可选）
              │           └ 2.6 CoT（可选）
              │
            【DP1】
            选教师+方法
```

<br>

**新增决策**：DP1 时不只是"训不训"，还要选**教师 + 方法组合**

---

## 🎓 学员需要新掌握什么

<br>

在原 12 周节奏上，**Week 4-7 SFT 阶段**新增：

1. ⏰ **Week 5 增加 1 天**：跑通 `train_kd.py` 白盒 KL demo
2. ⏰ **Week 6 增加 1 天**：跑通 `build_cot_data.py`
3. 📚 **必读新文档**：
   - `00_overview/teacher_model_comparison.md`
   - `03_sft/distillation_techniques.md`

<br>

**总时长不变**（W6/W7 略压缩超参扫描即可）。

---

## ✅ Week 5 新作业（白盒 KL demo）

<br>

```bash
# Step 1: 用小教师 (Qwen 14B) + 小学生 (Qwen 1.5B) 跑通流程
python precompute_teacher_logits.py \
  --teacher Qwen/Qwen2.5-14B-Instruct \
  --data sample_100.jsonl \
  --out sample_with_teacher.jsonl \
  --topk 32

# Step 2: 训练学生
python train_kd.py --config configs/kd_demo.yaml

# Step 3: 对比 v_sft vs v_kd 在同 100 条 case 上的成功率
```

<br>

**通过标准**：v_kd 比 v_sft **成功率 ≥ +3%**（或至少不降）

---

## 📚 学员速查（必收藏）

<br>

| 文档 | 用途 |
|:---|:---|
| `teacher_model_comparison.md` | 选教师查这里 |
| `distillation_techniques.md` | 选方法查这里 |
| `train_kd.py` | 白盒 KL 实现 |
| `precompute_teacher_logits.py` | 教师 logits 预计算 |
| `build_cot_data.py` | CoT 合成 |
| `configs/kd_qwen72b_to_7b.yaml` | 白盒 KL 配置 |
| `configs/blackbox_claude_to_qwen7b.yaml` | 黑盒 SFT 配置 |

---

## ⚠️ 团队 Code Review 新增项

<br>

PR review 时多检查：

- [ ] 教师和学生 tokenizer 是否同源？
- [ ] License 是否允许蒸馏（教师输出训第三方模型）？
- [ ] 教师 logits 预计算是否压缩到 top-k？
- [ ] CoT 数据是否只对复杂 case 生成（避免冗余）？
- [ ] 训练 config 是否标注蒸馏类型 (`distillation_type` 字段)？

---

## 🎁 给学员的核心心法

<br>

<div class="gold">

**1. 三轴独立**：教师 / 方法 / 学生 是三件事，分开选

**2. 同家族优先**：白盒蒸馏只能在同 tokenizer 内做

**3. 学生 ≤ 教师**：蒸馏不会魔法般超越教师

**4. 简单先行**：先黑盒 SFT，不行再加 KL，再加 CoT

**5. License 先查**：教师输出能否训第三方模型，必须 legal 确认

</div>

---

## ❓ Q&A

<br>

**Q**: 我们已经有 Claude trace 了，还需要 Qwen 72B 教师吗？
**A**: 不必须。先用现有数据跑 DP1。如果黑盒 SFT 卡住才考虑加白盒 KL。

**Q**: 直接用 R1-Distill-Qwen-7B，省得自己训？
**A**: 阶段 1 必测！如果它在你们业务 benchmark 上已经够用，省下整个 SFT 阶段。

**Q**: 白盒 KL 比黑盒强多少？
**A**: 同等数据 + 5-15%，但需要付出 3-4x 训练成本。

**Q**: 豆包能做教师吗？
**A**: 闭源 API，且 ToS 限制蒸馏，不推荐。要 API 教师不如直接用 Claude（已有数据）。

---

<!-- _class: cover -->

# 🎓 课后任务

<br>

📖 **必读**：
- `teacher_model_comparison.md`（30 min）
- `distillation_techniques.md`（30 min）

🛠️ **动手**：
- 跑一遍 `precompute_teacher_logits.py` 看 logit 长啥样

🤔 **思考**：
- 我们项目当前应该选 A / B / C 哪套？写 200 字理由。

<br>

**下周分享你的判断 →**
