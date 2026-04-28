# RL 在当前业务中的再评估与落地

> 原方案把 RL 放在最后一个阶段"暂缓"，客户质疑："RL 就真的不适合吗？"
> 本文档正面回答：**RL 不是不适合，是需要前置条件**。
> 并给出**可以现在就启动的 RL POC**。

---

## 1. 原方案为什么说"暂缓"

原判断依据是需求文档第 4.4 节列的 5 个条件：
1. Benchmark 体系稳定
2. 人工业务评分映射稳定
3. 能定义明确的 environment
4. 能定义明确的 reward
5. 需要优化的是多步任务策略，而不只是输出质量

原方案把这 5 条作为"**全部满足**才启动 RL"的门槛。

**问题**：这是 RL **规模化上线**的前提，**不是"做 RL POC"的前提**。把两件事混在一起导致"一刀切"。

---

## 2. 重新定义：RL 的三种做法

不是所有 RL 都需要前置 5 条件。按做法分三档：

### 2.1 轻量级：RL on Verifiable Rewards（可验证奖励）

**特征**：
- Reward 来自**可计算的规则**（不需要人、LLM judge、线上信号）
- 例：JSON 是否合法 / 工具参数是否匹配 schema / 数学答案是否正确 / 代码是否跑通

**前置条件**：
- ❌ 不需要稳定的人工评分
- ❌ 不需要线上回流
- ✅ 只需要**一个可写出规则的子任务**

**代表**：DeepSeek R1（数学 + 代码）、OpenAI o1 训练

**本项目可选场景**：
- 工具调用参数 schema 校验 → 作为 reward
- JSON 输出合法性 → 作为 reward
- tool_call name 匹配预期 → 作为 reward

### 2.2 中量级：RLAIF（AI 作裁判）

**特征**：
- Reward 来自另一个 LLM（Claude judge）的打分
- 不需要人

**前置条件**：
- ⚠️ 需要稳定的 judge prompt 和判据
- ⚠️ Judge 的 bias 可能传染

**代表**：Anthropic Constitutional AI, Self-Rewarding LM

**本项目可选场景**：
- 文案生成质量打分
- 风格一致性打分
- 复杂多步决策合理性打分

### 2.3 重量级：RLHF / 业务 RL

**特征**：
- Reward 来自真实用户行为 / 业务指标
- 需要线上流量 + 回流

**前置条件**（就是原方案列的 5 条）：
- ✅ 稳定 benchmark
- ✅ 稳定人工评分
- ✅ 线上 shadow / canary 机制
- ✅ 业务信号能快速回流（<1 小时）

**本项目时间点**：**灰度上线稳定 1 个月后**

---

## 3. 本项目 RL 落地路线（分阶段）

### 🎯 立即可做：POC 1 - 工具参数可验证 RL

**目标**：让小模型的工具调用**参数格式**和**字段准确性**比纯 SFT 再提升 30%+

**做法**：
1. 选 1 个工具（比如 `search`），规则容易写
2. 构造 500 条用户输入，期望的 `search` 参数用规则检查能通过/不通过
3. 用 **GRPO** 或 **RLOO** 算法（不需要 value model，简单）
4. Reward = 参数合法性（0/1）+ 参数关键字段命中率（连续分）
5. 小规模 LoRA，预计 3-5 天跑完

**为什么可行**：
- 不需要人工评分（规则自动判）
- 不需要 environment（单步 tool call，不是多轮）
- 不需要业务信号
- 可以**立即验证** RL 是否带来增益

**代码参考**：`03_sft/train_rl_grpo.py`（本次新增）

### 🎯 中期（DP2 后）：POC 2 - 用教师 judge 的 RLAIF

**目标**：SFT 后业务风格对齐用 RL 代替 DPO 试试

**做法**：
1. 学生采样 K=8 个输出
2. Claude 对每个打 1-5 分（判据：业务相关 + 准确 + 风格）
3. GRPO 训练，reward = Claude 打分
4. 和 DPO 版本对比

**价值**：
- 如果 RL 显著强于 DPO，可规模化
- 如果持平，证明 DPO 已够，不需要 RL

### 🎯 长期（灰度稳定后）：POC 3 - 业务采纳率 RL

**前置条件**：
- ✅ 小模型已上线灰度至少 1 月
- ✅ 用户采纳信号每天稳定回流
- ✅ Fallback 兜底防止 RL 崩

**做法**：
1. 收集线上 trace + 用户行为（采纳 / 修改后采纳 / 弃用）
2. 每周训一次 RL（增量 LoRA）
3. 用线上流量的**小比例**做 on-policy 训练
4. 持续 shadow evaluation 防 reward hacking

**价值**：**模型能自我进化**，超越教师上限（Claude）成为可能。

---

## 4. RL 的常见坑（本项目特别注意）

### 4.1 Reward Hacking（reward 作弊）

**现象**：模型找 reward 函数的漏洞。
- 如果 reward = JSON 合法 → 模型学会输出 `{}`
- 如果 reward = 长度 → 模型学会重复一句话 100 遍

**防范**：
- Reward 函数**组合 3+ 维度**（合法性 + 命中 + 业务判据）
- 每 N step 做 benchmark 验证
- 加 KL penalty 约束不要偏离 SFT 模型太远

### 4.2 训练崩溃（model collapse）

**现象**：训着训着输出乱码 / 空 / 重复。

**原因**：
- lr 太大
- KL 系数太小（偏离参考模型太远）
- Advantage 归一化没做

