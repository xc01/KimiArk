# 唯一下一里程碑：Plan A 固定候选的开局契约计算

基线：23a623a 独立审查；先合入本轮 review patch。不是新战术生成或扩大搜索。

目标：把现有诊断数字转为可验证的局部计算或明确 UNKNOWN，形成可直接反馈 Kimi 的准确证据。保留原 Plan A 及历史 artifacts。

范围与预算：只使用已保存的 A03 三个候选（angel/caper/aprl）和既有 A01/A02/A04/A05 候选；不新增候选、不更改战术，不调用 Kimi，不运行关卡模拟。最多复核原 12 个结构组合，不额外搜索。允许独立纯计算与小型机制回归测试。

1. 先补交 scripts/build_operator_runtime_fidelity.py 的真实服务器版本、hash 与来源；若无法找回，明确 UNKNOWN，禁止伪造原始生成 commit 或重新生成表冒充历史表。
2. 为现有 A03 候选按实际选定技能、逐击 DEF、SP 获取/消耗、初始 SP、攻击间隔和覆盖方向计算有限窗口伤害。用源码/事实核实每个假设；不得把长期平均 eDPS直接当成 route-1 805 / route-3 941 的击杀证书。未支持的 trait/targeting/device occupancy 阻断具体结论时停止并标 UNKNOWN。
3. DP 账本关联实际 operator/成本，区分 deployment cost 与 merchant upkeep；明确退款金额与入账帧的证据状态。保留 COND_ROUTE6 的不部署 A05 分支，不把成本上限当成最低成本。无法证实的机制不补猜测值。
4. 验收：每个拒绝理由都有具体 slot/operator/窗口/源证据/适用条件；能力不足、真实计划矛盾、运行时未支持三类清楚区分。只有有限窗口计算证明冲突才生成失败反例；否则 UNKNOWN。有真实矛盾则输出可反馈 Kimi 的条件性证据，不擅自提出新战术。
5. 干净检出能执行只读 targeted 测试，全部必需源码与新 artifacts 上传 GitHub；报告真实提交、manifest、测试范围和遗留 UNKNOWN。完成后 Work 审查，再决定是否一次有界 Kimi 修订。

禁止：V4、新 OperationalPlans、扩大模拟搜索、修改无证据机制、将本轮诊断视为全战略不可行。无 WIN 声明。
