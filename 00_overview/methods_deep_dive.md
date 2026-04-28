# SFT / DPO / RL 深度对比 —— 怎么选、怎么用、常见坑

> 本文补齐 `concepts_and_techniques.md` 的技术深度。
> 客户最常问："我到底该用 SFT、DPO 还是 RL？"

---

## TL;DR（决策树，先看这个）

```
问题 1: 你有监督数据（input → correct output）吗？
    │
    ├─ 有，数据充足 (>1000 条) ──▶ 从 SFT 开始
    │                               │
    │                               ▼
    │                        问题 2: SFT 后技术指标达标但人工评分不够？
    │                               │
    │                               ├─ 是 ──▶ 加 DPO / ORPO
    │                               └─ 否 ──▶ 数据回炉 / 换基座
    │
    └─ 没有监督数据 或 需要从奖励信号学 ──▶ 考虑 RL
                                              │
                                              ▼
                                     问题 3: 有稳定的 reward？有 environment？
                                              ├─ 有 ──▶ PPO / GRPO / DAPO
                                              └─ 无 ──▶ 先别做 RL，去补 reward
```

---

## 1. SFT（Supervised Fine-Tuning）

### 1.1 原理

给定 `(x, y)` 对，训练模型让 `P(y|x)` 最大化。Loss 是**交叉熵**：

```
L_SFT = -∑_t log P(y_t | y_<t, x)
```

**本质**：模仿学习。教师给正确答案，学生背下来。

### 1.2 适用场景（本项目重点）

| 场景 | 为什么用 SFT |
|---|---|
| 格式不稳（JSON 崩） | 学格式最直接 |
| 业务流程不熟 | 学流程 = 学 token 序列 |
| 工具调用参数错 | 学参数 = 学输出分布 |
| 没见过的业务模式 | 学"要这样做" |

### 1.3 技术细节

**关键超参**：
- `learning_rate`：LoRA 用 2e-4；全参用 1e-5 到 5e-5
- `epochs`：1-3（别更多）
- `lora_r`：16 默认，简单任务 8，复杂 32
- `max_seq_length`：按业务最长输入定；默认 4096

**Loss mask（极其重要）**：
- 只在 **assistant 部分**算 loss
- user / tool / system 都 mask 掉
- TRL 的 `DataCollatorForCompletionOnlyLM` 处理

**代码**：`03_sft/train.py`

### 1.4 常见坑

| 症状 | 原因 | 解决 |
|---|---|---|
| Loss 不降到 0 | response_template 不对 | 查 collator 的 mask 位置 |
| Loss 降得太快（< 0.3） | 过拟合 | 减 epoch / 加 dropout |
| 通用能力退化 | 灾难性遗忘 | 混 20-30% 通用指令数据 |
| 工具调用格式崩 | 数据里格式不统一 | 清洗 + 约束解码 |
| OOM | 显存不够 | QLoRA + grad_checkpoint + 减 batch |

### 1.5 SFT 的局限

**SFT 学不好的**：
1. **偏好排序**：A 和 B 都对，但 A 更好 → SFT 学不了"偏好"
2. **长 horizon 规划**：多步决策的"哪条路更好" → SFT 给不了信号
3. **稀有错误修正**：错误样本不能进 SFT（会学成"这样也行"）
4. **新能力探索**：SFT 只学"已见过的"，探索不了新解法

**这四个 SFT 解决不了的 → 后面的 DPO / RL 补**

---

## 2. DPO（Direct Preference Optimization）

### 2.1 原理

给定偏好对 `(x, y_w, y_l)`（w = 胜者 / chosen，l = 败者 / rejected），直接训练让模型更倾向 `y_w`：

```
L_DPO = -log σ(β · [log(π_θ(y_w|x) / π_ref(y_w|x)) - log(π_θ(y_l|x) / π_ref(y_l|x))])
```

**本质**：对比学习。不需要奖励模型（RM），直接从偏好对学。

**和 RLHF 的关系**：DPO 论文（2023）证明"最优策略形式"和 RLHF 的 KL 约束最大化等价，所以不用跑 PPO。

### 2.2 适用场景

| 场景 | 举例 |
|---|---|
| SFT 后技术 OK 但风格不对 | 文案生硬、不吸引人 |
| 多个合理答案，要选最好的 | 营销文案、推荐理由 |
| 业务偏好和通用偏好不一致 | 本公司特有的表达风格 |

### 2.3 技术细节

**关键超参**：
- `learning_rate`：5e-7 到 5e-6（**比 SFT 小 100-1000 倍！**）
- `beta`：0.1-0.5（越大越保守）
- `epochs`：1-2（容易过拟合）
- **参考模型**：SFT 后的 adapter，冻结

