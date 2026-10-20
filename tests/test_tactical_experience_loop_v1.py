from __future__ import annotations

import json
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest import mock
import pytest

import codex_model_authorization_v1 as authorization
import run_gpt_tactical_stage_session_v1 as runner
import tactical_experience_v1 as experience


def _record(experience_id: str, category: str, mechanics: str = "m23", status: str = "EVIDENCE_SUPPORTED") -> dict:
    return {
        "experience_id": experience_id,
        "stage_id": "main_08-07",
        "mechanics_version": mechanics,
        "code_commit_sha256": "test",
        "game_data_sha256": "test",
        "source_plan_id": "PARENT",
        "source_artifact_sha256": "0" * 64,
        "failure_category": category,
        "status": status,
        "applicable_conditions": ["test"],
        "verified_events": ["event"],
        "evidence_paths": ["evidence"],
        "supported_hypotheses": [],
        "refuted_hypotheses": [],
        "unproven": [],
        "responsibility_tags": ["contract"],
        "relevant_operator_ids": ["char_212_ansel"],
    }


def test_category_scoped_retrieval_excludes_invalidated_and_marks_status() -> None:
    records = [
        _record("INVALID", "LEGAL_BATTLE_LOSS", status="INVALIDATED"),
        _record("CANDIDATE", "LEGAL_BATTLE_LOSS", status="CANDIDATE_REFLECTION"),
        _record("EVIDENCE", "LEGAL_BATTLE_LOSS"),
        _record("CONTRACT", "CONTRACT_INVALID"),
    ]
    battle = experience.retrieve_experiences(
        records, stage_id="main_08-07", mechanics_version="m23",
        failure_category="LEGAL_BATTLE_LOSS", responsibility_tags={"contract"},
        operator_ids={"char_212_ansel"}, limit=2,
    )
    assert [record["experience_id"] for record in battle] == ["EVIDENCE", "CANDIDATE"]
    assert battle[0]["applicability_status"] == "CURRENT_MECHANICS"
    assert battle[0]["status"] != "EVIDENCE_SUPPORTED" or battle[0]["experience_id"] == "EVIDENCE"
    assert battle[1]["status"] == "CANDIDATE_REFLECTION"


def test_exact_plan_counterexample_wins_over_older_id() -> None:
    records = [_record("OLD", "CONTRACT_INVALID"), _record("EXACT", "CONTRACT_INVALID")]
    records[1]["source_plan_id"] = "EXACT_SOURCE"
    retrieved = experience.retrieve_experiences(
        records, stage_id="main_08-07", mechanics_version="m23",
        failure_category="CONTRACT_INVALID", responsibility_tags={"contract"},
        source_plan_id="EXACT_SOURCE", limit=1,
    )
    assert [record["experience_id"] for record in retrieved] == ["EXACT"]


def test_stale_mechanics_experience_is_marked_for_revalidation() -> None:
    record = _record("OLD", "LEGAL_BATTLE_LOSS", mechanics="m22")
    retrieved = experience.retrieve_experiences(
        [record], stage_id="main_08-07", mechanics_version="m23",
        failure_category="LEGAL_BATTLE_LOSS", responsibility_tags={"contract"},
        operator_ids={"char_212_ansel"}, limit=1,
    )
    assert retrieved[0]["applicability_status"] == "REQUIRES_REVALIDATION"


def test_changed_game_data_requires_revalidation_even_with_current_mechanics() -> None:
    record = _record("DATA", "LEGAL_BATTLE_LOSS", mechanics="m23")
    retrieved = experience.retrieve_experiences(
        [record], stage_id="main_08-07", mechanics_version="m23",
        game_data_sha256="different", limit=1,
    )
    assert retrieved[0]["applicability_status"] == "REQUIRES_REVALIDATION"


