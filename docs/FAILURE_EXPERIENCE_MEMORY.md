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

## REVIEW-PLAN-A-OPENING-004：合并 anchor 与 trait/退款语义不可暂视为已建立

- 状态：CONFIRMED_FROM_CODE（当前候选/几何/DP 计算）；战斗结果 UNKNOWN。
- 条件：仅限 `R8OP-A-MERGED-ANCHOR-REFUND-LATTICE` frame 0–941、当前 fidelity 表、当前 [3,3]/[8,5]/[9,2]/[5,1]/[6,1] 结构与最多 3 候选/槽、16 组合预算。
- 事实：A03 三个候选 effective DPS 均低于 450 vs 150 DEF；`char_4211_snhunt` 的 skill-only DPS 可达下限，但 ammo/trait `atk_scale` unsupported。A02 trait 说明技能未开时 block 0；A04/A05 的 merchant trait interval/cost decision-critical unsupported。
- 退款：来源与到账时刻 UNKNOWN，当前模拟器为 no refund。无退款时 A05 缺 5.7 DP；假设 full-cost refund 仍缺 0.7 DP。
- 结论：没有 faithful opening witness，因此 0–941 模拟 0 次。这是 scoped conflict；不能推为全战略不可行，也不能用假设退款或放行 trait 制造 witness。

## REVIEW-FIDELITY-003：缺表静默扩大候选池

CONFIRMED_FROM_CODE；适用于load_fidelity_tables缺任一表的fresh checkout。证据review/f1a1c7d/：无fidelity/census时已保存21候选变22，新增char_4211_snhunt；原测试仅非空断言仍通过。原因是缺表静默跳过trait/talent检查，不能把其pool当忠实候选。修复本轮reverification缺表BLOCKED并保持候选UNKNOWN。局限：不证明新增干员不合法，也不证明计划不可行；必须恢复原表并逐职责核对selected usage。

## EXP-23A-REVIEW: 限定前轮反例
CONFIRMED_FROM_CODE: DPS原始平均公式非逐击有限窗口伤害界；账本15为A03成本上限而候选11/12；COND_ROUTE6有让路分支。旧低于450与0.7/5.7缺口仅诊断，不能作为计划不可行。适用范围为该公式与示例成本/退款分支；不证明任何候选可行。wscoot未开技能阻挡0与无技能dam职责冲突仅适用于该实例；merchant运行时未支持是验证缺口，不等于真实战术不可行。

## PLAN-A-FIXED-CONTRACT-001: 有限窗口与固定候选经济

- 状态：CONFIRMED_FROM_CODE for simulator/base-cost model；真实游戏结果 UNKNOWN。
- 条件：仅限 Plan A 固定候选、[9,2] origin、[8,5] 目标、route-1/route-3 当前确定性上下文、1 秒攻击、attack-SP cycle、模拟器 target ordering 和 A02 持续阻挡假设。若目标不停留在 [8,5]，caper 也不能同时完成两个 3300 HP 契约。
- 事实：caper 在 450 帧部署时 route-1 780 帧击杀，但 route-3 810–1140 帧击杀，超过 941。双期限模型要求 A03 最晚 250 帧开火；该前缀可用 DP 5.333，aprl 缺 5.667，caper/angel 缺 6.667。angel/aprl 缺少 [8,5] 覆盖。
- 限制：[9,2] roadblock 部署、退款、merchant 成本/upkeep、真实 target ordering、技能调度和 Exact GameData timing 未证实；当前 UNSUPPORTED 是证据缺口，不是游戏不可行证明。该经验只用于条件性反馈，不触发无授权 V4。

## EXP-D930-CAPER（条件性模型经验）
CONFIRMED_FROM_CODE: 344ATK/1s/3normal+1skill(2.3x), two3300HP/150DEF continuously held, no intervening targets/fire, instant hits: first450->kills780/1140; strict805/941 requires first<=250. No-refund/no-upkeep fixed13DPprefix leaves5.333 at250 versuscaper12. Applies only to stated assumptions; not generaldeadline/minimalUNSAT/globalstrategyfailure. Wscootblock0 under inactive skill undermines holding assumption; support/occupancy/targeting/timing unknown. Refund ledger bug corrected: hypothetical5 refund persists,729balance+2.3 for12-costanchor; not game proof. Kimi should revise assumptions, not blindly satisfy250.

## PLAN-A1-REVISION-001: 修订开局的条件共享与让路

- 状态：Kimi 调用与新计划内容 CONFIRMED_FROM_CODE；战斗结果和真实机制 UNKNOWN。
- 可复用经验：若 block-2 依赖未开技能，则不能同时承担“无技能阻挡”和“火力合作”。当同一 live duelist 无法占两个槽时，条件让路必须实际省略部署和成本，而不是只改文字。退款金额未确认时，自然 DP 前缀和假设退款账本必须分开。
- 条件事实：在当前模拟器逐击公式、两目标持续被挡、当前 target ordering 和 talr+caper 同时开火的假设下，route-1 431、route-3 600 完成；这不是通用 FIRE deadline。若 cooperation、roadblock 部署或 merchant upkeep 未证实，计划必须回落到显式 concession。
