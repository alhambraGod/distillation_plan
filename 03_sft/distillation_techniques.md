# 蒸馏技术全景与方案选择

> 配套 `00_overview/teacher_model_comparison.md`（教师选型）。  
> 本文回答："教师选定后，**怎么蒸馏**？"

---

## 1. 蒸馏（Distillation）一图概览

```
                  ┌─────────────────┐
                  │   Teacher LLM   │  （大、贵、能力强）
                  └────────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  只看输出文字        看输出 + 概率        看输出 + 中间态
   (Black-box)         (White-box logits)   (White-box hidden)
        │                  │                  │
        ▼                  ▼                  ▼
  ┌───────────┐    ┌───────────────┐  ┌──────────────────┐
  │ SFT       │    │ KL 散度蒸馏   │  │ Hidden-state     │
  │ on output │    │ on logits     │  │ Feature matching │
  └───────────┘    └───────────────┘  └──────────────────┘
```

**轴 1：信号粒度** — 输出文字 vs 概率分布 vs 隐状态  
**轴 2：数据来源** — 历史已有 vs 实时合成 vs On-policy 学生采样  
**轴 3：训练算法** — SFT / DPO / KL / RL

---

## 2. 蒸馏技术分类（7 种主流方法）

### 2.1 Black-box SFT Distillation（黑盒输出蒸馏）⭐ 现状

**原理**：教师产出 `(prompt, output)` 对，学生用 SFT 学。
**适用**：只能调用教师 API，没有 logits/权重。
**本项目位置**：**主线**（已有 Claude trace）。
**代码**：`03_sft/train.py`。

**优点**：
- 简单，工具链成熟
- 适用任何教师（包括只有 API 的）
- 数据可复用历史 trace

**缺点**：
- 信号粒度粗（只学最终输出 token）
- 教师"为什么这样答"的信息丢失
- 收敛慢，需要更多数据

---

### 2.2 White-box Logit Distillation（白盒 KL 蒸馏）

**原理**：教师对每个 token 的概率分布 `p_T(x_t | x_<t)` 暴露给学生，学生最小化：

```
L_KD = α · CE(student_logits, label) + β · KL(student_logits || teacher_logits)
                ↑                            ↑
             硬标签 SFT                  软标签 KL
```

**经典论文**：Hinton 2015 - "Distilling the Knowledge in a Neural Network"

**关键约束**：教师和学生**必须同 tokenizer**（Qwen → Qwen，Llama → Llama）。

**优点**：
- **信号丰富**：每个 token 学的不是"对/错"，而是"概率应该多少"
- 收敛快（同等数据 + 量级提升 5-15%）
- 学生能"模仿"教师的不确定性

**缺点**：
- 必须能跑教师推理（教师 logits 实时算或预计算）
- 同 tokenizer 限制
- 计算开销 1.5-2x SFT

**本项目位置**：**强推作为补强阶段**。代码见 `train_kd.py`（本目录）。

---

### 2.3 Sequence-Level KD（序列级 KL）

**原理**：不是 per-token KL，而是教师对整个 sequence 给概率分布，学生学整体。

**优点**：能捕捉长依赖（不只局部 token）  
**缺点**：实现更复杂，需要对 K 个候选采样  
**位置**：进阶选项，本项目暂不实施。

---

### 2.4 CoT / Chain-of-Thought Distillation（思维链合成蒸馏）

**原理**：让教师产出 **(input, reasoning_chain, final_answer)** 三元组，学生学完整 reasoning。

**经典论文**：
- Magister et al. 2023 - "Teaching Small Language Models to Reason"
- Hsieh et al. 2023 - "Distilling Step-by-Step"
- DeepSeek R1 paper（2025）

**做法**：
```python
# 让教师对每条 case 输出 CoT
prompt = "解决这个营销分析问题"
teacher_output = "<think>步骤1：识别目标客群...步骤2：评估渠道...</think>结论：xxx"

# SFT 学生时，把整个 reasoning + answer 都喂进去
```

**优点**：
- 学生学到推理过程，不只学最终答案
- 在数学/逻辑/复杂分析任务上效果显著
- DeepSeek-R1-Distill-Qwen-7B 就是这么训出来的

**缺点**：
- 训练 + 推理时 token 数翻 2-5 倍
- 不是所有任务都需要 CoT（简单查询反而冗余）

**本项目位置**：**辅助手段**。
- ✅ 有用的场景：复杂多工具决策、长 horizon agent 任务
- ❌ 不需要：简单格式化输出、tool argument 填充

代码：`build_cot_data.py`（本目录）。

---

