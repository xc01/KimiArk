# 当前入口：审查 R8OP-A1 条件动作候选

基线：d9304bb 审查补丁已合入为 `8a2a0d3`；Kimi-K3 已完成唯一一次 Plan A 开局修订，确定性有界校验完成。

目标：外部审查模型核对真实请求/响应、`R8OP-A1-BLOCK1-COOP-ANCHOR390`、2 个 distinct 组合、1 条动作候选、DP/逐击证书与 UNKNOWN。审查通过后可决定是否执行一条固定前缀模拟。

关键证据：`output/r8_1_plan_a_bounded_kimi_revision_v4/llm_request.json`、`llm_raw_response.txt`、`llm_structured_output.json`，以及 `output/r8_1_plan_a1_bounded_validation_v1/`。

必须审查的边界：[9,2] roadblock 部署合法性、退款金额与到账帧、merchant cost/upkeep、真实 target ordering、Exact GameData timing、route-3 handoff 和 route-6/route-8 concession 生命周期。这些保持 UNKNOWN；不得升格为战术不可行。

禁止：再次调用 Kimi、新增 OperationalPlans、扩大模拟搜索、修改无证据机制、将本轮条件候选说成 faithful witness 或 WIN。无 WIN 声明。
