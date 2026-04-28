# 核心概念 & 技术对比

> 面向初学者的一站式术语解释 + 为什么选这条路线 + 还有什么替代方案。  
> 读这一份，看其他文档就不会卡在名词上。

## Part 1：术语扫盲

### 1.1 LangSmith trace

**是什么**：LangSmith（LangChain 推出的观测平台）记录下来的一次"LLM 应用运行"的完整执行轨迹。

**一条 trace 通常包含**：
- 用户输入 / 系统 prompt
- 每次模型调用的输入输出
- 每次工具调用（name、arguments、return）
- 每个中间节点的状态变化
- 总耗时、token 数、成本
- 最终状态（success / error）

**为什么重要**：
> 这是我们蒸馏的**唯一数据源**——我们没有专门为小模型训练准备的标注数据，只有 Claude 已经跑过的真实业务 trace。

**对应到需求文档第 3 节**：`用户输入 / system / 已加载 skill / AI 工具调用 / 工具返回 / report_progress / submit_final_report / 最终状态`——全部都是从 trace 里抽的字段。

**结构示意**：
```
Run (chain)
├── inputs: {user_input: "...", system: "...", skills: [...]}
├── child_runs:
│   ├── LLM call (Claude) → outputs: {tool_calls: [...]}
│   ├── Tool call: search → outputs: {results: [...]}
│   ├── LLM call (Claude) → outputs: {content: "..."}
│   └── Tool call: submit_final_report
├── outputs: {final_response: "..."}
└── status: success
```

我们的 pipeline 把整棵树"拍平"成标准 messages 序列（见 `01_data_pipeline/code/extract_fields.py`）。

---

### 1.2 LoRA（Low-Rank Adaptation）

**是什么**：一种参数高效微调方法。不改动基座的 70 亿参数，只在几个关键位置插入小的"旁路矩阵"（秩 r，通常 8/16/32），训练时只更新这些旁路。

**直觉**：基座是一本印刷好的字典，LoRA 是贴上去的便利贴——便利贴很小，但能改变你读字典时的理解。

**为什么所有现代微调都用它**：
- 训练参数减少 100-1000 倍
- 单卡就能训 7B/9B 模型
- 不同任务训不同 adapter，推理时可切换
- 不污染基座，随时回滚

**QLoRA**：LoRA + 4-bit 量化基座。9B 模型可以在 24GB 显卡上训。

### 1.3 SFT（Supervised Fine-Tuning）

**是什么**：给模型"正确答案"，让它学会模仿。最传统的微调方式。**也是一种蒸馏**（black-box distillation——只用教师的输出文字训练）。

**进一步**：SFT 之外还有 6 种蒸馏方法（白盒 KL、CoT 合成、On-policy、Reverse KL 等）。详见 [`../03_sft/distillation_techniques.md`](../03_sft/distillation_techniques.md)。

**数据形式**：`(输入, 期望输出)` 对。
```
输入：用户问 + 工具定义
输出：AI 的完整回复（含 tool_call）
```

**训练目标**：next token prediction——给定前面的 token，预测下一个。

**什么时候选**：
- 模型会做这类任务，但**不稳定** → 学习正确姿势
- 输出**格式**老是崩（JSON 不合法、字段缺失） → 学格式
- 模型**没见过**这个任务 → 学新能力

**SFT 不擅长什么**：
- 微调后所有"像"的输出都学会了，包括错误答案的错误模式
- 不能区分"A 比 B 好"——它只知道 A 是"对"的

### 1.4 DPO（Direct Preference Optimization）

**是什么**：不用奖励模型，直接用偏好对 `(chosen, rejected)` 训练，让模型更倾向 chosen。

**论文**：Rafailov et al., "Direct Preference Optimization: Your Language Model is Secretly a Reward Model", NeurIPS 2023。

**直觉**：SFT 教模型"应该这样答"；DPO 教模型"A 比 B 好"。

**数据形式**：
```json
{
  "prompt": "写一句营销文案",
  "chosen": "...打动人心的版本...",
  "rejected": "...平淡的版本..."
}
```

**核心 loss**（简化）：
```
L = -log σ(β · [log π(chosen|prompt) - log π(rejected|prompt) 
              - log π_ref(chosen|prompt) + log π_ref(rejected|prompt)])
```
其中 `π_ref` 是 SFT 后的参考模型（冻结），`π` 是正在训的模型。

