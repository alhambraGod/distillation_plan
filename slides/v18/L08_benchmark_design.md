---
marp: true
theme: default
paginate: true
header: 'L08 · Benchmark 设计'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #7E22CE; border-bottom: 4px solid #7E22CE; padding-bottom: 8px; }
  h2 { color: #9333EA; }
  section.cover { background: linear-gradient(135deg, #7E22CE 0%, #9333EA 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #7E22CE; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  .big { font-size: 44px; text-align: center; color: #7E22CE; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L08 · Benchmark 设计

## 三层指标 + 三组对照 + Rubric 人工评分

<br>

📅 **第 8 课 · 60 分钟**
📚 教材：`eval_spec.md` + `project_critique_and_fixes.md` §3

---

## 🎯 本课目标

- 理解评估 = **唯一真源**
- 掌握三层指标体系
- 学会 Rubric 化人工评分
- **动手**：起草 eval_spec V1

---

## 🚨 问题：没 benchmark 一切都白搭

<div class="big">
"训完我们再看好不好"
→ ❌ 错
</div>

<br>

**先有评估，再有训练**。Benchmark 是：
- DP1 决策的依据
- 每轮训练的验收门
- 灰度上线的守门员

**没 eval_spec 签字，不能开训**。

---

## 📊 三层指标（不只是"成功率"）

| 层 | 指标例 | 用途 |
|---|---|---|
| **结果** | 成功率、工具 F1 | 总表现 |
| **诊断** | 首 token 延迟、JSON 合法率、步骤数、幻觉率 | 定位问题 |
| **业务** | 采纳率、NPS、时延 P95 | 真实价值 |

<br>

<div class="highlight">
原方案只列结果指标 → 修复：加诊断指标
</div>

---

## 📊 诊断指标举例

| 指标 | 判断什么 |
|---|---|
| First Token Latency | 模型"起步"是否够快 |
| JSON 合法率 | 格式学会了吗 |
| Schema 合法率 | 工具 args 符合声明吗 |
| 步骤数分布 | 是否过度冗长或过度早停 |
| 幻觉率 | 编造事实的比例 |
| 指令遵循率 | 按指令走还是漂移 |

---

## 🔬 三组对照（必须有）

| 组 | 角色 | 作用 |
|---|---|---|
| Claude 3.5 Sonnet | 上限 | 目标 |
| Haiku / GPT-4o-mini | 同价位 | 横向 |
| Qwen-base 未训 | 下限 | 训练增益量化 |

<br>

**没有对照 → 说"75% 成功率"是高还是低说不清**。

---

## 📝 Rubric 化人工评分

❌ 错：凭感觉 "好 / 一般 / 差"

✅ 对：**Rubric 行为描述**

```
可用性（Usability）
5: 直接采纳，无需修改
4: 轻微调整（换 1-2 个词）
3: 中等修改（改结构或补 1 段）
2: 重写主要部分
1: 完全不可用
```

<br>

**关键**：有"行为描述"，两个人标才会一致。

---

## 🎯 Cohen's Kappa ≥ 0.7

两个标注人独立标同一批样本：

```python
from sklearn.metrics import cohen_kappa_score
kappa = cohen_kappa_score(a_scores, b_scores)
```

| Kappa | 判定 |
|---|---|
| < 0.4 | 重新对齐 rubric |
| 0.4-0.7 | 分歧样本开会讨论 |
| ≥ 0.7 | 可上线 |

<br>

**< 0.7 时不信任人工评分** → 训练决策就不能看这个数据

---

## 🏗️ eval_spec.md 结构

```markdown
## 1. 适用范围     （V1 / V2 哪一套）
## 2. 评估对象     （一条 agent trace 的结构）
## 3. 评估维度
   3.1 技术维度（自动）
   3.2 业务维度（LLM-as-Judge）
   3.3 业务维度（人工）
   3.4 失败原因分类
## 4. 评估流程
## 5. 阈值         （研发阈值 / 上线阈值）
## 6. V1/V2 隔离规则
## 7. 局限
附录：Rubric 全文 / Judge prompt
```

---

## 🎨 双盲标注

**为什么**：标注人知道哪个是 Claude / 小模型 → 天然偏向。

**做法**：
- 随机 shuffle 两版输出
- 标注人只看输出，不知来源
- 打完分再揭示
- **品牌偏见归零**

---

## 🎯 阈值设计示例

| 指标 | 研发阈值 | 上线阈值 |
|---|---|---|
| 成功率 | ≥ 70% | ≥ 85% |
| Tool F1 | ≥ 0.80 | ≥ 0.90 |
| JSON 有效 | ≥ 0.95 | ≥ 0.99 |
| 人工分 | ≥ 3.5 | ≥ 4.0 |
| P95 时延 | ≤ 30s | ≤ 15s |
| 成本节省 | ≥ 50% | ≥ 60% |

<br>

**业务 lead 签字才生效**。

---

## 🏗️ 三种 Benchmark 集

| 集 | 用途 | 数量 |
|---|---|---|
| **黄金集** | 人工精标，跨版本对比 | 200 |
| **回放集** | 历史 trace 抽样 | 1000 |
| **压测集** | 长输入 / 并发 / 高负载 | 50 |

<br>

<div class="highlight">
黄金集贯穿整个项目，不能随便改
</div>

---

## 🏋️ 实操（20 分钟）

**任务**：起草 eval_spec V1 草稿

给你一张空模板，填：
- 本项目适用范围（V2 marketing）
- 3 个最重要的结果指标
- 2 个诊断指标
- Usability 的 5 级 Rubric
- 你认为的上线阈值

完成后 5 人互相 review。

---

## ⚠️ 常见坑

1. **先训练后想评估** → 训白了
2. **只有成功率没诊断** → 失败了不知道怎么改
3. **没对照组** → 分数解读不了
4. **凭感觉人工打分** → Kappa 只有 0.3
5. **黄金集 10 条就够了** → 不稳定
6. **改 eval_spec 不走 PR** → 评估数字飘

---

## 🏠 课后作业

1. 读完 `eval_spec.md` 全文
2. 把起草的 V1 发给业务 lead review
3. 2 人试标 10 条样本，算 Kappa

<br>

**下节课**：L09 Harness 实操

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: Rubric 太严会不会标注慢？→ A: 慢一倍，值得
- Q: Judge 和人工冲突怎么办？→ A: 以人工为准，Judge 只做筛选
- Q: 对照组的 Haiku 很贵吗？→ A: 一次 benchmark 几十美元，值
