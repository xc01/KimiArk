from __future__ import annotations

import unittest
from pathlib import Path
from dataclasses import replace

from arknights_planner.adapters import ApproximateRealSimulationAdapter, RealSimulationApproximationPolicy
from arknights_planner.gamedata import GameDataRepository
from arknights_planner.models.simulation import EventType
from arknights_planner.models.stage import BattleDevice, SpawnEvent
from arknights_planner.models.strategy import Action, ActionType, Strategy
from arknights_planner.search.stage_mechanics import (
    StageMechanicsAnalyzer,
    combine_complete_stage_fidelity,
)
from arknights_planner.simulator import SimulationConfig, Simulator
from arknights_planner.simulator.synthetic import synthetic_enemies, synthetic_operators, synthetic_stage

ROOT = Path(__file__).resolve().parents[1]


class StageMechanicsFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = GameDataRepository(ROOT / "data/ArknightsGameData")
        cls.analyzer = StageMechanicsAnalyzer()

    def test_r8_1_predeployed_roadblocks_are_observed_not_inferred(self):
        record = self.analyzer.analyze(self.repository, "main_08-01")
        tokens = [item for item in record.mechanics if item.family == "PREDEPLOYED_ENTITY"]
        self.assertEqual(len(tokens), 5)
        self.assertEqual({item.details["token_key"] for item in tokens}, {"trap_020_roadblock"})
        self.assertEqual(
            {item.details["canonical_position"] for item in tokens},
            {(5, 3), (9, 2), (7, 4), (1, 4), (3, 1)},
        )
        self.assertFalse(all(item.details["dependent_units_present"] for item in tokens))
        self.assertEqual(record.dimensions["devices"], "SAFE_WITH_BOUNDED_INFERENCE")
        self.assertEqual(record.dimensions["targetable_objects"], "SAFE_WITH_BOUNDED_INFERENCE")
        self.assertEqual(record.overall, "SAFE_WITH_BOUNDED_INFERENCE")
        self.assertIn("DEVICE_DESTRUCTIBILITY_INSTANTIATED_LOW_PRIORITY_TARGETING_IS_BOUNDED_INFERENCE", record.reason_codes)

    def test_inactive_path_blocker_does_not_cap_stage_mechanics(self):
        record = self.analyzer.analyze(self.repository, "main_08-01")
        path_blockers = [item for item in record.mechanics if item.family == "PATH_BLOCKER"]
        self.assertTrue(path_blockers)
        self.assertTrue(all(item.decision_criticality == "PRESENT_BUT_INACTIVE_IN_STAGE_CONTEXT" for item in path_blockers))
        self.assertEqual(record.overall, "SAFE_WITH_BOUNDED_INFERENCE")

    def test_complete_fidelity_supports_bounded_inference(self):
        mechanics = self.analyzer.analyze(self.repository, "main_08-01")
        complete = combine_complete_stage_fidelity(
            eligibility_simulator_supported=True,
            enemy_fidelity="FULL_RUNTIME_SAFE",
            stage_mechanics=mechanics,
        )
        self.assertEqual(complete.stage_mechanics_fidelity, "SAFE_WITH_BOUNDED_INFERENCE")
        self.assertEqual(complete.complete_fidelity, "SAFE_WITH_BOUNDED_INFERENCE")

    def test_partial_enemy_fidelity_still_caps_complete_fidelity(self):
        mechanics = self.analyzer.analyze(self.repository, "main_08-01")
        complete = combine_complete_stage_fidelity(
            eligibility_simulator_supported=True,
            enemy_fidelity="PARTIAL",
            stage_mechanics=mechanics,
        )
        self.assertEqual(complete.enemy_fidelity, "PARTIAL")
        self.assertEqual(complete.stage_mechanics_fidelity, "SAFE_WITH_BOUNDED_INFERENCE")
        self.assertEqual(complete.complete_fidelity, "PARTIAL_STAGE_RUNTIME")
        self.assertEqual(complete.capping_layer, "ENEMY_FIDELITY")

    def test_enemy_fidelity_alone_cannot_restore_high_fidelity(self):
        mechanics = self.analyzer.analyze(self.repository, "main_08-01")
        complete = combine_complete_stage_fidelity(
            eligibility_simulator_supported=True,
            enemy_fidelity="FULL_RUNTIME_SAFE",
            stage_mechanics=mechanics,
        )
        self.assertNotEqual(complete.complete_fidelity, "HIGH_FIDELITY_PLANNING_SAFE")

    def test_no_mechanic_stage_with_full_enemy_support_is_high(self):
        mechanics = self.analyzer.analyze(self.repository, "main_01-01")
        complete = combine_complete_stage_fidelity(
            eligibility_simulator_supported=True,
            enemy_fidelity="FULL_RUNTIME_SAFE",
            stage_mechanics=mechanics,
        )
        self.assertEqual(mechanics.overall, "EXACT")
        self.assertEqual(complete.complete_fidelity, "HIGH_FIDELITY_PLANNING_SAFE")

    def test_r8_1_pool_fixture_instantiates_five_source_backed_devices(self):
        repository = GameDataRepository(ROOT / "data/ArknightsGameData")
        adapter = ApproximateRealSimulationAdapter(repository)
        fixture = adapter.build_pool_fixture(
            stage_id_or_code="main_08-01", configurations=(),
            policy=RealSimulationApproximationPolicy.m11_second_quantized(),
        )
        self.assertEqual(len(fixture.stage.devices), 5)
        self.assertEqual({item.tile for item in fixture.stage.devices}, {(5, 3), (9, 2), (7, 4), (1, 4), (3, 1)})
        self.assertTrue(all(
            item.template_id == "trap_020_roadblock" and item.hp == 8000
            and item.defense == 200 and item.magic_resistance == 20 and item.taunt_level == -1
            for item in fixture.stage.devices
        ))

    def test_low_priority_device_attack_event_order_and_destruction(self):
        device = BattleDevice("roadblock#1", "trap_020_roadblock", (1, 3), 10.0, 200.0, 20.0, -1, True, "ENEMY")
        stage = replace(synthetic_stage(), devices=(device,), spawn_events=(SpawnEvent(100.0, "slug", "main"),))
        strategy = Strategy(("archer",), (Action(ActionType.DEPLOY, 0.0, "archer", (1, 2), "DOWN"),))
        result = Simulator().run(
            stage=stage, operators=synthetic_operators(), enemies=synthetic_enemies(),
            strategy=strategy, config=SimulationConfig(dt=0.1, max_time=2.0),
        )
        types = [event.event_type for event in result.events]
        self.assertIn(EventType.DEVICE_TARGET_SELECTION, types)
        self.assertIn(EventType.DEVICE_DAMAGE, types)
        self.assertIn(EventType.DEVICE_DESTROYED, types)
        self.assertLess(types.index(EventType.DEVICE_DAMAGE), types.index(EventType.DEVICE_DESTROYED))
        last_damage = next(event for event in reversed(result.events) if event.event_type is EventType.DEVICE_DAMAGE and event.target_id == "roadblock#1")
        self.assertEqual(last_damage.source_id, "archer")


if __name__ == "__main__":
    unittest.main()
