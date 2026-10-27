from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_gpt_tactical_stage_session_v1 as gpt_runner  # noqa: E402


def load_low_star_runner():
    spec = importlib.util.spec_from_file_location(
        "run_r8_1_low_star_full_tactical_closure_v1",
        ROOT / "scripts/run_r8_1_low_star_full_tactical_closure_v1.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def comparison(
    candidate_ids=("a", "b", "c"),
    selected_count=1,
    selected_path="comparison",
    selected_id=None,
    key="candidates",
):
    rows = [
        {"structure_id": candidate_id, "selected": False}
        for candidate_id in candidate_ids
    ]
    if selected_count:
        for index in range(min(selected_count, len(rows))):
            rows[index]["selected"] = True
    if selected_id:
        rows[0]["structure_id"] = selected_id
    comparison_object = {"candidates": rows}
    if key != "candidates":
        comparison_object = {key: comparison_object.pop("candidates")}
    if selected_path == "comparison":
        comparison_object["selected_structure_id"] = "different-id" if selected_id else rows[0]["structure_id"]
    elif selected_path == "root":
        return {"comparison": comparison_object, "root_selected": rows[0]["structure_id"]}
    return {"comparison": comparison_object}


def parsed_payload(comparison_data, hypothesis_ids=("h1",), parent_id="h1", deployed_ids=None):
    deployed_ids = deployed_ids if deployed_ids is not None else ["char_123_fang"]
    deploy_actions = [
        {
            "action_type": "DEPLOY",
            "frame": 30 * (index + 1),
            "operator_id": operator_id,
            "tile": [3, 4],
            "direction": "RIGHT",
        }
        for index, operator_id in enumerate(deployed_ids)
    ]
    return {
        "revised_operational_plans": [{
            "operational_plan_id": "R8_7_GPT_TEST_V1",
            "parent_hypothesis_id": parent_id,
            "tactical_thesis": "contract regression",
            "selected_low_star_operator_ids": list(deployed_ids),
            "deployment_positions_and_directions": [],
            "formation_structure": {},
            "formation_transitions": [],
            "corridor_responsibilities": [],
            "pressure_window_responsibilities": [],
            "skill_intents": [],
            "mandatory_tactical_invariants": [],
            "action_timeline": deploy_actions,
        }],
        "revised_stage_understanding": {
            "m58_open_roster_comparison": comparison_data["comparison"],
        },
        "revised_strategic_hypotheses": [
            {"hypothesis_id": hypothesis_id} for hypothesis_id in hypothesis_ids
        ],
        "revised_tactical_requirements": {},
        "revision_hypothesis": {
            "hypothesis_id": parent_id,
            "parent_plan_id": "R8_7_PARENT",
            "operational_plan_id": "R8_7_GPT_TEST_V1",
            "referenced_experience_ids": ["M60_FEEDBACK"],
            "tactical_hypothesis": "One hypothesis may be referenced by the selected plan.",
            "changed_responsibilities": ["Move the comparison selected ID to the nested contract path."],
            "expected_first_observable_event": {
                "event_type": "DEPLOY",
                "source_id": None,
                "target_id": deployed_ids[0],
                "earliest_frame": 30,
                "latest_frame": 30,
            },
            "if_expected_event_absent": "The first contract observation does not validate.",
        },
        **({"selected_structure_id": comparison_data["root_selected"]} if "root_selected" in comparison_data else {}),
    }


def evidence(limit=8):
    return {
        "m58_open_roster_policy": {"minimum_structure_candidates": 3},
        "milestone_constraints": {"max_unique_deployed_operator_ids": limit},
    }


def assert_contains(errors: list[str], expected: str) -> None:
    assert any(expected in error for error in errors), errors


def test_future_prompt_uses_single_nested_selected_path() -> None:
    prompt = gpt_runner.build_prompt({
        "stage_active_facts": {"roadblock_plan_tiles_row_col": [[1, 2]]},
        "m58_open_roster_policy": {"minimum_structure_candidates": 3},
    })
    assert "set `selected_structure_id` exactly at `revised_stage_understanding.m58_open_roster_comparison.selected_structure_id`" in prompt
    assert "set top-level `selected_structure_id`" not in prompt
    assert "repeating all comparison structures as separate hypotheses is not required" in prompt


