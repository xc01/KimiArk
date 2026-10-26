from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m57_open_roster_structure_v1/facts/llm_evidence_context.json"
TARGET = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m58_user_premise_open_roster_v1/facts/llm_evidence_context.json"


def main() -> None:
    evidence = json.loads(SOURCE.read_text(encoding="utf-8"))
    evidence["user_confirmed_tactical_premise"] = (
        "Enemy attacks have intervals; many attacks point at one object and occupy the attacker during the action. "
        "Operators may bait attacks, absorb key hits, buy replacement/output windows, and may deliberately withdraw "
        "or sacrifice for these effects. This is USER_CONFIRMED_TACTICAL_PREMISE, not new client evidence. Do not "
        "generalize it to all attacks, phases, targets, cooldowns, retreats, landing tiles, or cycles; every tactic "
        "must identify the known or assumed behavior it uses."
    )
    evidence["m58_open_roster_policy"] = {
        "schema_version": "M58_OPEN_ROSTER_STRUCTURE_POLICY_V1",
        "dynamic_evidence_gate": "REVOKED_BY_USER",
        "minimum_structure_candidates": 3,
        "roster_bound": "OPEN_NORMAL_LOW_STAR_CATALOG",
        "max_unique_deployed_operator_ids": 8,
        "death_policy": "EVALUATE_BY_CONTRIBUTION_AND_COST",
        "mechanism_rewrite_policy": "FORBIDDEN",
        "simulation_policy": "AT_MOST_ONE_FIXED_FULL_STAGE_SIMULATION_AFTER_STATIC_PASS",
    }
    evidence["m58_execution_capability_contract"] = {
        "ordinary_attack": "Current model selects the target at ATTACK_STRIKE; it has no reliable pre-swing target lock. A completed attack's cooldown is not reset by changing target.",
        "artillery_ability": "Ability cast starts target selection and cooldown; projectile birth locks the impact point and has its own delayed splash flow.",
        "spot_skill": "EXECUTABLE_APPROXIMATED: initial SP25/SP40, 25 seconds, ATK+45%, 1.3-second healing interval, x-4 nine-cell range, and healing stops attacks; the physical-dodge talent is unsupported.",
        "ansel_talent": "The probabilistic extra-heal talent is unsupported; do not assume double healing.",
        "usage": "These are current executor limits, not arguments against user experience. Separate current-model-checkable baiting from USER_PREMISE_NOT_EXPRESSIBLE pre-swing timing.",
    }
    evidence["m58_budget_policy"] = {
        "real_tactical_cli_process_starts": 1,
        "fixed_full_stage_simulations": 1,
        "count_started": True,
        "retry_or_resume": False,
        "historical_balance_transfer": False,
        "internal_request_count": "UNKNOWN_CLI_INTERNAL",
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
