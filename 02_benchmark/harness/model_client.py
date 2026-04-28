"""统一的模型客户端接口 + 几个常见实现。

真实 agent 逻辑需要接你们的 DeerFlow / V1 agent-service 的运行时；
本文件只给"跑单次对话"的薄封装，作为教学骨架。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Protocol

from .case import BenchmarkCase, ToolCall, Trace


def _parse_arguments(arguments) -> tuple[dict | str, bool]:
    if isinstance(arguments, dict):
        return arguments, True
    if isinstance(arguments, str):
        try:
            return json.loads(arguments), True
        except Exception:
            return arguments, False
    return {}, False


class ModelClient(Protocol):
    name: str
    def run(self, case: BenchmarkCase, tools: list[dict] | None = None, timeout: float = 120.0) -> Trace: ...


# ------------------------------------------------------------
# Claude (Anthropic)
# ------------------------------------------------------------
@dataclass
class ClaudeClient:
    name: str = "claude-3-5-sonnet"
    max_tokens: int = 4096

    def __post_init__(self):
        from anthropic import Anthropic
        self.client = Anthropic()

    def run(self, case: BenchmarkCase, tools: list[dict] | None = None, timeout: float = 120.0) -> Trace:
        start = time.time()
        messages = [case.initial_input]
        all_tool_calls: list[ToolCall] = []
        try:
            # 单轮（非 agent）示例；真实 agent 需要循环直到 stop_reason == end_turn
            resp = self.client.messages.create(
                model=self.name,
                system=case.system or "",
                messages=messages,
                tools=tools or [],
                max_tokens=self.max_tokens,
                timeout=timeout,
            )
            # 提取 tool_use blocks
            final_text_parts = []
            for block in resp.content:
                if block.type == "tool_use":
                    args, valid = _parse_arguments(block.input)
                    all_tool_calls.append(ToolCall(name=block.name, arguments=args, arguments_valid_json=valid))
                elif block.type == "text":
                    final_text_parts.append(block.text)
            status = "success" if resp.stop_reason in ("end_turn", "tool_use") else "error"
            return Trace(
                case_id=case.case_id,
                model=self.name,
                messages=messages + [{"role": "assistant", "content": resp.content}],
                tool_calls=all_tool_calls,
                final_status=status,
                final_output="\n".join(final_text_parts),
                duration_ms=(time.time() - start) * 1000,
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
            )
        except Exception as e:
            return Trace(
                case_id=case.case_id, model=self.name, messages=messages,
                tool_calls=[], final_status="error", final_output="",
                duration_ms=(time.time() - start) * 1000, error_message=str(e),
            )


# ------------------------------------------------------------
# vLLM (OpenAI 兼容接口)
# ------------------------------------------------------------
@dataclass
class OpenAICompatClient:
    """通用 OpenAI 兼容客户端：vLLM、Ollama（开启 OpenAI 兼容 API）、ollama-python、TGI 都可用。"""
    name: str
    base_url: str
    api_key: str = "EMPTY"
    max_tokens: int = 4096

    def __post_init__(self):
        from openai import OpenAI
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def run(self, case: BenchmarkCase, tools: list[dict] | None = None, timeout: float = 120.0) -> Trace:
        start = time.time()
        messages = [{"role": "system", "content": case.system}] if case.system else []
        messages.append(case.initial_input)
        all_tool_calls: list[ToolCall] = []
        try:
            resp = self.client.chat.completions.create(
                model=self.name,
                messages=messages,
                tools=tools,
                max_tokens=self.max_tokens,
                timeout=timeout,
            )
            choice = resp.choices[0]
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    args, valid = _parse_arguments(tc.function.arguments)
                    all_tool_calls.append(ToolCall(name=tc.function.name, arguments=args, arguments_valid_json=valid))
            status = "success" if choice.finish_reason in ("stop", "tool_calls") else "error"
            return Trace(
                case_id=case.case_id,
                model=self.name,
                messages=messages + [choice.message.model_dump()],
                tool_calls=all_tool_calls,
                final_status=status,
                final_output=choice.message.content or "",
                duration_ms=(time.time() - start) * 1000,
                prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
            )
        except Exception as e:
            return Trace(
                case_id=case.case_id, model=self.name, messages=messages,
                tool_calls=[], final_status="error", final_output="",
                duration_ms=(time.time() - start) * 1000, error_message=str(e),
            )


def build_client(name: str) -> ModelClient:
    if name.startswith("claude"):
        return ClaudeClient(name=name)
    if name.startswith("local-"):
        return OpenAICompatClient(
            name=name.replace("local-", ""),
            base_url=os.environ.get("VLLM_URL", "http://localhost:8000/v1"),
        )
    raise ValueError(f"unknown model: {name}")