def test_three_candidates_and_one_hypothesis_pass_future_schema() -> None:
    schema = gpt_runner.apply_open_roster_contract_schema(gpt_runner.experience.add_revision_hypothesis_schema({
        "type": "object",
        "additionalProperties": True,
        "required": ["revised_operational_plans", "revised_stage_understanding", "revised_tactical_requirements", "revised_strategic_hypotheses"],
        "properties": {
            "revised_operational_plans": {"type": "array", "minItems": 1, "maxItems": 1},
            "revised_stage_understanding": {"type": "object"},
            "revised_tactical_requirements": {"type": "object"},
            "revised_strategic_hypotheses": {"type": "array"},
        },
    }))
    parsed = parsed_payload(comparison(), ("h1",))
    assert not list(Draft7Validator(schema).iter_errors(parsed))
    assert not gpt_runner.validate_open_roster_contract(parsed, evidence())


def test_root_selected_contenders_missing_duplicate_and_inconsistent_are_rejected() -> None:
    cases = {
        "root_selected": comparison(selected_path="root"),
        "contenders": comparison(key="contenders"),
        "missing_selected": comparison(selected_path="none"),
        "duplicate_ids": comparison(("same", "same", "other")),
        "multiple_selected": comparison(selected_count=2),
        "selected_mismatch": comparison(selected_id="other"),
    }
    expected = {
        "root_selected": "remove the JSON root-level field",
        "contenders": "must not use contenders",
        "missing_selected": "selected_structure_id is required at",
        "duplicate_ids": "must be distinct",
        "multiple_selected": "exactly one selected candidate",
        "selected_mismatch": "must reference one comparison candidate",
    }
    for name, comparison_data in cases.items():
        errors = gpt_runner.validate_open_roster_contract(parsed_payload(comparison_data), evidence())
        assert_contains(errors, expected[name])

    inconsistent = comparison()
    inconsistent["comparison"]["selected_structure_id"] = "b"
    errors = gpt_runner.validate_open_roster_contract(parsed_payload(inconsistent), evidence())
    assert_contains(errors, "must equal the unique selected candidate structure_id")


def test_parent_hypothesis_must_exist() -> None:
    errors = gpt_runner.validate_parent_hypothesis_reference(parsed_payload(comparison(), parent_id="missing"))
    assert_contains(errors, "parent_hypothesis_id must reference")


def test_operator_union_limit_is_eight_not_nine() -> None:
    eight_ids = [f"char_{index:03d}_test" for index in range(8)]
    assert not gpt_runner.validate_open_roster_contract(
        parsed_payload(comparison(), deployed_ids=eight_ids), evidence()
    )
    errors = gpt_runner.validate_open_roster_contract(
        parsed_payload(comparison(), deployed_ids=eight_ids + ["char_999_ninth"]), evidence()
    )
    assert_contains(errors, "hard limit is 8")


def test_catalog_and_star_checks_cover_selected_and_action_ids() -> None:
    module = load_low_star_runner()
    catalog_evidence = {
        "stage_active_facts": {
            "roadblock_tiles_col_row": module.ROADBLOCK_TILES_COL_ROW,
            "active_device_tiles_col_row": [],
            "deployable_ground_tiles_col_row": [[4, 3]],
            "deployable_high_ground_tiles_col_row": [[2, 2]],
        },
        "normal_low_star_catalog": [{
            "operator_id": "char_123_fang",
            "identity": {"rarity": 3, "position": "MELEE"},
            "qualification": {"normal_mode": True},
        }],
    }
    valid = parsed_payload(comparison(), deployed_ids=["char_123_fang"])
    valid["revised_stage_understanding"] = {}
    assert not module.validate_operational_plan_output(valid, catalog_evidence)

    outside = parsed_payload(comparison(), deployed_ids=["char_328_cammou"])
    outside["revised_stage_understanding"] = {}
    errors = module.validate_operational_plan_output(outside, catalog_evidence)
    assert_contains(errors, "unknown selected operator char_328_cammou")
    assert_contains(errors, "unknown action[0] operator char_328_cammou")

    four_star = dict(catalog_evidence["normal_low_star_catalog"][0])
    four_star = {
        "operator_id": "char_999_high",
        "identity": {"rarity": 4, "position": "MELEE"},
        "qualification": {"normal_mode": True},
    }
    catalog_evidence["normal_low_star_catalog"].append(four_star)
    errors = module.validate_operational_plan_output(
        parsed_payload(comparison(), deployed_ids=["char_999_high"]), catalog_evidence
    )
    assert_contains(errors, "outside ordinary 1-3 star domain: char_999_high")
