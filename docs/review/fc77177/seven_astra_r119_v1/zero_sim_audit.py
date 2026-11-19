"""Event parsing and code-grounded arithmetic only: no battle/fixture execution."""
from collections import defaultdict
from prepare import BASE, ROOT, read, write, sha
import hashlib, json
from arknights_planner.gamedata.repository import GameDataRepository

def indexed(events, predicate):
    return [{"raw_index": i, **e} for i, e in enumerate(events) if predicate(e)]

def main():
    registry = read(BASE / "parent_registry_v1.json")
    facts = read(BASE / "input_bundle/template_context.json")
    sources = {alias: read(ROOT / registry[alias]["artifacts"]["diagnostic_events.json"]["path"])["events"] for alias in ["B", "E"]}
    repo = GameDataRepository(ROOT / "data/ArknightsGameData")
    rows = []
    for target in ["enemy_1108_uterer#1", "enemy_1107_uoffcr#6", "enemy_1107_uoffcr#10", "enemy_1107_uoffcr#12"]:
        enemy = repo.get_enemy(target.split("#")[0], level=0)
        bysource = {}
        for alias, events in sources.items():
            damages = indexed(events, lambda e: e["event_type"] == "DAMAGE" and e.get("target_id") == target)
            heals = indexed(events, lambda e: e["event_type"] == "HEAL" and e.get("target_id") == target)
            leak = indexed(events, lambda e: e["event_type"] == "ENEMY_LEAK" and e.get("source_id") == target)
            choices = indexed(events, lambda e: e["event_type"] == "TARGET_SELECTION" and e.get("source_id", "").startswith("char_") and target in e.get("details", {}).get("candidate_ids", []))
            grouped = {}
            for op in sorted({e["source_id"] for e in choices}):
                selections = [e for e in choices if e["source_id"] == op]
                grouped[op] = {"eligible_selection_count": len(selections), "selected_count": sum(e.get("target_id") == target for e in selections), "first": selections[0], "last": selections[-1], "actual_damage": [e for e in damages if e["source_id"] == op]}
            hp0 = float(enemy.stats.max_hp.value)
            hp = hp0 - sum(e["details"]["amount"] for e in damages) + sum(e["details"]["amount"] for e in heals)
            bysource[alias] = {"last_effective_damage": damages[-1] if damages else None, "all_damage": damages, "heal_events": heals, "leak": leak[0], "HP_at_leak": {"value": round(hp, 8), "classification": "CODE_AND_COMPLETE_EVENTS_DERIVED_NOT_HP_SNAPSHOT", "formula": "runtime_spawn_HP - all recorded DAMAGE + all recorded HEAL", "initial_hp": hp0, "gamedata_hp_source": enemy.stats.max_hp.source_path, "gamedata_hp_source_file": enemy.stats.max_hp.source_file, "raw_regeneration_value": enemy.stats.hp_recovery_per_second.value, "runtime_regeneration_rule": "None -> 0.0 in Simulator._spawn; positive passive recovery emits HEAL", "direct_HP_snapshot": "UNKNOWN"}, "fang_hits": [e for e in damages if e["source_id"] == "char_123_fang"], "actual_eligible_and_selected": grouped, "other_possible_future_shots": "UNKNOWN: no continuous position/attack cooldown snapshot; raw eligibility at selection time is not a future completed strike"}
        rows.append({"enemy": target, "sources": bysource})
    ev = sources["E"]
    fang = "char_123_fang"
    block = indexed(ev, lambda e: e["event_type"] == "BLOCK" and e.get("source_id") == fang)
    dp = indexed(ev, lambda e: e["event_type"] == "DP_CHANGE" and e.get("source_id") == fang)
    deploys = indexed(ev, lambda e: e["event_type"] == "DEPLOY")
    cumulative = 0.0
    conditional = []
    for e in deploys:
        bonus = sum(x["details"]["amount"] for x in dp if x["frame"] <= e["frame"])
        conditional.append({"deployment": e, "observed_cumulative_fang_DP": bonus, "balance_if_only_fang_skill_DP_removed_all_other_actions_unchanged": round(e["details"]["dp_after"] - bonus, 8), "scope": "Arithmetic counterfactual only, not legality or a Fang-free plan; omission also saves deployment cost and changes combat"})
    paths = ["src/arknights_planner/simulator/simulator.py", "src/arknights_planner/adapters/approximate_real.py", "src/arknights_planner/simulator/range.py", "data/ArknightsGameData/zh_CN/gamedata/levels/enemydata/enemy_database.json"]
    authority = {p: sha(ROOT / p) for p in paths}
    diff = read(ROOT / "docs/review/fc77177/seven_astra_r118_v1/best_canonical_action_diff.json")
    write(BASE / "zero_sim_priority_v1.json", {"scope": "Before new CLI: no production checks/candidates/simulations. Parsed old full event logs, static source and HP/DP arithmetic only; Astra makes priority and tactics.", "source_B": registry["B"], "source_E": registry["E"], "only_tactical_diff": diff, "rows": rows, "fang_responsibility": {"first_actual_block": block[0], "all_actual_blocks": block, "first_DP_skill": dp[0], "DP_deployment_counterfactual": conditional, "first_deployment_requiring_fang_generated_DP_if_all_other_actions_fixed": next((e for e in conditional if e["balance_if_only_fang_skill_DP_removed_all_other_actions_unchanged"] < -1e-7), None), "catalog_fang": next(x for x in facts["normal_low_star_catalog"] if x["operator_id"] == fang), "actual_first_deploy_cost": deploys[0], "cost_warning": "catalog stats.cost11 versus runtime DEPLOY10: actual adapter talent deployment cost delta applies. Use execution facts, not raw cost alone.", "delegation": "Actual next executor UNKNOWN until Astra designs and production static-checks legal replacement/deployment order; one failed Fang-free variant cannot establish necessity."}, "HP_rule_sources": {"spawn": "Simulator._spawn lines151-169", "damage": "Simulator._damage_enemy lines535-547", "regen": "Simulator._advance_enemy_passives lines714-721", "adapter": "ApproximateRealSimulationAdapter.build_pool_fixture returns repo enemy objects without changing HP"}, "source_hashes": authority})
    lines = ["# R119 零模拟优先级事实表", "", "仅解析旧事件与实际代码作算式；不代 Astra 选择战术，不运行战斗。余血为代码+完整事件可还原值，非直接 HP 快照；快照仍 UNKNOWN。", "", "| 敌人 | B 最后受击 / 漏前余血 | E 最后受击 / 漏前余血 | 芬新增两击 | 其他实际选中/范围候选 |", "|---|---|---|---|---|"]
    for row in rows:
        b, e = row["sources"]["B"], row["sources"]["E"]
        def last(s):
            x = s["last_effective_damage"]
            return "无受击" if x is None else f"{x['source_id']}@{x['frame']}"
        extra = ",".join(str(x["frame"]) for x in e["fang_hits"])
        others = "; ".join(f"{k}:候选{v['eligible_selection_count']}/选中{v['selected_count']}" for k,v in e["actual_eligible_and_selected"].items() if k != fang) or "无其他实际候选记录"
        lines.append(f"| {row['enemy'].split('#')[-1]} | {last(b)} / {b['HP_at_leak']['value']} | {last(e)} / {e['HP_at_leak']['value']} | {extra} | {others} |")
    lines += ["", "史都华德对 #10/#12 曾有范围候选记录，却实际选炮兵。未观察到的新增攻击能否选中并完成仍 UNKNOWN，不能以几何覆盖代替实际输出。", "", f"芬首次实际 BLOCK：{block[0]['target_id']}@{block[0]['frame']}。首次自动技能570回6DP；保持其他动作不变且仅删除回费，第一笔不足是841玫兰莎部署（差2.9667DP）。这不是无芬方案的费用结论：不部署芬也省实际10DP，部署顺序和自然回费均可重算。", "", "保留 R117/R118 的独立事实：#6与#5输出部分重叠；#9更晚；#14受路障#4未清和后续承伤链影响。是否可委托其他人由Astra决定，不能宣称芬必需或只差最后一击。"]
    (BASE / "zero_sim_priority_v1.md").write_text("\n".join(lines) + "\n")
    old = ROOT / "docs/review/fc77177/seven_astra_r118_v1"
    index = read(old / "old_action_index.json")
    import batch_service
    for p in sorted((old / "session/candidates").glob("*/simulation/plan_snapshot.json")):
        index[batch_service.action_key(read(p))] = str(p.relative_to(ROOT))
    write(BASE / "old_action_index.json", index)
    print({"priority_rows": len(rows), "old_behavior_dedup": len(index), "new_battles": 0})

if __name__ == "__main__":
    main()
