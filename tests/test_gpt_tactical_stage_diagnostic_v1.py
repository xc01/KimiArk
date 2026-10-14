from __future__ import annotations

import run_gpt_tactical_stage_diagnostic_v1 as diagnostic


def test_validated_unique_deployments_allows_retreat_backed_redeploy() -> None:
    actions = [
        {"action_type": "DEPLOY", "operator_id": "a", "frame": 0},
        {"action_type": "RETREAT", "operator_id": "a", "frame": 10},
        {"action_type": "DEPLOY", "operator_id": "a", "frame": 20},
        {"action_type": "DEPLOY", "operator_id": "b", "frame": 30},
    ]
    assert [item["operator_id"] for item in diagnostic.validated_unique_deployments(actions)] == ["a", "b"]


def test_validated_unique_deployments_rejects_reuse_without_retreat() -> None:
    actions = [
        {"action_type": "DEPLOY", "operator_id": "a", "frame": 0},
        {"action_type": "DEPLOY", "operator_id": "a", "frame": 10},
    ]
    try:
        diagnostic.validated_unique_deployments(actions)
    except RuntimeError as exc:
        assert "source-backed RETREAT" in str(exc)
    else:
        raise AssertionError("redeploy without retreat was accepted")
