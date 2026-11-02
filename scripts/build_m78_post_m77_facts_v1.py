from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m77_success_condition_facts_v1/llm_evidence_context.json"
DEFAULT_OUTPUT = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m78_post_m77_facts_v1/llm_evidence_context.json"


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
    facts["schema_version"] = "KIMIARK_M78_POST_M77_FACTS_V1"
    facts["milestone"] = "MAIN_08-07_GPT_M78_POST_M77_REDUCTION_V1"
    facts["milestone_constraints"] = {
        "counting_rule": "The union of selected_low_star_operator_ids and every DEPLOY action operator_id is counted; retreat and redeploy do not reduce distinct-operator count.",
        "max_unique_deployed_operator_ids": 7
    }
    facts["decision_task"] = {
        "deliverable": "one compact OperationalPlan JSON only",
        "forbidden": "No automatic controller, mechanism rewrite, unverified pre-swing lock, instant redeploy, death refund, or hidden action repair.",
        "must_cover": "the earliest changed success window, all routes, continuous protected passage, artillery closure, #28/#31/#34 contact, and final WIN condition",
        "objective": "design an open-roster complete WIN with at most 7 distinct deployed operator IDs; M77 exhausted five candidate positions without a WIN",
        "required_research_product": [
            "compare at least three materially different structures and select exactly one",
            "state which M70 duty each selected change replaces, when and where",
            "project the earliest affected window through coupled projectile, healing, blocking and protection events",
            "verify artillery, #34, continuous roadblocks, protected passage and late duties before emitting actions"
        ],
        "priorities": [
            "avoid repeating M77's failed A-direction assumptions unchanged",
            "track shared splash, medical target competition and mixed late pressure together",
            "compare substitutions, staged rotations and role fusion without forcing any one option",
            "keep every conditional skill income, retreat refund and redeploy timing explicit"
        ]
    }
    facts["m78_post_m77_research_v1"] = {
        "baseline": {
            "name": "M70 verified eight-ID WIN",
            "result": "33 kills, 0 leaks, 0 operator deaths, life 3, both protected targets arrived",
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
        "m77_compact_results": [
            {
                "candidate": 1,
                "plan_id": "R8_7_GPT_M77_V1",
                "structure": "A_CONTINUOUS_MELANTHA",
                "result": "LOSS 19/14/life-12; 7 operator deaths. Both medics died by3043, artillery survived and later killed protected #3, first scheduled leak #19@4611, and #21@5046 first brought life to0."
            },
            {
                "candidate": 2,
                "plan_id": "R8_7_GPT_M77_V2",
                "structure": None,
                "result": "SERVICE_ROUTING_DISCOVERY_TIMEOUT with no tactical output; not a tactical counterexample."
            },
            {
                "candidate": 3,
                "plan_id": "R8_7_GPT_M77_V3",
                "structure": "A_SPLIT_MEDIC_SPOT_PERMANENT",
                "result": "STATIC_CONTRACT_FAILED_NO_STAGE_SIMULATION; Spot DEPLOY@1231 was 5.9667 DP short, and later Spot skill errors were derived."
            },
            {
                "candidate": 4,
                "plan_id": "R8_7_GPT_M77_V4",
                "structure": "A_SPLIT_MEDIC_PERMANENT_MELANTHA",
                "result": "LOSS 14/19/life-18; 8 death events across 7 unique IDs. Ansel@2111 and Melantha@2261 died before #13@3425; #18@4370 first brought life to0."
            },
            {
                "candidate": 5,
                "plan_id": "R8_7_GPT_M77_V5",
                "structure": "C_CARDIGAN_PERMANENT_FUSION",
                "result": "LOSS 16/17/life-16; 7 death events across 6 unique IDs. Cardigan's early BLOCK occurred, but Friston@1479 died, #7@1821 leaked, and #13@3425 first brought life to0."
            }
        ],
        "unclosed_m77_conditions": [
            "No M77 simulation killed artillery enemy_1112_emppnt#0; it leaked@5759 and killed protected #3 in C1/C4/C5.",
            "No M77 candidate achieved zero leaks, protected-target survival or protected arrival.",
            "M77 did not prove that early retreat/relay is infeasible; C2 had no plan and no tested early relay produced a WIN."
        ],
        "required_comparisons": [
            {
                "direction": "A_REPLACEMENT_OR_FUSION",
                "question": "Can another legal 1-3 star operator or role fusion replace a failed M77 duty while keeping artillery, lower lanes and recovery simultaneously valid?"
            },
            {
                "direction": "B_STAGED_ROTATION",
                "question": "Can supported retreat, refund, redeploy and successor BLOCK cover released enemies and shared splash without assuming pre-swing locks?"
            },
            {
                "direction": "C_ROUTE_OR_BLOCK_SPLIT",
                "question": "Can position or blocking split reduce simultaneous medical and artillery pressure without leaving an upper/lower window open?"
            }
        ],
        "output_guidance": "Use concise explanation fields already allowed by the operational schema. The selected structure must contain the success-condition difference table, earliest-window projection and global responsibility check. Unselected structures need only concise conditions, costs and reason."
    }
    facts["prior_execution_interruptions"] = [
        {
            "source": "M77",
            "result": "Phase closed with no WIN after 3 full simulations, 1 static failure, and 1 no-output service failure.",
            "lesson": "Continuous lower output, split-medic permanent Melantha, and Cardigan fusion each failed before joint late closure."
        }
    ]
    facts["provenance"] = {
        **facts.get("provenance", {}),
        "m78_source_context": {
            "path": str(source.relative_to(ROOT)),
            "bytes": source.stat().st_size,
            "sha256": sha256_file(source)
        },
        "m78_derivation": "M77 complete catalog/stage/mechanism facts retained; M77 causal closeout and M78 open-roster research contract added."
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