**什么时候选**：
- SFT 之后，技术指标（成功率/工具调用率）已经够 → 还要对齐"风格"或"偏好"
- 有**多个都能完成任务**的候选，但业务方觉得一个明显更好

**DPO 的坑**：
- lr 比 SFT 小 100-1000 倍
- 容易 reward hack（找到"漏洞"拉高差值而不改善实际输出）
- 对长度敏感，容易学到"chosen 都更长"这种虚假相关

### 1.5 ORPO（Odds Ratio Preference Optimization）

**是什么**：把 SFT 和 DPO 合成一步训练，不需要参考模型，不需要先 SFT 再 DPO。

**论文**：Hong et al., "ORPO: Monolithic Preference Optimization without Reference Model", 2024。

**和 DPO 的区别**：
| 维度 | DPO | ORPO |
|---|---|---|
| 需不需要 SFT 基底 | 需要（强推荐） | 不需要 |
| 参考模型 | 需要（占显存） | 不需要 |
| 数据 | 偏好对 | 偏好对 |
| 训练阶段 | 两步（SFT → DPO） | 一步 |

**什么时候选 ORPO 而不是 DPO**：
- 显存紧张，装不下参考模型
- 手头本来就有偏好对数据（不想再 SFT 一遍）
- 想省一个训练阶段

**ORPO 的问题**：
- 论文数据表现好，但生产落地不如 DPO 成熟
- 超参调优经验少

### 1.6 RLHF（Reinforcement Learning from Human Feedback）

**是什么**：经典三步走——
1. SFT
2. 训练一个**奖励模型（RM）**：输入 prompt 和 response，输出奖励分
3. 用 **PPO** 等 RL 算法，让 LLM 生成高奖励的输出

**ChatGPT 就是这么训的**。

**和 DPO 的关系**：DPO 论文的核心贡献就是证明——你不需要显式训 RM 和跑 PPO，直接优化偏好对也能达到近似效果。

**为什么现在大家不太用 RLHF**：
- 训练 pipeline 复杂（要维护 4 个模型：policy、reference、RM、value）
- PPO 不稳定，超参敏感
- DPO/ORPO/SimPO 等"轻量替代"在大多数场景表现不输

**什么时候仍然需要 RLHF/RL**：
- 需要优化**多步策略**而不只是单轮输出
- 有在线交互能产生新样本（不是静态偏好对）
- 需要从稀疏/长期奖励中学习

### 1.7 RLAIF（RL from AI Feedback）

**是什么**：用更强的 LLM（如 Claude、GPT-4）代替人类打分，生成奖励信号或偏好对。

**好处**：省标注成本。

**坏处**：
- Judge 模型的偏好不等于业务方的偏好
- 容易把 judge 的 bias 放大到学生模型里

**本项目定位**：我们在阶段 1 会用 Claude 做 LLM-as-Judge 做自动指标，但**最终决策还是要人工**。

### 1.8 GRPO（Group Relative Policy Optimization）

**是什么**：DeepSeek R1 用的 RL 算法。不需要 value model，对一个 prompt 采样 K 个输出，相对排序计算 advantage。

**为什么最近火**：DeepSeek R1 证明了 GRPO 能学出"长推理"能力。

**本项目阶段**：**暂缓**。我们的业务不是推理类，是 agent + 工具使用，GRPO 没有直接优势。

### 1.9 KTO（Kahneman-Tversky Optimization）

**是什么**：不需要成对偏好，只需要"这个输出好 / 不好"的二元标签。

**好处**：数据收集更容易（不用成对比）。

**坏处**：生态不如 DPO 成熟。

### 1.10 SimPO（Simple Preference Optimization）

**是什么**：不需要参考模型的 DPO 简化版，通过长度归一化规避 DPO 的长度偏差。

**坏处**：发布晚，实战验证少。

---

## Part 2：为什么是 SFT → DPO → (RL 暂缓)

### 2.1 决策树

```
                    benchmark 显示小模型表现如何？
                                │
           ┌────────────────────┼─────────────────────┐
           ▼                    ▼                     ▼
      离 Claude 很远        能做大部分            基本能做
      （<50%）             但不稳（50-80%）       但业务方觉得一般
           │                    │                     │
           ▼                    ▼                     ▼
     先问：是否这个        优先 SFT            优先 DPO/ORPO
     模型根本不够格？      学格式 + 流程        学偏好 + 风格
           │
           ▼
     换更大的基座           若 SFT 后还有 gap
                            → 继续 DPO
```

### 2.2 为什么不跳过 SFT 直接 DPO？