**防范**：
- lr 1e-6 起步
- KL coef 0.05-0.2
- 打印 `rewards/mean`、`rewards/std`、`kl` 曲线

### 4.3 训练过慢

**原因**：
- 每 step 要采样 K 次（GRPO 常用 K=8）
- Sampling + forward + backward 串行
- GPU 利用率低

**优化**：
- 用 vLLM 做采样（比 HF 快 5-10x）
- 分布式训练
- Batch 放大

### 4.4 Sample efficiency 低

**现象**：训 1000 step 效果还不如 SFT 100 step。

**原因**：RL **本来就 sample inefficient**，这是常态。

**应对**：
- 如果 SFT 能解决，就**别用 RL**（大多数情况）
- 如果必须 RL，准备好 10-100x 数据量

---

## 5. GRPO（本项目推荐算法）详解

### 5.1 为什么选 GRPO

| 算法 | 优点 | 缺点 | 推荐 |
|---|---|---|---|
| PPO | 最稳 | 要 value model，4 个模型同时在显存 | ❌ 太重 |
| GRPO | 不要 value model | 超参敏感 | ✅ **推荐** |
| RLOO | 更简单 | 采样方差大 | ⚠️ 备选 |
| DPO | 简单 | 严格不算 RL | ✅ 已用 |

### 5.2 GRPO 原理

对每个 prompt，采样 G 个回答 `{y_1, ..., y_G}`，计算 advantage：

```
r_i = reward(y_i)
mu, sigma = mean(r), std(r)
A_i = (r_i - mu) / sigma   # group-relative advantage

L_GRPO = -E[min(ratio_i · A_i, clip(ratio_i) · A_i) - β · KL(π || π_ref)]
```

**核心**：同一 prompt 里谁比别人好，就往这个方向推。

### 5.3 关键超参

```yaml
grpo:
  num_generations: 8        # K，每 prompt 采样数
  kl_coef: 0.04             # KL 约束
  epsilon: 0.2              # clip 范围
  max_new_tokens: 1024
train:
  lr: 1e-6                  # 比 SFT 小 200x
  batch_size: 1             # 因为一条 prompt 已经是 8 个 seq
  grad_accum: 8
  epochs: 1
```

---

## 6. RL POC 起步脚本（推荐实施）

**脚本**：`03_sft/train_rl_grpo.py`（本次新增）

**起步任务**：工具参数可验证 RL（POC 1）

**流程**：
1. 准备 500 条 `(prompt, expected_tool_call)` 对
2. 定义 `reward_fn(prompt, output)`：
   - 解析 output 的 tool_call
   - 和 expected 比对
   - 返回 0-1 连续分
3. 跑 GRPO 训练（基于 SFT 后的 adapter）
4. 对比 SFT vs GRPO 在测试集上表现

**期望**：工具参数错误率降 20-40%，且总能力不降。

---

## 7. 什么时候**千万别**做 RL

明确的反模式：

| 场景 | 为什么不能 RL |
|---|---|
| SFT 都没跑通 | 没有基础，RL 会崩 |
| 没有 eval 体系 | 无法判断 RL 好坏 |
| 业务还在大改 | environment 不稳，reward 会漂移 |
| 团队没做过 RL | 先看 3 篇论文 + 跑 demo |
| 算力紧 | RL 比 SFT 贵 10-30x |
| 想省标注成本 | RL 不省标注，标的是 reward 判据 |
| 赶 3 个月上线 | 除非走"轻量 verifiable reward"路线 |

---

## 8. 给客户的澄清对话稿

**客户**："你们为什么不上 RL？听起来 RL 最先进。"

**我们**：
> RL 不是我们不想上，是它有三档难度：
>
> - 轻量 RL（可验证奖励）：**可以现在就做 POC**，比如工具参数训练。只需要能写规则判好坏。
> - 中量 RL（AI 裁判）：SFT 后做，效果可能超 DPO。**我们会在阶段 3 做对照实验**。
> - 重量 RL（业务信号）：需要灰度上线稳定+数据回流，**这是阶段 5 的事**。
>
> 所以不是"不做 RL"，是"按复杂度分层做"。本项目规划的 RL 路线有三个落地点，不只是最后一个。

---

## 9. 对主方案的修正

### 9.1 原方案的表述需要改

**旧表述**：
> 阶段 5：RL - 暂缓，仅做前置调研

**新表述**：
> **阶段 5：RL** - 分三档落地
> - POC 1（可现在做）：工具参数可验证 RL
> - POC 2（阶段 3）：RLAIF 对比 DPO
> - 规模化（阶段 5）：业务采纳率 RL

### 9.2 DP5 决策书需要调整

原 `06_decisions/DP5_rl_evaluation.md` 基于"启不启动"二选一，实际应该：
- DP5a：POC 1 启不启动（阶段 2 期间）
- DP5b：POC 2 启不启动（阶段 3 期间）
- DP5c：规模化启不启动（阶段 5）

---

## 10. 相关文档

| 文档 | 关系 |
|---|---|
| `methods_deep_dive.md` §4-5 | RL 基础原理 |
| `08_rl_future/readings.md` | RL 学习资料 |
| `concepts_and_techniques.md` §1.6-1.8 | RL / PPO / GRPO 术语 |
| `03_sft/train_rl_grpo.py` | GRPO 起步脚本（本次新增） |
| `06_decisions/DP5_rl_evaluation.md` | RL 决策书（待拆分） |

---

## 变更记录
- 2026-04-24：首版，纠正"RL 暂缓"的表述，给出三档落地路线
