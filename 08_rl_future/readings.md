# RL 前置调研（暂缓阶段阅读）

> 本项目当前**不启动 RL**。本文档的作用：建立认知、留后手，满足 DP5 触发时能快速启动。

> 为什么不启动：参考 `00_overview/concepts_and_techniques.md` §2.3 和 `06_decisions/DP5_rl_evaluation.md` 的五个必要条件。

## 学习路径（3 个月，按顺序）

### Month 1：RL 基础
1. David Silver 的 RL 课程（2015，UCL）
   - 🎥 [YouTube 播放列表](https://www.youtube.com/watch?v=2pWv7GOvuf0)
   - 📝 [讲义 PDF](https://www.davidsilver.uk/teaching/)
   - 先看前 5 讲就够了
2. Sutton & Barto 《Reinforcement Learning: An Introduction》第 2 版（免费）
   - 📄 [官网](http://incompleteideas.net/book/the-book.html)
   - 重点第 3、4、6、8、13 章

### Month 2：Policy Gradient / PPO
1. Spinning Up in Deep RL（OpenAI）
   - 📄 [spinningup.openai.com](https://spinningup.openai.com/)
   - 看 Policy Gradient 和 PPO 部分
2. PPO 论文精读
   - 📄 [Schulman et al., 2017](https://arxiv.org/abs/1707.06347)
3. PPO 37 个实现细节
   - 📝 [ICLR 2022 blog](https://iclr-blog-track.github.io/2022/03/25/ppo-implementation-details/) 🔴 **必读**
4. 实现一个 cartpole PPO（1 天）

### Month 3：LLM RL
1. InstructGPT 论文
   - 📄 [Ouyang et al., 2022](https://arxiv.org/abs/2203.02155)
2. HuggingFace RLHF 博客
   - 📝 [Illustrating RLHF](https://huggingface.co/blog/rlhf)
3. DeepSeek-R1 论文 + GRPO
   - 📄 [DeepSeek-R1](https://arxiv.org/abs/2501.12948)
   - 💻 [open-r1](https://github.com/huggingface/open-r1)
4. TRL PPO 示例
   - 💻 [trl/examples](https://github.com/huggingface/trl/tree/main/examples)

## 五个必要条件深度解读

### 1. Benchmark 体系稳定
**解释**：RL 训练几百上千 step，每 step 要评估模型表现。如果 benchmark 本身都不稳，每次评估抖动大，训练信号就被噪声淹没。

**怎么判断稳定**：
- 同一模型跑 3 次 benchmark，指标方差 < 5%
- 过去 3 个月 benchmark 集没大改
- 每条 case 的 reward 多次计算结果一致

### 2. 人工评分映射稳定
**解释**：RL 最终要让模型"对齐业务偏好"。业务偏好如果每月变、业务方内部分歧大，RL 就是在追一个移动靶。

**怎么判断**：
- 2 个标注人 Cohen's κ ≥ 0.7
- 业务判据文档稳定，过去 3 个月没大改
- 有 200 条"黄金标注"已经共识

### 3. 明确的 Environment
**解释**：RL 需要模型和环境交互（收到 observation → 给出 action → 得到 reward）。对 agent 任务，environment = 工具 + 数据 + 用户反馈模拟。

**要求**：
- 工具接口稳定（不能 weekly 改）
- 能完整复现一次 agent 执行（deterministic replay）
- 有 mock / sandbox 环境（不能动线上）

### 4. 明确的 Reward
**这是最难的**。候选：

| reward 类型 | 优 | 劣 |
|---|---|---|
| 规则基（如 JSON 有效 + 工具 F1） | 客观、快 | 不够细，容易 hack |
| LLM-as-Judge | 能细 | Judge bias，成本高 |
| 业务指标（用户采纳） | 真实 | 延迟反馈、稀疏 |
| 组合 | 折中 | 调权重是门玄学 |

**reward hacking**：模型会找 reward 函数的漏洞。比如 reward = JSON 有效率，模型学会输出 `{}` 拿满分。

### 5. 多步策略问题
**解释**：如果 bad case 主要是"格式错"或"工具选错"，SFT/DPO 更好（因为有明确的监督信号）。RL 的优势在**长链路决策**——当且仅当"这一步该做什么依赖之前几步做了什么"。

**判断**：
- 看 bad case 分类：F01-F05（单步问题）占比高 → 不用 RL
- F09（死循环）、跨节点问题多 → RL 有帮助

## 如果未来要启动 RL，建议路线

### Step 1：POC（2 周）
- 挑 50 条 bad case
- 用 TRL 的 PPOTrainer 在 SFT 基础上微调
- 看能否提升 bad case 成功率

### Step 2：Reward 设计（4 周）
- 多套 reward 组合（rule + judge + business）
- 做 reward 消融实验
- 对抗测试：找 reward hacking 空间

### Step 3：小规模训练（4 周）
- 用 trl 的 PPO 或 GRPO
- 只训 LoRA
- 每 100 step 跑 benchmark 防漂移

### Step 4：评估 + 决策（2 周）
- 对比 RL vs DPO vs SFT
- 成本/收益分析
- 决定是否规模化

## 技术选型（未来启动时）

| 方案 | 优点 | 缺点 |
|---|---|---|
| TRL PPO | 成熟 | 实现复杂 |
| TRL GRPO（新） | 简化，省 value model | 较新 |
| open-r1 代码 | 参考 DeepSeek | 目标是推理任务，agent 场景要改 |
| veRL / LMFlow / OpenRLHF | 大规模训练友好 | 门槛高 |

## 替代方案（RL 之外）

如果 DP5 判定 RL 条件不满足，可考虑：

1. **更大基座 + SFT**：直接上 14B / 32B 模型
2. **Inference-time 增强**：
   - Self-consistency（采样投票）
   - Reflection（自纠错）
   - Process Reward Model（PRM）
   - MCTS（蒙特卡洛搜索）
3. **Workflow 优化**：
   - 拆子任务（复杂→简单）
   - 加 critic agent 审核
   - 保留关键步骤用 Claude

这些都不需要训练，ROI 通常高于 RL。

## 参考论文清单（按优先级）

1. 🔴 [InstructGPT](https://arxiv.org/abs/2203.02155) - ChatGPT 原始做法
2. 🔴 [DPO](https://arxiv.org/abs/2305.18290) - 为啥不用 PPO 也能做对齐
3. 🔴 [PPO](https://arxiv.org/abs/1707.06347) - RL 基础算法
4. 🔴 [DeepSeek-R1](https://arxiv.org/abs/2501.12948) - GRPO 应用
5. 🔴 [Constitutional AI](https://arxiv.org/abs/2212.08073) - 自我批判 RL
6. 🔴 [WebGPT](https://arxiv.org/abs/2112.09332) - Agent + RL
7. 🔴 [Sparrow](https://arxiv.org/abs/2209.14375) - RL 对齐

## 评估体系 → RL 体系的演化路径

阶段 1-4 建的评估体系，为 RL 做了准备：
1. Benchmark harness → 可 drive reward
2. LLM-as-Judge → 可作 reward model
3. 黄金集 → 固定评估集
4. 人工评估 → 对齐基准

**所以正确的路线是**：先把 SFT/DPO 做扎实，评估体系打磨稳，RL 才是锦上添花。

## 什么时候重新评估 RL？

触发条件（任一）：
- 业务方反馈：小模型在"多步决策"类任务持续不满意（≥ 3 个月）
- 技术上：发现明确的 reward 信号（比如用户采纳率能在 1 小时内反馈）
- 研究上：新的 RL 方法在类似场景被证明有效且便宜

直到这些触发条件成立，**优先资源投 prompt / 数据 / SFT / DPO**。
