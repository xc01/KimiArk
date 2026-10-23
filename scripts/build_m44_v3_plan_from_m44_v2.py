from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m44_joint_responsibility_iteration_v1/attempt_02_cli/llm_structured_output.json"
DESTINATION = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m44_joint_responsibility_iteration_v1/attempt_03_cli/llm_structured_output.json"


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    plan = payload["revised_operational_plans"][0]
    for action in plan["action_timeline"]:
        if action["frame"] == 1500 and action["operator_id"] in {"char_4093_frston", "char_281_popka"}:
            action["frame"] = 1440

    plan["operational_plan_id"] = "R8_7_GPT_M44_V3"
    plan["parent_hypothesis_id"] = "R8-7-M44-V3-H1"
    plan["tactical_thesis"] = (
        "Keep M44 V2's Beagle-preserving economy and Popukar lower-outer successor, but move the living handoff "
        "from frame 1500 to 1440. V2 proved that waiting until 1500 misses Friston's frame-1457 ordinary-attack "
        "death, leaving Popukar unable to block the already advanced runner. The 1440 handoff spends the same "
        "DP before that death and does not assume same-frame retreat ordering."
    )

    revision = dict(payload["revision_hypothesis"])
    revision.update({
        "changed_responsibilities": [
            "Move the Friston-to-Popukar handoff from frame 1500 to frame 1440, before the observed frame-1457 death.",
            "Retain all other M44 V2 opening, treatment, artillery and late deployment responsibilities.",
        ],
        "expected_first_observable_event": {
            "earliest_frame": 1440,
            "event_type": "DEPLOY",
            "latest_frame": 1440,
            "source_id": "char_281_popka",
            "target_id": None,
        },
        "hypothesis_id": "R8-7-M44-V3-H1",
        "if_expected_event_absent": (
            "Treat the last M44 simulation as failed. Do not infer that a later handoff can repair an already "
            "advanced runner; inspect Friston vitality, DP, tile release and the first block event."
        ),
        "operational_plan_id": "R8_7_GPT_M44_V3",
        "parent_plan_id": "R8_7_GPT_M44_V2",
        "referenced_experience_ids": ["M44_V2_FRAME_1500_LATE_HANDOFF_FEEDBACK_V1"],
        "tactical_hypothesis": (
            "Deploying Popukar at frame 1440, while Friston is still alive, restores immediate blocking of the "
            "frame-1457 killer and removes the V2 1616 leak without changing the broader strategy."
        ),
    })
    payload["revision_hypothesis"] = revision

    hypotheses = payload["revised_strategic_hypotheses"]
    hypotheses.append({
        "falsifiers": [
            "Friston is absent at frame 1440.",
            "Popukar is unaffordable or the frame-1440 deployment is illegal.",
            "Popukar does not block enemy_1108_uterer#5 before frame 1616.",
            "Artillery or late clearing creates an independent full-stage failure.",
        ],
        "hypothesis": "A 1440 living handoff is early enough to restore lower-outer blocking and remove the V2 1616 leak.",
        "hypothesis_id": "R8-7-M44-V3-H1",
        "revision_basis": "M44 V2 verified the Popukar deployment but showed frame 1500 is after Friston's frame-1457 death.",
    })
    payload["revised_strategic_hypotheses"] = hypotheses

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
