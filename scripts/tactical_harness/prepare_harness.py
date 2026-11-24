#!/usr/bin/env python3
"""KimiArk reusable tactical-experiment harness: batch preparation (no model, no simulation).

Parameterised replacement for the hand-copied per-batch ``prepare.py`` files. It does NOT
write tactics: it registers parent plans from any existing batch archive, derives a canonical
evidence bundle, and lays down the session/ledger/budget/authorization files that the
production closed-loop service already understands.

Nothing here starts a model or a simulation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION  # noqa: E402


def read(path: Path):
    path = Path(path)
    if not path.exists() and Path(str(path) + ".gz").exists():
        import gzip

        return json.loads(gzip.decompress(Path(str(path) + ".gz").read_bytes()))
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact_catalog() -> list[dict]:
    from run_r8_1_low_star_full_tactical_closure_v1 import compact_operator_catalog

    return compact_operator_catalog()


def resolve_candidate_source(spec: str):
    """spec = alias=<path-to-batch-dir>[:candidate-id]

    - With candidate-id: read that candidate's frozen source + simulation artifacts.
    - Without: treat <dir> as a directory holding llm_structured_output.json / llm_evidence_context.json
      (the R129-style parent bundle) and optional diagnostic_events.json / diagnostic_summary.json.
    """
    alias, _, rest = spec.partition("=")
    if not alias or not rest:
        raise SystemExit(f"--parent must be alias=path[:candidate-id], got {spec!r}")
    directory, _, candidate_id = rest.partition(":")
    directory = Path(directory)
    if not directory.is_absolute():
        directory = ROOT / directory
    evidence_path = None
    if candidate_id:
        root = directory / "session" / "candidates" / candidate_id
        payload_path = root / "source" / "llm_structured_output.json"
        evidence_path = root / "source" / "llm_evidence_context.json"
        events_path = root / "simulation" / "diagnostic_events.json"
        summary_path = root / "simulation" / "diagnostic_summary.json"
    else:
        payload_path = directory / "llm_structured_output.json"
        evidence_path = directory / "llm_evidence_context.json"
        events_path = directory / "diagnostic_events.json"
        summary_path = directory / "diagnostic_summary.json"
    if not payload_path.is_file():
        raise SystemExit(f"parent payload not found: {payload_path}")
    payload = read(payload_path)
    plan = payload.get("revised_operational_plans", [{}])[0]
    record = {
        "alias": alias,
        "source_dir": str(directory.relative_to(ROOT)) if directory.is_relative_to(ROOT) else str(directory),
        "candidate_id": candidate_id or None,
        "payload": payload,
        "plan_id": plan.get("operational_plan_id"),
        "payload_path": str(payload_path.relative_to(ROOT)),
        "payload_sha256": sha(payload_path),
        "evidence_path": str(evidence_path.relative_to(ROOT)) if evidence_path and evidence_path.is_file() else None,
        "evidence": read(evidence_path) if evidence_path and evidence_path.is_file() else None,
        "events": read(events_path).get("events") if events_path.is_file() else None,
        "summary": read(summary_path) if summary_path.is_file() else None,
    }
    return record


def build_evidence(template_evidence: dict, *, fixed_roster, max_operators: int, plan_label: str):
    """Derive the canonical execution evidence from a full template bundle."""
    context = copy.deepcopy(template_evidence)
    context["mechanics_version"] = ACTIVE_MECHANICS_VERSION
    context["normal_low_star_catalog"] = compact_catalog()
    manifest = read(ROOT / "output/normal_low_star_facts_v1/manifest.json")
    sources = {Path(row["path"]).name: row for row in manifest["outputs"]}
    source = context.setdefault("normal_low_star_capability_source", {})
    source["facts_sha256"] = sources["normal_low_star_facts.json"]["sha256"]
    source["support_sha256"] = sources["normal_low_star_mechanism_support.json"]["sha256"]
    milestone = {"max_unique_deployed_operator_ids": max_operators}
    if fixed_roster:
        milestone["fixed_operator_ids"] = sorted(fixed_roster)
        milestone["counting_rule"] = "selected union every DEPLOY id exactly equal to the fixed roster"
    context["milestone_constraints"] = milestone
    return context


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare a reusable tactical-experiment harness batch")
    ap.add_argument("--out", required=True, help="harness batch directory (repository-relative)")
    ap.add_argument("--template-evidence", required=True, help="a full llm_evidence_context.json to derive from")
    ap.add_argument("--template-schema", required=True, help="revision_output_schema.json paired with the evidence")
    ap.add_argument("--parent", action="append", default=[], help="alias=<batch-dir>[:candidate-id] (repeatable)")
    ap.add_argument("--template-parent", default=None, help="alias to also register as an empty protocol container")
    ap.add_argument("--roster", default="open", help="open | fixed:id1,id2,...")
    ap.add_argument("--max-operators", type=int, default=7)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--max-checks", type=int, default=20)
    ap.add_argument("--max-candidates", type=int, default=5)
    ap.add_argument("--max-simulations", type=int, default=5)
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--stage-id", required=True)
    ap.add_argument("--plan-prefix", required=True)
    ap.add_argument("--plan-label", required=True)
    ap.add_argument("--model", default="gpt-test")
    ap.add_argument("--reasoning-effort", default="medium")
    ap.add_argument("--backend", default="CONTROLLED_RUNNER", choices=["CONTROLLED_RUNNER", "TEST_ONLY_FAKE"])
    ap.add_argument("--session-name", default=None, help="human label recorded in the manifest")
    ap.add_argument("--reserve-simulations", type=int, default=0, help="simulations held back for independent verification of a best candidate")
    args = ap.parse_args()

    out = ROOT / args.out
    if (out / "session_config_v1.json").exists():
        raise SystemExit(f"refusing to overwrite an existing harness batch: {out/'session_config_v1.json'}")
    if args.backend == "TEST_ONLY_FAKE":
        if not args.session_id.startswith("TEST_ONLY-") or not args.stage_id.startswith("FAKE_TEST-"):
            raise SystemExit("TEST_ONLY_FAKE requires session-id TEST_ONLY-... and stage-id FAKE_TEST-...")
    if args.reserve_simulations < 0 or args.reserve_simulations >= args.max_simulations:
        raise SystemExit("reserve-simulations must be >=0 and smaller than max-simulations")
    fixed_roster = []
    if args.roster.startswith("fixed:"):
        fixed_roster = [item for item in args.roster[len("fixed:"):].split(",") if item]

    template_evidence = read(ROOT / args.template_evidence)
    context = build_evidence(template_evidence, fixed_roster=fixed_roster, max_operators=args.max_operators, plan_label=args.plan_label)
    write(out / "input_bundle" / "template_context.json", context)
    write(out / "input_bundle" / "llm_evidence_context.json", context)
    schema = read(ROOT / args.template_schema)
    write(out / "input_bundle" / "revision_output_schema.json", schema)

    parents = {}
    registry = {}
    for spec in args.parent:
        record = resolve_candidate_source(spec)
        alias = record["alias"]
        target = out / "parents" / alias
        write(target / "payload.json", record["payload"])
        write(target / "plan.json", record["payload"].get("revised_operational_plans", [{}])[0])
        if record["evidence"] is not None:
            write(target / "evidence.json", record["evidence"])
        if record["events"] is not None:
            write(target / "events.json", {"events": record["events"]})
        if record["summary"] is not None:
            write(target / "summary.json", record["summary"])
        registry[alias] = {
            "plan_id": record["plan_id"],
            "parent_plan_id": record["payload"].get("revised_operational_plans", [{}])[0].get("parent_plan_id"),
            "payload_copy_sha256": sha(target / "payload.json"),
            "payload_source_path": record["payload_path"],
            "payload_source_sha256": record["payload_sha256"],
            "evidence_source_path": record["evidence_path"],
            "has_events": record["events"] is not None,
            "distinct_operator_union": sorted(
                set((record["payload"].get("revised_operational_plans") or [{}])[0].get("selected_low_star_operator_ids") or [])
                | {a["operator_id"] for a in ((record["payload"].get("revised_operational_plans") or [{}])[0].get("action_timeline") or []) if a.get("action_type") == "DEPLOY"}
            ),
        }
        parents[alias] = record["payload"]

    if args.template_parent:
        alias = args.template_parent
        donor = next(iter(parents.values()))
        template = copy.deepcopy(donor)
        plan = template["revised_operational_plans"][0]
        new_id = f"{args.plan_prefix}PROTOCOL_TEMPLATE"
        parent_id = plan.get("operational_plan_id")
        plan.update(
            operational_plan_id=new_id,
            parent_plan_id=parent_id,
            parent_hypothesis_id=new_id,
            action_timeline=[],
            deployment_positions_and_directions=[],
            validation_card={"status": "NO_TACTIC_NO_SIMULATION", "purpose": "empty protocol container; the tactical session supplies all actions"},
        )
        template["revision_hypothesis"].update(
            hypothesis_id=new_id,
            operational_plan_id=new_id,
            parent_plan_id=parent_id,
            tactical_hypothesis="EMPTY PROTOCOL SCAFFOLD ONLY; the tactical session authors the complete timeline",
            changed_responsibilities=["empty protocol container carries no tactical responsibility"],
        )
        template["revised_strategic_hypotheses"][0]["hypothesis_id"] = new_id
        target = out / "parents" / alias
        write(target / "payload.json", template)
        write(target / "plan.json", plan)
        registry[alias] = {
            "plan_id": new_id,
            "protocol_container": True,
            "no_events": True,
            "payload_copy_sha256": sha(target / "payload.json"),
            "distinct_operator_union": [],
        }
    write(out / "parent_registry_v1.json", registry)
    write(out / "old_action_index.json", {})

    config = {
        "schema_version": "KIMIARK_CLOSED_LOOP_SESSION_CONFIG_V1",
        "session_id": args.session_id,
        "stage_id": args.stage_id,
        "plan_id_prefix": args.plan_prefix,
        "plan_label": args.plan_label,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "features_apps": False,
        "mechanics_version": ACTIVE_MECHANICS_VERSION,
        "facts_source_dir": str((out / "input_bundle").relative_to(ROOT)),
        "session_root": str((out / "session").relative_to(ROOT)),
        "budget_path": str((out / "simulation_budget_v1.json").relative_to(ROOT)),
        "candidate_ledger_path": str((out / "candidate_ledger_v1.json").relative_to(ROOT)),
        "authorization_config_path": str((out / "model_authorization_v1.json").relative_to(ROOT)),
        "max_unique_deployed_operators": args.max_operators,
        "max_candidates": args.max_candidates,
        "max_check_calls": args.max_checks,
        "simulation_timeout_seconds": 1800,
        "execution_backend": args.backend,
        "allow_fake_execution": args.backend == "TEST_ONLY_FAKE",
    }
    write(out / "session_config_v1.json", config)
    write(out / "candidate_ledger_v1.json", {
        "schema_version": "KIMIARK_CLOSED_LOOP_CANDIDATE_LEDGER_V2",
        "session_id": args.session_id,
        "stage_id": args.stage_id,
        "max_check_calls": args.max_checks,
        "used_check_calls": 0,
        "max_candidates": args.max_candidates,
        "used_candidates": 0,
        "checks": [],
        "attempts": [],
    })
    write(out / "simulation_budget_v1.json", {
        "schema_version": "KIMIARK_STAGE_SIMULATION_BUDGET_V1",
        "stage_id": args.stage_id,
        "max_stage_simulations": args.max_simulations,
        "prior_stage_simulations": 0,
        "started_stage_simulations": 0,
    })
    write(out / "model_authorization_v1.json", {
        "schema_version": "KIMIARK_CODEX_CLI_AUTHORIZATION_V1",
        "provider": "openai",
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "features_apps": False,
        "extra_config_values": [],
        "real_cli_starts": {"authorized_real_cli_starts": 0, "used_real_cli_starts": 0, "automatic_retry": False, "automatic_resume": False},
        "scope": f"harness batch {args.session_name or args.plan_label}",
    })
    write(out / "batch_state.json", {
        "schema_version": "KIMIARK_TACTICAL_HARNESS_BATCH_STATE_V1",
        "rounds": [],
        "variants": [],
        "stopped": False,
        "cli_started": 0,
        "independent_runs": [],
        "teaching_records": [],
    })
    write(out / "batch_constraints.json", {
        "schema_version": "KIMIARK_TACTICAL_HARNESS_CONSTRAINTS_V1",
        "round_definition": "one question -> one batch of checks/runs -> decide the next step from evidence (NOT one simulation)",
        "roster_mode": "fixed" if fixed_roster else "open",
        "fixed_operator_ids": sorted(fixed_roster),
        "max_unique_deployed_operators": args.max_operators,
        "round_max": args.rounds,
        "operational_safety_ceiling": {"check": args.max_checks, "PASS_candidate": args.max_candidates, "actual_full_simulation": args.max_simulations},
        "reserved_for_independent_verification": args.reserve_simulations,
        "old_balances_transfer": False,
        "no_push": True,
    })
    if fixed_roster:
        context.setdefault("current_batch_authority", {})["fixed_operator_ids"] = sorted(fixed_roster)
        write(out / "input_bundle" / "llm_evidence_context.json", context)
        write(out / "input_bundle" / "template_context.json", context)

    manifest = {
        "schema_version": "KIMIARK_TACTICAL_HARNESS_PREPARE_MANIFEST_V1",
        "session_name": args.session_name,
        "out": str(out.relative_to(ROOT)),
        "mechanics_version": ACTIVE_MECHANICS_VERSION,
        "backend": args.backend,
        "template_evidence_path": args.template_evidence,
        "parents": registry,
        "files": {
            str(p.relative_to(out)): sha(p)
            for p in sorted(out.rglob("*"))
            if p.is_file()
        },
    }
    write(out / "harness_manifest_v1.json", manifest)
    print(json.dumps({
        "status": "PREPARED",
        "out": str(out.relative_to(ROOT)),
        "parents": sorted(registry),
        "backend": args.backend,
        "budget": {"check": args.max_checks, "candidate": args.max_candidates, "simulation": args.max_simulations},
        "rounds": args.rounds,
        "fixed_roster": sorted(fixed_roster) if fixed_roster else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
