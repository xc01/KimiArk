# 当前入口：审查 Plan A 固定候选开局契约

基线：审查补丁已合入为 `491a9a0`，Plan A 固定候选契约计算已完成。下一步不是自动 V4，也不是扩大搜索。

目标：外部审查模型核对真实代码、manifest、12 个结构组合账本、caper 逐击合同和 UNKNOWN 边界。只有审查通过并明确授权后，才进行一次有界 Kimi 修订。

关键证据：`output/r8_1_plan_a_fixed_candidate_contract_v1/finite_window_damage_contracts.json`、`actual_candidate_cost_ledgers.json`、`structural_combination_contracts.json`、`source_input_manifest.json`。

必须审查的边界：[9,2] roadblock 部署合法性、退款金额与到账帧、merchant cost/upkeep、真实 target ordering、Exact GameData timing 和 route-1/route-3 目标是否持续位于 [8,5]。这些保持 UNKNOWN；不得升格为战术不可行。

禁止：未授权 V4/Kimi、新 OperationalPlans、扩大模拟搜索、修改无证据机制、将本轮诊断视为全战略不可行。无 WIN 声明。
