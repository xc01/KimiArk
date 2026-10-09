# Failure Experience Memory

## 既有五份条件经济冲突与一次战斗失败

REPORTED_BY_PREVIOUS_WORKER：保留 `output/r8_1_constraint_informed_revision_v3/feasibility_experience_memory.json` 的 EXP-001…006 和 PROJECT_CHARTER 历史记录；确认保存文件确实存在，但引用的旧 ledgers、unsat certificates、历史 trace 未交付。不得把来源恢复前的内容标为 independently proven，不得扩大到整个战略不可行。

每条仍保持 stage/main_08-01、mechanics/m18.9-stage-device-runtime-v1、source plan、deadline、mandatory distinct capability/responsibility、最低成本与可用收入、证据路径、适用条件、失败原因和局限。旧冲突集不保证 minimal UNSAT core；历史早期死亡不要求所有新结构采用同一 pocket fire。

## REVIEW-295-001：简化前缀诊断不可升级为战术失败

- 状态：CONFIRMED_FROM_CODE（分析程序与保存内容）；真实关卡 deadline 和成本来源 UNKNOWN。
- 条件：现有 V3 A/B/C 的 fire 槽均选择 route-3:FIRE；分析器仅用 route/kind deadline、不同干员指派和 10+frame/30。
- 证据：review/FRAME295_REVIEW.md；review/evidence_index.json 的三条 JSON pointers、SHA-256；V3 feasibility_analysis、plan_capability_pool。
- 诊断：保存值 22/21/22 DP 在 295 与自然 DP 19.8333 冲突。
- 约束来源：295 的 repair 函数/context 缺失；不是已确认的不可放宽游戏规则。A/C 的队列要求和 B 的上游分流可能改变 fire deadline，仍待验证。
- 失败原因：确定性系统尚未证明 deadline、共享/条件/阶段与完整经济保持战术语义，却标 proven 并计为已替换旧冲突。
- 可复用经验：先恢复、验证 contract；只把真实且具适用范围的反例交给 Kimi，由 Kimi 决定改战术。
- 局限：不证明三份计划可行、不证明 295 错误、不证明退款能救前缀，不指定新打法。禁止把 synthetic regression 当作真实游戏复验。

## REVIEW-RETREAT-002：待验证条件漏报

- 状态 CONFIRMED_FROM_CODE；适用于非空小写 retreat_basis / must_vacate_slot。
- 证据：原 V3 L982–988 的 uppercase RETREAT 判断与真实三个计划；原 certificates 的 unverified list 全空；新增回归。
- 原因：大小写字面匹配漏掉真实小写文本。
- 修复：依据字段存在性列待验证退款/安全交接条件；不授权任何 refund 数额、时机或机制。

## REVIEW-CONTACT-295-003：接敌事件不是开火 establishment deadline

- 状态：CONFIRMED_FROM_CODE；适用于 main_08-01 route-3、`enemy_1107_uoffcr`、mechanics `m18.9-stage-device-runtime-v1`。
- 事实：spawn frame 240，speed 1.1，earliest operator contact distance 2，formula `ceil(240 + 2 / 1.1 * 30) = 295`；route-3 BLOCK 事实是 431。
- 修正：295 是最早可能接敌事件，不是 FIRE establishment deadline。V3 A/B/C 的 plan-specific FIRE deadline 保持 UNKNOWN；400–600 叙述是战术目标，不自动升格为游戏事实。
- 保留限制：22/21/22 DP vs 19.8333 的前缀算术只是自然-only、distinct-unit、无退款/技能收入假设下的诊断冲突集。它不证明计划不可行，也不证明退款能解决冲突。
- 可复用经验：区分 CONTACT、BLOCK、FIRE establishment 和 KILL-by target；只有计划/机制显式要求时才把事件转为 deadline。
