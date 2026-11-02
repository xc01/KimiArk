from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m76_open_reduction_v1/facts/llm_evidence_context.json"
DEFAULT_OUTPUT = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m77_success_condition_facts_v1/llm_evidence_context.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build(source: Path, output: Path) -> None:
    facts = json.loads(source.read_text(encoding="utf-8"))
    source_sha256 = sha256_file(source)

    facts["schema_version"] = "KIMIARK_M77_SUCCESS_CONDITION_FACTS_V1"
    facts["milestone"] = "MAIN_08-07_GPT_M77_SUCCESS_CONDITION_REDUCTION_V1"
    facts["milestone_constraints"] = {
        "counting_rule": "The union of selected_low_star_operator_ids and every DEPLOY action operator_id is counted; retreat and redeploy do not reduce distinct-operator count.",
        "max_unique_deployed_operator_ids": 7
    }
    facts["decision_task"] = {
        "deliverable": "one compact OperationalPlan JSON only",
        "forbidden": "No automatic controller, mechanism rewrite, unverified pre-swing lock, instant redeploy, death refund, or hidden action repair.",
        "must_cover": "the earliest changed success window, all routes, continuous protected passage, artillery closure, #28/#31/#34 contact, and final WIN condition",
        "objective": "design an open-roster complete WIN with at most 7 distinct deployed operator IDs, starting from the M70 success chain without freezing its roster or actions",
        "required_research_product": [
            "compare at least three materially different structures and select exactly one",
            "give a compact success-condition difference table for every material change",
            "project the earliest affected window backward and forward through coupled events",
            "verify artillery, #34, continuous roadblocks, protected passage and late duties before producing actions"
        ],
        "priorities": [
            "identify which M70 success condition each candidate breaks or replaces",
            "model projectile cast, born lock, hit, shared splash and healing windows",
            "treat rotation, continued damage, early kill pressure and role fusion as comparable options",
            "track survival-dependent skill income, retreat refund and redeploy constraints"
        ]
    }
    facts["m77_success_condition_research_v1"] = {
        "baseline": {
            "name": "M70 verified eight-ID WIN",
            "result": "33 kills, 0 leaks, 0 operator deaths, life 3, both protected targets arrived",
            "plan_artifact": "docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/candidate_v1/llm_structured_output.json",
            "event_artifact": "output/r8_1_r8_7_batch_v1/main_08-07/m70_full_roster_reassessment_v1/attempt_01_diagnostic/diagnostic_events.json",
            "operator_ids": [
                "char_123_fang",
                "char_4093_frston",
                "char_283_midn",
                "char_208_melan",
                "char_212_ansel",
                "char_120_hibisc",
                "char_284_spot",
                "char_210_stward"
            ]
        },
        "success_event_windows": {
            "first_artillery_hit": "Shell hit Melantha@1993 for 845; she survived. This is an observation, not proof every later recipient survives the same hit.",
            "second_artillery_lock": "Shell born@2053 locked Melantha's position; she retreated@2054 before impact. No operator hit was recorded after that lock; Spot deployed@2341, not as an instant same-frame replacement.",
            "artillery_closure": "Steward deployed@2071, killed artillery@4273, retreated@4280 with refund, and returned@6381.",
            "late_block_closure": "#34 was actually BLOCKed by Friston@6596 and killed by Steward@7197.",
            "officer_pressure": "Friston blocked #28@5871 and #31@6081; their first recorded injuries were@6438 and@6708 and deaths@6681 and@6886. The blocked-to-injury gaps are research inputs, not removable free time.",
            "spot_fusion": "Spot combined officer blocking/output and late healing; deleting or replacing him requires separate blocking, mixed damage and recovery coverage.",
            "protected_passage": "Both protected targets arrived after continuous roadblock clearance; keep their predecessor roadblock duties in any substitution."
        },
        "counterexample_to_avoid": {
            "m76_candidate_1": "A projectile was already locked@1903; Melantha retreated@1967 and Spot replaced her on the same tile@1968, then took 558 splash@1993. The next shell@2053 locked Ansel's position; Steward deployed@2071 into splash, both took the hit@2143, and the following shell killed Ansel and Steward@2293. Rotation occurred but did not make the tile or adjacent geometry automatically safe.",
            "m72_candidate_1": "Fang died@1209, so her survival-dependent six DP income@1320 did not occur; Ansel's deployment@1381 failed from insufficient DP. Skill income is conditional on survival and continuous deployment."
        },
        "required_comparisons": [
            {
                "direction": "A_CONTINUED_DAMAGE",
                "question": "Can position, healing competition, skills and damage timing make consecutive artillery recipients survive while retaining their other duties?"
            },
            {
                "direction": "B_LOCK_AND_TRANSFER",
                "question": "Can an existing supported retreat/transfer happen after a lock or before the next lock, with release, tile, refill, redeploy and splash costs fully checked?"
            },
            {
                "direction": "C_EARLY_KILL_OR_FUSION",
                "question": "Can earlier real contact, route split, economy or role fusion kill a pressure source or remove a late dependency?"
            }
        ],
        "output_guidance": "Use concise explanation fields already allowed by the operational schema; do not invent a new outer JSON contract. The selected structure must include the success-condition difference table, earliest-window projection and global responsibility check. Unselected structures need only concise conditions, costs and the reason they were not selected."
    }
    facts["prior_execution_interruptions"] = [
        {
            "source": "M76",
            "result": "No M76 WIN; four full simulations were legal battle losses and candidate 3 was static-contract failure.",
            "lesson": "M76 candidate 1 did test early post-lock retreat, but same-tile replacement and later adjacent deployment still entered projectile splash."
        }
    ]
    facts["provenance"] = {
        **facts.get("provenance", {}),
        "m77_source_context": {
            "path": str(source.relative_to(ROOT)),
            "bytes": source.stat().st_size,
            "sha256": source_sha256
        },
        "m77_derivation": "M76 complete catalog, stage and mechanism facts retained; decision task and success-condition research section replaced for M77."
    }
    write_json(output, facts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    build(arguments.source, arguments.output)


if __name__ == "__main__":
    main()
