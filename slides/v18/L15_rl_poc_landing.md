---
marp: true
theme: default
paginate: true
header: 'L15 · RL 在本项目的落地'
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
  .gold { background: #FEF3C7; padding: 12px; border-left: 4px solid #D97706; }
---

<!-- _class: cover -->

# L15 · RL 在本项目落地

## 从"暂缓"到三档落地路线

<br>

📅 **第 15 课 · 60 分钟**
📚 教材：`08_rl_future/rl_in_current_business.md`

---

## 🎯 本课目标

- 消除"RL 暂缓 = RL 不做" 的误解
- 掌握 RL 在本项目的 **三档落地** 路线
- 能写 POC 1 的计划
- **动手**：走读 `train_rl_grpo.py`

---

## 🤔 "RL 暂缓" 的误解

<div class="gold">

原方案：**RL 暂缓，先调研**

客户质疑：**"RL 就真的不适合吗？"**

正确理解：**RL 不是"不做"，是"分档做"**，和 SFT / DPO 并行推进。

</div>

---

## 📊 三档 RL 落地

<br>

| 档 | 形式 | 前置 | 何时 |
|---|---|---|---|
| 🟢 POC 1 | RLVR（可验证奖励） | SFT 跑通 | **现在就能启动** |
| 🟡 POC 2 | RLAIF（AI judge） | SFT + 稳定 judge | 阶段 3 对比 DPO |
| 🔴 规模化 | 业务信号 RL | 线上稳定 + 回流 | 阶段 5 |

<br>

**三档前置条件递增**，不必等到全部满足。

---

## 🟢 POC 1：工具参数 RLVR

**场景**：工具调用参数生成

**Reward**：**规则可验证**
- `search` 工具的参数 name 对？0/1
- arguments 合法 JSON？0/1
- 参数字段命中？0-1 连续分
- 组合 = 最终 reward

<br>

<div class="highlight">
不需要人 / 不需要 judge / 不需要 environment
</div>

---

## 🟢 POC 1 详细做法

```
1. 从 LangSmith 挑 500 条 case
2. 规则化 expected_tool_call
3. Reward 函数 = 参数对错
4. GRPO LoRA 训练（基于 SFT adapter）
5. 对比 SFT vs RL 在 benchmark 上的表现
```

**预期收益**：工具参数错误率**再降 30%+**

**成本**：3-5 天 A100，预算约 $500

---

## 📝 Reward 函数实例

```python
def reward_tool_call_exact(output, expected) -> float:
    # 解析 output 的 <tool_call>
    tc = parse_tool_call(output)
    if not tc:
        return 0.0
    if tc["name"] != expected["name"]:
        return 0.0
    # 比对参数
    a_keys = set(tc["arguments"].keys())
    e_keys = set(expected["arguments"].keys())
    if a_keys != e_keys:
        return 0.3
    match = sum(tc["arguments"][k] == expected["arguments"][k] 
                for k in e_keys)
    return 0.7 * (match / len(e_keys)) + 0.3
```

---

## 🟡 POC 2：RLAIF 对比 DPO

**场景**：文案风格对齐

**做法**：
- 学生采样 K=8 个输出
- Claude 当 judge 打 1-5 分
- GRPO 训练

**目的**：和 DPO 版本**对照**
- RL > DPO → 规模化
- RL = DPO → DPO 就够
- RL < DPO → 不做 RL

---

## 🔴 规模化：业务信号 RL（远期）

**场景**：用真实用户行为当 reward

```
用户点"采纳" → 正 reward
改稿后采纳 → 低正 reward  
弃用 → 负 reward
```

**前置条件**（必须满足）：
- ✅ 小模型已灰度 ≥ 1 个月
- ✅ 用户采纳信号稳定回流
- ✅ Fallback 兜底到位
- ✅ Shadow eval 防 reward hack

---

## 📝 train_rl_grpo.py 核心

```python
def compute_grpo_loss(model, ref_model, prompt, expected,
                     reward_fn, k=8, kl_coef=0.04):
    # 1. 采 K 个输出
    samples = sample_k_generations(model, prompt, k)
    rewards = torch.tensor([reward_fn(s, expected) for s in samples])
    
    # 2. group-relative advantage
    adv = (rewards - rewards.mean()) / rewards.std()
    
    # 3. 每个输出计算 ratio + KL
    for seq, a in zip(samples, adv):
        ratio = (logp_policy - logp_ref).exp()
        loss += -a * ratio + kl_coef * kl
```

---

## ⚙️ GRPO 起步超参

```yaml
base_model: Qwen/Qwen2.5-7B-Instruct
sft_adapter: adapters/v2_sft_best

grpo:
  num_generations: 8     # K
  kl_coef: 0.04
  max_new_tokens: 256

train:
  lr: 1.0e-6             # ⚠️ 比 SFT 小 200x
  max_steps: 500         # POC
```

---

## 📊 POC 1 验收标准

| 指标 | 目标 |
|---|---|
| 工具参数 exact match | +20% over SFT |
| JSON 合法率 | 不降 |
| 总 benchmark 成功率 | 不降（防 reward hacking） |
| 通用能力（MMLU） | 不降 5% |
| 训练稳定性 | 无崩溃 |

<br>

5 项都过 → POC 1 成功，可考虑规模化

---

## 🚨 RL 监控：什么时候停

| 曲线异常 | 立刻停 |
|---|---|
| rewards 飙高但 benchmark 降 | reward hacking |
| KL > 阈值持续 | 偏离参考模型太远 |
| Loss NaN | lr 太大 |
| 输出乱码 / 重复 | 模型崩 |

<br>

<div class="highlight">
每 50 step 跑一次 mini benchmark
</div>

---

## 🏋️ 实操（20 分钟）

走读 `train_rl_grpo.py`：

```bash
cat 03_sft/train_rl_grpo.py
cat 03_sft/configs/grpo_tool_params.yaml
```

讨论：
- Reward 函数还有什么维度可以加？
- 采样 K=8 为什么？K=2 够吗？
- 如果 reward 总是 0，怎么办？

---

## 💡 组合完整路线（建议）

```
W5-W7 SFT (必做)
  ↓
W8-W10 DPO (必做)
  ↓
W11-W12 灰度上线（SFT + DPO 版本）
  ↓
同时：
W15 后开启 POC 1（工具参数 RLVR）
W20 后考虑 POC 2（RLAIF 对比）

远期（稳定 1 月后）：
业务信号 RL 规模化
```

---

## 🏠 课后作业

1. 读 `rl_in_current_business.md` + `08_rl_future/readings.md`
2. 写 POC 1 启动计划 1 页：目标 / 数据 / reward / 预算
3. 思考：我们业务有哪些子任务可以做 RLVR（可验证 reward）？

<br>

**下节课**：L16 推理部署 + Fallback

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: 3 档必须按顺序做吗？→ A: POC 1 可独立，POC 2 要 SFT 先成
- Q: RL 训完要重新 DPO 吗？→ A: 不必，RL 是 DPO 的替代
- Q: POC 失败怎么办？→ A: 总结失败 → 不规模化，不影响主线
