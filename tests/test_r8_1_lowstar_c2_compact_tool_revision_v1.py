import json
import unittest
from pathlib import Path

from run_r8_1_low_star_full_tactical_closure_v1 import output_schema
from compile_r8_1_lowstar_c2_plan_v1 import (
    automatic_dp_skill_events,
    declared_target_objects,
    build_dp_ledger,
    file_record,
    first_skill,
    supported_auto_dp_skill,
    structured_range_checks,
    uncovered_declared_targets,
)
from kimi_readonly_tools import TOOLS_SCHEMA
from kimi_readonly_tools import ReadOnlyQueryEngine
from run_r8_1_lowstar_c2_tool_revision_v1 import (
    FINAL_TOKEN_LIMIT,
    MAX_REQUEST_BODY_BYTES,
    OUT,
    QUERY_TOKEN_LIMIT,
    finalize_plan_payload,
)


class CompactC2Tests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads((OUT / "llm_evidence_context.json").read_text())
        self.payload = json.loads((OUT / "llm_request.json").read_text())
        self.body = (OUT / "llm_request_body.txt").read_bytes()

    def test_query_phase_is_compact_and_not_schema_bound(self):
        self.assertLessEqual(len(self.body), MAX_REQUEST_BODY_BYTES)
        self.assertEqual(QUERY_TOKEN_LIMIT, self.payload["max_output_tokens"])
        self.assertEqual(32768, self.payload["max_output_tokens"])
        self.assertNotIn("text", self.payload)
        self.assertEqual(34, len(self.evidence["normal_low_star_catalog"]))
        self.assertEqual(
            17,
            len([row for row in self.evidence["normal_low_star_catalog"] if row["identity"]["rarity"] == 3]),
        )
        self.assertTrue(all("runtime_support" in row for row in self.evidence["normal_low_star_catalog"]))
        self.assertNotIn("normal_low_star_mechanism_support", self.evidence)
        self.assertNotIn("action_window_frames", self.evidence["decision_task"])

    def test_final_continuation_binds_schema_and_explicit_instruction(self):
        schema = output_schema()
        continuation = {
            "model": "kimi-k3",
            "stream": True,
            "max_output_tokens": QUERY_TOKEN_LIMIT,
            "input": [
                {"role": "user", "content": [{"type": "input_text", "text": "query"}]},
                {"type": "function_call", "call_id": "call-1", "name": "query_mechanic", "arguments": "{}"},
                {"type": "function_call_output", "call_id": "call-1", "output": "{}"},
            ],
            "tools": TOOLS_SCHEMA,
        }
        finalized = finalize_plan_payload(continuation, schema)
        self.assertEqual(FINAL_TOKEN_LIMIT, finalized["max_output_tokens"])
        self.assertEqual("json_schema", finalized["text"]["format"]["type"])
        self.assertEqual(schema, finalized["text"]["format"]["schema"])
        self.assertEqual("function_call_output", finalized["input"][-2]["type"])
        self.assertEqual("user", finalized["input"][-1]["role"])
        self.assertIn("All readonly tool calls have now been executed", finalized["input"][-1]["content"][0]["text"])

    def test_structured_range_checks_require_exact_action_identity(self):
        action = {"operator_id": "op", "tile": [4, 6], "direction": "UP"}
        rows = [
            {"operator_id": "op", "tile": [4, 6], "direction": "UP", "targets": []},
            {"operator_id": "op", "tile": [4, 7], "direction": "UP", "targets": [{"label": "wrong", "tile": [4, 6]}]},
            {"operator_id": "op", "tile": [4, 6], "direction": "DOWN", "targets": [{"label": "wrong", "tile": [4, 6]}]},
            {"operator_id": "other", "tile": [4, 6], "direction": "UP", "targets": [{"label": "wrong", "tile": [4, 6]}]},
        ]
        self.assertEqual([rows[0]], structured_range_checks({"declared_range_checks": rows}, action))

    def test_declared_configuration_omits_derived_internal_fields(self):
        engine = ReadOnlyQueryEngine(evidence_path=OUT / "llm_evidence_context.json")
        arguments = {
            "operator_id": "char_120_hibisc",
            "configuration": {
                "rarity": 3,
                "phase_index": 1,
                "level": 55,
                "skill_level_index": 6,
                "potential_level": 1,
                "trust": 0,
            },
            "tile": [5, 7],
            "direction": "DOWN",
            "targets": [{"label": "beagle", "tile": [4, 6]}],
        }
        result = engine.query_range_coverage(arguments)
        self.assertIn("covered_tiles_json_row_col", result)

    def test_declared_configuration_rejects_actual_mismatch(self):
        engine = ReadOnlyQueryEngine(evidence_path=OUT / "llm_evidence_context.json")
        arguments = {
            "operator_id": "char_120_hibisc",
            "configuration": {
                "rarity": 3,
                "phase_index": 1,
                "level": 54,
                "skill_level_index": 6,
                "potential_level": 1,
                "trust": 0,
            },
            "tile": [5, 7],
            "direction": "DOWN",
            "targets": [{"label": "beagle", "tile": [4, 6]}],
        }
        with self.assertRaisesRegex(ValueError, "declared configuration"):
            engine.query_range_coverage(arguments)

    def test_no_skill_operator_omits_skill_fields(self):
        engine = ReadOnlyQueryEngine(evidence_path=OUT / "llm_evidence_context.json")
        arguments = {
            "operator_id": "char_285_medic2",
            "configuration": {
                "rarity": 1,
                "phase_index": 0,
                "level": 30,
                "potential_level": 1,
                "trust": 0,
            },
            "tile": [2, 9],
            "direction": "LEFT",
            "targets": [{"label": "melantha", "tile": [1, 7]}],
        }
        result = engine.query_range_coverage(arguments)
        self.assertEqual("3-1", result["range_id"])

    def test_compiler_reads_selected_skills_not_legacy_skills(self):
        operator = {"selected_skills": [{"skill_id": "skill"}], "skills": []}
        self.assertEqual({"skill_id": "skill"}, first_skill(operator))

    def test_uncovered_targets_preserve_conflict_field_name(self):
        result = {"targets": [
            {"tile_json_row_col": [4, 6], "covered": True},
            {"tile_json_row_col": [1, 6], "covered": False},
        ]}
        self.assertEqual([[1, 6]], uncovered_declared_targets(result))

    def test_declared_coordinate_list_targets_are_preserved_as_tool_objects(self):
        targets = declared_target_objects({"targets": [[1, 6], {"label": "x", "tile": [4, 7]}]})
        self.assertEqual([
            {"label": "declared_0", "tile": [1, 6]},
            {"label": "x", "tile": [4, 7]},
        ], targets)

    def test_compiler_file_record_contains_hash_and_size(self):
        record = file_record(OUT / "llm_evidence_context.json")
        self.assertEqual(64, len(record["sha256"]))
        self.assertGreater(record["bytes"], 0)

    def test_auto_dp_skill_timing_cycles_and_retreat_stop(self):
        skill = {
            "skill_id": "fang", "skill_type": "AUTO", "sp_type": "INCREASE_WITH_TIME",
            "duration": 0, "initial_sp": 6, "sp_cost": 25, "blackboard": {"cost": 6},
        }
        operator = {
            "selected_skills": [skill],
            "runtime_support": {"skills": [{"skill_id": "fang", "status": "EXECUTABLE_APPROXIMATED"}]},
        }
        catalog = {"fang": operator}
        supports = {"fang": {"deployment_sp_bonus": 0}}
        self.assertIs(skill, supported_auto_dp_skill(operator))
        active_plan = {
            "action_timeline": [
                {"action_type": "DEPLOY", "operator_id": "fang", "frame": 0},
                {"action_type": "DEPLOY", "operator_id": "other", "frame": 1500},
            ],
        }
        active_events = automatic_dp_skill_events(active_plan, catalog, supports)
        self.assertEqual([570, 1320], [row["frame"] for row in active_events])
        self.assertEqual([6, 6], [row["amount"] for row in active_events])
        retreat_plan = {"action_timeline": active_plan["action_timeline"][:1] + [{"action_type": "RETREAT", "operator_id": "fang", "frame": 700}]}
        retreated_events = automatic_dp_skill_events(retreat_plan, catalog, supports)
        self.assertEqual([570], [row["frame"] for row in retreated_events])

    def test_c2_auto_income_restores_frame_600_payment(self):
        evidence = json.loads((OUT / "llm_evidence_context.json").read_text(encoding="utf-8"))
        plan = json.loads((OUT / "llm_structured_output.json").read_text(encoding="utf-8"))["revised_operational_plans"][0]
        catalog = {row["operator_id"]: row for row in evidence["normal_low_star_catalog"]}
        supports = {row["operator_id"]: row.get("runtime_support") or {} for row in evidence["normal_low_star_catalog"]}
        ledger = build_dp_ledger(plan, catalog, supports)
        by_key = {(row["frame"], row["event"], row.get("operator_id")): row for row in ledger["entries"]}
        auto = by_key[(570, "AUTO_SKILL_DP_INCOME", "char_123_fang")]
        deploy = by_key[(600, "DEPLOY_COST", "char_500_noirc")]
        self.assertEqual((8, 8, 14), (auto["balance_before"], ledger["entries"][ledger["entries"].index(auto) - 1]["balance_after"], auto["balance_after"]))
        self.assertEqual((15, 1), (deploy["balance_before"], deploy["balance_after"]))
        self.assertEqual([], ledger["conflicts"])
