from __future__ import annotations

import run_gpt_tactical_stage_session_v1 as runner


def test_stage_prompt_pins_plan_identity_and_roadblock_coordinate_conversion() -> None:
    original = (runner.STAGE_ID, runner.PLAN_ID, runner.PLAN_LABEL)
    try:
        runner.STAGE_ID = "main_08-02"
        runner.PLAN_ID = "R8_2_GPT_V3"
        runner.PLAN_LABEL = "R8-2-V3"
        prompt = runner.build_prompt({})
        assert '"operational_plan_id": "R8_2_GPT_V3"' in prompt
        assert "roadblock_tiles_col_row` is [col,row]" in prompt
        assert "forbids DEPLOY [row,col]=[3,5]" in prompt
    finally:
        runner.STAGE_ID, runner.PLAN_ID, runner.PLAN_LABEL = original
