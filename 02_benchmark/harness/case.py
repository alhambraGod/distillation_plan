"""Benchmark case 与执行轨迹的数据类。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkCase:
    case_id: str
    task_type: str                 # marketing_ai_v1 / v2
    system: str
    skills_loaded: list[str]
    initial_input: dict            # {role: "user", content: "..."}
    expected_status: str           # success / error
    expected_tools: list[str]      # 工具名序列
    expected_tools_strict: bool
    golden_output: str
    source_sample_id: str | None = None

    @classmethod
    def from_jsonl(cls, path: Path) -> list["BenchmarkCase"]:
        cases = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    cases.append(cls(**{k: v for k, v in d.items() if k in cls.__annotations__}))
        return cases


@dataclass
class ToolCall:
    name: str
    arguments: dict | str  # str 表示 parse 失败的原始字符串
    arguments_valid_json: bool = True


@dataclass
class Trace:
    case_id: str
    model: str
    messages: list[dict]           # 完整对话（含 assistant 的 tool_call）
    tool_calls: list[ToolCall]     # 扁平化后的工具调用序列
    final_status: str              # success / error / timeout
    final_output: str              # 最后一条 assistant content
    duration_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tool_calls"] = [asdict(tc) for tc in self.tool_calls]
        return d
