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

## R8_1_LOW_STAR_FIXED_PREFIX_DIAGNOSTIC_V1

输入：1e92747审查补丁、固定GameData `0ef7f952`、已保存B2六动作、公共 `ApproximateRealSimulationAdapter` 和 `Simulator`。Kimi0次、新计划0个、新候选0个、扩搜0次；main_08-01固定前缀运行1次，边界941。

结果：0漏怪、3击杀、生命5、941剩余DP约10.3667、4名活跃敌人、0干员死亡。route-2/route-1/route-3模型击杀帧分别为576/691/881；route-4于887被接敌；route-6/7/8未漏且仍活跃。完整3563事件保存于 `output/r8_1_low_star_fixed_prefix_diagnostic_v1/diagnostic_events.json`。

BUDGET_CORRECTION：实际main_08-01执行共4次，超出“最多一次”限制：1次未保存探查、2次脚本在保存前崩溃、1次最终保存运行。仅最终3563事件用于结论；不能宣称整体预算合规。

边界：公共runtime继续使用ZERO_WINDUP、instant projectile、量化spawn和通用伤害模型；Friston-3减伤、GALLUS²减抗/优先目标、Kroos概率天赋显式省略。结果只可审查模型行为，不认证faithful，也不外推真实游戏上下界。定向直接函数测试48/48；pytest不可用。


## 2026-10-10 Work审查bc14455（覆盖冲突旧结论）

bc14455独立fetch/HEAD及18manifest条目核实，3563事件账本一致。REPORTED_BY_PREVIOUS_WORKER运行4次/3次未保存，预算FAIL；仅1份保存可核验。CONFIRMED_FROM_CODE：事件六部署有五个晚1帧、route4被Lancet2高台阻挡；错误坐标源头影响路线/装置和旧事实。四回归旧基线FAIL，最小修复后55PASS。本轮真实关卡模拟0/Kimi0；历史outputs保持。

## 2026-10-10 开局路线静态事实实验

CONFIRMED_FROM_CODE：`scripts/build_r8_1_opening_route_spatial_facts_v1.py`从固定GameData重建route-1/2/3/4/6/7/8；输出见`output/r8_1_opening_route_spatial_facts_v1/`。核心结果见CURRENT_PROJECT_STATE。`run_manifest.json`记录11个源/输出文件hash并在本轮复验PASS。compileall PASS；pytest在系统和`.venv`中均UNAVAILABLE_NOT_INSTALLED，因此以只读函数调用执行7项新增断言，并以unittest执行2项既有route-contact/leak回归，全部PASS。真实关卡模拟0。


## 2026-10-11 Work审查1223c03（覆盖冲突旧结论）

1223c03独立检出/远端HEAD，11manifest及固定level源hash匹配。route2旧latest147与自己记录589矛盾，两个公共首次访问消费者最小修复；2行为回归旧FAIL后PASS。原7断言复验；修后64定向+5静态adapter共69PASS。本轮真实关卡模拟0/Kimi0。静态确认route2/6/7/8直连段均有FLY_ONLY内部反例，历史outputs不改。


## R8_1_WALK_NAVIGATION_FACTS_V1

- 实际预算：Kimi 0，真实关卡模拟 0，新 OperationalPlan 0，新动作候选 0，战术搜索扩展 0。
- 实现：`src/arknights_planner/navigation.py` + 公共 adapter WALK 转换。
- 证据：`output/r8_1_walk_navigation_facts_v1/`。
- 验证：`compileall` PASS；`unittest` 导航/事实 8/8 PASS；`pytest` 不可用（本环境无模块）。
- 结论范围：地形 SPFA/Bresenham 模型与静态通行一致；不是客户端完整运行时导航，也不是战术 deadline。
- roadblock：普通 WALK 敌人的导航效果 UNKNOWN；“全阻隔代价1000”变体仅为假设对照。


## Work review 2026-10-11 — 4b1b523

