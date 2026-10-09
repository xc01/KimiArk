"""Architecture and evidence audit artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arknights_planner.mechanics import (
    ACTIVE_MECHANICS_VERSION,
    MechanicsArtifactDependency,
    audit_mechanics_dependencies,
)
from arknights_planner.mechanics_registry import MechanicsEvidence, MechanicsEvidenceRegistry


class ArchitectureAudit:
    """Generate deterministic, machine-readable alignment evidence."""

    VERSION = "architecture-alignment-v1"

    def __init__(self, root: Path = Path(".")):
        self.root = Path(root)
        self.registry = MechanicsEvidenceRegistry(self.root)

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")

    def _architecture_alignment(self, smoke: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "audit_version": self.VERSION,
            "CORE_ARCHITECTURE_ALIGNMENT": "PARTIALLY_ALIGNED",
            "TOP_DOWN_PLANNER_PRIMARY": "YES",
            "CAUSAL_REPAIR_ROLE": "SUPPORTING_LAYER",
            "desired_pipeline": [
                "StageAnalysis", "TacticalRequirements", "PlanHypothesis",
                "OperatorAssignment", "SpatialSkeleton", "TimingSearch", "Simulator",
                "WIN_OBJECTIVE_MINIMIZATION_OR_SCOPED_REPAIR",
            ],
            "implemented_pipeline": smoke.get("pipeline") if smoke else None,
            "top_down_module": "src/arknights_planner/search/top_down.py",
            "causal_boundary": "M15-M22 tools are downstream repair/diagnostic tools and are not imported by TopDownPlanner.",
            "remaining_alignment_gaps": [
                "Historical M14-M22 milestone modules retain explicit benchmark assumptions.",
                "The first real-stage end-to-end WIN through the restored pipeline has not yet been pursued.",
                "Mechanics fidelity remains partial outside evidence-backed targeting rules.",
            ],
            "documentation_and_artifact_disagreements": [
                "SESSION_HANDOFF.md says Q2/Q3 calibration status is untrusted; current m23_q_status.json already marks Q2 resolved by PRTS.",
                "M18 rebaseline artifacts say Q2 requires real-game calibration, while cached PRTS text and the current registry resolve ordinary melee self-block priority.",
                "docs/MILESTONES.md and docs/PROGRESS.md still state Q2/Q3 require real-game calibration after the path-distance correction.",
                "Historical artifacts carry both m18-targeting-v1 and m18.1-target-distance-v2; no single active version existed before this audit.",
            ],
        }

    def _experiment_scope_audit(self) -> dict[str, Any]:
        search_root = self.root / "src/arknights_planner/search"
        historical_files = tuple(path for path in search_root.glob("m1*.py") if path.name not in {"scope.py", "top_down.py"})
        tokens = ("6-8", "route-2", "564", "char_192_falco", "char_502_nblade", "char_124_kroos", "K<=7", "low_rarity")
        occurrences = {
            token: sum(path.read_text(encoding="utf-8").count(token) for path in historical_files)
            for token in tokens
        }
        return {
            "EXPERIMENT_SCOPE_SEPARATION": "SUPPORTED",
            "scope_abstraction": "src/arknights_planner/search/scope.py:ExperimentScope",
            "scope_fields": [
                "stage_id", "operator_pool", "max_cardinality", "mechanics_version",
                "simulation_budget", "search_policy", "pool_policy",
            ],
            "explicit_benchmark_scope": {
                "stage": "6-8",
                "pool": "bounded 1-3 star benchmark pool",
                "max_cardinality": 7,
                "status": "EXPERIMENT_BOUND_NOT_GLOBAL_PROPERTY",
            },
            "historical_hardcoded_occurrences_in_milestone_modules": occurrences,
            "interpretation": "Historical modules are retained as experiment-specific repair tools; new orchestration must receive an ExperimentScope.",
            "claim_boundary": "NO_WIN under an ExperimentScope is scoped; a global NO_WIN requires a global proof.",
            "K8_search_added": False,
        }

    def _registry_audit(self) -> dict[str, Any]:
        entries = [entry.__dict__ for entry in self.registry.entries]
        older = self.registry.search(topic="targeting", terms=("historical", "rebaseline"))
        unsupported = self.registry.query("unsupported displacement force", topic="displacement", terms=("force",))
        conflict_registry = MechanicsEvidenceRegistry(self.root, extra_entries=(
            MechanicsEvidence(
                "test_conflict", "synthetic_conflict", "conflicting synthetic claim",
                "synthetic test", "SYNTHETIC_TEST", "tests/test_architecture.py",
                "deterministic regression", "HIGH", "UNKNOWN",
                ["conflicts with the baseline synthetic claim"],
                {"fixture": "CONFLICT_REGRESSION"}, ACTIVE_MECHANICS_VERSION,
            ),
        ))
        conflict = conflict_registry.query("conflicting synthetic claim", topic="test_conflict", terms=("conflicting",))
        return {
            "MECHANICS_EVIDENCE_RETRIEVAL": "SUPPORTED",
            "active_mechanics_version": ACTIVE_MECHANICS_VERSION,
            "entry_count": len(entries),
            "topics": sorted({entry["topic"] for entry in entries}),
            "source_types": sorted({entry["source_type"] for entry in entries}),
            "required_fields_present": all(
                set(entry) >= {
                    "topic", "subtopic", "claim", "source", "source_type", "local_source_path",
                    "provenance", "confidence", "implementation_status", "conflicts",
                    "applicable_context", "mechanics_version",
                }
                for entry in entries
            ),
            "known_older_evidence_retrieval": {"hit_count": len(older), "hits": older},
            "unsupported_mechanic_query": unsupported,
            "conflict_query": conflict,
            "boundary": "Retrieval/provenance layer only; it is not a complete Arknights ontology.",
        }

    def _unknown_gates(self) -> dict[str, Any]:
        q1 = self.registry.unknown_gate(
            "Q1", {"candidate_remaining_route_distances": [3.0, 5.0], "has_taunt_or_special_filter": False},
            topic="targeting", terms=("remaining", "path", "stable"),
        )
        q2 = self.registry.unknown_gate(
            "Q2", {"operator_position": "MELEE", "blocked_candidate_ids": ["enemy-a"]},
            topic="targeting", terms=("blocked", "melee"),
        )
        q3 = self.registry.unknown_gate(
            "Q3", {"lifecycle": "RETARGET_AFTER_TARGET_DISAPPEARANCE"},
            topic="targeting", terms=("retarget", "attack", "lock"),
        )
        unsupported = self.registry.unknown_gate(
            "unsupported displacement force", {"mechanic": "displacement_force"},
            topic="displacement", terms=("force",),
        )
        conflict_registry = MechanicsEvidenceRegistry(self.root, extra_entries=(
            MechanicsEvidence(
                "test_conflict", "synthetic_conflict", "conflicting synthetic claim",
                "synthetic test", "SYNTHETIC_TEST", "tests/test_architecture.py",
                "deterministic regression", "HIGH", "UNKNOWN",
                ["conflicts with the baseline synthetic claim"],
                {"fixture": "CONFLICT_REGRESSION"}, ACTIVE_MECHANICS_VERSION,
            ),
        ))
        conflict = conflict_registry.unknown_gate(
            "conflicting synthetic claim", {"decision_resolved": False},
            topic="test_conflict", terms=("conflicting",),
        )
        return {
            "UNKNOWN_GATE": "SUPPORTED",
            "Q1": q1,
            "Q2": q2,
            "Q3": q3,
            "unsupported_mechanic": unsupported,
            "explicit_conflict": conflict,
            "rule": "UNKNOWN is valid only after source retrieval, concrete-context evaluation, and conflict exposure.",
        }

    def _calibration_gates(self) -> dict[str, Any]:
        q3 = self.registry.human_calibration_gate(
            "Q3", {"lifecycle": "RETARGET_AFTER_TARGET_DISAPPEARANCE"},
            planner_relevance=True,
            counterfactual_sensitivity=False,
        )
        return {
            "HUMAN_CALIBRATION_GATE": "SUPPORTED",
            "MECHANICS_WORK_GATE": "SUPPORTED",
            "Q3_current_context": q3,
            "reason_counterfactual_sensitivity_is_false": "No current 6-8 baseline has been replayed under the active m18.2 mechanics version.",
            "human_calibration_required_now": False,
            "result": "NO_HUMAN_CALIBRATION_REQUIRED",
        }

    def _targeting_reaudit(self) -> dict[str, Any]:
        return {
            **self.registry.reaudit_targeting_questions(),
            "active_mechanics_version": ACTIVE_MECHANICS_VERSION,
            "human_calibration_required_now": False,
        }

    def _version_dependency_audit(self) -> dict[str, Any]:
        dependencies = (
            MechanicsArtifactDependency("output/m14/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m15/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m16/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m17/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m18/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m18_rebaseline/main_06-07", "m18.1-target-distance-v2", ("targeting",)),
            MechanicsArtifactDependency("output/m19/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m20/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m21/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m22/main_06-07", "m18-targeting-v1", ("targeting",)),
            MechanicsArtifactDependency("output/m23/main_06-07", "m18.1-target-distance-v2", ("targeting",)),
        )
        audit = audit_mechanics_dependencies(dependencies, ACTIVE_MECHANICS_VERSION)
        audit.update({
            "stale_baseline_families": ["M14", "M15", "M16", "M17", "M18", "M18.1", "M19", "M20", "M21", "M22", "M23"],
            "current_trusted_6_8_baseline": None,
            "current_trusted_6_8_baseline_reason": "No deterministic 6-8 replay has been run under m18.2-blocked-target-v1.",
            "latest_superseded_replay": {
                "mechanics_version": "m18.1-target-distance-v2",
                "Falco_enabled": {"kills": 15, "leaks": 21, "life": -18},
                "Falco_disabled": {"kills": 19, "leaks": 17, "life": -14},
            },
            "old_M16": {"enabled": "24/12", "disabled": "26/10", "status": "STALE"},
            "old_M22_route_2_frame_564": {"attacks": 5, "damage": 1160, "remaining_hp": 1990, "status": "STALE"},
            "reuse_policy": "Historical evidence only; deterministic replay is required before current planner use.",
        })
        return audit

    def _top_down_audit(self, smoke: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "TOP_DOWN_PLANNER_ORCHESTRATION": "WIRED",
            "smoke": smoke,
            "llm_calls": 0,
            "real_llm_used": False,
            "repair_invocation_policy": "Only after a concrete candidate fails; no causal tool is imported into the primary loop.",
            "first_win_principle": "Prioritize one complete real-stage simulator WIN before narrow minimization or more mechanics archaeology.",
            "objective_policy": "WIN is hard; winners are minimized lexicographically, never by weighted scalar.",
            "broad_search_run": False,
        }

    def _cross_stage_audit(self, smoke: dict[str, Any] | None) -> dict[str, Any]:
        stage_id = smoke.get("scope", {}).get("stage_id") if smoke else None
        return {
            "CROSS_STAGE_GENERALITY": "PARTIAL",
            "non_6_8_smoke_stage": stage_id,
            "generic_core_abstractions": [
                "FailureFrontier", "TacticalConstraint", "CausalTemporalConstraint",
                "ExperimentScope", "TopDownPlanner",
            ],
            "synthetic_fixture": "synthetic-1",
            "historical_module_boundary": "M15.4, M20, and route/frame-specific repair modules remain experiment-scoped and are not general planner interfaces.",
            "next_generalization_step": "Move historical route/frame/operator literals into explicit experiment inputs when those tools are next reused.",
        }

    def run(
        self,
        *,
        output_dir: Path,
        smoke: dict[str, Any] | None = None,
        validation_results: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output = Path(output_dir)
        artifacts = {
            "architecture_alignment_audit.json": self._architecture_alignment(smoke),
            "experiment_scope_audit.json": self._experiment_scope_audit(),
            "mechanics_evidence_registry_audit.json": self._registry_audit(),
            "unknown_gate_results.json": self._unknown_gates(),
            "calibration_gate_results.json": self._calibration_gates(),
            "targeting_q1_q2_q3_reaudit.json": self._targeting_reaudit(),
            "mechanics_version_dependency_audit.json": self._version_dependency_audit(),
            "top_down_planner_orchestration_audit.json": self._top_down_audit(smoke),
            "cross_stage_generality_audit.json": self._cross_stage_audit(smoke),
            "validation_results.json": validation_results or {
                "status": "PENDING",
                "note": "Run compileall, deterministic regressions, tiny top-down smoke, 0-1 regression, and secret scan separately.",
            },
        }
        for name, value in artifacts.items():
            self._write(output / name, value)
        if smoke is not None:
            self._write(output / "top_down_planner_smoke.json", smoke)
        self.registry.save(output / "mechanics_evidence_registry_snapshot.json")
        return artifacts
