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

- 2026-10-09 / 23a623a independent review: actual remote/hash verified; fresh Plan A baseline initialization fails on absent generator. Minimal provenance/diagnostic correction; targeted41 PASS, historical artifacts unchanged. DPS and cost-cap deficits remain UNKNOWN, no stage execution. See review/23a623a/REVIEW.md.

## Plan A 固定候选契约计算（2026-10-09）

代码/输入：`run_r8_1_plan_a_fixed_candidate_contract_v1.py` + deterministic context + census + 旧 Plan A frontier。

证据状态：当前模拟器公式、确定性路线/候选事实为 CONFIRMED_FROM_CODE；真实游戏、退款、merchant 经济、roadblock 部署和 Exact timing 为 UNKNOWN。

结果：实际枚举固定结构组合 12 个；faithful witness 0，阶段模拟 0，Kimi 0。caper 在 450 帧部署时 route-1 780 帧完成，但 route-3 810–1140 帧完成，错过 941。双期限模型要求最晚 250 帧开火；A01+A02 后可用 DP 5.333，aprl 缺 5.667，caper/angel 缺 6.667。angel/aprl 无 [8,5] 覆盖。该结果是 scoped model conflict，不是全局不可行。

- d9304bb independent review: generator and12manifest records verified, baseline48tests reproduced; conditional caper780/1140 and latest250 derived. Corrected persistent refund accounting, actualA05omission and fabricated test results;52targetedPASS. No historical artifact changes or new stage simulations. Next: one bounded Kimi revision.

## Plan A Kimi 修订 V4（2026-10-10）

代码/输入：`run_r8_1_plan_a_kimi_revision_v4.py`、`run_r8_1_plan_a1_bounded_validation_v1.py`、corrected review evidence、deterministic context、census、raw Kimi stream。

证据状态：调用/模型/终态和确定性计算为 CONFIRMED_FROM_CODE；真实游戏、退款、upkeep、roadblock 部署、target ordering、client timing 为 UNKNOWN。

结果：Kimi-K3 一次调用完成，返回 `R8OP-A1-BLOCK1-COOP-ANCHOR390`。有界校验保留 2 个 distinct 组合、1 条动作候选和条件 DP/逐击证书；完整 witness 0，阶段模拟 0。新计划吸收了 250 非 deadline、wscoot block0、退款未知、A05 重复干员和 [9,2] roadblock 等证据。

- 51e0410 independent review: realremote/manifests/rawresponse replay confirmed. Tactical revision changes roles and conditions; no faithful witness. Corrected missing450 caper attack; unchanged conditional431/600, changedtrace. baseline59 and corrected62 testsPASS. Existing2combos distinct but only primary has arithmetic. Guards unresolved; next bounded guard-source verification, no stage run.

## EXP-A1-EXEC-PREREQ
CONFIRMED_FROM_CODE/GAMEDATA：合入 51e0410 review 后，仅复用原5个动作；公共运行时最小修复 merchant upkeep 与 active device occupancy。固定候选在 frame 207 出现0.1 DP upkeep 缺口；frame 390 caper 缺9 DP且被 roadblock 占格拒绝。0 Kimi调用、0新计划、0关卡模拟。证据：`output/r8_1_plan_a1_execution_prerequisites_v1/`。首扣帧和负费边界保持 UNKNOWN/PARTIAL，不影响该候选的局部不可执行结论。

- 48fa985独立审查：固定GameData character_table实际获取并核验；正常候选池305项未含13reserve实例。用户普通模式禁止预备干员约束已持久化。费用/占格源事实可反馈Kimi，精确首扣/207/390仍条件性。独立pytest68项初始1失败，修正测试空列表断言后68通过。无机制改动、无Kimi、无关卡模拟。

- Review期间用户收紧调试域为普通模式1～3星。旧A1全部4/5星，保留其机制反例但停止作为当前候选。固定源资格34、旧census覆盖17，资格与runtime支持分开。
## R8_1_NORMAL_LOW_STAR_TACTICAL_REVISION_V1

输入：48fa985审查补丁、固定GameData commit `0ef7f952`、34名普通低星事实目录、既有R8-1 deterministic context、A1反例。输出目录 `output/r8_1_normal_low_star_tactical_revision_v1/`。

结果：Kimi调用1/1成功；新计划1；候选槽4个、完整组合1、方向完整候选1；阶段模拟0。所有6个部署动作合法，DP账本全支付且末值0。计划声称约17 DP banked，但实际0；保存为narrative discrepancy。没有operationally verified witness。

实现：`scripts/build_normal_low_star_facts.py`、`src/arknights_planner/adapters/normal_low_star.py`、`scripts/run_r8_1_normal_low_star_kimi_revision_v1.py`、`scripts/compile_r8_1_normal_low_star_plan_v1.py`。最小公共机制补充为deployment SP bonus、deployment global heal、redeploy-time delta；AoE geometry仍未实现并保持NOT_PLANNER_SAFE。pytest不可用，定向直接函数测试47/47。


## 2026-10-10 Work独立审查1e92747（覆盖冲突旧结论）

CONFIRMED_FROM_CODE：1e92747实际检出和远端HEAD核实；34人源ID匹配；27 artifact+7输入manifest基线匹配；44724 SSE事件completed且structured一致。原定向集合本环境48通过，3回归后51通过。修复630/941 DP错时比较、声明认证和分类遮盖。历史output原样。本轮Kimi0、关卡模拟0；尚无执行witness。