CONFIRMED_FROM_CODE: terrain navigation model exists; manifest 11/11 matches; review pytest 8 PASS / 3 FAIL (contradictory tests). Client algorithm equivalence is UNKNOWN; binary addresses/hash and extraction conclusions remain REPORTED_BY_PREVIOUS_WORKER until reproducible excerpts are supplied. This qualification supersedes earlier wording that independently confirmed client semantics. No new runtime bug or tactical impossibility is established. Next bounded task: reproducible active-roadblock navigation evidence; Kimi and real-stage simulations remain zero. See [review](review/4b1b523/REVIEW.md).

## 2026-10-12 Client roadblock evidence extraction

输入：`arknights-hg-2771.apk`、AArch64 `libil2cpp.so`、解密 global metadata、Il2CppDumper 1.0.0+be9358c77c660e932a683fed7e9c6ea99b2e7034、capstone 5.0.9、固定GameData commit `0ef7f952`。

结果：通用 SPFA/tile-option/special-block-condition 链已由 focused disassembly 支持；`trap_020_roadblock` prefab/skill payload 因 custom/LZHAM bundle 未解码而保持 UNKNOWN。没有把 generic token 重写推广为该路障规则。证据目录 `output/r8_1_roadblock_navigation_evidence_v1/`，targeted unittest 12/12 PASS。

预算：Kimi 0；真实关卡模拟 0；新 OperationalPlan 0；新动作候选 0；战术扩搜 0。无 WIN 声明。

## 2026-10-12 Roadblock prefab extraction V2

方法：第一次使用默认 UnityPy，在自定义 flag 4 上失败；第二次注册 isHarryh/Ark-Unpacker 的 BSD-3-Clause LZ4AK 解码器，成功解码 `btl_pfb_tokens_0.ab`。精确资源为 `dyn/battle/prefabs/[uc]tokens/trap_020_roadblock.prefab`，GameObject path ID `1390663109743954708`。

关键值：`_rewriteTileOptions=1`；mode `_tileOptions.passableMask=0`；`overrideObstacleLikeMoveCost=1`；`_keepCurrentPassableMask=1`；filter tag `tap_roadblock`。反汇编确认 TryUpdateOptions 在 keep-current 开启时保留旧 passableMask，SPFA 的 `avoidObstacleLike=true` 检查会因 moveCost 1000 拒绝该格。

分类：普通 WALK 的 passability mask 不变；avoidObstacleLike 可达性为 false。默认路径生成是否使用该标志仍 UNKNOWN；平民/塔露拉的 tag 绑定和跨版本适用性仍 UNKNOWN。脚本/证据：`scripts/extract_roadblock_prefab_evidence_v2.py` 与 `output/r8_1_roadblock_prefab_evidence_v2/`。验证：compileall PASS；定向 unittest 17/17 PASS。预算：Kimi 0；真实关卡模拟 0；新 OperationalPlan 0；新动作候选 0；战术扩搜 0。无 WIN 声明。

## 2026-10-12 Roadblock ordinary WALK navigation V3

输入：已固定 build 2771 的 `libil2cpp.so`（SHA-256 `3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259`）、固定 GameData commit `0ef7f952` 与 V2 prefab artifact。生成器：`scripts/extract_roadblock_walk_navigation_v3.py`；证据：`output/r8_1_roadblock_walk_navigation_v3/`。

结果：两条 V2 硬化结论标记失效并给出精确算术/调用边界；新增 `Map.InitRouteAndPassableMap -> Route..ctor(SPFA)`、`Map.UpdateAllRoutes -> Route.ReconstructNextMap`、Tile 更新/恢复、SPFA 缓存与成本计算的反汇编边。`Route.ReconstructNextMap -> SPFA` 因 Route 方法体不可静态解码保持 UNKNOWN。R8-1 源路线范围记录为 35 项（33 WALK、2 E_NUM），不引入战术期限。预算全部为 0；定向 unittest 12/12 PASS；compileall PASS。

## 2026-10-12 Route navigation decodability V4

