"""Retrieval-first mechanics evidence and uncertainty gates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from arknights_planner.mechanics import ACTIVE_MECHANICS_VERSION


@dataclass(frozen=True)
class MechanicsEvidence:
    topic: str
    subtopic: str
    claim: str
    source: str
    source_type: str
    local_source_path: str
    provenance: str
    confidence: str
    implementation_status: str
    conflicts: list[str]
    applicable_context: dict[str, Any]
    mechanics_version: str


@dataclass(frozen=True)
class _SourceCheck:
    source_type: str
    path: str


class MechanicsEvidenceRegistry:
    """A provenance and retrieval layer, not an Arknights ontology."""

    def __init__(self, root: Path = Path("."), extra_entries: tuple[MechanicsEvidence, ...] = ()):
        self.root = Path(root)
        self.entries: list[MechanicsEvidence] = list(self._build())
        self.entries.extend(self._stronghold_reference_entries())
        self.entries.extend(extra_entries)
        self._source_checks = (
            _SourceCheck("PRTS_LOCAL", "data/prts/battle-mechanics.html"),
            _SourceCheck("PRTS_LOCAL", "data/prts/game-data-basics.html"),
            _SourceCheck("PRTS_LOCAL", "data/prts/hatred.html"),
            _SourceCheck("GAME_DATA", "data/ArknightsGameData"),
            _SourceCheck("CLIENT_ARCHAEOLOGY", "docs/CLIENT_FRAME_TIMING.md"),
            _SourceCheck("HISTORICAL_AUDIT", "output/m18_rebaseline/main_06-07"),
            _SourceCheck("HISTORICAL_AUDIT", "output/m23/main_06-07"),
            _SourceCheck("IMPLEMENTED_SIMULATOR", "src/arknights_planner/simulator/simulator.py"),
        )

    def _build(self) -> tuple[MechanicsEvidence, ...]:
        battle = "data/prts/battle-mechanics.html"
        hatred = "data/prts/hatred.html"
        return (
            MechanicsEvidence(
                "targeting", "ordinary_priority",
                "Ordinary ally priority is blocking (melee only), special priority, second priority, hatred/remaining path, then earliest appearance.",
                "PRTS 作战机制/sandbox", "PRTS_LOCAL", battle,
                "cached local wiki snapshot", "HIGH", "PARTIAL",
                [], {"unit_side": "ALLY", "selector": "ORDINARY"},
                ACTIVE_MECHANICS_VERSION,
            ),
            MechanicsEvidence(
                "targeting", "remaining_path_distance",
                "Enemy hatred uses shortest remaining legal path distance; it is not Euclidean distance to the exit or raw route progress.",
                "PRTS 仇恨", "PRTS_LOCAL", hatred,
                "cached local wiki snapshot", "HIGH", "IMPLEMENTED_FOR_MODELED_ROUTES",
                [], {"entity_type": "ENEMY", "routes": "MODELED_LEGAL_ROUTES"},
                ACTIVE_MECHANICS_VERSION,
            ),
            MechanicsEvidence(
                "targeting", "stable_tie",
                "Stable selector sorting preserves entity creation order when reference values tie.",
                "PRTS 仇恨", "PRTS_LOCAL", hatred,
                "cached local wiki snapshot", "HIGH", "IMPLEMENTED",
                [], {"selector": "STABLE_SORT", "tie": "CREATION_ORDER"},
                ACTIVE_MECHANICS_VERSION,
            ),
            MechanicsEvidence(
                "targeting", "blocked_priority",
                "Most ordinary melee units can and prioritize enemies they personally block, even when that enemy is outside normal attack range; ordinary ranged units generally do not.",
                "PRTS 作战机制/sandbox", "PRTS_LOCAL", battle,
                "cached local wiki snapshot", "HIGH", "IMPLEMENTED",
                [], {"unit_position": "MELEE", "selector": "ORDINARY"},
                ACTIVE_MECHANICS_VERSION,
            ),
            MechanicsEvidence(
                "targeting", "attack_lock",
                "When an operator locks a target during attack windup, that attack usually does not change because eligibility or position changes.",
                "PRTS 作战机制/sandbox", "PRTS_LOCAL", battle,
                "cached local wiki snapshot", "HIGH", "PARTIAL_FOR_PENDING_PROJECTILES",
                [], {"lifecycle": "ATTACK_WINDUP_OR_PROJECTILE"},
                ACTIVE_MECHANICS_VERSION,
            ),
            MechanicsEvidence(
                "targeting", "retarget_timing",
                "Exact ordinary death/range-exit retarget timing and next-attack behavior are not specified by the cached local sources.",
                "PRTS 作战机制/sandbox", "PRTS_LOCAL", battle,
                "negative result after cached-source retrieval", "MEDIUM", "UNKNOWN",
                [], {"lifecycle": "RETARGET_AFTER_TARGET_DISAPPEARANCE"},
                ACTIVE_MECHANICS_VERSION,
            ),
            MechanicsEvidence(
                "data", "numeric_source_boundary",
                "GameData is the primary source for exact stage, route, character, skill, and enemy values; simulator traces do not supersede it.",
                "ArknightsGameData repository", "GAME_DATA", "data/ArknightsGameData",
                "project source boundary", "HIGH", "IMPLEMENTED",
                [], {"data_kind": "NUMERIC_AND_STRUCTURE"},
                ACTIVE_MECHANICS_VERSION,
            ),
            MechanicsEvidence(
                "timing", "client_frame_clock",
                "Client frame-clock provenance remains partially unresolved; configured 30 FPS is not silently promoted to real-client truth.",
                "CLIENT_FRAME_TIMING audit", "CLIENT_ARCHAEOLOGY", "docs/CLIENT_FRAME_TIMING.md",
                "local static archaeology", "MEDIUM", "PARTIAL",
                [], {"artifact": "FRAME_CLOCK"},
                ACTIVE_MECHANICS_VERSION,
            ),
            MechanicsEvidence(
                "targeting", "historical_path_distance_rebaseline",
                "The path-distance correction changed the preserved M16 paired replay and invalidated old M22 route-2@564 constraints.",
                "M18 rebaseline artifacts", "HISTORICAL_AUDIT", "output/m18_rebaseline/main_06-07",
                "deterministic replay evidence", "HIGH", "HISTORICAL_EVIDENCE",
                [], {"stage": "6-8", "families": ["M16", "M17", "M18.1", "M22"]},
                "m18.1-target-distance-v2",
            ),
    )

    def _stronghold_reference_entries(self) -> tuple[MechanicsEvidence, ...]:
        repository = "https://github.com/sganggs/Stronghold-Protocol"
        commit = "bce182703b1331e14fa442c51907c952461a568d"
        version = ACTIVE_MECHANICS_VERSION

        def entry(
            topic: str,
            subtopic: str,
            claim: str,
            path: str,
            lines: str,
            upstream_basis: str,
            confidence: str,
            implementation_status: str,
            context: dict[str, str],
            conflicts: list[str],
        ) -> MechanicsEvidence:
            return MechanicsEvidence(
                topic, subtopic, claim, f"{repository}@{commit}", "SECONDARY_EXECUTABLE_REFERENCE",
                f"external/Stronghold-Protocol/{path}", f"upstream basis: {upstream_basis}; read-only GPL reference",
                confidence, implementation_status, conflicts, context, version,
            )

        return (
            entry("tick", "phase_order", "Battle ticks run scheduled, spawns, DP, buffs, enemies, allies, projectiles, redeploy, hooks, time, and end checks.", "server/sim/Battle.js", "400-448", "ASSUMED", "MEDIUM", "PARTIAL", {"scope": "ordinary_main_stage"}, ["LOCAL_TICK_ORDER_IS_A_FUNCTIONALLY_EQUIVALENT_APPROXIMATION"]),
            entry("attack", "ally_loop", "Attack cooldown advances, then target acquisition, optional about-to-attack skill, re-acquisition, attack, and interval reset run in order.", "server/sim/ai.js", "68-92", "PRTS_BACKED", "HIGH", "FUNCTIONALLY_EQUIVALENT", {"scope": "basic_attacks_and_manual_skills"}, []),
            entry("targeting", "self_blocked_priority", "Self-blocked enemies are selectable and participate in ordinary enemy target sorting.", "server/sim/ai.js", "107-143", "PRTS_BACKED", "HIGH", "IMPLEMENTED", {"scope": "melee_blocks"}, []),
            entry("targeting", "remaining_distance", "Enemy remaining distance includes current segment suffix and all later route legs.", "server/sim/ai.js", "410-442", "PRTS_BACKED", "HIGH", "IMPLEMENTED_FOR_MODELED_ROUTES", {"scope": "modeled_legal_routes"}, []),
            entry("blocking", "contact", "Unblocked ground enemies can be blocked by nearby legal-capacity ground blockers on repeated contact checks.", "server/sim/Battle.js", "1110-1148", "PRTS_BACKED", "HIGH", "FUNCTIONALLY_EQUIVALENT_WITH_TICK_QUANTIZATION", {"scope": "ordinary_ground_routes"}, ["LOCAL_ROUTE_CROSSING_CHECKS_ARE_QUANTIZED"]),
            entry("damage", "pipeline", "Damage passes selection, mitigation, source/target multipliers, caps, HP loss, then fatal handling.", "docs/SIM.md", "597-671", "PRTS_BACKED", "HIGH", "FUNCTIONALLY_EQUIVALENT", {"scope": "physical_and_arts_basic_damage"}, []),
            entry("skill", "runtime", "Skills use SP/charge readiness, activation legality, active effects, duration, and attack-loop triggers.", "server/sim/skills.js", "235-451", "PRTS_BACKED", "HIGH", "FUNCTIONALLY_EQUIVALENT_FOR_SUPPORTED_SKILLS", {"scope": "supported_synthetic_skills"}, []),
            entry("projectile", "ranged_attack_impact", "Ordinary ranged attacks create projectiles at attack time and resolve damage on impact.", "server/sim/ai.js", "145-179", "PRTS_BACKED", "HIGH", "DIFFERENT_BY_EXPLICIT_APPROXIMATION", {"scope": "ranged_basic_attacks"}, ["LOCAL_INSTANT_PROJECTILE_POLICY"]),
            entry("projectile", "travel_and_shooter_death", "Homing projectiles normally continue after shooter death; target death fizzles an ordinary projectile.", "server/sim/projectiles.js", "46-75", "ASSUMED", "MEDIUM", "DIFFERENT_BY_EXPLICIT_APPROXIMATION", {"scope": "ranged_projectiles"}, ["LOCAL_INSTANT_PROJECTILE_POLICY"]),
        )

    def register(self, entry: MechanicsEvidence) -> None:
        self.entries.append(entry)

    def search(
        self,
        topic: str | None = None,
        terms: tuple[str, ...] = (),
    ) -> list[dict[str, Any]]:
        rows = self.entries
        if topic is not None:
            rows = [entry for entry in rows if entry.topic == topic]
        if terms:
            lowered = tuple(term.lower() for term in terms)
            rows = [
                entry for entry in rows
                if any(term in f"{entry.topic} {entry.subtopic} {entry.claim}".lower() for term in lowered)
            ]
        return [asdict(entry) for entry in rows]

    def _source_trail(self) -> list[dict[str, Any]]:
        return [
            {
                "source_type": check.source_type,
                "path": check.path,
                "exists": (self.root / check.path).exists(),
                "checked": True,
            }
            for check in self._source_checks
        ]

    @staticmethod
    def _conflicts(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for hit in hits:
            for conflict in hit.get("conflicts", []):
                rows.append({
                    "topic": hit["topic"],
                    "subtopic": hit["subtopic"],
                    "claim": hit["claim"],
                    "conflict": conflict,
                })
        return rows

    def query(
        self,
        question: str,
        *,
        topic: str | None = None,
        terms: tuple[str, ...] = (),
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = dict(context or {})
        hits = self.search(topic=topic, terms=terms or (question,))
        return {
            "question": question,
            "topic": topic,
            "terms": list(terms or (question,)),
            "context": context,
            "evidence_retrieval_performed": True,
            "source_trail": self._source_trail(),
            "hits": hits,
            "hit_count": len(hits),
            "conflicts": self._conflicts(hits),
        }

    @staticmethod
    def _context_resolution(question: str, context: dict[str, Any]) -> bool:
        if isinstance(context.get("decision_resolved"), bool):
            return context["decision_resolved"]
        candidates = context.get("candidate_remaining_route_distances")
        if question == "Q1" and isinstance(candidates, list) and candidates:
            minimum = min(candidates)
            return candidates.count(minimum) == 1 and not context.get("has_taunt_or_special_filter")
        if question == "Q2":
            return context.get("operator_position") == "MELEE" and bool(context.get("blocked_candidate_ids"))
        return False

    def unknown_gate(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        *,
        topic: str | None = None,
        terms: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        retrieval = self.query(question, topic=topic, terms=terms, context=context)
        context = dict(context or {})
        resolved = self._context_resolution(question, context)
        missing_sources = [row for row in retrieval["source_trail"] if not row["exists"]]
        if resolved and retrieval["hits"]:
            status = "KNOWN"
            unknown_valid = False
            reason = "Existing evidence resolves the concrete decision."
        elif retrieval["hits"]:
            status = "UNKNOWN"
            unknown_valid = not retrieval["conflicts"]
            reason = "Existing evidence was retrieved but does not settle the concrete context."
        else:
            status = "NO_APPLICABLE_EVIDENCE"
            unknown_valid = True
            reason = "No indexed applicable evidence was found after source retrieval."
        if missing_sources:
            unknown_valid = False
            reason += " Some configured local sources are missing, so exhaustion is not established."
        return {
            **retrieval,
            "concrete_context_resolved": resolved,
            "concrete_context_unresolved": not resolved,
            "existing_evidence_exhausted": not missing_sources,
            "unknown_status": status,
            "unknown_declaration_valid": unknown_valid,
            "reason": reason,
        }

    def mechanics_work_gate(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        *,
        planner_relevance: bool,
        counterfactual_sensitivity: bool,
    ) -> dict[str, Any]:
        gate = self.unknown_gate(question, context)
        required = gate["concrete_context_unresolved"] and planner_relevance and counterfactual_sensitivity
        return {
            **gate,
            "planner_relevance": planner_relevance,
            "counterfactual_sensitivity": counterfactual_sensitivity,
            "mechanics_work_gate": "MECHANICS_WORK_REQUIRED" if required else "NO_MECHANICS_WORK_REQUIRED",
            "reason": (
                "The uncertainty is unresolved, planner-relevant, and counterfactually capable of changing the result."
                if required else
                "At least one mechanics-work precondition is false; accept the scoped approximation and continue planning."
            ),
        }

    def human_calibration_gate(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        *,
        planner_relevance: bool,
        counterfactual_sensitivity: bool,
    ) -> dict[str, Any]:
        gate = self.mechanics_work_gate(
            question,
            context,
            planner_relevance=planner_relevance,
            counterfactual_sensitivity=counterfactual_sensitivity,
        )
        required = all((
            gate["existing_evidence_exhausted"],
            gate["concrete_context_unresolved"],
            planner_relevance,
            counterfactual_sensitivity,
        ))
        return {
            **gate,
            "human_calibration_gate": "CALIBRATION_REQUIRED" if required else "NO_HUMAN_CALIBRATION_REQUIRED",
            "reason": (
                "All stricter calibration conditions hold."
                if required else
                "At least one stricter calibration condition is false; do not request a real-game observation."
            ),
        }

    def reaudit_targeting_questions(self) -> dict[str, Any]:
        q1 = self.unknown_gate(
            "Q1",
            {"candidate_remaining_route_distances": [3.0, 5.0], "has_taunt_or_special_filter": False},
            topic="targeting",
            terms=("remaining", "path", "stable"),
        )
        q2 = self.unknown_gate(
            "Q2",
            {"operator_position": "MELEE", "blocked_candidate_ids": ["blocked"]},
            topic="targeting",
            terms=("blocked", "melee"),
        )
        q3 = self.unknown_gate(
            "Q3",
            {"lifecycle": "RETARGET_AFTER_TARGET_DISAPPEARANCE"},
            topic="targeting",
            terms=("retarget", "attack", "lock"),
        )
        return {
            "Q1": {
                "status": "CONTEXTUALLY_RESOLVED",
                "gate": q1,
                "unknown_detail": None,
            },
            "Q2": {
                "status": "RESOLVED_BY_EXISTING_EVIDENCE",
                "gate": q2,
                "unknown_detail": None,
            },
            "Q3": {
                "status": "PARTIALLY_RESOLVED",
                "gate": q3,
                "unknown_detail": {
                    "what_is_unknown": "Exact ordinary retarget timing and next-attack behavior after target death or range exit.",
                    "sources_checked": [
                        "data/prts/battle-mechanics.html",
                        "data/prts/hatred.html",
                        "data/prts/game-data-basics.html",
                        "output/m18_rebaseline/main_06-07",
                        "output/m23/main_06-07",
                    ],
                    "why_sources_do_not_settle_it": "They document attack locking but not exact post-disappearance retarget timing.",
                    "planner_effect": "Unknown until a fresh current-context replay demonstrates counterfactual sensitivity.",
                },
            },
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"active_mechanics_version": ACTIVE_MECHANICS_VERSION, "entries": [asdict(entry) for entry in self.entries]}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
