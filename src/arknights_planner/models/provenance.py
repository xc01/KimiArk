from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class KnowledgeStatus(str, Enum):
    """How a value was obtained; UNKNOWN means it must not drive precise simulation."""

    KNOWN = "KNOWN"
    DERIVABLE = "DERIVABLE"
    APPROXIMATED = "APPROXIMATED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ValueWithSource(Generic[T]):
    value: T | None
    status: KnowledgeStatus
    confidence: float
    source_file: str | None = None
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


def known(value: T, source_file: str, source_path: str) -> ValueWithSource[T]:
    return ValueWithSource(value, KnowledgeStatus.KNOWN, 1.0, source_file, source_path)


def unknown() -> ValueWithSource[None]:
    return ValueWithSource(None, KnowledgeStatus.UNKNOWN, 0.0)