输入：固定 `libil2cpp.so`（SHA-256
`3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259`）、本地
Il2CppDumper `dump.cs`/`script.json` 摘录和 ELF `.eh_frame`。工具为 Capstone
5.0.7 AArch64 little-endian；环境没有第二静态 A64 解码器，因此没有声称交叉验证。

结果：`Route..ctor`、`Route.ReconstructRoute` 和 `Route.ReconstructNextMap` 默认
入口解码失败，均为 0 条指令、0 字节消费。`.eh_frame` 确认各自边界。四字节对齐重
同步分别得到 40/117、22/105、34/107 个可解码词，但只保留为
`CANDIDATE_CLUES_ONLY`。没有恢复 `Route.ReconstructNextMap -> SPFA` 调用体；原因
保持 UNKNOWN，加密、运行时变换和数据误分类均未证明。V3 旧
`NO_VALID_A64_INSTRUCTIONS` 分类失效，V1/V2/V3 artifacts 原样保留。

证据与脚本：`output/r8_1_route_navigation_decodability_v4/` 和
`scripts/diagnose_route_navigation_decodability_v4.py`。验证：compileall PASS；
定向 unittest 18/18 PASS；V4 与 V3 manifest 哈希校验通过。预算：Kimi 0；真实关卡
模拟 0；新 OperationalPlan 0；新动作候选 0；战术扩搜 0。无 WIN 声明。

## 2026-10-12 Low-star full tactical closure V1

输入与准备：`output/r8_1_low_star_full_tactical_closure_v1/llm_evidence_context.json`
（229KB）覆盖 34 名普通 1～3 星、35 条源路线、完整波次、模型生成时序、route-2/3/6/7/8
地形事实、设备占格、敌方数值、前次 B2 结果和机制边界。实际 Kimi-K3 调用一次，响应 ID
`resp_021791801860205137f500080bf18603e76d17d12e7c43e659c8c`，终点
`response.incomplete`，assistant message status `incomplete`，原始流 8,165,408 字节。

根因：当时提示没有嵌入 evidence JSON；Kimi 部分文本自述 `PROMPT_SUMMARY_ONLY`。
输出在 32,768 token 上限内截断，40,059 字符 JSON 解析失败。结果：0 个有效
OperationalPlan、0 条动作候选、0 次关卡模拟。部分输出保留为失效证据，不作为战术。
已修复 future prompt evidence embedding 和 SSE 空 incomplete envelope 处理。

## 2026-10-12 — V2离线验收

实验：`r8_1_low_star_full_tactical_closure_v2`。只执行prepare和mock验收；Kimi 0，真实关卡
模拟0，新真实OperationalPlan/候选0，扩搜0。

结果：9/9 runner离线unittest两次通过（`PYTHONPATH=scripts`和`PYTHONPATH=src`）；
`compileall`通过。mock urlopen检查到实际`Request.data`与固化body完全一致；401、超时、流中断
均保存失败记录且不重试；`response.incomplete`被拒绝；空/多计划、缺方向DEPLOY被schema/contract
拒绝；合成合法计划能转换到公共`Strategy/Action`，状态是`HANDOFF_READY_NOT_COMPILED`，没有
战术保真声明。待发送body：112,541字节，SHA-256
`3749ad4ded4bc9dfbcc142cba21cc60ba717ad1a780d61ef9da75a897a80dbac`。

## 2026-10-13 — 调用前V2修复验收

Work批准body后执行离线修复。`llm_request.json`与完整prompt从body恢复入库，不重生成事实。
空evidence、body mismatch、旧缓存、截断响应、空/多计划、缺方向DEPLOY均被拒绝；401、超时、
流中断保存预算记录；二次尝试在联网前拒绝。完成响应mock验证`Request.data`、schema、evidence、
完整计划、非对称坐标交接和`strategy_handoff.json`。

结果：12/12测试两次通过，`compileall`通过，`jsonschema`导入可用；body不变。Kimi调用0，
模拟0，新真实计划0。之后才允许Work批准的一次实际Kimi调用。
