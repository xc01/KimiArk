from __future__ import annotations
from dataclasses import dataclass, asdict
from itertools import combinations
import json
from pathlib import Path
from arknights_planner.agent.tactical import PlanHypothesis
from arknights_planner.adapters import ApproximateRealSimulationAdapter, M13LoadoutPolicy, RealOperatorConfiguration, RealSimulationApproximationPolicy
from arknights_planner.search.m11 import M11MinimumSquadSearch, M11SearchConfig

@dataclass(frozen=True)
class GroundedTeam:
    hypothesis_id: str; team_id: str; operators: tuple[str, ...]; rarity: int; capabilities: tuple[str, ...]


@dataclass(frozen=True)
class CardinalityAuditTeam:
    """One exact-cardinality or one controlled K-1 realization of an LLM plan."""
    hypothesis_id: str
    variant: str
    requested_cardinality: int
    operators: tuple[str, ...]
    rarity: int
    deployment_order: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    removed_operator_id: str | None = None
    removed_capabilities: tuple[str, ...] = ()
    placement_policy: str = "LLM coordinates ignored; canonical route-coverage geometry selects legal tile and facing"
    skill_intent_policy: str = "No skill action: revised hypothesis explicitly limits this evaluation to basic attacks/healing"
    retreat_intent_policy: str = "No retreat action: revised hypothesis provides conditional intent only, not a source-backed event"

def load_hypotheses(path: Path) -> tuple[PlanHypothesis, ...]:
    return tuple(PlanHypothesis.from_dict(x) for x in json.loads(path.read_text(encoding="utf-8")))

def ground_teams(hypotheses, adapter, *, per_hypothesis=6):
    configs={x.operator_id:x for x in adapter.m13_low_rarity_configurations()}
    out=[]; seen=set()
    for h in hypotheses:
        ids=tuple(x for x in (*h.preferred_operator_ids,*h.alternative_operator_ids) if x in configs)
        # M14 permits only a small K<=3 pilot.  Never silently reinterpret a
        # higher-cardinality LLM proposal as a three-operator strategy.
        if h.target_cardinality < 1 or h.target_cardinality > 3:
            continue
        k=h.target_cardinality
        for team in combinations(dict.fromkeys(ids), k):
            if team in seen: continue
            seen.add(team); rarity=sum(int(adapter.repository.get_operator(x).star_rarity.value or 0) for x in team)
            out.append(GroundedTeam(h.hypothesis_id,f"{h.hypothesis_id}-T{len(out)+1}",team,rarity,h.required_capabilities))
            if sum(x.hypothesis_id==h.hypothesis_id for x in out)>=per_hypothesis: break
    return tuple(out)

def grounding_rejections(hypotheses) -> tuple[dict, ...]:
    return tuple({"hypothesis_id": h.hypothesis_id, "status": "REJECTED", "reason": "target_cardinality exceeds bounded M14 K<=3 scope"}
                 for h in hypotheses if h.target_cardinality < 1 or h.target_cardinality > 3)


def _operator_capabilities(adapter, operator_id: str) -> tuple[str, ...]:
    operator = adapter.repository.get_operator(operator_id)
    phase = operator.phases[-1]
    block = int(phase.stats_max.block_count.value or 0)
    capabilities: set[str] = set()
    if operator.position.value == "MELEE" and block:
        capabilities.add("BLOCKING")
    if operator.profession.value == "DEFENDER":
        capabilities.add("DURABLE_BLOCKER")
    if operator.profession.value == "VANGUARD":
        capabilities.add("EARLY_DEPLOYMENT")
    if operator.profession.value == "MEDIC":
        capabilities.add("HEALING")
    if operator.profession.value == "CASTER":
        capabilities.add("ARTS_DPS")
    if operator.profession.value == "SNIPER":
        capabilities.add("PHYSICAL_RANGED_DPS")
    if operator.profession.value in {"GUARD", "SPECIALIST"}:
        capabilities.add("PHYSICAL_MELEE_DPS")
    return tuple(sorted(capabilities))