def test_real_event_protocol_and_alias_semantics() -> None:
    parsed = {
        "revision_hypothesis": {
            "expected_first_observable_event": {
                "event_type": "ENEMY_BLOCKED", "source_id": "char_192_falco",
                "target_id": "enemy_1108_uterer#1", "earliest_frame": 471, "latest_frame": 471,
            }
        }
    }
    evaluated = experience.evaluate_revision_hypothesis(parsed, [
        {"event_type": "BLOCK", "source_id": "char_192_falco", "target_id": "enemy_1108_uterer#1", "frame": 471}
    ])
    assert evaluated["status"] == "VERIFIED"
    assert evaluated["query"]["event_type"] == "BLOCK"
    assert evaluated["query"]["event_type_declared"] == "ENEMY_BLOCKED"

    parsed["revision_hypothesis"]["expected_first_observable_event"] = {
        "event_type": "OPERATOR_DEATH", "source_id": "char_283_midn",
        "target_id": None, "earliest_frame": 1680, "latest_frame": 1680,
    }
    observed = experience.evaluate_revision_hypothesis(parsed, [
        {"event_type": "OPERATOR_DEATH", "source_id": "char_283_midn", "target_id": None, "frame": 1680}
    ])
    assert observed["status"] == "VERIFIED"
    absent = experience.evaluate_revision_hypothesis(parsed, [], observation_complete=True)
    assert absent["status"] == "EVENT_NOT_OBSERVED"
    incomplete = experience.evaluate_revision_hypothesis(parsed, [], observation_complete=False)
    assert incomplete["status"] == "UNKNOWN"
    invalid = experience.evaluate_revision_hypothesis({
        "revision_hypothesis": {"expected_first_observable_event": {"event_type": "UNDECLARED_EVENT"}}
    }, [])
    assert invalid["status"] == "INVALID_QUERY"


def test_operator_death_subject_semantics_rejects_targeted_query() -> None:
    parsed = {
        "revision_hypothesis": {
            "expected_first_observable_event": {
                "event_type": "OPERATOR_DEATH", "source_id": "char_283_midn",
                "target_id": "char_283_midn", "earliest_frame": 0, "latest_frame": 1,
            }
        }
    }
    evaluated = experience.evaluate_revision_hypothesis(parsed, [], observation_complete=True)
    assert evaluated["status"] == "INVALID_QUERY"
    assert evaluated["reason"] == "OPERATOR_DEATH_TARGET_MUST_BE_NULL"


def test_protected_target_last_hit_is_not_assumed_artillery() -> None:
    path = Path("docs/review/fc77177/m26_tactical_experience_records_v1.json")
    records = experience.load_experience_records(path)
    by_id = {record["experience_id"]: record for record in records}
    assert by_id["M26-EXP-0007"]["status"] == "INVALIDATED"
    corrected = by_id["M26-EXP-0008"]
    events = {event["target_id"]: event for event in corrected["verified_events"]}
    assert events["enemy_3001_upeopl#3"]["last_hit_source_id"] == "enemy_1112_emppnt#0"
    assert events["enemy_3001_upeopl#14"]["last_hit_source_id"] == "enemy_1107_uoffcr#18"
    assert "M26-EXP-0007" not in experience.retrieve_experiences(
        records, stage_id="main_08-07", mechanics_version="m23-behavioral-mechanics-v1",
        failure_category="LEGAL_BATTLE_LOSS", responsibility_tags={"protected_target"},
        limit=3,
    )


