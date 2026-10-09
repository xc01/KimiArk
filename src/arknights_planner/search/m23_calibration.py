"""M23 calibration boundary; never emits a human request when gates fail."""
from __future__ import annotations

import json
from pathlib import Path

from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION
from arknights_planner.mechanics_registry import MechanicsEvidenceRegistry


class M23CalibrationPacket:
    def __init__(self, root: Path = Path(".")):
        self.root = Path(root)

    def run(self):
        registry = MechanicsEvidenceRegistry(self.root)
        historical_decisions = json.loads(
            (Path("output/m18_1/main_06-07") / "m18_1_targeting_decisions.json").read_text(encoding="utf-8")
        )["causally_relevant"]
        sensitive_count = sum(
            item["fidelity_class"] == "UNRESOLVED_DECISION_SENSITIVE"
            for item in historical_decisions
        )
        gates = {
            question_id: registry.human_calibration_gate(
                question_id,
                context,
                planner_relevance=True,
                counterfactual_sensitivity=False,
            )
            for question_id, context in (
                ("Q1", {"candidate_remaining_route_distances": [3.0, 5.0], "has_taunt_or_special_filter": False}),
                ("Q2", {"operator_position": "MELEE", "blocked_candidate_ids": ["blocked"]}),
                ("Q3", {"lifecycle": "RETARGET_AFTER_TARGET_DISAPPEARANCE"}),
            )
        }
        return {
            "m23_information_value_ranking": {
                "selected_count": 0,
                "historical_sensitive_decisions": sensitive_count,
                "ranking_basis": "current evidence and calibration gates; historical sensitivity is not current truth",
            },
            "m23_calibration_questions": {"questions": []},
            "m23_experiment_plan": {
                "phase": "A",
                "status": "PAUSED_NO_HUMAN_CALIBRATION_REQUIRED",
                "trials": [],
                "no_observations_recorded": True,
            },
            "m23_observation_template": None,
            "m23_precalibration_state": {
                "active_mechanics_version": ACTIVE_MECHANICS_VERSION,
                "targeting_fidelity": "PARTIALLY_ALIGNED",
                "current_6_8_baseline": None,
                "reason": "A fresh m18.2 deterministic replay is required before Q3 sensitivity can be established.",
            },
            "m23_evidence_gate": gates,
            "m23_q_status": {
                "Q1": "CONTEXTUALLY_RESOLVED",
                "Q2": "RESOLVED_BY_EXISTING_EVIDENCE",
                "Q3": "PARTIALLY_RESOLVED",
            },
            "m23_results": {
                "HUMAN_CALIBRATION_REQUIRED": False,
                "status": "NO_HUMAN_CALIBRATION_REQUIRED",
            },
        }

    def instructions(self):
        return (
            "# M23 Target Allocation Calibration\n\n"
            "No human calibration is currently required.\n\n"
            "Q1 is contextually resolved by remaining-path evidence. Q2 is resolved by cached "
            "sandbox evidence for ordinary melee self-blocked priority. Q3 remains partially "
            "resolved, but current counterfactual sensitivity has not been established under "
            f"{ACTIVE_MECHANICS_VERSION}. Run a deterministic rebaseline first.\n"
            "Status: NO_HUMAN_CALIBRATION_REQUIRED\n"
        )
