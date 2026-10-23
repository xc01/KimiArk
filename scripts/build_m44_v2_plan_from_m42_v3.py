from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m42_retreat_redeploy_artillery_window_v1/attempt_04_cli/llm_structured_output.json"
DESTINATION = ROOT / "output/r8_1_r8_7_batch_v1/main_08-07/m44_joint_responsibility_iteration_v1/attempt_02_cli/llm_structured_output.json"


def insert_action(actions: list[dict], action: dict) -> None:
    index = next((index for index, item in enumerate(actions) if item["frame"] >= action["frame"]), len(actions))
    actions.insert(index, action)


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    plan = payload["revised_operational_plans"][0]
    removed = {
        ("RETREAT", "char_122_beagle", 1290),
        ("DEPLOY", "char_500_noirc", 1290),
        ("DEPLOY", "char_212_ansel", 1410),
        ("DEPLOY", "char_120_hibisc", 1890),
        ("RETREAT", "char_123_fang", 2250),
        ("DEPLOY", "char_209_ardign", 2250),
        ("RETREAT", "char_4093_frston", 3240),
        ("ACTIVATE_SKILL", "char_212_ansel", 2160),
        ("ACTIVATE_SKILL", "char_212_ansel", 3960),
        ("ACTIVATE_SKILL", "char_212_ansel", 5760),
    }
    actions = [
        action for action in plan["action_timeline"]
        if (action["action_type"], action["operator_id"], action["frame"]) not in removed
        and not (action["action_type"] == "ACTIVATE_SKILL" and action["operator_id"] == "char_212_ansel")
    ]

    for action in actions:
        if action["operator_id"] == "char_120_hibisc" and action["action_type"] == "ACTIVATE_SKILL":
            action["frame"] += 450
        if action["operator_id"] == "char_208_melan" and action["frame"] == 3240:
            action["tile"] = [6, 5]
            action["direction"] = "RIGHT"

    insert_action(actions, {"action_type": "RETREAT", "frame": 1500, "operator_id": "char_4093_frston"})
    retreat_index = next(index for index, item in enumerate(actions) if item["frame"] == 1500 and item["operator_id"] == "char_4093_frston")
    actions.insert(retreat_index + 1, {
        "action_type": "DEPLOY", "frame": 1500, "operator_id": "char_281_popka",
        "tile": [6, 3], "direction": "LEFT",
        "rationale": "Replace the surviving Friston before the frame-1513 artillery impact and preserve two-block interception.",
    })
    insert_action(actions, {
        "action_type": "DEPLOY", "frame": 1860, "operator_id": "char_212_ansel",
        "tile": [5, 5], "direction": "LEFT",
        "rationale": "Restore professional treatment after Popukar is established and Gallus has vacated a slot.",
    })
    insert_action(actions, {"action_type": "RETREAT", "frame": 2100, "operator_id": "char_212_ansel"})
    insert_action(actions, {
        "action_type": "DEPLOY", "frame": 2340, "operator_id": "char_120_hibisc",
        "tile": [2, 3], "direction": "RIGHT",
        "rationale": "Reopen upper treatment after Ansel leaves the lower/central exposure.",
    })
    insert_action(actions, {"action_type": "RETREAT", "frame": 3240, "operator_id": "char_285_medic2"})

    actions.sort(key=lambda item: item["frame"])
    plan["action_timeline"] = actions
    if "char_281_popka" not in plan["selected_low_star_operator_ids"]:
        plan["selected_low_star_operator_ids"].append("char_281_popka")
    declarations = plan["deployment_positions_and_directions"]
    declarations = [item for item in declarations if item["operator_id"] not in {"char_500_noirc", "char_209_ardign"}]
    declarations.append({
        "direction": "LEFT",
        "operator_id": "char_281_popka",
        "role": "Living frame-1500 lower outer successor; two-block interception and western lower roadblock attacks.",
        "tile": [6, 3],
    })
    for item in declarations:
        if item["operator_id"] == "char_208_melan":
            item["tile"] = [6, 5]
            item["direction"] = "RIGHT"
            item["role"] = "Eastern lower roadblock clearance and later lower outer damage support."
    plan["deployment_positions_and_directions"] = declarations
    plan["operational_plan_id"] = "R8_7_GPT_M44_V2"
    plan["parent_hypothesis_id"] = "R8-7-M44-V2-H1"
    plan["tactical_thesis"] = (
        "Use M42 V3's supported opening economy but refuse its frame-1661 interception failure: keep Beagle, "
        "withdraw Friston one action before the observed frame-1513 artillery impact, and place Popukar on the "
        "same tile before the first leak. Restore Ansel at 62 seconds, withdraw her at 70 seconds, and resume "
        "Hibiscus treatment at 78 seconds. Keep Fang's income, replace the M42 lower-outer successor with "
        "Popukar, move Melantha to the vacated eastern lower roadblock tile, and remove unavailable late Ansel "
        "cycles. The plan does not assume M42 V3 established a safe window or all Steward attacks."
    )

    revision = dict(payload.get("revision_hypothesis") or {})
    revision.update({
        "changed_responsibilities": [
            "Preserve Beagle rather than trading her for Noirc, retaining the strongest three-block lower anchor.",
            "Withdraw Friston at frame 1500 and deploy Popukar on the same tile, replacing the failed frame-1661 handoff.",
            "Use Ansel only for the bounded 1860-2100 treatment bridge and resume Hibiscus at 2340.",
            "Keep Fang instead of exchanging her for Ardign, preserving reliable income and upper central interception.",
            "Move Melantha to [6,5] after Confes retreats and remove unavailable Ansel cycles.",
        ],
        "expected_first_observable_event": {
            "earliest_frame": 1500,
            "event_type": "DEPLOY",
            "latest_frame": 1500,
            "source_id": "char_281_popka",
            "target_id": None,
        },
        "hypothesis_id": "R8-7-M44-V2-H1",
        "if_expected_event_absent": (
            "Treat the early interception repair as failed. Inspect Friston's frame-1500 vitality, Popukar DP, "
            "tile release, and the first enemy advance before crediting later artillery or protected-target work."
        ),
        "operational_plan_id": "R8_7_GPT_M44_V2",
        "parent_plan_id": "R8_7_GPT_M42_V3",
        "referenced_experience_ids": ["M44_M43_V1_DP_AND_OPENING_FAILURE_V1"],
        "tactical_hypothesis": (
            "The first leak can be removed without Vanilla's unready income by preserving Beagle, using a living "
            "same-tile Friston handoff, and adding Popukar before the old 1661 leak."
        ),
    })
    payload["revision_hypothesis"] = revision

    hypotheses = payload.get("revised_strategic_hypotheses") or []
    hypotheses.append({
        "falsifiers": [
            "Friston is absent or the retreat is illegal at frame 1500.",
            "Popukar cannot deploy for DP or the released runner escapes before frame 1661.",
            "Beagle, Popukar, Fang or Hibiscus creates an independent early collapse.",
            "Deployment limit exceeds eight at any later reinforcement.",
            "Either civilian dies or fails to arrive safely.",
            "Artillery survives its available damage windows.",
        ],
        "hypothesis": "Repair M42 V3's earliest interception with a living Popukar handoff while retaining its reliable opening economy and correcting late deployment capacity.",
        "hypothesis_id": "R8-7-M44-V2-H1",
        "revision_basis": "M42 V3's 1661 leak is not an established interception baseline; M43 V3's Vanilla-funded opening produced a legal but catastrophic LOSS.",
    })
    payload["revised_strategic_hypotheses"] = hypotheses

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
