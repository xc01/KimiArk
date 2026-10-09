# Experiment Ledger

|里程碑|代码/输入|证据状态|结果与失效结论|
|---|---|---|---|
|迁移前完整历史|用户交接，详见 PROJECT_CHARTER|REPORTED_BY_PREVIOUS_WORKER|旧 667/170 faithful 和 111 hallucination 标签不可当有效结论；历史五个 DP 冲突尚缺源复验|
|V3 保存产物|abb8526 实现、c25300a artifacts，获取时 HEAD 5d31ce0|CONFIRMED_FROM_CODE（保存文件内容）；真实调用/机制为 REPORTED_BY_PREVIOUS_WORKER|三份结构化计划、295 前缀算术；无动作/witness/模拟。不可推为三个真实战术失败|
|接管获取|clone + ls-remote；5d31ce04693837b5909537a4fcb7c68ea4a2fbd8|CONFIRMED_FROM_CODE|23 tracked files；原仓库五个 commits；默认 master；关键源依赖未交付|
|基线测试|原 V3 tests 8，transport tests 10|CONFIRMED_FROM_CODE|V3 5 PASS、1 failure、2 errors；transport 10 PASS；旧 validation PASS 不适用于本 fresh clone|
|frame295 代码审查|review/FRAME295_REVIEW.md + evidence_index.json|CONFIRMED_FROM_CODE / HYPOTHESIS 按报告分项|共享 route-3:FIRE 调用路径已确认；295 来源和真实性未确认；诊断升级 proof 等程序缺陷确认|
|最小补丁回归|test_v3_frame295_review_regression.py（synthetic fixtures）|CONFIRMED_FROM_CODE|同五项测试基线 5 FAIL，修复后 5 PASS；不验证游戏机制；未知不伪造 proof|
|补丁后全套|review/validation.json|CONFIRMED_FROM_CODE|23 项共 20 PASS，原缺件 3 项故障保留；compileall/diff-check PASS；未执行 Kimi/模拟|
|源证据恢复|review/evidence_index.json + review/gamedata_source.json + V3 raw SSE gzip manifest|CONFIRMED_FROM_CODE（交付文件与哈希）/ REPORTED_BY_PREVIOUS_WORKER（历史执行）|恢复 src、repair 依赖、旧 plan/ledger/certificate/trace、GameData 版本清单和 V3 调用证据；未提交 1.1 GB GameData|
|frame295 只读复验|run_r8_1_v3_source_evidence_reverification_v1.py + output/r8_1_v3_source_evidence_reverification_v1/|CONFIRMED_FROM_CODE|A/B/C 的 295 均为 route-3 最早接敌；plan-specific FIRE deadline UNKNOWN；295 前缀冲突仅诊断。定向测试 3/3 PASS；模拟 0，Kimi 0|
|Plan A 开局复验|run_r8_1_plan_a_opening_witness_v1.py + plan_a artifacts + two fidelity tables|CONFIRMED_FROM_CODE / UNKNOWN|候选 1/1/3/2/2，结构组合 12，faithful 组合 0；snhunt 为缺表唯一差异且因 decision-critical trait 被拒；退款 UNKNOWN；模拟 0，Kimi 0|

失败新增知识：本次证据不是新战斗失败，而是发现旧前缀判定并未建立 plan-specific deadline/完整经济/fidelity 证明；下一决策改为恢复并验证确定性契约，避免 Kimi 对伪反例学习。

## f1a1c7d 独立复审（2026-10-09）

接受接敌295/FIRE UNKNOWN重分类；manifest12项及原SSE重放验证通过；GameData固定commit的level/目标enemy独立匹配。缺fidelity两表导致记录pool21→fresh22，新增计划示例anchor；worker29测试仍PASS不能证明闭包齐全。最小修复将缺项显式BLOCKED，增加只读测试模式；定向31/31通过。fresh baseline unittest67项32PASS/1failure/34errors，原日志保留。下一阶段收窄为Plan A开局0–941 witness，最多16组合和1固定prefix执行，无新战术或Kimi调用。
