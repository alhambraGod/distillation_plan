---
marp: true
theme: default
paginate: true
header: 'L02 · SFT / DPO / RL 深度对比'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #1E3A8A; border-bottom: 4px solid #1E3A8A; padding-bottom: 8px; }
  h2 { color: #2563EB; }
  section.cover { background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  section.cover h2 { color: #E0E7FF; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #1E40AF; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 16px; }
  code { background: #F3F4F6; padding: 2px 6px; border-radius: 4px; }
  .big { font-size: 44px; text-align: center; color: #1E3A8A; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L02 · 方法深度对比

## SFT / DPO / RL 怎么选、怎么用、踩什么坑

<br>

📅 **第 2 课 · 60 分钟**
📚 教材：`methods_deep_dive.md`

---

## 🎯 本课目标

- 能用一句话讲清 SFT / DPO / RL 区别
- 掌握选择方法的决策树
- 了解每种方法的主要坑
- **本课结束能填"本项目训练路线图"**

---

## 🔑 先记三句话

<div class="big">
SFT 学分布<br>
DPO 学排序<br>
RL 学策略
</div>

<br>

类比（帮记忆）：
- **SFT** = 背标准答案的学生
- **DPO** = 两份答案选更好的学生
- **RL** = 根据反馈自己试错的学生

---

## 📖 SFT — Supervised Fine-Tuning

**原理**：`(x, y)` 对，训 P(y|x) 最大化

```
loss = -∑ log P(y_t | y_<t, x)    # 交叉熵
```

**适合**：
- 格式不稳（JSON 崩）
- 流程不熟（忘调工具）
- 输出风格统一

**关键超参**：
- lr = 2e-4 (LoRA)，epoch = 1-3
- **必须 loss mask**：只在 assistant 部分算 loss

---

## ⚠️ SFT 的局限

SFT **学不好**的四类问题：

1. 偏好排序（A 和 B 都对，谁更好？）
2. 长 horizon 规划
3. 稀有错误修正
4. 新能力探索

<br>

<div class="highlight">
🎯 这就是为什么需要 DPO / RL 补齐
</div>

---

## 📖 DPO — Direct Preference Optimization

**原理**：偏好对 `(x, y_w, y_l)`，让 y_w 概率更高

```
loss = -log σ(β · [log(π/π_ref)(y_w) - log(π/π_ref)(y_l)])
```

**适合**：SFT 后**技术 OK，风格不对**的场景

**关键**：
- lr = **5e-7**（比 SFT 小 400x！）
- epoch = 1-2（容易过拟合）
- 需要参考模型（SFT adapter）

---

## ⚠️ DPO 三大坑

| 症状 | 原因 | 解决 |
|---|---|---|
| Reward hacking | 模型找漏洞 | 降 lr + 加 beta |
| 长度偏差 | chosen 更长 → 学"越长越好" | 构造偏好对长度匹配 |
| 崩溃 | lr 太大 | lr 5e-7 起步 |

<br>

记住：**DPO 比 SFT 敏感 10 倍**。

---

## 🌟 DPO 的变体

| 变体 | 关键 | 何时用 |
|---|---|---|
| **ORPO** | 不要参考模型，一步 | 显存紧 |
| **SimPO** | 无 ref + 长度归一化 | 长度偏差严重 |
| **KTO** | 不要成对，只要好/坏标签 | 数据收集难 |

<br>

**本项目推荐**：先 DPO，不稳再 SimPO。

---

## 📖 RL — 强化学习

**原理**：模型自己产输出，用 reward 当监督

**三种落地形式**：

1. **RL on Verifiable Rewards**（规则判好坏，如 JSON 合法）
2. **RLAIF**（AI 当裁判）
3. **RLHF**（真实人类 / 业务信号）

<br>

**算法**：PPO（经典）/ GRPO（DeepSeek R1）/ RLOO（简化）

---

## 🧐 RL 为什么"难"

**四大难题**：

- **Reward 设计**：容易被模型 hack
- **Environment**：agent 要 sandbox 交互
- **训练稳定性**：PPO 有 37 个坑
- **成本**：SFT 的 10-30x

<br>

<div class="highlight">
⚠️ 本项目不跳过 RL，但分三档启动（L15 专门讲）
</div>

---

## 🔍 决策树：我该用哪个？

```
有 (x, y) 监督数据？
├─ 有 > 1k 条 → 先 SFT
│   └─ SFT 后风格不对？ → 加 DPO
└─ 没有，但能定义 reward → 考虑 RL
    └─ reward 是可验证规则？ → GRPO POC
```

<br>

**顺序不能乱**：SFT → DPO → (RL)

---

## 📊 方法全景对比

| 维度 | SFT | DPO | PPO | GRPO |
|---|:---:|:---:|:---:|:---:|
| 数据 | (x,y) | (x,yw,yl) | reward | reward |
| 训练稳 | 🟢 | 🟡 | 🔴 | 🟡 |
| 计算成本 | 1x | 2x | 10-30x | 5-15x |
| 超教师能力 | ❌ | ❌ | ✅ | ✅ |
| 本项目 | W5-W7 | W9 | 备选 | W15 POC |

---

## 💡 组合使用最佳实践

```
Step 1: SFT (学格式 / 流程)
  ↓ adapter_sft
Step 2: DPO (对齐偏好)
  ↓ adapter_dpo
Step 3: RL (可选，探索 / 业务信号)
  ↓ adapter_rl
Step 4: 上线 + 线上数据回流
  ↓
Step 5: 用线上数据再 SFT (回 Step 1)
```

**迭代循环**，不是线性一次性。

---

## 🎯 现场练习（10 分钟）

5 个场景，你选哪个方法？

1. agent 经常调错工具 name
2. 多候选都对，但业务方喜欢其中一种
3. JSON 有效率 99%，但被用户弃用率高
4. 想让模型学会"如果发现结果错，主动重新搜"
5. 学员和教师 tokenizer 不同，还想学教师的 logit

（答案：1=SFT / 2=DPO / 3=DPO or RLAIF / 4=RL / 5=不能白盒，只能黑盒 SFT）

---

## 🏠 课后作业

1. 读完 `methods_deep_dive.md`（45 min）
2. 画一张"本项目训练路线图"（含备选）
3. 写 300 字：我们为什么先 SFT 不直接 DPO

<br>

**下节课**：L03 数据 pipeline

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: DPO 能不能没有 SFT 直接做？ → A: 强不推荐，DPO 只会放大错误
- Q: RL 不是最强吗？ → A: 在脆弱的 benchmark 上，SFT 也能比 RL 强