DPO 的训练目标是"在参考模型基础上让 chosen 比 rejected 概率更高"。如果参考模型本身就做不对（没经过 SFT），DPO 只会把"错得好看"放大。

**DPO ≈ 风格/偏好调优，不是能力训练。能力必须先 SFT 打底。**

### 2.3 为什么 RL 暂缓？

需求文档第 4.4 节给了非常清晰的答案。我直接把它翻译成问题清单——**下面每一个答不上来，RL 就不该上**：

- [ ] 能否 100% 自动判断一次 agent 执行的 reward？（不能的话就是需要人标，RL 成本爆炸）
- [ ] 当前 benchmark 能否反映真实业务效果？（评估体系不稳，RL 就是刷指标）
- [ ] environment 是否稳定？（agent 接的工具还在频繁改，一改策略就失效）
- [ ] reward 函数能否抗 hack？（稀疏奖励下模型会找漏洞）
- [ ] 需要优化的是多步决策而不只是输出质量？

当前答案全是否，**所以 RL 不值得投入**。

### 2.4 还有哪些技术可以考虑？

| 技术 | 什么时候考虑 | 本项目评估 |
|---|---|---|
| **Prompt Engineering** | DP1 结论是"差距不大" | 推荐先试，可能不用训练 |
| **Few-shot / In-context** | 类似上 | 可和 prompt 组合 |
| **Distillation（logits 蒸馏）** | 能拿到 Claude 内部 logits | ❌ Claude API 不给 logits |
| **Distillation（输出蒸馏 = SFT）** | 有教师模型输出 | ✅ 我们本质上在做这个 |
| **LoRA SFT** | 微调首选 | ✅ 主线 |
| **QLoRA** | 显存紧 | ✅ 9B 起推荐 |
| **全参微调** | 有大算力 + 大数据 | ❌ 成本高，效益不显著 |
| **DPO** | SFT 后偏好对齐 | ✅ 阶段 3 |
| **ORPO** | 想一步到位 | ⚠️ 备选，不如 DPO 稳 |
| **SimPO** | 想省 reference model | ⚠️ 观望 |
| **KTO** | 只有二元标签 | ⚠️ 备选 |
| **RLHF (PPO)** | 需要 online policy | ❌ 成本太高 |
| **GRPO** | 需要多步推理 | ❌ 不匹配业务 |
| **Constitutional AI** | 需要自我批判 | ❌ 不匹配业务 |
| **约束解码（outlines/xgrammar）** | JSON 格式必须 100% 有效 | ✅ 推理时加，和训练互补 |
| **Router + Fallback** | 多模型协作 | ✅ 阶段 4 必做 |

### 2.5 推理时的补充技术（和训练互补）

训练只能让模型"更倾向"做对，但不能保证一定做对。推理时可以加：

1. **约束解码**（outlines / xgrammar）：强制输出符合 JSON schema / 正则
2. **Self-consistency**：采样 K 次投票
3. **Reflection**：让模型检查自己的输出，错了重来
4. **Tool result verification**：工具返回后检查格式才继续

这些**不需要训练**，可以大幅提升稳定性，是 ROI 很高的"低垂果实"。

---

## Part 3：三条路径对比表

| 维度 | Prompt | SFT + LoRA | SFT → DPO | SFT → RLHF/RL |
|---|---|---|---|---|
| 时间成本 | 1 天 | 1-2 周 | 3-4 周 | 2-3 月 |
| 算力成本 | 0 | 1 卡几天 | 1-2 卡几周 | 多卡几月 |
| 数据需求 | 0 | 1k-10k 样本 | 1k-5k 偏好对 | 持续在线样本 |
| 能改变什么 | 格式、风格 | 格式、流程、新能力 | 偏好、风格、细粒度 | 多步策略、长期奖励 |
| 风险 | 低 | 中（过拟合） | 中高（reward hack） | 高（训崩、成本失控） |
| 需要的团队能力 | 会写 prompt | 会跑 HF 脚本 | 懂 DPO 超参 | 懂 RL + 大规模训练 |

## Part 4：给初学者的建议阅读顺序

1. 先看 1.1-1.3 理解我们手头有什么数据、SFT 在做什么
2. 看 2.1 决策树，对齐路线
3. 回到 `implementation_plan.md` 看具体阶段
4. 碰到某个名词忘了，回来查 Part 1

读完这份文档 + `core_principles.md`，你对这个项目的"为什么"就有 80% 的把握了。
