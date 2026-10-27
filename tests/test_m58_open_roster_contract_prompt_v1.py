from __future__ import annotations

import run_gpt_tactical_stage_session_v1 as runner


def test_m58_prompt_requires_exact_comparison_contract_fields() -> None:
    prompt = runner.build_prompt({
        "stage_active_facts": {"roadblock_plan_tiles_row_col": [[1, 2]]},
        "m58_open_roster_policy": {"minimum_structure_candidates": 3},
    })
    assert "Save the comparison in revised_stage_understanding.m58_open_roster_comparison" in prompt
    assert '`{"candidates":[...]}`' in prompt
    assert "Each candidate requires `structure_id`" in prompt
    assert "Exactly one candidate has `selected: true`" in prompt
    assert "set `selected_structure_id` exactly at `revised_stage_understanding.m58_open_roster_comparison.selected_structure_id`" in prompt
    assert "set top-level `selected_structure_id`" not in prompt
    assert "do not use `contenders`" in prompt
    assert "repeating all comparison structures as separate hypotheses is not required" in prompt
