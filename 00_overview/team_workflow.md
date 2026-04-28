# 团队协作 & 工作流

> 给团队而不是给个人的指南。能让 2-5 人的 ML 团队协同不踩坑。

## 1. Git 工作流

### 分支策略
```
main          # 线上可复现版本
├── develop   # 集成分支
├── feat/sft-qwen-v3    # 功能开发
├── feat/benchmark-v2
└── fix/oom-issue
```

**规则**：
- 训练 config 改动必须走 PR
- Benchmark spec 改动必须业务 lead 签字
- 数据 pipeline 改动必须带单元测试

### Commit message
```
<type>: <what>

type: feat / fix / data / train / bench / docs
示例：
- train: lower DPO lr to 5e-7 to fix reward hack
- bench: add tool_f1 metric
- data: add PII redaction for github tokens
```

## 2. PR 模板（ML 专用）

放到 `.github/pull_request_template.md`：

```markdown
## 目的

（一句话：这个改动为什么存在）

## 改动类型
- [ ] 数据 pipeline
- [ ] 训练 config / 代码
- [ ] 评估 harness
- [ ] 推理 / 服务
- [ ] 文档

## 影响范围
- [ ] 会导致已有实验不可复现？
- [ ] 会改变已有数据集？
- [ ] 需要重新跑 benchmark？

## 验证

（怎么知道这个改动是对的？贴命令和结果）

## 风险 / 回滚
（如果挂了怎么办？）

## 关联
- 关联任务 / decision 文档：
- W&B run：
- Benchmark report：
```

## 3. Code Review Checklist（ML 项目）

### 数据层
- [ ] 有 PII 脱敏？
- [ ] 清洗规则独立函数，可单测？
- [ ] 数据集版本化？
- [ ] Schema 校验通过？

### 训练层
- [ ] config 用 YAML 管理？
- [ ] W&B run name 规范？
- [ ] 超参不硬编码？
- [ ] random seed 固定？
- [ ] adapter 保存路径包含版本号？

### 评估层
- [ ] 指标实现带单测？
- [ ] 报告引用 spec 版本？
- [ ] 使用黄金集？
- [ ] 分 V1/V2？

### 服务层
- [ ] 有 fallback？
- [ ] 有超时？
- [ ] 有 sanity check？
- [ ] 有日志 / metric？

## 4. 实验命名规范

W&B run name：
```
{stage}_{arch}_v{N}_{model}_{lr}_{r}_{epoch}_{YYYYMMDD}

示例：
sft_v2_v3_qwen7b_lr2e-4_r16_e3_20260501
dpo_v2_v1_qwen7b_beta0.1_lr5e-7_e1_20260601
```

好处：file name / dashboard / 报告互查方便。

## 5. 模型版本化

```
adapters/
├── v2_sft_v1/          # 第一版 SFT
├── v2_sft_v2/          # 数据增强后
├── v2_sft_best -> v2_sft_v5/    # 软链接指向当前最佳
├── v2_dpo_v1/
└── archived/
    └── v2_sft_v3_failed/        # 失败版本保留
```

Config 文件同步版本化：`configs/sft_v2_v3.yaml`。

## 6. 每周节奏

### 周会 30 分钟
- 上周指标（5 min）
- 关键决策（10 min）
- 本周计划（10 min）
- 风险 / 阻塞（5 min）

### 业务方双周会 20 分钟
- 抽检分析
- 需求变化
- 灰度进度

## 7. 事故响应

### P0（服务不可用 / 重大质量问题）

**15 分钟内**：
- 降 fallback / 降灰度
- 发 Slack #incident

**1 小时内**：
- 定位根因或范围
- 决定：修复 or 回滚

**24 小时内**：
- 复盘文档 `incidents/YYYY-MM-DD.md`
- 根因 / 影响 / 修复 / 预防措施

### P1（质量下降）
同上，但 4 小时内决定。

### 事故报告模板

```markdown
# YYYY-MM-DD 小模型 fallback 率飙升

## 影响
- 时间：HH:MM - HH:MM（持续 X 分钟）
- 影响业务：
- 受影响调用数：

## 时间线
- HH:MM 告警触发
- HH:MM 值班工程师介入
- HH:MM 定位原因
- HH:MM 处置（降灰度到 0%）
- HH:MM 恢复

## 根因
（具体是什么出了问题？）

## 修复
（做了什么）

## 后续动作
- [ ] 改进项 1
- [ ] 改进项 2

## 参与人
```

## 8. 知识库

`docs/` 目录是团队的永久记忆：
- `runbook.md`：SOP（怎么发布、怎么回滚）
- `decisions/`：所有 DP 决策文档
- `incidents/`：事故复盘
- `onboarding.md`：新人入职 checklist

## 9. 新人入职 Checklist（1 周内完成）

- [ ] 读完 `README.md` + `00_overview/` 所有文件
- [ ] 按 `environment_setup.md` 搭环境
- [ ] 跑通 `03_sft/train.py --config sft_v2_base.yaml`（用 10 条小数据）
- [ ] 跑通一次 benchmark
- [ ] 读最新 3 份 `06_decisions/` 决策文档
- [ ] 参加一次周会 + 一次业务 review

## 10. 文档更新原则

- **每次决策** → 更新对应 DP 文档
- **每次事故** → 更新 runbook + incidents
- **每次新发现** → 更新 troubleshooting
- **每次架构变动** → 更新 `implementation_plan.md`

**文档不同步代码 = 技术债**。

## 11. 跨团队沟通

### 对业务方
- 不说 "LoRA / DPO"，说"我们训了一版新模型"
- 抽检结果 + 成本节省，用他们关心的语言
- 每两周一次书面同步

### 对 SRE / infra
- 资源申请书面化（GPU / 磁盘 / 监控）
- 上线前提前 2 周对齐
- 异常告警走统一渠道

### 对 legal / compliance
- 训练数据来源和 license 白皮书
- PII 脱敏方法说明
- 模型风险评估

## 12. 代码质量工具

```bash
# ruff：格式化 + linter
ruff format .
ruff check .

# mypy：类型检查
mypy training/ benchmark/

# pytest：单测
pytest tests/ -v
```

放到 pre-commit hook，commit 时自动跑。

## 13. 反模式（别做）

| 做 | 不做 |
|---|---|
| 一次 PR 一个改动 | 一次 PR 改 10 个地方 |
| 超参走 config | 超参写死在代码里 |
| 数据集带版本号 | 数据集原地覆盖 |
| 训练前先跑 benchmark | "训完再看" |
| 失败实验保留 | 失败实验直接删 |
| 文档跟代码一起更 | 文档过时半年才发现 |