**数据 schema**：
```json
{
  "prompt": "写一句高端护肤品广告",
  "chosen": "点燃东方美学，唤醒肌肤本真光泽",
  "rejected": "我们的面霜很不错，你应该买"
}
```

**代码**：`04_dpo/train_dpo.py`

### 2.4 常见坑（比 SFT 更多更隐蔽）

| 症状 | 原因 | 解决 |
|---|---|---|
| **Reward hacking** | 模型找 reward 漏洞，margin 飙升但 benchmark 掉 | 降 lr + 降 epoch + 加 beta |
| **长度偏差** | chosen 平均更长 → 模型学"越长越好" | 构造偏好对时做长度匹配 |
| **崩溃** | lr 太大，通用能力全没 | lr 5e-7 起步 |
| **学不到东西** | 偏好对质量差，chosen/rejected 几乎一样 | 筛选区分度大的对 |
| **SFT 掉分** | 参考模型选错（选了基座不是 SFT） | ref = SFT adapter |

### 2.5 DPO 的变体

| 变体 | 关键改动 | 什么时候用 |
|---|---|---|
| **ORPO** | 不需要参考模型，SFT + DPO 一步 | 显存紧 / 快速迭代 |
| **SimPO** | 去掉参考模型 + 长度归一化 | 长度偏差严重 |
| **KTO** | 不需要成对偏好，只要 good/bad 标签 | 数据收集更易 |
| **IPO** | 修复 DPO 理论漏洞 | 实验性 |
| **CPO** | SFT 和 DPO 目标合并 | 和 ORPO 类似 |

**推荐**：**先 DPO，不稳再 SimPO**。ORPO 作为备选。

---

## 3. ORPO vs DPO 关键对比

| 维度 | DPO | ORPO |
|---|---|---|
| 需要 SFT 基底 | ✅ 必须 | ❌ 不需要 |
| 需要参考模型 | ✅ 占显存 | ❌ 省显存 |
| 训练阶段 | 两步（SFT → DPO） | 一步 |
| 超参稳定性 | 更稳 | 较新，经验少 |
| 生产验证 | 多 | 少 |

**本项目选 DPO**，ORPO 在"显存非常紧"时作备选。

---

## 4. RL（Reinforcement Learning）

### 4.1 原理

**经典 RLHF 三步**：
1. SFT（初始化）
2. 训练奖励模型（RM）
3. 用 PPO / GRPO / DAPO 让模型最大化 reward

**Loss**（PPO 简化）：
```
L_PPO = E[min(π_θ/π_old · A, clip(π_θ/π_old, 1-ε, 1+ε) · A)]
     其中 A = 优势函数（advantage）
```

**本质**：探索 + 利用。模型自己产输出，拿 reward 当监督信号。

### 4.2 为什么 RL 强？

**SFT / DPO 做不到的 RL 能做**：
- **多步决策优化**：不只优化单条输出质量，优化整条策略
- **自我探索**：模型可能找到教师没见过的解法（超越教师上限！）
- **稀疏奖励学习**：只在最后一步给信号也能学（如"最终采纳率"）
- **真实业务信号**：直接用"用户点赞"当 reward

### 4.3 为什么 RL 难？

**RL 的四大难题**：

1. **Reward 函数设计**
   - 规则基 reward（JSON 有效率等）容易 hack
   - LLM-as-judge reward 慢且贵
   - 业务信号 reward（采纳率）稀疏且延迟
   - **最难的是"怎么定义好"**

2. **Environment**
   - Agent 要 interact，需要 sandbox（工具模拟）
   - 环境要**稳定**，不能每周改
   - 复现成本高

3. **训练稳定性**
   - PPO 有 37 个实现细节坑
   - GRPO 对 group 大小、KL 系数敏感
   - reward hacking 随时可能出现

4. **成本**
   - 每 step 跑多次学生采样 + 教师 judge
   - 训练时长是 SFT 的 10x+
   - GPU 利用率低（采样时卡空转）

### 4.4 RL 的主流算法

| 算法 | 特点 | 什么时候用 |
|---|---|---|
| **PPO** | 经典 RLHF，最稳但复杂 | 大预算 / 成熟团队 |
| **DPO** | 理论等价 PPO（其实不是 RL） | 大部分场景的第一选择 |
| **GRPO** | DeepSeek R1 用，不要 value model | 推理任务 / 想试新的 |
| **RLOO** | Reinforce 变体，实现简单 | 快速 POC |
| **DAPO** | GRPO 改进，稳定性更好 | GRPO 翻车时 |
| **REINFORCE** | 最古老最简单 | 教学 / baseline |

### 4.5 RL 在 LLM 场景的三种落地形式

