# DPO 常见坑 & 排查

## 症状 1：训着训着模型崩了（输出乱码 / 空）

**最常见原因**：learning rate 太大。

**排查**：
- 如果你把 SFT 的 `lr: 2e-4` 直接搬过来，立刻崩
- DPO 正确区间：`5e-7` 到 `5e-6`
- 看 W&B 里 `logits/chosen` 和 `logits/rejected`——剧烈波动说明 lr 过大

**修正**：
```yaml
train:
  lr: 5.0e-7   # 或更小
```

## 症状 2：Reward margin 很高，但 benchmark 分掉了

**术语**：reward hacking。模型学会了"人为拉大 chosen 和 rejected 的差"，但实际输出变差。

**识别**：
- W&B：`rewards/margin` 迅速上升到 10+
- `rewards/accuracies` = 100%
- 但 `eval/loss` 反弹，或下游 benchmark 分数下降

**修正**：
1. 降 lr 再训
2. 降 epoch（训到 0.3-0.5 epoch 就停）
3. 加大 `beta`（0.1 → 0.3）更严格约束
4. 检查偏好数据是否有"偷懒"特征（chosen 都带某个关键词等）

## 症状 3：长度偏差

**现象**：训完模型输出越来越长，但 benchmark 实际分数没提升甚至下降。

**原因**：偏好数据里 chosen 普遍比 rejected 长，模型学到"长 = 好"。

**检查**：
```python
import json
lengths = []
with open("dpo_train.jsonl") as f:
    for line in f:
        d = json.loads(line)
        lengths.append((len(d["chosen"]), len(d["rejected"])))
import numpy as np
diffs = [c - r for c, r in lengths]
print(f"mean diff: {np.mean(diffs)}, std: {np.std(diffs)}")
# 如果 mean diff 很大，就是长度偏差
```

**修正**：
1. 构造偏好对时做**长度匹配采样**：chosen 和 rejected 长度差 < 2x
2. 用 SimPO 替代 DPO（SimPO 原生长度归一化）
3. 后处理惩罚长度

## 症状 4：eval loss 一直在 0.69 不动

**原因**：模型完全没分辨能力（log(2) ≈ 0.693）。可能是：
- 参考模型和训练模型共享参数（配错了）
- 偏好对数据里 chosen/rejected 几乎一样

**修正**：
1. 打印几对样本看是否有区分度
2. 确认 DPOTrainer 的 `ref_model` 配置（本项目传 `None` 时会用 adapter disabled 作 ref，正确）
3. 检查 LoRA 是否真的在更新（看 `trainable params` 日志）

## 症状 5：OOM（DPO 比 SFT 更吃显存）

DPO 需要同时保留：
- Policy model（在训）
- Reference model（冻结）
- 两者的激活值

**解决顺序**：
1. 开 QLoRA
2. 开 `gradient_checkpointing=True`
3. `ref_model=None`（复用 policy 的 adapter disabled 状态，省一半）
4. 减 `max_length` 和 `max_prompt_length`
5. 减 `batch_size`
6. 换更小基座

## 症状 6：训练很慢，GPU util 低

- DPO 天然比 SFT 慢（要跑 2 次 forward：policy + ref）
- 检查 DataLoader 瓶颈（`dataloader_num_workers`）
- 不要开 packing（DPO 不支持）

## 症状 7：ORPO 效果不如 DPO

ORPO 理论上合并 SFT+DPO，但：
- 超参调优经验少
- 偏好数据要同时承担"学能力"+"学偏好"两个角色，数据质量要求更高
- 很多场景下不如 "SFT → DPO" 稳

**建议**：本项目主线走 DPO，ORPO 只作对比实验。

## 症状 8：人工评估不升反降

DPO 训完技术指标好看，但业务方觉得变差。

**排查**：
1. 偏好数据是否真的反映业务偏好？
   - 随机抽 50 对让业务方评价 chosen 和 rejected，看业务方是否同意选择
   - < 70% 同意率说明数据质量有问题
2. Judge 模型是不是偏见大？（LLM-as-Judge 会偏好长/复杂输出）
3. 是否训 overfit 了？回滚到更早的 checkpoint

## 调试 Checklist

- [ ] lr 在 1e-7 到 5e-6 区间？
- [ ] beta 在 0.1-0.5？
- [ ] epoch ≤ 3？
- [ ] 偏好数据通过长度偏差检查？
- [ ] 偏好数据抽样 50 对，业务方同意率 ≥ 80%？
- [ ] SFT adapter 是最佳版本？（别在半成品上叠 DPO）
- [ ] W&B 记录完整？

## 决策

DPO 训完，拿 benchmark + 人工双指标对比 SFT 版本。**任何一个没过**就不上。

- 都过 → 进灰度（DP3 → DP4）
- 技术指标升人工降 → 回滚 SFT 版本，DPO 数据回炉
- 都降 → 回滚，且这一轮 DPO 失败
