# ML 基础知识回顾（按需读）

> 面向：转行过来的工程师、没做过训练的初学者。  
> 不是 ML 课程，只串联这个项目会用到的核心概念。  
> 每节留"往哪里深入读"的链接。

## 1. Loss / Gradient / Backward（3 分钟）

训练 = "让 loss 降低"。方法：
```
输入 → 模型前向 → 输出 → 和答案比较算 loss
                                   ↓
                        loss.backward() 算梯度
                                   ↓
                        optimizer.step() 用梯度更新参数
```

LLM 训练 loss 叫 **cross-entropy**：给定前面的 token，预测下一个 token 的概率分布，答案是 ground truth。loss 低 = 预测对的概率高。

深入：[3Blue1Brown 神经网络 1-4 集](https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi)

## 2. Learning Rate（最重要超参）

- 太大：loss 震荡、发散（NaN）
- 太小：收敛慢、卡在局部最小
- 常见值：
  - Full fine-tune：1e-5 到 5e-5
  - LoRA：1e-4 到 5e-4
  - **DPO：5e-7 到 5e-6**（⚠️ 小很多）

### LR Schedule（学习率随时间变）
| 类型 | 用途 |
|---|---|
| Constant | baseline |
| Linear decay | 简单任务 |
| **Cosine** | 主流首选 |
| Warmup + Cosine | 带 3-10% warmup，最稳 |

## 3. Batch Size / Gradient Accumulation

- **per_device_train_batch_size**：单卡单步 batch
- **gradient_accumulation_steps**：累积 N 步梯度再 update
- **效果 batch = 单卡 batch × 卡数 × 累积步数**

显存不够但要大 batch？用 grad_accum：
```yaml
per_device_train_batch_size: 2
gradient_accumulation_steps: 8
# 效果相当于 batch=16 但显存只用 2 的
```

代价：训练速度变慢。

## 4. Mixed Precision（bf16 / fp16）

- **fp32**：32bit 精度，稳，但显存占 2x
- **fp16**：16bit，省显存，但数值稳定性差（可能 NaN）
- **bf16**：16bit 但指数位和 fp32 一样，**训练首选**（A100 / 3090+ 支持）

配置：
```yaml
bf16: true      # 支持的 GPU 开这个
fp16: false     # bf16 不支持才用 fp16
```

## 5. Gradient Checkpointing

- 默认训练：前向保存所有激活值 → 反向传用
- Checkpointing：只保存部分，反向时重算
- 省显存 40-60%，慢 20-30%

**显存不够就开**：
```yaml
gradient_checkpointing: true
```

## 6. 优化器（AdamW、Adafactor、Lion）

| 优化器 | 特点 | 显存 |
|---|---|---|
| **AdamW** | 主流，稳，首选 | 2x 参数显存 |
| Adafactor | 省显存（1x） | 稍慢收敛 |
| Lion | 最近的选择 | 显存比 AdamW 少 |

LoRA 训练显存主要是激活值，优化器影响不大。

## 7. Attention 实现（训练速度关键）

| 实现 | 速度 | 显存 | 兼容 |
|---|---|---|---|
| `eager` | 慢 | 高 | 最稳 |
| `sdpa`（PyTorch 原生） | 中 | 中 | 稳 |
| `flash_attention_2` | **快 2-3x** | **省 50%** | 需要装 flash-attn |

`transformers` 里设：
```python
model = AutoModelForCausalLM.from_pretrained(..., attn_implementation="flash_attention_2")
```

Gemma 2 在某些 flash-attn 版本有 bug，用 `eager` 或 `sdpa` 保险。

## 8. Distributed / 多卡

单机多卡、多机多卡场景：
- **DataParallel (DP)**：过时，不用
- **DDP (DistributedDataParallel)**：标准多卡
- **DeepSpeed ZeRO**：省显存（切参数/梯度/优化器）
- **FSDP（PyTorch 原生）**：类似 ZeRO

HuggingFace `accelerate` 封装了这些，一条命令切换：
```bash
accelerate config  # 交互式配置
accelerate launch train.py ...
```

本项目单卡能跑，不急着上多卡。

## 9. Chat Template / Tokenization

模型不懂"角色"这个概念，只懂 token。Chat template 把 `messages` 转成特殊 token 序列：

Qwen 2.5 例：
```
<|im_start|>system
你是营销助理<|im_end|>
<|im_start|>user
写一句广告<|im_end|>
<|im_start|>assistant
```

Gemma 2 例：
```
<bos><start_of_turn>user
你是营销助理。写一句广告<end_of_turn>
<start_of_turn>model
```

用 `tokenizer.apply_chat_template(messages)` 自动生成。

## 10. Perplexity / Eval Loss

- **Perplexity** = `exp(loss)`，"困惑度"，越低越好
- SFT 训练 eval loss 正常从 1.5-2.0 降到 0.8-1.5
- **太低（< 0.3）**：过拟合信号

## 11. 过拟合信号 & 对策

信号：
- train loss 继续降，eval loss 开始升
- 模型只能做训练分布的任务，其他全崩

对策（按强度）：
1. 减 epoch
2. 加 dropout（0.05 → 0.1）
3. 减 LoRA r
4. 加正则化样本（通用数据混入）
5. Early stop

## 12. 生成（Inference）策略

控制输出多样性的参数：
- **temperature**：0 贪心（最稳），1 默认，>1 更随机
- **top_p**：nucleus sampling，0.9 常用
- **top_k**：截断前 k 个 token
- **repetition_penalty**：1.0 关闭，>1 惩罚重复
- **max_new_tokens**：输出长度上限

生产推荐：`temperature=0.3, top_p=0.9, repetition_penalty=1.1`。

## 13. Tokenizer 坑

- 不同模型 tokenizer **不共享**！训练用 A 的 tokenizer，推理换成 B 就乱码
- 始终和模型同源：`AutoTokenizer.from_pretrained(same_model_name)`
- pad_token 很多基座没有，需要手动设：
```python
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
```

## 14. 深入资料

| 想深入 | 去哪 |
|---|---|
| 神经网络原理 | Karpathy Zero-to-Hero |
| Transformer 底层 | Illustrated Transformer / Annotated Transformer |
| HF 生态 | 官方 NLP Course |
| RL | Spinning Up in Deep RL |
| 论文阅读 | arXiv + PapersWithCode |

参考 `learning_resources.md`。

## 15. 速查卡（贴墙）

```
学习率：LoRA 2e-4 / DPO 5e-7
Schedule：cosine + 3-5% warmup
Batch：单卡 per_device 2-8，grad_accum 凑 16-32 effective
Precision：bf16 > fp16 > fp32
Attention：flash-attn 2 > sdpa > eager
LoRA r：16，alpha=32，dropout=0.05
Epoch：SFT 3，DPO 1
Seq len：4096（超长才上 8k+）
优化器：AdamW
```