#### 形式 A：经典 RLHF（对齐偏好）
- 先 SFT，再训 RM，再 PPO
- 目标：让模型更符合人类偏好
- 例：ChatGPT / Claude 初版

#### 形式 B：RLAIF（AI 当裁判）
- 同上但 reward 来自另一个 LLM
- 省标注成本
- 例：Anthropic Constitutional AI

#### 形式 C：RL on Verifiable Rewards（可验证奖励）
- reward 来自**可计算的规则**：数学答案对错、代码跑通与否
- 不需要人 / LLM judge
- 例：DeepSeek R1（数学 + 代码）

---

## 5. RL 在**本项目**的重新评估

> 原方案说"RL 暂缓"，客户质疑。这里正面回答。

### 5.1 原判断的问题

原方案的 5 条件拒绝 RL：
1. Benchmark 体系稳定
2. 人工评分映射稳定
3. Environment 明确
4. Reward 明确
5. 是多步策略问题

**问题**：这 5 条是 RL **规模化**的前提，但**不代表不能做 POC**。
我们可以在**受控子任务**上跑小规模 RL，验证价值后再规模化。

### 5.2 RL 在本业务**可以**怎么落地

#### 落地 1：小规模可验证奖励 RL（推荐 POC）

**场景**：工具调用参数生成
- 用户说 "查一下上周北京销量"
- Agent 要调 `search` 工具，参数要对（日期、地区、指标）
- **Reward = 参数对 / 参数错**（可验证）

**做法**：
1. 用 GRPO 或 RLOO
2. 数据：从 LangSmith 挑能自动验证的 case（100-500 条）
3. 规模：LoRA 小实验，不全量

**预期**：比 SFT 参数错误率再降 30-50%。

#### 落地 2：RL-as-DPO（其实是 DPO，但用"RL 思维"构造数据）

**场景**：文案生成偏好对齐
- 对同一 prompt，学生采 K 个输出
- 教师（或业务方）排序
- 前后做 DPO（本质是 on-policy 蒸馏）

**这在 04_dpo/build_preferences.py 已实现**。是本项目的 RL 味道的 DPO。

#### 落地 3：业务采纳率 RL（长期方向）

**场景**：用真实用户行为信号
- 用户点"采纳" = 正 reward
- 用户改稿后采纳 = 低正 reward
- 用户弃用 = 负 reward

**为什么暂时不做**：
- 需要**线上回流机制**（shadow evaluation / canary）
- 需要 reward 信号**足够快**（延迟 > 1 天就难训）
- 需要有**降级保护**（避免 reward hack 影响真实业务）

**什么时候做**：**阶段 4 灰度稳定 1 个月后**，线上采纳信号累积起来再启动。

### 5.3 RL 在本项目的分阶段路线（更新版）

```
阶段 2-3: SFT + DPO（主线）
        │
        └── 在此期间准备 RL 所需：
              - 稳定 benchmark
              - 确定"可验证 reward"的子任务
              - 积累 200 条标注的黄金集

阶段 4: 灰度上线
        │
        ├── 可以并行做 RL POC：
        │     └── 工具参数 RL（落地 1）
        │
        └── 线上收集采纳信号

阶段 5: 稳定 1 个月后
        │
        └── 业务采纳率 RL（落地 3）
              - 此时已经有稳定 reward 信号
              - 已经有 fallback 兜底
              - 灰度窗口已经建好
```

**结论修正**：
- **RL 不是"永远不做"**
- **RL 的前置是"稳定的基础"**
- 原方案把 RL 放在最后 = 合理
- 但**客户/团队应该知道 RL 是明确的第 5 阶段**，不是被砍掉的能力

---

## 6. 三种方法（和变体）全面对比

| 维度 | SFT | DPO | ORPO/SimPO | PPO | GRPO | RLAIF |
|---|---|---|---|---|---|---|
| 数据类型 | (x, y) | (x, y_w, y_l) | (x, y_w, y_l) | reward | reward | AI reward |
| 需要 RM | ❌ | ❌ | ❌ | ✅ | ❌ | ✅（AI） |
| 需要参考模型 | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ |
| 训练稳定 | 🟢 | 🟡 | 🟡 | 🔴 | 🟡 | 🔴 |
| 数据量要求 | 1k-10k | 1k-5k pairs | 1k-5k | 持续 | 持续 | 持续 |
| 计算成本 | 1x | 2x | 1.5x | 10-30x | 5-15x | 5-15x |
| 能探索超教师 | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| 本项目阶段 | 2 主 | 3 主 | 3 备选 | 5 后期 | 5 POC | 5 |

---

## 7. 组合使用的最佳实践

### 7.1 不要只用一种

