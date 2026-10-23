from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m43_joint_responsibility_closure_v1/attempt_03_cli/llm_structured_output.json"
DESTINATION = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m44_joint_responsibility_iteration_v1/attempt_01_cli/llm_structured_output.json"


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    plan = payload["revised_operational_plans"][0]
    actions = plan["action_timeline"]

    for action in actions:
        if action["operator_id"] == "char_281_popka" and action["action_type"] == "ACTIVATE_SKILL":
            action["frame"] -= 240
        if action["operator_id"] == "char_120_hibisc" and action["frame"] == 5460:
            action["frame"] = 5400

    actions.sort(key=lambda item: item["frame"])
    plan["operational_plan_id"] = "R8_7_GPT_M44_V1"
    plan["parent_hypothesis_id"] = "R8-7-M44-V1-H1"
    plan["tactical_thesis"] = (
        "Retain the M43 V3 earlier-healing and living Friston handoff, then move Popukar's two lower-outer "
        "attack windows twelve and forty seconds earlier and return Hibiscus sixty frames before the M43 V3 "
        "final handoff. This changes the remaining premise that the post-handoff hiatus and late lower medical "
        "return are sufficient: the changed plan spends the same legal redeployment window to strengthen lower "
        "clearance and bridge the protected-target and roadblock routes. Artillery handling, dual civilian "
        "protection, four-corridor coverage, retreat economics, and Beagle preservation remain required gates."
    )

    plan["formation_structure"]["medical_handoffs"] = (
        "Ansel leaves the exposed lower medic position at 70 seconds. Popukar receives an earlier lower-outer "
        "attack window and Hibiscus returns at 180 seconds rather than 182, reducing the late lower treatment "
        "gap. The earlier return is still an availability, price and deployment-slot obligation."
    )
    plan["formation_structure"]["artillery_structure"] = (
        "Steward covers the eastern upper flight. Midnight and Lava cover the western return. Actual artillery "
        "hits must sum to lethal damage before exit; neither roadblock damage nor civilian evacuation satisfies "
        "this obligation."
    )
    plan["skill_intents"] = [
        {**item, "intent": (
            "Activate Popukar at 108 seconds, then 168 seconds, rather than waiting for the M43 V3 116/176 "
            "cycle. Each activation still requires actual readiness and pauses Time-SP while active."
        )} if item.get("operator_id") == "char_281_popka" else item
        for item in plan["skill_intents"]
    ]
    plan["mandatory_tactical_invariants"] = [
        {**item, "requirement": (
            "Require remaining_life > 0, zero leaks, exhausted spawns and no active enemies, zero protected-"
            "target deaths, exactly two protected targets safely arrived, and record operator deaths separately."
        )} if item.get("id") == "ACCEPTANCE" else item
        for item in plan["mandatory_tactical_invariants"]
    ]

    revision = dict(payload.get("revision_hypothesis") or {})
    revision.update({
        "changed_responsibilities": [
            "Move both Popukar lower-outer attack windows earlier to improve the lower handoff and officer-wave throughput.",
            "Return Hibiscus at frame 5400 instead of 5460, reducing the late lower medical hiatus while preserving all other M43 V3 corridor ownership.",
            "Reject M42 V3's assumed living 108-second Friston retreat and 1661-safe claim; require M43 V3's living 1590 handoff as the parent gate.",
        ],
        "expected_first_observable_event": {
            "earliest_frame": 3240,
            "event_type": "SKILL_ACTIVATE",
            "latest_frame": 3240,
            "source_id": "char_281_popka",
            "target_id": None,
        },
        "hypothesis_id": "R8-7-M44-V1-H1",
        "if_expected_event_absent": (
            "Treat the changed lower-outer throughput as failed and inspect Popukar readiness, lower blocking, "
            "and the first leak before crediting later Hibiscus acceleration or artillery handling."
        ),
        "operational_plan_id": "R8_7_GPT_M44_V1",
        "parent_plan_id": "R8_7_GPT_M43_V3",
        "referenced_experience_ids": ["M43_SCHEMA_CONTRACT_FEEDBACK_V1"],
        "tactical_hypothesis": (
            "The M43 V3 parent's earlier lower healing should make the Friston handoff live; advancing Popukar's "
            "supported attack cycle and Hibiscus's legal redeployment improves lower clearance and protection "
            "without changing the verified artillery or evacuation obligations."
        ),
    })
    payload["revision_hypothesis"] = revision

    hypotheses = payload.get("revised_strategic_hypotheses") or []
    hypotheses.append({
        "falsifiers": [
            "Friston dies before frame 1590 or the released runner escapes.",
            "Popukar is not ready at frame 3240 or 5040.",
            "Hibiscus cannot legally redeploy at frame 5400 or the lower anchors suffer an independent failure.",
            "Either civilian dies or fails to arrive safely.",
            "Artillery survives its available damage windows.",
        ],
        "hypothesis": "Advance the M43 V3 parent's lower-outer damage and late medical return while retaining its corrected opening, evacuation, artillery and final-formation structure.",
        "hypothesis_id": "R8-7-M44-V1-H1",
        "revision_basis": "M43 V3 remains unexecuted; M42 V3 is not an established interception baseline. The M44 change must be verified against the complete fixed simulation.",
    })
    payload["revised_strategic_hypotheses"] = hypotheses

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
