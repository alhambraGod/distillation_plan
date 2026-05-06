# DPO / ORPO 完整指南

> 前置：`00_overview/concepts_and_techniques.md` §1.4 和 §1.5
>
> 与 `04_dpo/build_preferences.py`（偏好对构造）、`04_dpo/troubleshooting.md`（DPO 调优）、`04_dpo/configs/dpo_v2.yaml`（生产配置）配套使用。

## 1. 什么时候进 DPO（DP2 通过）

前置条件：
- [ ] SFT adapter 的**技术指标**（成功率、工具调用 F1、JSON 有效率）已达研发阈值
- [ ] **人工评估**仍有明显 gap，特别是：
  - 多候选都能完成，但业务方偏好其中一个
  - 风格不自然、语气不对
  - 输出冗长或空洞
- [ ] 能构造至少 1000-5000 对**高质量偏好对**

如果 SFT 后技术指标都不行，**不要用 DPO 救**——回去改 SFT 数据或换基座。

## 2. 核心原理简述

> 详细解释看 `concepts_and_techniques.md` §1.4。这里只讲工程要点。

**DPO loss**（简化）：
```
L = -log σ(β * [log(π_θ(y_w|x) / π_ref(y_w|x)) - log(π_θ(y_l|x) / π_ref(y_l|x))])
```
- `π_θ`：正在训的模型
- `π_ref`：参考模型（**冻结**，通常是 SFT 后的模型）
- `y_w` / `y_l`：chosen / rejected
- `β`：温度，0.1-0.5 常见

**直觉**：增加 chosen 的概率、减少 rejected 的概率，但被参考模型"拉住"，不能偏离太远。

## 3. DPO vs ORPO 怎么选

| 情况 | 选 |
|---|---|
| 已有 SFT 模型 + 偏好对数据 | **DPO** |
| 没做过 SFT，想一步到位 | ORPO |
| 显存紧张（放不下参考模型） | ORPO |
| 追求效果稳定、生产落地 | DPO |
| 探索新方法 | ORPO / SimPO |

**本项目推荐**：SFT → DPO。ORPO 作为备选。

## 4. 偏好数据构造

### 4.1 三种来源

#### 来源 A：LangSmith 历史挖掘
同一输入，在 trace 历史里找出两次不同的执行结果，人工判断哪个好。
- 优点：真实分布
- 缺点：数据稀疏，很多 prompt 只出现一次

#### 来源 B：SFT 多次采样 + 打分
```python
# 对每个 prompt 采样 K 次
for _ in range(K):
    outputs.append(sft_model.generate(prompt, temperature=0.8))
# 用 LLM-as-judge 或人工选最优/最差
chosen, rejected = rank_and_pick(outputs)
```
- 优点：想要多少有多少
- 缺点：都来自同一模型，"偏好"可能是 self-bias

#### 来源 C：合规教师 vs SFT
把合规教师输出当 chosen，SFT 输出当 rejected。若教师是 Claude，必须先有 Anthropic 书面许可。
- 优点：立即可得
- 缺点：学到的是"教师风格"，可能丢失业务偏好
- **⚠️ 慎用**

### 4.2 推荐配比

| 来源 | 比例 | 备注 |
|---|---|---|
| A（历史挖掘） | 30% | 真实分布锚点 |
| B（采样排序） | 50% | 主力 |
| C（合规教师 vs SFT） | 20% | 补充，不超过 20% |

### 4.3 数据质量规则

一对偏好对要满足：
- [ ] chosen 和 rejected 基于**同一 prompt**
- [ ] 两者**可区分**（不能几乎一样）
- [ ] chosen **客观上更好**（能说清楚为什么）
- [ ] 长度差别不大（防长度偏差）——建议做长度匹配采样

### 4.4 数据规模建议

- 起步：1000-2000 对
- 理想：3000-5000 对
- 超过 10k 收益递减

质量 > 数量。宁可 1000 对严选，也别 10000 对凑数。

## 5. 训练流程

### 5.1 准备
1. SFT adapter 已训好
2. 偏好对数据在 `datasets/dpo_v2.jsonl`（schema 见 `01_data_pipeline/design.md`）
3. 参考模型路径 = SFT adapter 路径

### 5.2 起步配置要点

**最重要三个超参**：
- `learning_rate: 5e-7`（⚠️ 比 SFT **小 100-1000 倍**）
- `beta: 0.1`（0.1-0.5，越大越"保守"）
- `num_train_epochs: 1`（1-3，多了过拟合）

详见 `configs/dpo_v2.yaml`。

### 5.3 跑训练

```bash
python train_dpo.py --config configs/dpo_v2.yaml
```

看 W&B：
- `rewards/chosen` 上升、`rewards/rejected` 下降（好迹象）
- `rewards/margin` 逐步增大
- `policy loss` 缓慢下降

**警告信号**：
- margin 立刻飙升但 eval 崩 → reward hacking
- loss 波动剧烈 → lr 太大
- chosen/rejected 同向上升 → 参考模型配错

## 6. 评估

DPO 评估重点**不是技术指标**——SFT 已经管了。重点是：
- 人工评估：**人工分应该上升**
- Judge 评估辅助看风格维度
- 通用能力抽查：`gsm8k`、`mmlu` 等基础题不能崩

如果技术指标不降、人工分不升，DPO 这一版就**不该上**。回滚 SFT 版本。

## 7. 常见坑

详见 `troubleshooting.md`。最常见：
1. **lr 太大**：SFT 用 2e-4，DPO 要 5e-7，差 400 倍
2. **Reward hacking**：margin 高但实际输出变差 → 降 lr、加正则
3. **长度偏差**：chosen 普遍比 rejected 长，模型学到"越长越好" → 采样时做长度匹配
4. **参考模型没 freeze**：DPOTrainer 默认会 freeze，检查日志

## 8. ORPO 备选方案

ORPO 不需要参考模型，直接从基座开始训：
```python
from trl import ORPOConfig, ORPOTrainer
# 超参：beta=0.1, lr=8e-6, epoch=3
```

ORPO 的优势是省显存（少一个模型），但生产验证比 DPO 少。作为备选方案。

## 9. 进 DP3 决策

DPO 阶段末：
- 人工分提升 → 进灰度
- 持平 → 回滚到 SFT 版本
- 下降 → 数据 / 超参有问题，回炉

决策文档：`06_decisions/DP3_dpo_value.md`。