真实项目通常是**组合拳**：

```
Step 1: SFT（学格式 / 流程）
    ↓ adapter_sft
Step 2: DPO（对齐偏好 / 风格）
    ↓ adapter_dpo
Step 3: RL（可选，探索 / 业务信号）
    ↓ adapter_rl
Step 4: 灰度上线 + 线上数据回流
    ↓
Step 5: 用线上数据继续 SFT（回到 Step 1）
```

### 7.2 顺序不能乱

❌ 错误顺序：
- 直接 DPO 没 SFT（没基础，DPO 放大错误）
- 直接 RL 没 SFT（训练崩溃）
- SFT 后直接 RL 跳过 DPO（大部分场景 DPO 就够）

✅ 正确顺序：
- SFT → DPO → (RL) → 上线 → 回流 → SFT 再训

### 7.3 各阶段的"足够"信号

| 阶段 | 认为"足够了"的信号 |
|---|---|
| SFT | 技术指标（成功率 / JSON 有效率）达标 |
| DPO | 人工评分提升 ≥ 0.3 分（5 分制） |
| RL | 业务 KPI 显著提升（采纳率 / NPS） |

---

## 8. 教学上如何让学员理解

### 8.1 三段话总结

**给完全不懂的人讲**：
> SFT 是"照着答案抄"，DPO 是"两个答案选更好的"，RL 是"自己试，根据反馈调整"。

**给开发讲**：
> SFT 学分布，DPO 学排序，RL 学策略。

**给业务讲**：
> SFT 让模型"会做"，DPO 让模型"做得合你心意"，RL 让模型"做得比你预期还好"。

### 8.2 类比（帮客户理解）

| 方法 | 类比 |
|---|---|
| SFT | 背标准答案的学生 |
| DPO | 看两份答案选更好的学生 |
| RL | 做题后根据反馈调整思路的学生 |

---

## 9. 代码与配置速查

| 需求 | 用哪个 | 代码 | 配置 |
|---|---|---|---|
| 基础 SFT | TRL SFTTrainer | `03_sft/train.py` | `sft_v2_base.yaml` |
| 黑盒蒸馏 SFT | 同上 | 同上 | `blackbox_claude_to_qwen7b.yaml` |
| 白盒 KL 蒸馏 | 自实现 Trainer | `03_sft/train_kd.py` | `kd_qwen72b_to_7b.yaml` |
| DPO | TRL DPOTrainer | `04_dpo/train_dpo.py` | `dpo_v2.yaml` |
| ORPO | TRL ORPOTrainer | 同 DPO 结构改 config | - |
| PPO | TRL PPOTrainer | 单独项目，超前 | - |
| GRPO | TRL GRPOTrainer / open-r1 | 超前 | - |

---

## 10. 学习路径

零基础到理解：
1. 读完本文（1 小时）
2. 读 `concepts_and_techniques.md`（30 min）
3. 读 `finetune_vs_distill.md`（30 min）
4. 看 HuggingFace TRL tutorial（2 小时）
5. 跑通 `03_sft/train.py` demo（1 天）

深入一步：
1. 跑通 `04_dpo/train_dpo.py`
2. 看 InstructGPT 论文 + DPO 论文
3. 了解 GRPO（看 DeepSeek R1 论文）
4. `rl_in_current_business.md` 了解落地

---

## 11. 关键参考

### 论文
- 🔴 [InstructGPT (2022)](https://arxiv.org/abs/2203.02155) - RLHF 原始
- 🔴 [DPO (2023)](https://arxiv.org/abs/2305.18290)
- 🔴 [ORPO (2024)](https://arxiv.org/abs/2403.07691)
- 🔴 [SimPO (2024)](https://arxiv.org/abs/2405.14734)
- 🔴 [KTO (2024)](https://arxiv.org/abs/2402.01306)
- 🔴 [DeepSeek R1 - GRPO (2025)](https://arxiv.org/abs/2501.12948)
- 🔴 [PPO 37 details](https://iclr-blog-track.github.io/2022/03/25/ppo-implementation-details/)

### 视频
- 🎥 [Karpathy - State of GPT](https://www.youtube.com/watch?v=bZQun8Y4L2A)
- 🎥 [Sebastian Raschka - LLM training comparison](https://magazine.sebastianraschka.com/p/llm-training-rlhf-and-its-alternatives)

### 代码
- 💻 [TRL](https://github.com/huggingface/trl)
- 💻 [open-r1](https://github.com/huggingface/open-r1)
- 💻 [OpenRLHF](https://github.com/OpenRLHF/OpenRLHF)

---

## 变更记录
- 2026-04-24：首版，增加 RL 深度 + 本项目 RL 落地路线