def test_branch_slots_use_context_and_win_hard_gate() -> None:
    state = {"frozen_baselines": {"r8_2": "FROZEN"}}
    def candidate(candidate_id: str, classification: str, result: dict) -> dict:
        return {
            "candidate_id": candidate_id, "parent_plan_id": "ROOT",
            "operational_plan_id": candidate_id, "classification": classification,
            "stage_id": "main_08-07", "mechanics_version": "m23",
            "objective_scope": experience.objective_scope(result),
            "revision_hypothesis": {"hypothesis_id": candidate_id}, "result": result,
        }
    loss = candidate("LOSS", "C_LEGAL_BATTLE_LOSS", {"win": False, "enemies_leaked": 17})
    loss_less = candidate("LOSS_LESS", "C_LEGAL_BATTLE_LOSS", {"win": False, "enemies_leaked": 5})
    win = candidate("WIN", "D_CURRENT_MODEL_WIN", {
        "win": True, "enemies_leaked": 1, "protected_target_deaths": 0,
        "protected_targets_reached": 2, "expected_protected_target_count": 2,
    })
    win_perfect = candidate("WIN_PERFECT", "D_CURRENT_MODEL_WIN", {
        "win": True, "enemies_leaked": 0, "protected_target_deaths": 0,
        "protected_targets_reached": 2, "expected_protected_target_count": 2,
    })
    state = experience.update_branch_state(state, loss)
    assert state["current_best"] is None
    assert state["exploration"]["candidate_id"] == "LOSS"
    state = experience.update_branch_state(state, loss_less)
    assert state["exploration"]["candidate_id"] == "LOSS_LESS"
    state = experience.update_branch_state(state, win)
    assert state["current_best"]["candidate_id"] == "WIN"
    state = experience.update_branch_state(state, win_perfect)
    assert state["current_best"]["candidate_id"] == "WIN_PERFECT"
    assert state["frozen_baselines"]["r8_2"] == "FROZEN"


def test_incompatible_win_context_is_not_silently_merged() -> None:
    state = {
        "current_best": {"candidate_id": "OLD", "stage_id": "r8_1", "mechanics_version": "m23", "objective_scope": {"win": True}},
        "candidates": [],
    }
    candidate = {
        "candidate_id": "NEW", "parent_plan_id": "ROOT", "operational_plan_id": "NEW",
        "classification": "D_CURRENT_MODEL_WIN", "stage_id": "r8_7", "mechanics_version": "m23",
        "objective_scope": {"win": True}, "revision_hypothesis": {}, "result": {"win": True},
    }
    updated = experience.update_branch_state(state, candidate)
    assert updated["current_best"]["candidate_id"] == "OLD"
    assert updated["comparison_conflicts"][0]["reason"] == "INCOMPATIBLE_CONTEXT_FOR_CURRENT_BEST"


def test_parent_plan_id_extracts_root_and_nested_forms() -> None:
    assert experience.extract_parent_plan_id({"parent_plan_id": "ROOT"}) == "ROOT"
    assert experience.extract_parent_plan_id({
        "revised_operational_plans": [{"operational_plan_id": "CHILD", "parent_plan_id": "ROOT"}]
    }) == "ROOT"


def test_previous_plan_id_and_declared_parent_are_separate() -> None:
    previous = {"operational_plan_id": "PARENT"}
    current = {
        "revision_hypothesis": {"parent_plan_id": "PARENT"},
        "revised_operational_plans": [{"operational_plan_id": "CHILD", "parent_plan_id": "PARENT"}],
    }
    assert experience.extract_operational_plan_id(previous) == "PARENT"
    assert experience.extract_declared_parent_plan_id(current) == "PARENT"
    assert experience.extract_parent_plan_id(current["revised_operational_plans"][0]) == "PARENT"


def test_one_of_two_protected_targets_is_not_perfect_and_unknown_count_is_unknown() -> None:
    one = experience.objective_scope({
        "win": True, "enemies_leaked": 0, "protected_target_deaths": 0,
        "protected_targets_reached": 1,
    }, expected_protected_target_count=2)
    assert one["protected_targets_all_reached"] is False
    assert one["perfect"] is False
    unknown = experience.objective_scope({
        "win": True, "enemies_leaked": 0, "protected_target_deaths": 0,
        "protected_targets_reached": 1,
    })
    assert unknown["protected_targets_all_reached"] is None
    assert unknown["perfect"] is None
    none_required = experience.objective_scope({
        "win": True, "enemies_leaked": 0, "protected_target_deaths": 0,
        "protected_targets_reached": 0,
    }, expected_protected_target_count=0)
    assert none_required["protected_targets_all_reached"] is True
    assert none_required["perfect"] is True


