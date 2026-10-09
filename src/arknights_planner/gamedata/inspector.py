from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TableInspection:
    path: str
    exists: bool
    json_kind: str | None
    top_level_keys: tuple[str, ...]
    item_count: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GameDataInspector:
    """Read-only inventory and shape inspection; it makes no semantic field claims."""

    EXPECTED_DIRECTORIES = (
        "zh_CN/gamedata/excel",
        "zh_CN/gamedata/levels",
        "zh_CN/gamedata/battle",
    )
    EXPECTED_TABLES = (
        "character_table.json", "skill_table.json", "range_table.json",
        "enemy_handbook_table.json", "stage_table.json", "battle_equip_table.json",
        "gamedata_const.json",
    )

    def __init__(self, data_root: str | Path):
        self.root = Path(data_root)

    def repository_report(self) -> dict[str, Any]:
        excel = self.root / "zh_CN/gamedata/excel"
        return {
            "root": str(self.root),
            "exists": self.root.is_dir(),
            "directories": {entry: (self.root / entry).is_dir() for entry in self.EXPECTED_DIRECTORIES},
            "expected_tables": {name: (excel / name).is_file() for name in self.EXPECTED_TABLES},
            "json_file_count": sum(1 for _ in self.root.rglob("*.json")) if self.root.is_dir() else 0,
        }

    def inspect_table(self, table: str | Path) -> TableInspection:
        candidate = Path(table)
        path = candidate if candidate.is_absolute() else self.root / "zh_CN/gamedata/excel" / candidate
        if not path.is_file():
            return TableInspection(str(path), False, None, (), None)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return TableInspection(str(path), True, "object", tuple(sorted(payload)[:40]), len(payload))
        if isinstance(payload, list):
            return TableInspection(str(path), True, "array", (), len(payload))
        return TableInspection(str(path), True, type(payload).__name__, (), None)