### 2.5 On-Policy Distillation（学生采样 → 教师批改）

**原理**：让**学生先产出**，再让教师评价 / 修正 / 排序，用结果训学生。

**关键洞察**：传统蒸馏喂给学生的是"教师认为对的"，但学生**实际会犯的错**没暴露给教师。On-policy 解决这点。

**变体**：
1. **Rejection Sampling Fine-tuning (RFT)**：学生采 K 个，教师选最好的，对它做 SFT
2. **Self-Rewarding / Self-Refine**：学生 → 教师批 → 学生重写
3. **DPO 用教师当 judge**：学生采两个，教师比较，做 DPO

**优点**：
- 训练分布 = 学生实际分布，**避免分布漂移**
- 偏好对齐效果接近 RLHF

**缺点**：
- 实施复杂（每轮都要教师推理）
- 成本高（每条样本要跑 K 次学生 + 1 次教师）

**本项目位置**：**阶段 3 DPO 的候选实现方式**。在 `04_dpo/build_preferences.py` 里"采样排序"路径就是 on-policy 雏形。

---

### 2.6 Reverse KL / On-Policy KL（如 MiniLLM）

**原理**：传统 KL 是 `KL(teacher || student)`，反向 KL 是 `KL(student || teacher)`。

**论文**：Gu et al. 2023 - "MiniLLM: Knowledge Distillation of Large Language Models"

**好处**：避免学生"过度模仿"教师的错误模式，更关注学生实际生成空间。

**缺点**：实现复杂，需要 RL 框架。

**本项目位置**：进阶研究方向，**暂不实施**。

---

### 2.7 Feature-Level Distillation（隐状态匹配）

**原理**：对齐教师和学生中间层 hidden state。

**论文**：FitNets, TinyBERT 等。

**优点**：信号最丰富。  
**缺点**：架构必须匹配（层数对齐）；实施复杂。  
**本项目位置**：❌ 不推荐（学生和教师层数不同时不可行）。

---

## 3. 选哪个？决策矩阵

按业务场景给推荐：

| 你的场景 | 推荐技术 | 为什么 |
|---|---|---|
| 只有 Claude API trace | **Black-box SFT** | 没 logits，只能黑盒 |
| Qwen 72B 自托管 + Qwen 7B 学生 | **White-box KL** + SFT | 同 tokenizer 收益最大 |
| 复杂多步推理任务 | + **CoT 合成** | 教学生"如何想" |
| SFT 后偏好不对 | **On-policy DPO** | 学生分布对齐 |
| 想要最强效果（不计成本） | **黑盒 SFT + 白盒 KL + CoT + DPO** 组合 | 多信号叠加 |
| 算力极紧 | 直接用 **R1-Distill-Qwen-7B**（已蒸） | 别自己训 |

---

## 4. 本项目分阶段技术路线（更新版）

```
阶段 1：数据 + Benchmark
   ├── 评估 Claude（基线）
   ├── 评估候选学生：Qwen 7B / Gemma 9B / R1-Distill-Qwen-7B
   ├── 评估候选教师：Qwen 72B（如果选作教师）
   └── 决策 DP1：是否训练 + 选哪种蒸馏

阶段 2：SFT（黑盒蒸馏，主线）
   ├── 用 Claude trace 做 SFT
   └── 产出 v2_sft_v* adapter
   
阶段 2.5（可选）：白盒 KL 增强
   ├── 用 Qwen 72B 教师跑 trace 产生 logits（预计算）
   ├── 学生 SFT loss + 0.3 × KL loss
   └── 产出 v2_kd_v* adapter

阶段 2.6（可选）：CoT 合成
   ├── 教师对复杂 case 产 CoT
   ├── 加入 SFT 数据
   └── 产出 v2_cot_v* adapter

阶段 3：DPO（偏好对齐）
   ├── 历史挖掘 / 采样排序 / Claude vs SFT
   └── 可结合 on-policy（学生采样 + 教师 judge）

阶段 4：灰度上线
```

**最强组合**：阶段 2 + 2.5 + 2.6 + 3 串联，预计比单 SFT **提升 10-20% 成功率**。  
**最简组合**：只跑阶段 2，先求"能用"。

---

## 5. 各方法的成本对比

按"训出一版可用 adapter"折算：

| 方法 | GPU 时长 | 数据准备成本 | 教师推理成本 | 总成本 |
|---|---|---|---|---|
| Black-box SFT | 1x | 已有 trace = $0 | $0 | **基准 1x** |
| White-box KL | 1.5x | + logits 预计算 | $$（72B 跑一遍） | 3-4x |
| CoT 合成 | 1x | + 教师生成 CoT | $$ | 2-3x |
| On-policy DPO | 2-3x | + K 采样 + judge | $$$ | 5-10x |
| Reverse KL (MiniLLM) | 5x+ | 复杂 | $$$ | 10x+ |