def test_authorization_rejects_medium_without_subprocess() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        config_path = Path(temporary) / "auth.json"
        config_path.write_text(json.dumps({
            "schema_version": authorization.AUTHORIZATION_SCHEMA_VERSION,
            "provider": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high",
            "extra_config_values": [],
        }))
        command = ["codex", "exec", "--json", "--sandbox", "read-only", "-m", "gpt-6.1-sol", "-c", 'model_provider="openai"', "-c", 'model_reasoning_effort="medium"']
        with mock.patch.object(subprocess, "run") as process:
            with __import__("pytest").raises(RuntimeError, match="reasoning_effort"):
                authorization.validate_cli_authorization(config_path, command)
            assert process.call_count == 0


@contextmanager
def temp_authorization_config():
    with tempfile.TemporaryDirectory() as temporary:
        config_path = Path(temporary) / "auth.json"
        config_path.write_text(json.dumps({
            "schema_version": authorization.AUTHORIZATION_SCHEMA_VERSION,
            "provider": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high",
            "extra_config_values": ["features.apps=false"],
        }))
        yield config_path


def test_real_build_command_high_authorization_is_accepted() -> None:
    with temp_authorization_config() as config_path:
        with (
            mock.patch.object(runner.codex_runner, "REASONING_EFFORT", "high"),
            mock.patch.object(runner.codex_runner, "EXTRA_CONFIG_VALUES", ["features.apps=false"]),
        ):
            command = runner.codex_runner.build_command(Path("output/test/final.txt"))
        result = authorization.validate_cli_authorization(config_path, command)
    assert result["status"] == "AUTHORIZED"
    assert result["effective_configuration"]["features.apps"] == "false"


def test_real_build_command_medium_or_conflict_is_rejected_before_start() -> None:
    with temp_authorization_config() as config_path:
        with (
            mock.patch.object(runner.codex_runner, "REASONING_EFFORT", "medium"),
            mock.patch.object(runner.codex_runner, "EXTRA_CONFIG_VALUES", ["features.apps=false"]),
        ):
            command = runner.codex_runner.build_command(Path("output/test/final.txt"))
        with pytest.raises(RuntimeError, match="configuration value mismatch"):
            authorization.validate_cli_authorization(config_path, command)
        with (
            mock.patch.object(runner.codex_runner, "REASONING_EFFORT", "high"),
            mock.patch.object(runner.codex_runner, "EXTRA_CONFIG_VALUES", ["features.apps=false"]),
        ):
            conflict_command = runner.codex_runner.build_command(Path("output/test/final.txt"))
        conflict_command[conflict_command.index("-m") - 2:conflict_command.index("-m") - 2] = [
            "-c", 'model_reasoning_effort="medium"',
        ]
        with pytest.raises(RuntimeError, match="duplicate configuration override key"):
            authorization.validate_cli_authorization(config_path, conflict_command)


def test_m26_experience_store_is_valid_and_has_correction() -> None:
    records = experience.load_experience_records(Path("docs/review/fc77177/m26_tactical_experience_records_v1.json"))
    assert len(records) == 10
    assert {record["experience_id"] for record in records} == {f"M26-EXP-{index:04d}" for index in range(1, 9)} | {"M28-EXP-0001", "M28-EXP-0002"}
    newest = next(record for record in records if record["experience_id"] == "M28-EXP-0002")
    assert newest["failure_category"] == "LEGAL_BATTLE_LOSS"


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


def test_prompt_declares_protected_target_perfect_scope() -> None:
    prompt = runner.build_prompt({
        "stage_active_facts": {"roadblock_plan_tiles_row_col": [[5, 2]]},
        "model_spawn_timeline": {"events": [
            {"enemy_id": "enemy_3001_upeopl", "count": 1},
            {"enemy_id": "enemy_3001_upeopl", "count": 1},
        ]},
    }, {})
    assert "all 2 expected protected targets safely reaching" in prompt
    assert "operator deaths are recorded separately" in prompt
    assert "OUTPUT_SCHEMA_JSON" in prompt
