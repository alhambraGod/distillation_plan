---
marp: true
theme: default
paginate: true
header: 'L05 · 合规 + V1/V2 隔离'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #7F1D1D; border-bottom: 4px solid #7F1D1D; padding-bottom: 8px; }
  h2 { color: #B91C1C; }
  section.cover { background: linear-gradient(135deg, #7F1D1D 0%, #B91C1C 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #7F1D1D; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 16px; }
  .green { color: #059669; font-weight: bold; }
  .red { color: #DC2626; font-weight: bold; }
  .yellow { color: #D97706; font-weight: bold; }
  .big { font-size: 44px; text-align: center; color: #7F1D1D; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
  .warning { background: #FEE2E2; padding: 12px; border-left: 4px solid #DC2626; }
---

<!-- _class: cover -->

# L05 · 合规 & V1/V2 隔离

## Anthropic ToS + PII + 隔离原则

<br>

📅 **第 5 课 · 60 分钟**
📚 教材：`anthropic_tos_compliance.md` + `compliance_and_safety.md`

---

## 🎯 本课目标

- 理解 Anthropic ToS 对蒸馏的限制
- 掌握三档风险判断
- 掌握 PII 脱敏规则
- 了解 Tool schema 版本管理
- **动手**：脱敏脚本运行 + ToS 风险自评

---

## 🚨 第一件事：Anthropic ToS

<div class="warning">

**❓ 核心问题：我们用 Claude 输出训小模型，合法吗？**

答案：**看场景**，三档风险。**必须 Legal 书面确认**。

</div>

<br>

不重视这个 → 项目做完被告 → 白干

---

## 📊 三档风险

| 档 | 场景 | 判断 |
|---|---|---|
| 🟢 低 | 企业 API + 内部使用 + 不对外卖 | 多数 ToS 允许 |
| 🟡 中 | 模型嵌入销售产品 / SaaS 订阅 | Case-by-case |
| 🔴 高 | 宣传 Claude 替代 / 开源模型注明数据源 | 大概率违反 |

<br>

<div class="highlight">
我们项目自评：🟢 <strong>低风险</strong>（内部用），但必须 Legal 书面背书
</div>

---

## ✅ Legal Review 流程

第 1 周必须做：

1. 把 `anthropic_tos_compliance.md` 给 Legal
2. 提供：
   - API 合同版本
   - 使用场景说明
   - 部署方式
3. 问明确：
   - 当前 ToS 原文
   - 是否触发禁止条款
   - 是否需签补充协议

---

## 🔄 如 Legal 判高风险：替代方案

**项目不会死**，有 3 个替代：

| 方案 | 做法 | 代价 |
|---|---|---|
| A | 换开源教师 Qwen 2.5 72B | 多花 3-4 周，质量略降 |
| B | 直接用 R1-Distill-Qwen-7B | 最快，但能力稍弱 |
| C | 不训练，Prompt 工程路线 | 成本降不到目标 |

<br>

<div class="highlight">
参考 `teacher_model_comparison.md` 和 `finetune_vs_distill.md`
</div>

---

## 🔐 PII 脱敏（所有数据共通）

**必须脱敏的 8 种**：

- 邮箱、手机号（含国际）、身份证、信用卡号
- OpenAI key（sk-*）、GitHub token（ghp_*、ghs_* 等）
- Anthropic key（sk-ant-*）、其他 token

<br>

**规则**：脱敏**前置**到 `clean.py`，进训练集前必须完成。

---

## 🧰 Presidio 作二次兜底

正则能漏，用微软 Presidio 做第二道关：

```python
from presidio_analyzer import AnalyzerEngine
analyzer = AnalyzerEngine()
results = analyzer.analyze(text=content, language="zh")
# 会识别姓名、地址等靠正则难捕获的 PII
```

**本项目**：正则 + Presidio 双层。

---

## 🏗️ V1 / V2 隔离

<div class="big">
V1 ≠ V2<br>
物理隔离
</div>

<br>

**为什么**：
- schema 不同（V1 多节点 / V2 单循环 agent）
- 业务不同
- benchmark 不可比

**做法**：
- 独立目录 / 独立 config / 独立 dashboard
- 两份 eval_spec.md
- 报告不做"平均"

---

## 🔧 Tool Schema 版本管理

**风险**：业务方改了 `search` 工具参数签名 → 小模型还用旧格式 → 线上错误率飙

**对策**：
1. 工具 schema 在 DB 里**带版本号**
2. 训练时记录 schema hash
3. Adapter 和 schema 绑定
4. 上线前 `schema_diff` 自动检查

---

## 📦 其他合规清单

- **数据来源链路**：每条样本记录 Claude 版本 + API 时间戳
- **保留撤回能力**：Anthropic 要求撤回时能快速定位
- **季度 re-review**：ToS 每 3 月重审
- **避免公开声明**：对外只说 "LangSmith 历史数据"
- **模型 Card**：每版 adapter 写 card

---

## 🏋️ 实操（课堂 15 分钟）

**任务 1**：脱敏脚本跑通
```bash
python 01_data_pipeline/code/clean.py \
  --in data/raw/demo.parquet \
  --out data/processed/demo_clean.parquet \
  --report data/processed/report.json
cat data/processed/report.json
# 看 pii_hits 字段
```

**任务 2**：ToS 自评
填 `anthropic_tos_compliance.md` §4 的表：
- 我们用企业版吗？
- 内部使用吗？
- 对外卖吗？

---

## ⚠️ 常见误区

1. "Legal 慢，我们先训了再说" → 违规风险大
2. "用 Claude trace 不训，只做 benchmark 安全" → benchmark 用 Claude 输出也要审
3. "合规是 Legal 的事，工程师不管" → 最后锅都是你的
4. "PII 脱敏日志跑跑就行" → 必须 100% 覆盖训练集和 benchmark

---

## 🏠 课后作业

1. 读 `anthropic_tos_compliance.md` 全文
2. 和 Legal 约一次 15 分钟会议，提出三个问题
3. 整理你们业务的 Tool schema 清单（当前版本）

<br>

**下节课**：L06 学生基座 Pilot

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: Legal 迟迟不回怎么办？→ A: 用开源教师先跑 pipeline，不阻塞
- Q: 我们已经在用 Claude trace 训练了怎么办？→ A: 立刻停，做 Legal review
- Q: 脱敏会影响效果吗？→ A: 影响小但有，trade-off 值得