def _least_structurally_necessary(adapter, team: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    capability_sets = {operator_id: _operator_capabilities(adapter, operator_id) for operator_id in team}
    counts = {capability: sum(capability in values for values in capability_sets.values())
              for values in capability_sets.values() for capability in values}
    ranked = []
    for operator_id, capabilities in capability_sets.items():
        lost = tuple(sorted(capability for capability in capabilities if counts[capability] == 1))
        # Fewer unique capabilities means lower structural necessity.  Tie-break
        # by higher rarity then stable ID, preserving deterministic ablations.
        rarity = int(adapter.repository.get_operator(operator_id).star_rarity.value or 0)
        ranked.append((len(lost), -rarity, operator_id, lost))
    _, _, selected, lost = min(ranked)
    return selected, lost


def ground_cardinality_audit(hypotheses, adapter) -> tuple[tuple[CardinalityAuditTeam, ...], tuple[dict, ...]]:
    """Ground at most full-K and one K-1 team per hypothesis, never global K3..K7 search."""
    configurations = {item.operator_id: item for item in adapter.m13_low_rarity_configurations()}
    teams: list[CardinalityAuditTeam] = []
    rejections: list[dict] = []
    for hypothesis in hypotheses:
        candidates = tuple(dict.fromkeys((*hypothesis.preferred_operator_ids, *hypothesis.alternative_operator_ids)))
        executable = tuple(item for item in candidates if item in configurations)
        if len(executable) < hypothesis.target_cardinality:
            rejections.append({"hypothesis_id": hypothesis.hypothesis_id, "status": "REJECTED", "reason": "insufficient executable preferred/alternative operators for requested cardinality"})
            continue
        selected = executable[:hypothesis.target_cardinality]
        order = tuple(item for item in hypothesis.deployment_order if item in selected)
        if set(order) != set(selected):
            order = selected
        rarity = sum(int(adapter.repository.get_operator(item).star_rarity.value or 0) for item in selected)
        teams.append(CardinalityAuditTeam(hypothesis.hypothesis_id, "FULL", hypothesis.target_cardinality, selected, rarity, order, hypothesis.required_capabilities))
        removed, removed_capabilities = _least_structurally_necessary(adapter, selected)
        reduced = tuple(item for item in selected if item != removed)
        reduced_order = tuple(item for item in order if item != removed)
        teams.append(CardinalityAuditTeam(
            hypothesis.hypothesis_id, "REDUCED", hypothesis.target_cardinality, reduced,
            sum(int(adapter.repository.get_operator(item).star_rarity.value or 0) for item in reduced),
            reduced_order, hypothesis.required_capabilities, removed, removed_capabilities,
        ))
    return tuple(teams), tuple(rejections)


def run_cardinality_audit(hypotheses, adapter, policy, *, simulation_budget: int = 500):
    """Execute bounded, hypothesis-conditioned full/K-1 tests for cardinality pressure."""
    teams, rejections = ground_cardinality_audit(hypotheses, adapter)
    results: list[dict] = []
    total_simulations = 0
    total_cache_hits = 0
    for team in teams:
        if total_simulations >= simulation_budget:
            rejections += ({"hypothesis_id": team.hypothesis_id, "variant": team.variant, "status": "NOT_RUN", "reason": "simulation budget exhausted"},)
            continue
        configurations = {item.operator_id: item for item in adapter.m13_low_rarity_configurations()}
        pool = tuple(configurations[item] for item in team.operators)
        # Retain enough direction-ranked records to obtain two *distinct tiles*
        # per operator; a top-three list can otherwise contain three facings of
        # the same tile.
        config = M11SearchConfig(max_squad_size=len(pool), max_teams=1, placement_options_per_operator=24, beam_width=2)
        outcome = M11MinimumSquadSearch(adapter=adapter, stage_id_or_code="6-8", policy=policy, operator_pool=pool, config=config).search_ordered_fixed_team(team.operators, team.deployment_order)
        total_simulations += outcome.metrics.unique_simulations
        total_cache_hits += outcome.metrics.cache_hits
        best = outcome.best
        if best is None:
            rejections += ({"hypothesis_id": team.hypothesis_id, "variant": team.variant,
                            "status": "REJECTED_AFTER_SPATIAL_GROUNDING",
                            "reason": "no complete legal ordered deployment skeleton within the bounded canonical geometry"},)
            continue
        events = best.result.events if best else ()
        first_leak = next((event.time for event in events if event.event_type.value == "ENEMY_LEAK"), None)
        first_death = next((event.time for event in events if event.event_type.value == "OPERATOR_DEATH"), None)
        results.append({
            **asdict(team), "result": "WIN" if best and best.result.win else "LOSS",
            "simulations": outcome.metrics.unique_simulations, "cache_hits": outcome.metrics.cache_hits,
            "strategies_generated": outcome.metrics.strategies_generated,
            "deployed_action_count": len(best.strategy.actions) if best else 0,
            "kills": best.result.enemies_killed if best else 0,
            "total_enemies": sum(item.count for item in outcome.fixture.stage.spawn_events),
            "leaks": best.result.enemies_leaked if best else None,
            "remaining_life": best.result.remaining_life if best else None,
            "attacks": sum(event.event_type.value == "ATTACK_START" for event in events),
            "damage_events": sum(event.event_type.value == "DAMAGE" for event in events),
            "first_leak_frame": config.frame_clock.frame_for_seconds(first_leak) if first_leak is not None else None,
            "termination_frame": config.frame_clock.frame_for_seconds(best.result.time_survived) if best else None,
            "timeline": outcome.timeline.to_dict() if outcome.timeline else None,
            "robustness": outcome.robustness_by_action,
        })
    return teams, tuple(results), rejections, {"simulation_budget": simulation_budget, "unique_simulations": total_simulations, "cache_hits": total_cache_hits}

def run_grounded(hypotheses, adapter, policy, *, per_hypothesis=6):
    teams=ground_teams(hypotheses, adapter, per_hypothesis=per_hypothesis); results=[]; summaries=[]
    cfg=M11SearchConfig(max_squad_size=3,max_teams=12,beam_width=2,placement_options_per_operator=2)
    for team in teams:
        pool=tuple(RealOperatorConfiguration(x,0,adapter.repository.get_operator(x).phases[0].keyframes[-1].level.value) for x in team.operators)
        outcome=M11MinimumSquadSearch(adapter=adapter,stage_id_or_code="6-8",policy=policy,operator_pool=pool,config=cfg).search()
        best=outcome.best
        events=best.result.events if best else ()
        result={"hypothesis_id":team.hypothesis_id,"team_id":team.team_id,"operators":team.operators,"simulations":outcome.metrics.unique_simulations,"cache_hits":outcome.metrics.cache_hits,"win":bool(best and best.result.win),"kills":best.result.enemies_killed if best else 0,"enemy_death_events":sum(e.event_type.value=="ENEMY_DEATH" for e in events),"attacks":sum(e.event_type.value=="ATTACK_START" for e in events),"damage_events":sum(e.event_type.value=="DAMAGE" for e in events),"leaks":best.result.enemies_leaked if best else None,"life":best.result.remaining_life if best else None,"survival":best.result.time_survived if best else 0,"deployment_errors":list(best.result.deployment_errors) if best else [],"first_failure_frame":None,"closest_score":best.result.score if best else None}
        result["zero_kill_classification"] = classify_zero_kill(result) if not result["kills"] else "WIN_OR_KILL"
        results.append(result)
    by={h.hypothesis_id:[] for h in hypotheses}
    for r in results: by.setdefault(r["hypothesis_id"],[]).append(r)
    for hid, rows in by.items():
        rows.sort(key=lambda r:(not r["win"],r["leaks"] if r["leaks"] is not None else 999,-r["kills"],-r["survival"]))
        b=rows[0] if rows else None
        summaries.append({"hypothesis_id":hid,"simulations":sum(r["simulations"] for r in rows),"wins":sum(r["win"] for r in rows),"best_kills":b["kills"] if b else 0,"leaks":b["leaks"] if b else None,"remaining_life":b["life"] if b else None,"first_leak_frame":"UNKNOWN","problematic_route":"UNKNOWN","DP_failure":"UNKNOWN","uncovered_route":"UNKNOWN","blocker_overload":"UNKNOWN","physical_damage_deficit":"UNKNOWN","arts_damage_deficit":"UNKNOWN","healing_deficit":"UNKNOWN","closest_candidate":b})
    return teams, tuple(results), tuple(summaries)

def classify_zero_kill(result: dict) -> str:
    if result.get("deployment_errors"): return "NO_DEPLOYMENT"
    if result.get("attacks", 0) == 0: return "NO_TARGET_ACQUISITION"
    if result.get("damage_events", 0) == 0: return "ATTACK_NO_DAMAGE"
    if result.get("enemy_death_events", 0) == 0: return "DAMAGE_INSUFFICIENT"
    return "UNKNOWN"
