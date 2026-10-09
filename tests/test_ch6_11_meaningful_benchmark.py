from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import TestCase

from arknights_planner.agent.tactical import PlanHypothesis
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.operator_assignment import OperatorAssignmentEngine
from arknights_planner.search.stage_understanding import TacticalRequirementModel
from arknights_planner.search.stage_understanding import derive_tactical_requirements
from arknights_planner.search.tactical_realizability import TacticalRealizabilityAnalyzer

from tests.test_executable_plan_lowering import main_01_01_spatial_fixture


ROOT = Path(__file__).resolve().parents[1]


def _load_benchmark_script():
    path = ROOT / "scripts" / "build_ch6_11_meaningful_benchmark.py"
    spec = importlib.util.spec_from_file_location("ch6_11_benchmark_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MeaningfulBenchmarkSelectionTests(TestCase):
    def test_structural_suite_selects_three_distinct_ch6_11_stages(self):
        module = _load_benchmark_script()
        records = [
            {
                "stage_id": "main_06-03",
                "display_stage_code": "6-3",
                "chapter": 6,
                "lane_count": 1,
                "blockable_lane_count": 1,
                "non_blockable_lane_count": 0,
                "enemy_count": 26,
                "simultaneous_pressure_estimate": {"maximum_simultaneous_lanes": 7},
                "enemy_threat": {"spawn_weighted_average_hp": 10000},
                "healing_sustain_relevance": {"classification": "SUSTAIN_RISK"},
                "eligible_for_autonomous_team_selection": True,
            },
            {
                "stage_id": "main_11-12",
                "display_stage_code": "11-14",
                "chapter": 11,
                "lane_count": 2,
                "blockable_lane_count": 2,
                "non_blockable_lane_count": 0,
                "enemy_count": 31,
                "simultaneous_pressure_estimate": {"maximum_simultaneous_lanes": 8},
                "enemy_threat": {"spawn_weighted_average_hp": 9000},
                "healing_sustain_relevance": {"classification": "SUSTAIN_RISK"},
                "eligible_for_autonomous_team_selection": True,
            },
            {
                "stage_id": "main_06-01",
                "display_stage_code": "6-1",
                "chapter": 6,
                "lane_count": 3,
                "blockable_lane_count": 2,
                "non_blockable_lane_count": 1,
                "enemy_count": 46,
                "simultaneous_pressure_estimate": {"maximum_simultaneous_lanes": 12},
                "enemy_threat": {"spawn_weighted_average_hp": 8000},
                "healing_sustain_relevance": {"classification": "SUSTAIN_RISK"},
                "eligible_for_autonomous_team_selection": True,
            },
        ]
        suite = module.select_suite(records)
        self.assertEqual(len(suite["stages"]), 3)
        self.assertEqual({item["stage_id"] for item in suite["stages"]}, {
            "main_06-03", "main_11-12", "main_06-01",
        })
        self.assertEqual(suite["stages"][0]["stage_id"], "main_06-03")
        self.assertNotIn("0-1", {item["display_stage_code"] for item in suite["stages"]})


class TacticalRealizabilityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.understanding, cls.search = main_01_01_spatial_fixture()

    def test_non_blockable_lane_hypothesis_is_revised_to_ranged_interception(self):
        requirement = TacticalRequirementModel(
            requirement_id="test-invalid-block",
            requirement_type="STALL_INTERCEPTION",
            evidence="regression requirement on an exact non-blockable route",
            pressure_window="early-pressure",
            affected_routes=("route-4",),
            hardness="HARD",
            confidence=1.0,
            capability="BLOCK",
            provenance="regression",
        )
        hypothesis = PlanHypothesis(
            hypothesis_id="invalid-dual-block",
            summary="Regression hypothesis",
            target_cardinality=2,
            tactical_archetype="DUAL_BLOCK_FRONTLINE",
            required_capabilities=("BLOCK", "RANGED_DPS"),
            preferred_operator_ids=("char_272_strong", "char_494_vendla"),
            deployment_order=("char_272_strong", "char_494_vendla"),
        )
        result = TacticalRealizabilityAnalyzer().validate(
            self.understanding, (requirement,), (hypothesis,)
        )
        self.assertEqual(len(result.accepted_hypotheses), 1)
        self.assertEqual(
            result.accepted_hypotheses[0].tactical_archetype,
            "BLOCK_REALIZABLE_LANE_RANGED_INTERCEPT_OTHER",
        )
        self.assertEqual(len(result.revision_ancestry), 1)

    def test_infeasible_nonblocking_requirement_rejects_hypothesis(self):
        requirement = TacticalRequirementModel(
            requirement_id="test-uncovered-route",
            requirement_type="PRE_CONTACT_DAMAGE",
            evidence="regression requirement with no exact coverage",
            pressure_window="early-pressure",
            affected_routes=("route-does-not-exist",),
            hardness="HARD",
            confidence=1.0,
            capability="RANGED_DPS",
            provenance="regression",
        )
        hypothesis = PlanHypothesis(
            hypothesis_id="uncovered-ranged",
            summary="Regression hypothesis",
            target_cardinality=1,
            tactical_archetype="RANGED_INTERCEPTION_ONLY",
            required_capabilities=("RANGED_DPS",),
            preferred_operator_ids=("char_494_vendla",),
            deployment_order=("char_494_vendla",),
        )
        result = TacticalRealizabilityAnalyzer().validate(
            self.understanding, (requirement,), (hypothesis,)
        )
        self.assertEqual(result.accepted_hypotheses, ())
        self.assertEqual(len(result.rejected_hypotheses), 1)
        self.assertIn(
            "no exact legal structural opportunity",
            result.checks[-1].evidence,
        )


class SkillLoweringTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.understanding, cls.search = main_01_01_spatial_fixture()
        cls.skill_operator_id = "char_1024_hbisc2"
        cls.block_operator_id = next(
            operator_id
            for operator_id, operator in cls.engine.fixture.operators.items()
            if operator.position.value == "MELEE"
            and int(operator.phases[0].stats_max.block_count.value or 0) > 0
        )
        cls.hypothesis = PlanHypothesis(
            hypothesis_id="skill-lowering-regression",
            summary="Skill lowering regression",
            target_cardinality=2,
            tactical_archetype="BLOCKER_PLUS_RANGED_SUPPORT",
            preferred_operator_ids=(cls.block_operator_id, cls.skill_operator_id),
            deployment_order=(cls.block_operator_id, cls.skill_operator_id),
            skill_use_intents=("activate the supported skill in the pressure window",),
        )
        audit = {}
        skeletons = cls.search.generate_skeletons(
            hypothesis_id=cls.hypothesis.hypothesis_id,
            hypothesis_archetype=cls.hypothesis.tactical_archetype,
            team=cls.hypothesis.preferred_operator_ids,
            deployment_order=cls.hypothesis.deployment_order,
            roles={cls.block_operator_id: "BLOCK", cls.skill_operator_id: "RANGED_DPS"},
            audit=audit,
        )
        cls.skeleton = skeletons[0]
        cls.audit = audit
        cls.candidates = cls.search.generate_timing_candidates(
            cls.skeleton,
            audit=audit,
            hypothesis=cls.hypothesis,
        )
        cls.skill_candidates = [
            candidate for candidate in cls.candidates if candidate.skill_anchors
        ]

    def test_skill_intent_lowers_to_event_relative_action(self):
        self.assertTrue(self.skill_candidates)
        candidate = self.skill_candidates[0]
        self.assertIn(ActionType.ACTIVATE_SKILL, [item.action_type for item in candidate.actions])
        self.assertTrue(candidate.dp_feasible)
        for anchor in candidate.skill_anchors:
            self.assertGreaterEqual(anchor.final_frame, anchor.desired_frame)
            self.assertGreaterEqual(anchor.final_frame, anchor.earliest_frame)
            self.assertEqual(anchor.operator_id, self.skill_operator_id)

    def test_base_and_skill_timing_candidates_both_survive_deduplication(self):
        patterns = {item.pattern_id for item in self.candidates}
        self.assertIn("EARLIEST_DP", patterns)
        self.assertTrue(any(item.pattern_id.endswith(
            ("SKILL_READY_AFTER_DEPLOY", "PRESSURE_START_MINUS_30", "PRESSURE_PEAK_MINUS_60", "FIRST_CONTACT_MINUS_30")
        ) for item in self.candidates))

    def test_skill_ready_legality_rejects_activation_before_ready(self):
        candidate = self.skill_candidates[0]
        deploy = next(
            item for item in candidate.actions
            if item.action_type is ActionType.DEPLOY and item.operator_id == self.skill_operator_id
        )
        skill = next(
            item for item in candidate.actions
            if item.action_type is ActionType.ACTIVATE_SKILL and item.operator_id == self.skill_operator_id
        )
        actions = list(candidate.actions)
        actions[actions.index(skill)] = Action(
            skill.action_type,
            deploy.time,
            skill.operator_id,
            skill.tile,
            skill.direction,
        )
        feasible, reasons = self.search.dp_legality(Strategy(candidate.strategy.team, tuple(actions)))
        self.assertFalse(feasible)
        self.assertIn("INSUFFICIENT_SKILL_SP", reasons)

    def test_skill_refinement_preserves_strategy_and_changes_skill_frame(self):
        candidate = self.skill_candidates[0]
        refined = self.search._timing_refinement_candidates(candidate)
        self.assertTrue(refined)
        self.assertTrue(all(isinstance(item.strategy, Strategy) for item in refined))
        legal_skill_refinements = [
            item for item in refined
            if item.dp_feasible
            and any(action.action_type is ActionType.ACTIVATE_SKILL for action in item.actions)
        ]
        self.assertTrue(legal_skill_refinements)
        parent_frame = self.search.config.frame_clock.frame_for_seconds(
            next(action.time for action in candidate.actions if action.action_type is ActionType.ACTIVATE_SKILL)
        )
        self.assertTrue(any(
            any(
                action.action_type is ActionType.ACTIVATE_SKILL
                and self.search.config.frame_clock.frame_for_seconds(action.time) != parent_frame
                for action in item.actions
            )
            for item in legal_skill_refinements
        ))

    def test_executable_fingerprint_distinguishes_skill_frame(self):
        deploy = Action(ActionType.DEPLOY, 1.0, "a", (1, 1), "RIGHT")
        early = Strategy(("a",), (deploy, Action(ActionType.ACTIVATE_SKILL, 2.0, "a")))
        late = Strategy(("a",), (deploy, Action(ActionType.ACTIVATE_SKILL, 3.0, "a")))
        self.assertNotEqual(
            self.search._executable_timeline_fingerprint(early),
            self.search._executable_timeline_fingerprint(late),
        )

    def test_high_pressure_control_roster_prioritizes_supported_skills(self):
        requirements = derive_tactical_requirements(self.understanding)
        plan = OperatorAssignmentEngine().assign(
            self.understanding,
            requirements,
            self.engine.fixture.operators,
            max_cardinality=12,
            team_size_policy="FEASIBILITY_FIRST",
        )
        control = next(
            item for item in plan.coverage_alternatives
            if item.archetype == "CONTROL_CAPABILITY_RICH"
        )
        skill_capabilities = {
            coverage.operator_id
            for coverage in control.operator_coverage
            if "SKILL" in (coverage.primary_capability, *coverage.secondary_capabilities)
        }
        self.assertTrue(skill_capabilities)
        self.assertTrue(all(
            self.engine.fixture.operators[operator_id].synthetic_skill is not None
            and not self.engine.fixture.operators[operator_id].synthetic_skill.auto_activate
            for operator_id in skill_capabilities
        ))
