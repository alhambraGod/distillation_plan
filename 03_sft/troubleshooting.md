# SFT 常见坑 & 排查

## 症状 1：loss 一直不下降或维持在 ~0

**最常见原因**：`response_template` 不对，`DataCollatorForCompletionOnlyLM` 把所有 token 都 mask 了。

**排查**：
```python
# 训练前 sanity check
from trl import DataCollatorForCompletionOnlyLM
batch = collator([tokenizer(example["text"]) for example in train_ds.select(range(2))])
# 看 labels 里不是 -100 的位置
labels = batch["labels"]
print((labels != -100).sum())  # 应该 > 0
```

**修正**：
- Qwen：`<|im_start|>assistant`
- Gemma：`<start_of_turn>model`
- 自己打印一个样本的原始 text，确认模板 token 匹配

## 症状 2：eval loss 反弹（过拟合）

**解决**：
1. 减 epoch（3 → 1-2）
2. 增加 dropout（0.05 → 0.1）
3. 减 LoRA r（16 → 8）
4. 混入通用指令数据（20-30%）
5. 样本去重更严（hash 相似度检测）

## 症状 3：OOM（显存不足）

按生效强度排序：
1. 开 QLoRA 4bit（显存减一半）
2. 开 `gradient_checkpointing=True`（显存省 40%，慢 30%）
3. 减 `max_seq_length`（4096 → 2048）
4. 减 `per_device_train_batch_size`，加 `grad_accum`
5. 开 `attn_implementation="flash_attention_2"`（如果支持）
6. 换更小基座（7B → 2B）

## 症状 4：tool_call JSON 输出格式崩

**原因**：训练数据里 tool_call 格式不统一（有的带 id 有的不带，有的 arguments 是 dict 有的是 string）。

**解决**：
1. 重跑 `01_data_pipeline/code/clean.py`，强制规范格式
2. 在格式化时确保 `arguments` 总是 JSON dict
3. 推理时加约束解码（outlines / xgrammar）兜底

## 症状 5：通用能力崩了（灾难性遗忘）

微调后模型不会打招呼、不会写诗，只会业务任务。

**解决**：
- 混入开源通用 SFT 数据（`HuggingFaceH4/ultrachat_200k` 等），占比 20-30%
- 降低 lr 或 epoch
- 用 DoRA / rsLoRA 等改良 LoRA 方法

## 症状 6：模型重复生成 / 死循环

**原因**：
- max_new_tokens 太大 + eos 没学对
- 训练样本里有重复模式（清洗漏了）

**解决**：
- 推理时加 `repetition_penalty=1.1`、`no_repeat_ngram_size=5`
- 重新检查 `response_template` 和 eos_token 对齐
- 检查训练样本是否去重

## 症状 7：训练很慢

**先排除**：
- `gradient_checkpointing=True` 会慢 30%——如果显存够就关
- `packing=False`——completion-only collator 必须关 packing，没办法加速
- DataLoader 瓶颈——看 GPU util，低说明是 CPU 瓶颈，增加 `dataloader_num_workers`

**加速杀手锏**：用 [Unsloth](https://github.com/unslothai/unsloth) 替代 transformers，7B 训练快 2x 显存省一半。

## 症状 8：保存的 adapter 无法加载

**原因**：版本不匹配或路径不对。

**标准加载方式**：
```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-7B-Instruct", torch_dtype="bfloat16", device_map="auto")
model = PeftModel.from_pretrained(base, "/path/to/adapter")
tokenizer = AutoTokenizer.from_pretrained("/path/to/adapter")
```

## 症状 9：W&B 没显示指标

- 确认 `WANDB_API_KEY` 已设置
- 确认 `report_to: wandb`
- 首次用需要 `wandb login`

## 调试 Checklist（训练崩了先照这个走）

- [ ] sanity check：能不能先用 100 条数据跑 10 step？
- [ ] response_template 是否匹配基座的 chat template？
- [ ] collator 输出的 labels 是否有非 -100 token？
- [ ] lr 是否在合理区间（1e-5 到 5e-4）？
- [ ] batch 总 token 数是否过大（>10k 可能 OOM）？
- [ ] 开 eval 但 eval_ds 是否为空？
- [ ] W&B 是否记录？（没记录训完不可复现）

## 如果卡住了

1. 在 `v2_sft_v1` 基础上，**只改一处**再跑，看问题是否复现
2. 发 `03_sft/configs/*.yaml` + 完整 error log 到团队 Slack
3. 如果怀疑是 HF 库问题，先 `pip list | grep -E 'transformers|trl|peft|torch'` 对一下版本
