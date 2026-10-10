# Architecture Decisions

来源与不可变约束：PROJECT_CHARTER（用户明确要求）。代码事实、历史报告、推测分别标 CONFIRMED_FROM_CODE、REPORTED_BY_PREVIOUS_WORKER、HYPOTHESIS。

1. 用户明确要求：Kimi-K3 决定战术；deterministic system 提供事实、计算、合法候选与验证；GPT / Work 管理审查；GLM 实现代码。任何确定性修复不得替 Kimi 选打法。
2. 用户明确要求：OperationalPlan 保留开局、路线职责、压力窗口、阵型演化、技能意图、暂时阻挡、共享火力、治疗、撤退和移交。合法动作不等于忠实战术。
3. 2026-10-09 CONFIRMED_FROM_CODE：当前 V3 是前缀诊断，不是完整 OperationalPlanCompilerContract 或 fidelity verifier。保留诊断数值，撤回自动 proven classification；没有替换为另一个固定打法或人为放宽 deadline。
4. 2026-10-09 CONFIRMED_FROM_CODE：未知 deadline 不得自动转成 spawn frame；自然-only 收入没有证明是完整经济上界；共享/条件/阶段语义缺失不得升级为全计划不可行。
5. 用户明确要求：机制 m18.9-stage-device-runtime-v1；GameData 主源；机制不能为让计划通过而猜改。两种 roadblock targeting 的 robust WIN 必须相同动作时间线；模拟器 WIN 和真实游戏通关分别记录。
6. 用户明确要求：失败经验必须具有条件、证据、来源与局限，冲突集合不称最小 UNSAT core；旧不完整 fidelity 结果不作为严格战术失败。
7. 2026-10-09 CONFIRMED_FROM_CODE：`EARLIEST_OPERATOR_CONTACT_FRAME` 不能自动成为 FIRE establishment deadline。A/B/C 的 route-3 FIRE deadline 保持 UNKNOWN；不发明替代期限。
8. 2026-10-09 CONFIRMED_FROM_CODE：selected-usage fidelity 仍必须检查实际依赖的 trait；ammo `atk_scale`、“技能未开时 block 0”、merchant cost/interval 都是 decision-critical 时不得因 aggregate selected-skill metadata 一刀切放行。缺表导致的 pool 数量差异不能通过人工增删干员抹平。

7.2026-10-09 CONFIRMED_FROM_CODE：source-reverification的candidate pool须具fidelity/census输入证据；缺失时BLOCKED，测试不得覆盖历史artifact。接敌事实与plan-specific FIRE deadline分离；下一阶段用一个现有计划的有限局部witness推进，不继续增加泛化审查层。

- 23a623a independent review: capability averages and cost caps cannot serve as finite-window damage certificates or economic lower bounds. Preserve conditional concession branches; record missing provenance without inventing files/hash; runtime UNSUPPORTED is an evidence gap, not game impossibility.

- d9304bb review: test execution results must come from actual runner logs, not literals in validators. DP credits persist across events and conditional omissions change executable ledger rows. Conditional derived deadlines stay tied to roster/targeting/damage assumptions. Next tactical revision belongs to Kimi-K3, one bounded call.

- 2026-10-10 CONFIRMED_FROM_CODE：d9304bb 审查补丁合入后允许唯一 Kimi-K3 修订。模型返回一个 Plan A 开局修订；确定性系统只生成 2 个 distinct opening 组合、1 条动作候选和条件证书，0 次阶段模拟。Python 不替 Kimi 发明新战术，也不把 conditional model conflict 升格为通用期限。

- 51e0410 review: continuous SP/attack state must cross target handoffs; per-plan literal certificates do not prove semantic compilation. UNKNOWN execution guards block faithful prefix validation; simulator omissions cannot certify those guards. Candidate-set absence remains scoped to actually supplied roster.

- 2026-10-10 CONFIRMED_FROM_CODE：公共运行时新增 generic merchant upkeep 与 active stage-device occupancy 检查。GameData description/trait blackboard 确认 strong/talr/nothin 每3秒扣3 DP且不足自动撤退；首扣帧仍未独立确认。`trap_020_roadblock#2` 活跃时占据 [9,2]，销毁（`hp <= 0` 后从 `active_devices` 移除）才释放部署格。机制版本不变，但不把这两个修复解释为战术通过。

- 用户2026-10-10：模式专属预备干员不得进入普通模式规划。复用GameData obtainability过滤，在LLM显式指派处也校验；基础事实记录不删除。候选资源范围必须明示，不能用旧7人集合缺项证明全普通 roster缺项。
- 48fa985审查：区分源确认的费用量/周期与未确认首扣相位；模型数字不升级为客户端精确观测。优先修正证据说明，禁止再造计划专用计算层。

- 用户约束：当前debug只用普通模式1～3星。资源资格与机制支持独立，资格在输入/显式选择/动作入口均需校验；不擅自放宽星级。旧高星阵型不约束新低星战术结构，战略决策仍属于Kimi。
