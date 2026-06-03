from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class PreviewDataEvent:
    data: dict[str, Any]
    force: bool = False


@dataclass(frozen=True)
class FinalDataEvent:
    data: list[dict[str, Any]]


@dataclass(frozen=True)
class ProgressEvent:
    value: int
    remaining_time: str


@dataclass(frozen=True)
class LogEvent:
    type: Literal["debug", "info", "warning", "error"]
    message: str
