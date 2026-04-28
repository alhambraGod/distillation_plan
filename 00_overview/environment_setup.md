# 环境搭建完整指南

> 0 基础能照抄跑完。  
> 目标：能在本机加载 2B 模型并做一次推理。

## 1. 硬件 / OS 检查

```bash
# Linux / WSL2（Windows 推荐用 WSL2）/ macOS 都行。生产环境强烈推荐 Ubuntu 22.04。

# 查 GPU（有 NVIDIA 显卡）
nvidia-smi
# 输出应包括：Driver Version、CUDA Version、GPU 型号和显存

# 查磁盘（至少 100 GB 可用）
df -h

# 查内存（建议 ≥ 32 GB）
free -h
```

没 GPU 也能学概念，但跑训练建议租云 GPU（见 `07_budget/compute_estimate.md`）。

## 2. CUDA / Driver

训练需要 CUDA 12.1+ 和对应 driver。

```bash
# 查当前 CUDA 版本
nvcc --version
# 或看 driver 报告的版本
nvidia-smi | grep "CUDA Version"
```

如果没安装，参考 [NVIDIA CUDA Toolkit 官方文档](https://developer.nvidia.com/cuda-downloads)。

## 3. Python 环境

**强烈推荐 miniforge / mamba**（比 anaconda 轻，速度快）：
```bash
# 装 miniforge（替代 conda）
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
source ~/.bashrc

# 建环境
mamba create -n distill python=3.11 -y
mamba activate distill
```

## 4. 核心依赖（分层安装）

### 4.1 PyTorch（必须最先装，对应你的 CUDA 版本）
```bash
# CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# CPU-only（开发用）
pip install torch torchvision torchaudio
```

### 4.2 HuggingFace 全家桶
```bash
pip install "transformers>=4.44.0" "datasets>=2.20.0" "accelerate>=0.33.0" "peft>=0.12.0" "trl>=0.11.0" "bitsandbytes>=0.43.0"
```

### 4.3 评估 / 训练辅助
```bash
pip install wandb einops sentencepiece protobuf jsonschema
pip install langsmith anthropic openai  # API 客户端
```

### 4.4 推理（只部署推理机器装）
```bash
pip install "vllm>=0.6.0"
# Flash Attention 2（显著加速训练，装有门槛）
pip install flash-attn --no-build-isolation
```

### 4.5 加速工具（可选）
```bash
pip install unsloth  # LoRA 训练加速 2x
```

## 5. 验证

```bash
# 1. PyTorch 能看到 GPU
python -c "import torch; print('CUDA:', torch.cuda.is_available(), 'GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')"

# 2. 能加载一个小模型
python - <<'PY'
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
t = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
m = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct", torch_dtype=torch.bfloat16).cuda()
inputs = t("你好", return_tensors="pt").to(m.device)
out = m.generate(**inputs, max_new_tokens=30)
print(t.decode(out[0]))
PY

# 3. bitsandbytes 4bit 能用
python -c "import bitsandbytes as bnb; print('bnb ok', bnb.__version__)"
```

三步全过 → 环境 OK。

## 6. 账号与凭证

需要这些环境变量（写进 `~/.bashrc` 或 `.env`）：
```bash
# HuggingFace（下载 gated 模型如 Gemma）
export HF_TOKEN="hf_xxxxxxxxxxxxx"
huggingface-cli login  # 或直接设 HF_TOKEN

# LangSmith
export LANGSMITH_API_KEY="lsv2_xxx"
export LANGSMITH_PROJECT="your-project"

# Anthropic（benchmark + judge）
export ANTHROPIC_API_KEY="sk-ant-xxxxx"

# Weights & Biases
wandb login   # 或 export WANDB_API_KEY=xxx
```

Gemma 模型需要先去 HuggingFace 页面同意 Gemma License。

## 7. 推荐目录结构

```bash
mkdir -p ~/work/small-model-distill
cd ~/work/small-model-distill
git init
mkdir -p data/{raw,processed,datasets} benchmark training/{sft,dpo} inference docs configs adapters
```

## 8. Git / 工具链

```bash
# Git 配置
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"

# pre-commit（可选但推荐）
pip install pre-commit ruff black mypy
```

## 9. IDE / 编辑器

推荐 VS Code + 以下插件：
- Python
- Jupyter
- Pylance
- Ruff
- GitLens
- Remote-SSH（远程开发）

## 10. 远程 GPU 工作流

如果训练机在远程服务器：
```bash
# 本地 SSH 进远程
ssh -L 6006:localhost:6006 user@gpu-server   # 端口转发 tensorboard

# 远程用 tmux 保持训练不断
tmux new -s train
# 启动训练...
# Ctrl-B D 离开，训练继续

# 回来
tmux attach -t train
```

## 11. 常见坑

| 坑 | 解 |
|---|---|
| `CUDA out of memory` 第一次跑就挂 | 换 QLoRA，减 batch，减 seq_len |
| `flash-attn` 装不上 | 先 `pip install wheel` 再 `pip install flash-attn --no-build-isolation` |
| `bitsandbytes` 报 `libcudart.so` 找不到 | 装对应 CUDA 版本，或 export `LD_LIBRARY_PATH` |
| `transformers` 和 `trl` 版本冲突 | 按本文版本号装，锁 requirements |
| HuggingFace 下载慢 | 用镜像：`export HF_ENDPOINT=https://hf-mirror.com` |
| Tokenizer 下载失败 | `trust_remote_code=True` 并确认网络 |

## 12. 最小 requirements.txt

```
torch>=2.3.0
transformers>=4.44.0
datasets>=2.20.0
accelerate>=0.33.0
peft>=0.12.0
trl>=0.11.0
bitsandbytes>=0.43.0
vllm>=0.6.0
wandb
einops
sentencepiece
protobuf
jsonschema
langsmith
anthropic
openai
pandas
pyarrow
pyyaml
```

## 13. 学习里程碑验收

跑完所有环境搭建后，完成以下任务才算通过：

- [ ] `nvidia-smi` 显示你的 GPU
- [ ] PyTorch `torch.cuda.is_available()` 返回 True
- [ ] 能加载并推理 Qwen 0.5B
- [ ] 能加载并推理 Qwen 7B（至少一次，证明大模型能跑）
- [ ] W&B 能登录且看到一个空项目
- [ ] 从 LangSmith 拉到 10 条 trace
- [ ] 从 Anthropic 成功调一次 Claude API

**通过后才能进 Week 1**。
