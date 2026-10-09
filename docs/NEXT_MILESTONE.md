# 已完成有界里程碑：现有 Plan A 开局 witness 复验（frame 0–941）

决定来自 2026-10-09 对 f1a1c7d 的独立源码审查，审查补丁已合入（`59add38`）。本阶段状态 `NO_FAITHFUL_WITNESS_SCOPED_CONFLICT`。只处理 R8OP-A-MERGED-ANCHOR-REFUND-LATTICE，未调用 Kimi，未新增计划，未扩大搜索，未模拟。

## 输入与契约

已合入审查 patch，并提交真正用于 worker 原 21 候选筛选的 `all_operator_fidelity.json`、`all_operator_census.json`。两者的 SHA-256、305-operator 计数和 m18.5 mechanics version 已记录；原始生成 commit 仍为 `UNKNOWN_ORIGINAL_GENERATION_COMMIT`，不冒称已确认。

固定 A 的 stub、dam、merged anchor、725/729 的职责及 conditional concession。逐项落实原 invariant：route-1 before 805、route-3 before 941；确认队列清除所需建立时间，不能直接赋值 earliest contact 295，也不能照抄叙述 400–500。区分完整计划与局部 0–941 证书，不将局部通过当作 WIN。

## 有界预算与验收

1. 表项已恢复：fidelity/census 均为 305 operators；缺表 fresh pool 为 22，实际历史表筛选后为 21，唯一差异是 `char_4211_snhunt`。
2. `char_4211_snhunt` 被拒绝的原因是其 ammo/trait `atk_scale` 被标记 UNSUPPORTED 且对 RANGED_DPS decision-critical；selected skill 1 本身支持，unused skill 2 不作为排除理由。它没有为凑数被人工放入或剔除。
3. Plan A 开局候选预算内得到 1/1/3/2/2，组合上限 12；qualified 组合为 0。A03 三个可用 anchor 的有效 DPS 均低于计划要求的 450 vs 150 DEF；只有 `char_4100_caper` 的一个方向覆盖 [8,5]，另两个不覆盖。示例 snhunt 的 skill-only DPS 可达下限，但 trait 仍不可用。
4. A01/A02/A04/A05 的关键 trait 未被支持：merchant 类 cost/interval 语义、wscoot 的“技能未开时 block 0”语义、以及 duelist 的 decision-critical trait 均阻止忠实 witness。
5. 退款保持 UNKNOWN；模拟器当前无退款。无退款时 A05 在 729 缺 5.7 DP；即使假设 full-cost refund，也缺 0.7 DP。未把假设退款转成事实。
6. 因为 qualified witness 为 0，frame 0–941 stage-prefix 模拟次数为 0。结论是 scoped conflict，不是全战略不可行，也不是 Kimi V4 触发条件。

本轮禁止：Kimi V4、新 OperationalPlans、>16 组合、>1 stage-prefix 执行、完整关卡搜索、无依据退款/trait/机制改动，以及将 diagnostic/UNKNOWN 强行记成成功或 proven failure。
