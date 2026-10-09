"""Manual real-world evidence records. They never mutate simulator parameters."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path


class HumanValidationStatus(str, Enum):
    UNTESTED = "UNTESTED"
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class HumanFailureCategory(str, Enum):
    DEPLOY_TOO_EARLY = "DEPLOY_TOO_EARLY"
    DEPLOY_TOO_LATE = "DEPLOY_TOO_LATE"
    SKILL_TOO_EARLY = "SKILL_TOO_EARLY"
    SKILL_TOO_LATE = "SKILL_TOO_LATE"
    RETREAT_TOO_EARLY = "RETREAT_TOO_EARLY"
    RETREAT_TOO_LATE = "RETREAT_TOO_LATE"
    WRONG_FACING = "WRONG_FACING"
    DP_NOT_READY = "DP_NOT_READY"
    OPERATOR_DIED = "OPERATOR_DIED"
    ENEMY_LEAKED = "ENEMY_LEAKED"
    DAMAGE_MISMATCH = "DAMAGE_MISMATCH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class HumanValidationRecord:
    stage_id: str
    timeline_id: str
    simulator_result: str
    operator_count: int
    rarity_sum: int
    validation_status: HumanValidationStatus = HumanValidationStatus.UNTESTED
    tester_note: str | None = None
    observed_failure_frame: int | None = None
    observed_failure_category: HumanFailureCategory | None = None

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        value = asdict(self)
        value["validation_status"] = self.validation_status.value
        value["observed_failure_category"] = self.observed_failure_category.value if self.observed_failure_category else None
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "HumanValidationRecord":
        value = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            **{**value, "validation_status": HumanValidationStatus(value["validation_status"]),
               "observed_failure_category": HumanFailureCategory(value["observed_failure_category"]) if value.get("observed_failure_category") else None},
        )
