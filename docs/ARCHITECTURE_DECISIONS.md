# Architecture Decisions

来源与不可变约束：PROJECT_CHARTER（用户明确要求）。代码事实、历史报告、推测分别标 CONFIRMED_FROM_CODE、REPORTED_BY_PREVIOUS_WORKER、HYPOTHESIS。

1. 用户明确要求：Kimi-K3 决定战术；deterministic system 提供事实、计算、合法候选与验证；GPT / Work 管理审查；GLM 实现代码。任何确定性修复不得替 Kimi 选打法。
2. 用户明确要求：OperationalPlan 保留开局、路线职责、压力窗口、阵型演化、技能意图、暂时阻挡、共享火力、治疗、撤退和移交。合法动作不等于忠实战术。
3. 2026-10-09 CONFIRMED_FROM_CODE：当前 V3 是前缀诊断，不是完整 OperationalPlanCompilerContract 或 fidelity verifier。保留诊断数值，撤回自动 proven classification；没有替换为另一个固定打法或人为放宽 deadline。
4. 2026-10-09 CONFIRMED_FROM_CODE：未知 deadline 不得自动转成 spawn frame；自然-only 收入没有证明是完整经济上界；共享/条件/阶段语义缺失不得升级为全计划不可行。
5. 用户明确要求：机制 m18.9-stage-device-runtime-v1；GameData 主源；机制不能为让计划通过而猜改。两种 roadblock targeting 的 robust WIN 必须相同动作时间线；模拟器 WIN 和真实游戏通关分别记录。
6. 用户明确要求：失败经验必须具有条件、证据、来源与局限，冲突集合不称最小 UNSAT core；旧不完整 fidelity 结果不作为严格战术失败。
7. 2026-10-09 CONFIRMED_FROM_CODE：`EARLIEST_OPERATOR_CONTACT_FRAME` 不能自动成为 FIRE establishment deadline。A/B/C 的 route-3 FIRE deadline 保持 UNKNOWN；不发明替代期限。
