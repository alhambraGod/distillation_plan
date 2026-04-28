---
marp: true
theme: default
paginate: true
header: 'L14 · RL 理论'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #1F2937; border-bottom: 4px solid #1F2937; padding-bottom: 8px; }
  h2 { color: #4B5563; }
  section.cover { background: linear-gradient(135deg, #1F2937 0%, #4B5563 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #1F2937; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  .big { font-size: 44px; text-align: center; color: #1F2937; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L14 · RL 理论

## PPO / GRPO / RLHF / RLAIF / RLVR

<br>

📅 **第 14 课 · 60 分钟**
📚 教材：`methods_deep_dive.md` §4 + `08_rl_future/readings.md`

---

## 🎯 本课目标

- 理解 RL 基本概念（policy / reward / environment）
- 知道 PPO vs GRPO 区别
- 熟悉 LLM RL 的 3 种形式（RLHF / RLAIF / RLVR）
- 理解 RL 为什么难

---

## 🔑 RL 三要素

<div class="big">
Policy + Reward + Environment
</div>

<br>

- **Policy** (π)：模型本身
- **Reward** (R)：反馈信号
- **Environment**：模型交互的世界

在 LLM 中：
- Policy = 你的 LLM
- Reward = 人打分 / 规则 / 另一个 LLM
- Environment = 对话上下文 / 工具调用

---

## 📖 RL 和 SFT/DPO 的本质区别

| 维度 | SFT | DPO | RL |
|---|---|---|---|
| 数据形式 | (x, y) | (x, y_w, y_l) | (x, policy 采样 y, reward) |
| 模型是否参与产生数据 | ❌ | ❌ | ✅ |
| 能否超越教师 | ❌ | ❌ | ✅ |

<br>

**关键**：RL 里**模型自己产输出**，拿 reward 调整。这是它能超越教师的根本原因。

---

## 🧮 经典 PPO 流程

```
1. SFT → 初始 policy π_0
2. 收集人类偏好 → 训奖励模型 RM
3. RL 阶段：
   for batch:
       y = π(x)                    # 模型采样
       r = RM(x, y)                # 奖励打分
       loss_ppo = -clip_ratio · A  # 策略梯度
       + β · KL(π || π_ref)       # 不能偏离太远
```

**4 个模型同时在**：policy / ref / RM / value

---

## 🚨 PPO 的问题

1. **4 个模型** → 显存爆炸
2. **训练不稳**：超参敏感
3. **实现复杂**：37 个已知坑
4. **需要 RM**：RM 有 bias → 传染到 policy

<br>

<div class="highlight">
这就是 DPO 诞生的原因：证明不需要 RM + PPO 也能做对齐
</div>

---

## 🚀 GRPO（DeepSeek R1 用的）

**核心简化**：不要 value model！

```
1. 对同 prompt 采样 G 个输出 {y_1, ..., y_G}
2. 每个 reward r_i
3. group advantage: A_i = (r_i - mean) / std
4. loss = -E[ratio_i · A_i] + β · KL(π || π_ref)
```

<br>

**优点**：
- 3 个模型（policy / ref / 没 value）
- 更稳
- DeepSeek R1 用它 + RLVR 成功

---

## 📚 LLM RL 的 3 种形式

### 形式 1：RLHF（经典）
- Reward = 人类偏好
- 代表：ChatGPT

### 形式 2：RLAIF（AI 当裁判）
- Reward = 另一个强 LLM 打分
- 代表：Anthropic Constitutional AI

### 形式 3：RLVR（Verifiable Reward）
- Reward = 可计算的规则（数学对错、代码跑通）
- 代表：**DeepSeek R1 / OpenAI o1**

---

## 🎯 RLVR 的革命性

DeepSeek R1 证明：**数学 + 代码可验证的 reward** 就能训出强推理能力。

**好处**：
- 不需要人标注
- 不需要 RM
- reward 稳定不会 hack

**启示**：本项目可以找**"可验证"的子任务**做 RLVR POC。

（具体 POC 看 L15）

---

## ⚠️ RL 的四大难

| 难 | 说明 | 缓解 |
|---|---|---|
| **Reward 设计** | 容易被 hack | 多维组合 + benchmark 监控 |
| **Environment** | Agent 要 sandbox | 先选单步任务 |
| **训练稳定** | lr / KL 敏感 | GRPO + lr=1e-6 |
| **成本** | 10-30x SFT | POC 先 500 条 |

---

## 🚨 Reward Hacking 实例

```
Reward = JSON 合法率
模型学会：输出 `{}` → 100% 合法 ✅
真实业务指标：崩
```

```
Reward = 长度
模型学会：重复 "我认为 XXX" 100 次
真实业务指标：崩
```

<br>

**防范**：Reward 必须**多维组合**，而且**每 N step 跑 benchmark**。

---

## 📊 LLM RL 算法全家

| 算法 | 特点 | 成熟度 |
|---|---|---|
| PPO | 经典 RLHF，稳但重 | ⭐⭐⭐⭐⭐ |
| GRPO | 无 value model，DeepSeek R1 用 | ⭐⭐⭐⭐ |
| RLOO | 简化 Reinforce | ⭐⭐⭐ |
| REINFORCE | 最古老最简单 | ⭐⭐⭐⭐ |
| DAPO | GRPO 改进，字节出 | ⭐⭐ |
| SPIN | Self-play | ⭐⭐ |

<br>

**本项目起步用 GRPO**（L15 POC）

---

## 🔬 Reward 的三种信号

| 类型 | 例 | 适合 |
|---|---|---|
| 规则判 | JSON 合法 / schema 匹配 | RLVR |
| LLM Judge | Claude 打分 | RLAIF |
| 业务信号 | 用户采纳率 | RLHF |

<br>

**本项目 3 档落地**（对应这三种，详见 L15）

---

## 🆚 RL 什么时候**不**该用

明确的反模式：
- SFT 都没跑通 → 别 RL
- 没有 eval 体系 → 别 RL
- 业务还在大改 → 别 RL
- 团队没做过 RL → 先看论文 + demo
- 算力紧 → 别 RL
- 想省标注成本 → RL 不省

---

## 🏠 课后作业

1. 读 `methods_deep_dive.md` §4 + `rl_in_current_business.md`
2. 看 Karpathy "State of GPT" 视频的 RL 部分
3. 思考：本项目如果要 RL，reward 怎么定？

<br>

**下节课**：L15 RL 落地 POC

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: DPO 算 RL 吗？→ A: 严格不算，但效果类似
- Q: RL 能超越教师这句话怎么理解？→ A: 教师只提供 reward 信号，探索是模型自己
- Q: PPO 和 GRPO 哪个先学？→ A: 先 GRPO（更新、更简单）
