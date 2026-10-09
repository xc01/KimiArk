# 已完成里程碑：恢复 V3 源证据并忠实复验现有 A/B/C

状态：SOURCE_EVIDENCE_RESTORED_AND_REVERIFIED，无新增战术，无 Kimi 调用，无模拟。下一步必须先由审查模型核对本轮证据；在此之前不启动 Kimi V4。

## 范围

已恢复 repair 源码与依赖闭包、关卡 context/catalog、GameData 版本清单、旧 ledger/trace、原 Kimi request/response/completion，并新增 `output/r8_1_v3_source_evidence_reverification_v1/`。23.9 MB SSE 原始响应以 gzip + SHA-256 交付；1.1 GB GameData 以精确 archive hash、upstream commit、data version 和恢复命令交付。可用 `docs/review/evidence_index.json`、`docs/review/gamedata_source.json` 和该 milestone 的 manifest 追溯。

只复验既有三份 OperationalPlans，保持原结构和用户职责边界。不生成新计划，不调用 Kimi，不扩大候选/模拟搜索，不猜改机制。

## 验收条件

1. fresh 交付包含 `src/`、repair/search/audit 脚本、旧 artifacts 和 V3 调用记录；缺失清单已清空。
2. 三个 fire 槽已确认 295 来自 route-3 `enemy_1107_uoffcr` 最早接敌事件：spawn 240、speed 1.1、contact distance 2、formula `ceil(240 + 2 / 1.1 * 30) = 295`。它与 431 的 BLOCK 语义不同。
3. 三份计划中的 FIRE establishment deadline 均为 UNKNOWN；A/C 的 queue contract 指向 route-1 before 805、route-3 before 941 并要求按 eDPS 解出 establishment；B 明确提出 dam split 和约 600 的叙述性 establishment。未发明替代 deadline。
4. 22/21/22 DP vs 19.8333 的 295 冲突保留为 `DIAGNOSTIC_CONFLICTING_CONSTRAINT_SET_NOT_PROVEN_UNSAT_CORE`；不再作为计划不可行证明。自然-only DP、distinct assignment、退款和技能收入仍是限制。
5. 未生成 faithful witness，因此模拟次数为 0；现有三份计划的可行性为 UNKNOWN，不是 proven feasible，也不是 proven infeasible。
6. 定向复验测试 29/29 PASS；compileall PASS。完整 unittest 94 项中 87 项 PASS，7 个模块因系统缺少 `pytest` 在导入阶段 BLOCKED，未标为通过。审查模型仍需核对真实 diff、manifest 和测试；未满足前不启动 Kimi V4。