**推荐策略**：先黑盒 SFT，效果不行再加 KL，再加 CoT。**别一上来就堆**。

---

## 6. 常见误解

### ❌ "白盒一定比黑盒好"
不一定。白盒受限于教师和学生 tokenizer 同源；如果不同源还要做映射，反而引入噪声。

### ❌ "学生能超越教师"
训练范式上**学生天花板 = 教师**。学生只可能更便宜更快，不可能更强。除非：
- 用多个教师 + 学生 ensemble
- 加 RL（学生自己探索新策略）

### ❌ "蒸馏出来的小模型就完全替代教师"
小模型天然有局限：长 horizon、罕见任务、新工具，都会比教师差。**保留 fallback** 永远有意义。

### ❌ "DPO 也是蒸馏"
不严格意义上的"蒸馏"，但**用教师当 judge 的 DPO** 算 on-policy 蒸馏的一种。

---

## 7. 工程考虑

### 教师推理预计算 vs 实时
- **预计算 logits**（推荐）：教师跑一遍 trace，存 logits 到磁盘，训练时 load
  - 优点：训练时不依赖教师可用性
  - 缺点：磁盘大（每 token 一个 vocab-size 向量，可压缩 top-k）
- **实时推理**：训练循环里调教师 forward
  - 优点：节省磁盘
  - 缺点：训练慢，需要教师常驻

**本项目推荐预计算**，且只存 top-100 logits（vocab 几万维其他都接近 0）。

### Top-k 压缩 logits
```python
# 只存 top-100，其他视为均匀
top_logits, top_indices = teacher_logits.topk(100, dim=-1)
# 训练时还原
student_logits_subset = student_logits.gather(dim=-1, index=top_indices)
loss = kl_div(student_logits_subset, top_logits)
```
磁盘从 vocab × 4 bytes 降到 100 × 8 bytes（97% 压缩）。

### Tokenizer 不一致怎么办
- 不能直接做白盒
- 退化到黑盒 SFT
- 或做"近似 token 对齐"（复杂，效果有损）

---

## 8. 推荐学习资料（按这个目录补到 `learning_resources.md`）

### 论文必读
1. 🔴 [Hinton 2015 - 经典蒸馏](https://arxiv.org/abs/1503.02531)
2. 🔴 [DistilBERT (2019)](https://arxiv.org/abs/1910.01108)
3. 🔴 [TinyBERT (2019)](https://arxiv.org/abs/1909.10351)
4. 🔴 [MiniLLM (Gu et al., 2023)](https://arxiv.org/abs/2306.08543)
5. 🔴 [Distilling Step-by-Step (Hsieh et al., 2023)](https://arxiv.org/abs/2305.02301)
6. 🔴 [DeepSeek R1（2025）](https://arxiv.org/abs/2501.12948) - 教学生推理的范本
7. 🔴 [Self-Rewarding LM (Yuan et al., 2024)](https://arxiv.org/abs/2401.10020)

### 开源代码
- 💻 [HF distillation example](https://github.com/huggingface/transformers/tree/main/examples/research_projects/distillation)
- 💻 [DistilKit](https://github.com/arcee-ai/DistillKit) - Arcee 的蒸馏工具包
- 💻 [DeepSeek-R1 蒸馏脚本](https://github.com/deepseek-ai/DeepSeek-R1)
- 💻 [open-r1](https://github.com/huggingface/open-r1)

### 中文
- 📝 [蒸馏综述（中文）](https://zhuanlan.zhihu.com/p/681030538)
- 📝 [DistilBERT 详解（中文）](https://zhuanlan.zhihu.com/p/89522799)

---

## 9. 决策清单

启动训练前回答：

- [ ] 数据来源是？（Claude trace / 自己用大模型生成 / 混合）
- [ ] 教师模型是？（参考 `teacher_model_comparison.md`）
- [ ] 教师和学生 tokenizer 是否同源？
- [ ] 主推方法是？（黑盒 SFT / 白盒 KL / 混合）
- [ ] 是否加 CoT 合成？哪些任务加？
- [ ] DPO 阶段用 on-policy 还是 offline？
- [ ] 教师推理是预计算还是实时？

填完写进 `06_decisions/DP1_train_or_not.md`。

---

## 变更记录
- 2026-04-24：首版，覆盖 7 类蒸馏技术
