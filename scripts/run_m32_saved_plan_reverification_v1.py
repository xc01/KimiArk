from __future__ import annotations

import argparse
import json
from pathlib import Path

import tactical_evaluation_gate_v1 as gate
from run_gpt_tactical_stage_diagnostic_v1 import run_full_diagnostic


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("diagnostic_output_dir", type=Path)
    parser.add_argument("budget_path", type=Path)
    parser.add_argument("--stage-id", required=True)
    parser.add_argument("--plan-id", required=True)
    arguments = parser.parse_args()

    with gate.consume_evaluation(
        source_dir=arguments.source_dir,
        diagnostic_output_dir=arguments.diagnostic_output_dir,
        budget_path=arguments.budget_path,
        stage_id=arguments.stage_id,
        expected_plan_id=arguments.plan_id,
    ) as gate_result:
        if gate_result["status"] != "AUTHORIZED":
            return
        summary = run_full_diagnostic(
            source=arguments.source_dir,
            out=arguments.diagnostic_output_dir,
            stage_id=arguments.stage_id,
            plan_id=arguments.plan_id,
        )
        gate_record = dict(gate_result)
        gate_record["reservation_status"] = "COMPLETED"
        (arguments.diagnostic_output_dir / "evaluation_gate.json").write_text(
            json.dumps(gate_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "plan_id": arguments.plan_id,
        "classification": summary["classification"],
        "result": summary["result"],
        "budget_path": str(arguments.budget_path),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
