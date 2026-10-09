from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "semantic_repair", ROOT / "scripts/run_r8_1_operational_semantic_preservation_repair_v1.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def operator(operator_id: str, **overrides):
    value = {
        "operator_id": operator_id,
        "position": "MELEE",
        "profession": "WARRIOR",
        "block_count": 2,
        "cost": 15,
        "attack": 500,
        "attack_interval_seconds": 1,
        "planner_safe_for_basic_attack": True,
        "skill_supported": True,
        "skill_auto_activate": True,
        "skill_recovery_mode": "ATTACK",
        "skill_effect": {"atk_multiplier": 1.0, "next_attack_atk_scale": 1.75},
    }
    value.update(overrides)
    return value


class SemanticPreservationTests(unittest.TestCase):
    def test_unsupported_unused_skill_does_not_block_supported_selected_skill(self):
        fidelity = {"op_a": {"dimensions": {"talent": "GENERIC_SUPPORTED", "trait": "UNKNOWN"}}}
        eligible, reasons = MODULE.selected_usage_fidelity(
            operator("op_a", planner_safe_for_selected_skills=False),
            role="KILLING_BLOCK",
            fidelity_by_id=fidelity,
            census_by_id={},
        )
        self.assertTrue(eligible)
        self.assertEqual(reasons, [])

    def test_unsupported_selected_skill_blocks_killing_block(self):
        eligible, reasons = MODULE.selected_usage_fidelity(
            operator("op_b", skill_supported=False),
            role="KILLING_BLOCK",
            fidelity_by_id={},
            census_by_id={},
        )
        self.assertFalse(eligible)
        self.assertIn("SELECTED_SKILL_UNSUPPORTED", reasons)

    def test_unsupported_decision_critical_trait_blocks_operator(self):
        fidelity = {"op_c": {"dimensions": {"talent": "GENERIC_SUPPORTED", "trait": "UNSUPPORTED"}}}
        census = {"op_c": {"trait_effects": {"candidates": [{"blackboard": [{"key": "atk_scale", "value": 1.2}]}]}}}
        eligible, reasons = MODULE.selected_usage_fidelity(
            operator("op_c"), role="KILLING_BLOCK", fidelity_by_id=fidelity, census_by_id=census
        )
        self.assertFalse(eligible)
        self.assertIn("DECISION_CRITICAL_TRAIT_UNSUPPORTED", reasons)

    def test_unsupported_noncritical_trait_metadata_does_not_block_blocker(self):
        fidelity = {"op_e": {"dimensions": {"talent": "GENERIC_SUPPORTED", "trait": "UNSUPPORTED"}}}
        census = {"op_e": {"trait_effects": {"candidates": [{"blackboard": [{"key": "interval", "value": 3.0}]}]}}}
        eligible, reasons = MODULE.selected_usage_fidelity(
            operator("op_e"), role="BLOCK", fidelity_by_id=fidelity, census_by_id=census
        )
        self.assertTrue(eligible)
        self.assertEqual(reasons, [])

    def test_unrelated_fidelity_metadata_does_not_block_operator(self):
        fidelity = {"op_d": {"dimensions": {"talent": "GENERIC_SUPPORTED", "trait": "UNKNOWN"}}}
        eligible, reasons = MODULE.selected_usage_fidelity(
            operator("op_d"), role="KILLING_BLOCK", fidelity_by_id=fidelity, census_by_id={}
        )
        self.assertTrue(eligible)
        self.assertEqual(reasons, [])

    def test_deadline_establishment_rejects_late_deployment(self):
        context = {
            "exact_route_threats": {"routes": [{"route_id": "route-2", "latest_safe_blocker_frame": 27}]}
        }
        slot = {"slot_id": "C03_STUB", "role": "BLOCK", "tile": [3, 3], "direction": "RIGHT"}
        roster = {"C03_STUB": "blocker"}
        operators = {"blocker": operator("blocker", position="MELEE", cost=1)}
        action = MODULE.Action(MODULE.ActionType.DEPLOY, MODULE.FrameClock.configured(30).seconds_for_frame(28), "blocker", (3, 3), "RIGHT")
        ok, reasons = MODULE.establishment_check(
            "R-OP-01-POCKET-AND-FLOOR", slot, roster, [action], operators, context, None
        )
        self.assertFalse(ok)
        self.assertTrue(any(reason.startswith("DEADLINE_MISSED:27") for reason in reasons))

    def test_earliest_phase_is_not_a_deadline_staged_noop(self):
        context = MODULE.load(MODULE.CTX_PATH)
        plans = MODULE.load(MODULE.RECOVER / "normalized_revised_operational_plans.json")["revised_operational_plans"]
        plan_id = "R-OP-01-POCKET-AND-FLOOR"
        pattern = MODULE.make_pattern(MODULE.import_prior_module().PATTERNS[plan_id], {})
        roster = {
            "C03_STUB": "char_272_strong",
            "POCKET_BLOCK": "char_123_fang",
            "POCKET_FIRE": "char_4100_caper",
            "C04_FIRE": "char_4006_melnte",
            "C07_FIRE": "char_235_jesica",
            "C05_BLOCK": "char_455_nothin",
            "C06_BLOCK": "char_4155_talr",
            "POCKET_MEDIC": "char_1020_reed2",
        }
        operators = {operator["operator_id"]: operator for operator in context["operators"]}
        deadline_actions, _ = MODULE.build_deadline_actions(pattern, roster, operators, context, plan_id, "DEADLINE_STAGED", "NO_SKILLS")
        earliest_actions, _ = MODULE.build_deadline_actions(pattern, roster, operators, context, plan_id, "EARLIEST_PHASE", "NO_SKILLS")
        self.assertNotEqual(
            [MODULE.frame_of(action) for action in deadline_actions],
            [MODULE.frame_of(action) for action in earliest_actions],
        )

    def test_scheduler_does_not_double_count_cumulative_deployment_cost(self):
        context = MODULE.load(MODULE.CTX_PATH)
        plan_id = "R-OP-01-POCKET-AND-FLOOR"
        pattern = MODULE.make_pattern(MODULE.import_prior_module().PATTERNS[plan_id], {})
        roster = {
            "C03_STUB": "char_272_strong",
            "POCKET_BLOCK": "char_123_fang",
            "POCKET_FIRE": "char_124_kroos",
            "C04_FIRE": "char_211_adnach",
            "C07_FIRE": "char_126_shotst",
            "C05_BLOCK": "char_237_gravel",
            "C06_BLOCK": "char_4155_talr",
            "POCKET_MEDIC": "char_181_flower",
        }
        operators = {operator["operator_id"]: operator for operator in context["operators"]}
        actions, frames = MODULE.build_deadline_actions(
            pattern,
            roster,
            operators,
            context,
            plan_id,
            "EARLIEST_PHASE",
            "NO_SKILLS",
        )
        ok, reasons = MODULE.dp_feasible(actions, operators, context)
        self.assertTrue(ok, reasons)
        c04_action = next(action for action in actions if action.operator_id == "char_211_adnach")
        self.assertLessEqual(MODULE.frame_of(c04_action), 660)
        self.assertEqual(MODULE.frame_of(c04_action), 390)
