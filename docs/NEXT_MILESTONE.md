# 唯一下一里程碑：现有 Plan A 开局 constructive witness（frame 0–941）

决定来自 2026-10-09 对 f1a1c7d 的独立源码审查，详见 review/f1a1c7d/REVIEW.md。状态 READY_WITH_EXPLICIT_INPUT_BLOCKERS。只处理 R8OP-A-MERGED-ANCHOR-REFUND-LATTICE，不调用 Kimi，不新增计划，不扩大搜索，不宣称完整通关。

## 输入与契约

先合入本轮审查 patch，再提交真正用于 worker 原 21 候选筛选的 all_operator_fidelity.json、all_operator_census.json 及 source hash/生成版本。使用已固定 GameData commit；依 README 恢复运行必需表，确认相关测试。只补齐本任务直接用到的输入，不重跑历史大型搜索。

固定 A 的 stub、dam、merged anchor、725/729 的职责及 conditional concession。逐项落实原 invariant：route-1 before 805、route-3 before 941；确认队列清除所需建立时间，不能直接赋值 earliest contact 295，也不能照抄叙述 400–500。区分完整计划与局部 0–941 证书，不将局部通过当作 WIN。

## 有界预算与验收

1. fidelity/census 缺项变为具真实 hash 的可复验输入；fresh checkout 对当前职责的候选筛选一致。若示例 char_4211_snhunt 被拒绝，提供确切 decision-critical 能力/trait/skill 证据，不能擅自放行或仅为符合报告剔除。
2. 按 A 授权的资源结构检查真实 selected skill、cost、HP/DEF、攻击时序、tile/facing/coverage、同格 roadblock 影响、阻挡队列和共享职责。撤退退款必须有源事实及发生时间，或者作为未验证条件明确停留 UNKNOWN；不改机制让计划通过。
3. 确定性候选只取每个 required opening slot 最多 3 个 source-qualified 选项、最多 16 个完整 roster/geometry 组合；若超过预算，不扩大搜索，以 BUDGET_EXHAUSTED/UNKNOWN 记录。不让 Python 替 Kimi 改开局经济结构、让路或拆分共享 anchor。
4. 产生最多一条 frame 0–941 的合法动作时间线，DEPLOY 必须包含 operator、tile、direction、frame，技能及撤退保持原战术意图；附完整 DP ledger、技能/退款到账时间和职责 traceability。无 witness 则给出 scoped conflict 或 UNKNOWN 条件，不称全战略不可行。
5. 只在忠实编译且机制输入足够后，用固定这条时间线做最多一次 0–941 stage-prefix 验证。不改变时间线再搜索，不运行完整关卡；记录 blocker 生存、queue、route-1/3 击杀时刻、生命消耗与首因。局部失败需说明哪些原假设被证伪；依赖不齐则模拟零次。
6. 完成后推送源代码、测试、原输入 hashes、实际 artifacts 及六份长期文档；GPT/Work 审查真实 diff 后决定下一阶段。既有两种 roadblock targeting 的完整 robust WIN 标准保持不变，真实游戏验证独立。

本轮禁止：Kimi V4、新 OperationalPlans、>16 组合、>1 stage-prefix 执行、完整关卡搜索、无依据退款/trait/机制改动，以及将 diagnostic/UNKNOWN 强行记成成功或 proven failure。
