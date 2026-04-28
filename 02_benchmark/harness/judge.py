"""LLM-as-Judge。用 Claude 3.5 Sonnet 或 GPT-4o 对输出打分。"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass

from .case import BenchmarkCase, Trace


JUDGE_PROMPT = """你是一个严格的营销内容评估专家。

用户输入：
{user_input}

AI 输出：
{ai_output}

标准参考（可选）：
{golden_output}

评估维度（每项 1-5 分，整数）：
1. 可用性（Usability）：输出是否可直接使用
2. 相关性（Relevance）：是否回应了用户意图
3. 完整性（Completeness）：是否覆盖了必要内容
4. 风格一致性（StyleFit）：语气/格式是否符合营销场景

严格要求：
- 每一项打分必须伴随一句话理由
- 如果有严重问题（事实错/格式崩/无法执行），可用性必须 ≤ 2

只输出 JSON，不加其他说明：
{{"usability": {{"score": N, "reason": "..."}}, "relevance": {{"score": N, "reason": "..."}}, "completeness": {{"score": N, "reason": "..."}}, "style_fit": {{"score": N, "reason": "..."}}}}
"""


@dataclass
class JudgeScore:
    usability: int
    relevance: int
    completeness: int
    style_fit: int
    reasons: dict[str, str]


class LLMJudge:
    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        from anthropic import Anthropic
        self.client = Anthropic()

    def _extract_json(self, text: str) -> dict:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise ValueError("no JSON in judge output")
        return json.loads(m.group(0))

    def score(self, case: BenchmarkCase, trace: Trace) -> JudgeScore:
        user_input = case.initial_input.get("content", "") if isinstance(case.initial_input, dict) else str(case.initial_input)
        prompt = JUDGE_PROMPT.format(
            user_input=user_input[:3000],
            ai_output=trace.final_output[:3000],
            golden_output=case.golden_output[:2000] if case.golden_output else "（无）",
        )
        for attempt in range(3):
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = resp.content[0].text
                data = self._extract_json(text)
                return JudgeScore(
                    usability=int(data["usability"]["score"]),
                    relevance=int(data["relevance"]["score"]),
                    completeness=int(data["completeness"]["score"]),
                    style_fit=int(data["style_fit"]["score"]),
                    reasons={k: v["reason"] for k, v in data.items()},
                )
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")
