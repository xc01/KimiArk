from __future__ import annotations

import json
from pathlib import Path

import run_gpt_tactical_stage_session_v1 as runner
import tactical_experience_v1 as experience


def _record(experience_id: str, category: str, mechanics: str = "m23") -> dict:
    return {
        "experience_id": experience_id,
        "stage_id": "main_08-07",
        "mechanics_version": mechanics,
        "code_commit_sha256": "test",
        "game_data_sha256": "test",
        "source_plan_id": "PARENT",
        "source_artifact_sha256": "0" * 64,
        "failure_category": category,
        "status": "EVIDENCE_SUPPORTED",
        "applicable_conditions": ["test"],
        "verified_events": ["event"],
        "evidence_paths": ["evidence"],
        "supported_hypotheses": [],
        "refuted_hypotheses": [],
        "unproven": [],
        "responsibility_tags": ["contract"],
        "relevant_operator_ids": ["char_212_ansel"],
    }


def test_category_scoped_retrieval_does_not_backfill_unrelated_records() -> None:
    records = [
        _record("BATTLE", "LEGAL_BATTLE_LOSS"),
        _record("CONTRACT", "CONTRACT_INVALID"),
    ]
    battle = experience.retrieve_experiences(
        records, stage_id="main_08-07", mechanics_version="m23",
        failure_category="LEGAL_BATTLE_LOSS", responsibility_tags={"contract"},
        operator_ids={"char_212_ansel"}, limit=2,
    )
    assert [record["experience_id"] for record in battle] == ["BATTLE"]
    assert all(record["applicability_status"] == "CURRENT_MECHANICS" for record in battle)


def test_stale_mechanics_experience_is_marked_for_revalidation() -> None:
    record = _record("OLD", "LEGAL_BATTLE_LOSS", mechanics="m22")
    retrieved = experience.retrieve_experiences(
        [record], stage_id="main_08-07", mechanics_version="m23",
        failure_category="LEGAL_BATTLE_LOSS", responsibility_tags={"contract"},
        operator_ids={"char_212_ansel"}, limit=1,
    )
    assert retrieved[0]["applicability_status"] == "REQUIRES_REVALIDATION"


def test_prompt_contains_schema_and_mandatory_revision_fields() -> None:
    schema = experience.add_revision_hypothesis_schema({
        "type": "object",
        "required": ["revised_operational_plans"],
        "properties": {
            "revised_operational_plans": {
                "type": "array", "items": {"type": "object", "required": ["operational_plan_id"]}
            }
        },
    })
    prompt = runner.build_prompt({
        "stage_active_facts": {"roadblock_plan_tiles_row_col": [[5, 2]]},
    }, schema)
    assert "MANDATORY OUTPUT CONTRACT" in prompt
    assert "revision_hypothesis" in prompt
    assert "parent_hypothesis_id must equal one of revised_strategic_hypotheses[*].hypothesis_id" in prompt
    assert '"latest_frame"' in prompt
    assert "OUTPUT_SCHEMA_JSON" in prompt


def test_revision_hypothesis_is_deterministically_verified_or_refuted() -> None:
    parsed = {
        "revision_hypothesis": {
            "expected_first_observable_event": {
                "event_type": "OPERATOR_DEATH", "source_id": None,
                "target_id": "char_212_ansel", "earliest_frame": 2200, "latest_frame": 2300,
            }
        }
    }
    verified = experience.evaluate_revision_hypothesis(parsed, [
        {"event_type": "OPERATOR_DEATH", "source_id": None, "target_id": "char_212_ansel", "frame": 2280}
    ])
    assert verified["status"] == "VERIFIED"
    assert verified["matches"][0]["frame"] == 2280
    not_verified = experience.evaluate_revision_hypothesis(parsed, [])
    assert not_verified["status"] == "NOT_VERIFIED"
    unknown = experience.evaluate_revision_hypothesis({}, [])
    assert unknown["status"] == "UNKNOWN"


def test_branch_update_preserves_frozen_baselines_and_best_slot(tmp_path: Path) -> None:
    state = {"frozen_baselines": {"r8_2": "FROZEN"}}
    parent = {
        "candidate_id": "PARENT", "parent_plan_id": "ROOT", "operational_plan_id": "PARENT",
        "classification": "C_LEGAL_BATTLE_LOSS", "revision_hypothesis": {"hypothesis_id": "H1"},
    }
    candidate = {
        "candidate_id": "CHILD", "parent_plan_id": "PARENT", "operational_plan_id": "CHILD",
        "classification": "A_CONTRACT_INVALID", "revision_hypothesis": {"hypothesis_id": "H2"},
    }
    updated = experience.update_branch_state(state, parent)
    updated = experience.update_branch_state(updated, candidate)
    assert updated["frozen_baselines"]["r8_2"] == "FROZEN"
    assert updated["current_best"]["operational_plan_id"] == "PARENT"
    assert updated["exploration"] is None
    assert [row["candidate_id"] for row in updated["candidates"]] == ["PARENT", "CHILD"]


def test_experience_store_records_are_valid() -> None:
    path = Path("docs/review/fc77177/m26_tactical_experience_records_v1.json")
    records = experience.load_experience_records(path)
    assert len(records) == 7
    assert {record["failure_category"] for record in records} == {"LEGAL_BATTLE_LOSS", "CONTRACT_INVALID"}
