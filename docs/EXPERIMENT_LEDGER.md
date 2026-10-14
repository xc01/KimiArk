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

## 2026-10-13 — 恰好一次Kimi-K3调用

输入：Work批准的`llm_request_body.txt`，SHA-256
`3749ad4ded4bc9dfbcc142cba21cc60ba717ad1a780d61ef9da75a897a80dbac`。结果：HTTP 200，
`response.completed`；request ID
`021791824072792ed0e184fb98d17720dee9f0ee33ee7e169ef96`。usage：input 29311、output 30806、
total 60117、reasoning 23245。

输出：`R8_1_LOWSTAR_PLAN_C1`，11名普通模式1～3星干员、21个有序动作；schema/contract通过。
`strategy_handoff.json`是`HANDOFF_READY_NOT_COMPILED`且certificate为`NONE`。没有编译证书、
关卡模拟或战术保真声明。预算：Kimi 1、重试0、模拟0、扩搜0。

## 2026-10-13 — 只读工具mock闭环

实验：`output/r8_1_readonly_tool_loop_v1/`。实际Kimi 0、真实关卡模拟0、新真实计划/候选0、扩搜0。
mock模型请求2次、只读工具调用4次；两条SSE均为synthetic。

结果：C1范围和SP反例通过公共接口复现；完整工具轨迹、call_id、工具结果、mock initial/
continuation request和最终计划交接已保存。回归：transport 10/10、C1入口 12/12、只读工具闭环
12/12。`compileall`、manifest哈希和secret scan通过。provider tool兼容性保持UNVERIFIED。

## 2026-10-13 — 只读工具V2修复

基线更正：`1714eb8fb2137037e6d8511ee803f84a616134ea`。证据：
`output/r8_1_readonly_tool_loop_fix_v2/`。实际Kimi 0、真实关卡模拟0、新真实计划/候选0、
扩搜0；C1复用只算协议测试。

结果：mock闭环2次请求、4次工具调用完成；续接包含9项（1 user + 4 function_call +
4 function_call_output）。非法参数、重复call_id、第七次调用、arguments done不一致、
incomplete和空计划绕过均被拒绝。已关联同帧17DP部署账本显示扣款前17、扣款后0；
未关联歧义账本返回UNKNOWN且无“付不起”冲突。

测试：定向pytest 46/46 PASS（借用本地pytest 9.1.1环境；项目venv当前缺pytest，
DNS阻断无法安装声明的pytest<9）。`compileall`、V2 manifest哈希、`git diff --check`通过。

## 2026-10-13 — 工具检查修复与最小真实续接

实验：`output/r8_1_kimi_tool_protocol_probe_v1/`。实际模型请求2/2、只读工具1/1、
新战术计划0、动作候选0、模拟0、扩搜0。

结果：第一次HTTP 200、request ID
`021791876935200a77e5a4c9aa25c0e7eca6d226bba90a0c1a19a`、usage 834 tokens，返回原生
`function_call(query_mechanic_0_38eb0904)`；本地查询执行一次；第二次HTTP 200、request ID
`021791876941005b531818cd979bd70c39b690ac6f23902ffe415`、usage 1105 tokens，成功返回坐标
约定确认。provider兼容性升格为“非战术工具轮CONFIRMED”；真实C2仍待Work批准。

测试：原43项（deselect本轮4项新回归）58/58 PASS；当前合计50/50 PASS。compileall、
diff check、secret scan、evidence manifest均通过。三次probe本地启动错误都未发起HTTP请求。

## 2026-10-13 — C2有界真实工具会话

预算与结果：真实模型请求1/3，只读工具0/6，新C2计划0，动作候选0，关卡模拟0，扩搜0。
首次请求body SHA-256
`6fa2f6ded0b4e8f386d3d9f677194870638a75a6c79a4e8ba091052aa4e6deaf`，372,545字节，显式
`max_output_tokens=20480`。HTTP 200、`response.completed`、request ID
`021791878824511534779bc6a83ab3f36a7a90c1e71ba351808b5`；usage input 101,086、output 18,523
（reasoning 18,453）、total 119,609。raw response为4,675,016字节。

失败分类：assistant消息是普通JSON，文字声称`tool_calls:initiated,calls:6`，但输出只有
`reasoning`和`message`，没有原生`function_call`项；因此工具门禁拒绝执行。该文本进入final-plan
校验时不是有效C2：缺少三个根级修订对象，且`revised_operational_plans`不是单元素列表。没有
静态编译、保真证书、模拟或WIN/LOSS声明。证据在
`output/r8_1_lowstar_c2_tool_revision_v1/post_call_evidence_analysis.json`。

调用前51/51定向pytest PASS。调用后未重试；manifest旧记录先于门禁修改生成，已在post-call
分析中补充实际调用的`kimi_tool_loop.py` SHA-256。

## 2026-10-13 — C2紧凑两阶段会话

V2准备：`compact_operator_catalog()`覆盖34名普通1–3星，其中17名三星；删除完整原始facts目录与
重复机制支持表，但保留来源、每个operator的`runtime_support`和UNKNOWN。删除
`action_window_frames=[0,941]`，win scope改为全关模拟器判定。查询请求127,262字节，
SHA-256 `89e5d5c685d47a1aa8232368675f244f72c01accce4b786b4d47b38a88ffe643`。

结果：1/3次真实请求，0/6次工具。HTTP 200但`response.incomplete`，request ID
`021791880929074b9f489096afc36acf45c00ec3935d23a8cad89`。usage input 33,101、output 4,096
（reasoning 4,093）、total 37,197。输出只有reasoning，没有assistant文本或原生function_call，
因此没有工具结果，也没有最终C2。静态编译、动作候选和模拟均为0。

修正：transport loop在`response.incomplete`时原先误标`NO_TERMINAL_EVENT`，已改为
`RESPONSE_INCOMPLETE`并加回归；本轮结果不重试。调用前54/54定向pytest PASS。

## 2026-10-13 — C2 V2输出预算与工具轮

V2将查询和最终输出均设为32768。首次请求127,263字节，HTTP 200且`response.completed`；usage为
input 33,097、output 26,430（reasoning 24,332）、total 59,527。模型发出6个原生完成function_call。
其中`check_timing_constraints_5_96e88269`执行成功；5个范围查询因configuration不完整未执行。

第二次请求未发送：最终续接体148,762字节，超过140,000上限8,762字节。预检阻断体SHA-256
`7346cce32d6d6bc63d9bec87961991f93af9ad9cf81acebb0b13aa829e7fda8d`。计入2/3请求、工具执行1/6、
无效调用5；无C2、静态编译或模拟。调用前54/54定向pytest PASS。

## 2026-10-13 — C2 V2保存调用恢复

配置校验修复后重验5个保存调用：全部EXECUTED。Hibiscus DOWN、Stward DOWN、Ansel LEFT和Kroos LEFT
的声名目标全部覆盖；Lancet-2 LEFT确认[1,7]覆盖、[1,6]不覆盖。原始拒绝记录保留，时序查询未重跑。

第3次唯一HTTP续接体155,456字节，上限200,000；HTTP 200、`response.completed`，request ID
`021791884974558640844006c495b97e3327b5d9afec85673843d`。usage input 40,811、output 15,862
（reasoning 6,304）、total 56,673。最终JSON契约失败：`verification_questions`三项是字符串，
schema要求object。无有效C2、静态编译或模拟。预算3/3请求、6/6工具执行。修复后专项与定向
pytest 57/57 PASS。一次预HTTP NameError未计入请求。

## 2026-10-13 — 保存C2规范化与静态编译

RESULT_NORMALIZED：保存响应中只有三个`verification_questions`字符串被无损包装成对象；
规范化副本通过schema/contract。该结果从“没有有效C2”更正为“已得到可执行检查的C2”，但仍不是
战术成功。

STATIC_CONFLICT：修复`selected_skills`读取和`tile_json_row_col`比较后，又把C2的坐标列表目标
适配为只读工具对象。静态结果为1个冲突、7个UNKNOWN。frame600 Noirc部署费用14而前余额9，
原样动作无法通过模拟前提；0/1次关卡模拟启动，没有改动作、没有扩搜、没有WIN/LOSS。
定向pytest 61/61 PASS。

## 2026-10-13 — 自动收入修复与原样模拟LOSS

FIX_CONFIRMED_FROM_CODE：补充AUTO TIME即时DP收入模型，并在回归中验证570帧首次触发、
后续周期、撤退停止和C2 frame600支付。重放静态检查后C2为0冲突、7个UNKNOWN；旧frame600
冲突因遗漏自动收入而失效。

SIMULATION_LOSS_DIAGNOSTIC_ONLY：使用原样22个动作启动1/1次全关模拟。结果LOSS：
击杀27、漏怪29、剩余生命-24、4名干员死亡。frame570芬自动收入6 DP，frame890死亡；
frame1243 Vanilla死亡导致route-6敌人解除阻挡，frame1295首次漏怪；frame1680 Hibiscus
部署不足。没有改动作、没有第二次模拟、没有WIN/实机/robust WIN声明。定向pytest 63/63 PASS。

## 2026-10-13 — C3失败修订请求

PREPARED：C3紧凑证据body 137,980字节，含C2关键结果、死亡/漏怪链、经济拒绝、22个动作结局和
完整低星目录。67/67定向pytest PASS。

FAILED_NO_C3：第1次请求`response.incomplete`，output 32,768全部为reasoning 32,765，无
assistant文本或原生function_call。第2次显式`tool_choice=required`请求HTTP 200，仍
`response.incomplete`且reasoning 32,765，无工具调用。预算2/3请求、0/6工具；第3次不消耗。
没有C3、静态编译、模拟或战术不可行证明。

## 2026-10-13 GPT战术入口

已准备`r8_1_gpt_tactical_revision_v1`：请求138,127字节、`gpt-6.1-sol`、medium reasoning、
输出上限32768；34名普通低星和17名三星完整。因`SUB2API_API_KEY`缺失，preflight在HTTP前停止。
实际记录：0/3模型请求、0/6只读工具、0个OperationalPlan。Codex本地可用不能证明项目Responses
续接兼容。

更新：项目会话实际日志4 STARTED / 3 FINISHED，按STARTED计为4/3（超出授权）；1/6只读工具；
0个通过契约的OperationalPlan。原生function_call和续接成功；唯一最终JSON因parent错误和
frame乱序被拒绝。attempt编号缺陷覆盖原始响应，已保存缺失记录并修复未来行为。

## 2026-10-13 GPT-C3恢复与执行

模型请求0、只读工具0、新战术计划0。离线恢复1份GPT-C3；schema/contract PASS；静态检查
0冲突/0 UNKNOWN。关卡模拟1/1次启动，结果LOSS：46杀、10漏、生命-5、0死亡，最早漏怪frame1579。
manifest阶段故障已记录；模拟没有重启。

## 2026-10-13 GPT-C4准备与503失败

C4使用同一GPT入口并参数化C3来源、C3诊断摘要和事件。移除完整C2计划，仅保留C2失败证据；阻挡
事件压缩到frame2070前的开局压力窗口，路线泄漏摘要保留完整。最终请求体138,957字节，低于
140,000上限；34名低星与17名三星完整。定向pytest 38/38 PASS。

第1次实际请求HTTP 503，request ID `43346c70-1bc4-4376-bcf3-212e096dd1a4`。持久预算为1/3请求、
0/6工具、0计划、0模拟；无自动重试，未生成C4，未执行静态检查，未运行关卡模拟。

## 2026-10-13 GPT-C4授权503恢复

新增`resume_after_503`最小恢复入口。它校验attempt1精确为已计数空HTTP 503、0工具、provider/model/
effort一致，且`llm_request.json`与attempt请求和body哈希完全一致；不重跑prepare，不新建实验。
定向pytest 38/38 PASS。

第2次请求原样重放同一body，仍HTTP 503，request ID
`47cd2c69-13aa-4a90-b824-4938ae83aadb`。预算更新为2/3请求、0/6工具、0计划、0模拟；已按授权停止，
不自动使用第3次请求。

## 2026-10-14 Codex CLI C4入口失败

新增只读Codex CLI入口，参数数组调用`codex exec --json --sandbox read-only`，使用OpenAI provider、
`gpt-6.1-sol`、medium reasoning和现有schema。复用C4紧凑证据，不读取auth token。相关pytest 58/58 PASS。

唯一CLI进程启动后因workspace routing discovery timed out失败；thread
`01a13607-f3d3-7ee2-9ccf-751acb5a2dd0`，退出码1，无usage记录，0计划，0模拟。根因观察是自动化子进程
未继承交互shell的本地代理变量；事后runner已加mihomo代理默认值并保留本次失败，不重跑。

## 2026-10-14 Codex CLI第二次启动

新目录`r8_1_gpt_c4_codex_cli_v2`复用v1 prompt/evidence。预检记录全部大小写代理变量、mihomo Singapore-02
监听与出口。相关pytest 59/59 PASS。

第2次CLI进程到达OpenAI但被400拒绝：response_format要求根schema`additionalProperties=false`，当前根为
true。thread `01a13615-a7e7-7c60-b818-39f5eea76eb7`，无usage记录；累计2/2 CLI启动、0计划、0模拟。

## 2026-10-14 Codex CLI第三次启动并完成C4诊断

新目录`r8_1_gpt_c4_codex_cli_v3`删除CLI `--output-schema`参数；保留JSONL、最终消息、read-only和显式
本地代理。相关pytest 17/17 PASS。第3次CLI启动成功，thread
`01a1361f-377b-70d3-9371-9a19f379f8d6`；内部模型请求数为UNKNOWN_CLI_INTERNAL。可观测usage：
input 410,911（cached 355,072）、output 6,856（reasoning 2,721）。

最终消息JSON通过本地schema/contract。无损规范化只新增`provenance.revision_source`，未改动作或
战术内容；静态检查0冲突/0未知。一次固定全关诊断模拟为LOSS：49杀、7漏、0干员死亡、剩余生命-2。
首漏route-10 `enemy_1108_uterer#15`在1950帧出生、2179帧无伤漏出；其余漏怪为route-12 2184、
route-11 2629、route-13 2634、route-23 4555、route-33 4879/4903。累计3/4 CLI启动、1/1计划、
1/1模拟；未做两种路障targeting重验，不称robust或实机结论。

证据完整性告警：当前规范化计划哈希为`bf3d...`，静态/模拟manifest记录为`cd04...`。当前文件可由
原始输出加provenance规范化复现，24项动作契约与direction-complete候选一致；但不能证明模拟加载的
序列化字节与当前文件逐字节一致。未重跑模拟，未扩搜。

## 2026-10-14 R8-1连续批次C5-C7

通用Codex CLI入口参数化source/feedback与plan identity，加入140KB prompt限制和provenance要求。
C5输入120,270字节，输出缺少provenance被本地契约拒绝；离线无损补加该项后静态检查0冲突，模拟为
51杀/5漏/0死。C6直接通过，静态0冲突，模拟55杀/1漏/0死。C7直接通过，静态0冲突，模拟
**WIN**：56/56杀、0漏、0死、剩余生命5；队伍8人、星级总和22。

本轮新增CLI启动3次（累计4、5、6），每次internal model request为UNKNOWN_CLI_INTERNAL。可观测
output usage分别为C5 4,828、C6 5,117、C7 4,406；C5还消耗reasoning 2,582，C6 reasoning 977，
C7 reasoning 499。新增固定模拟3次。C7是条件模型WIN，不是实机结论；roadblock targeting复验尚未执行，
不称robust WIN。

C7同一动作时间线完成两种roadblock targeting复验：A_NOT_ORDINARILY_TARGETABLE和
B_LOW_PRIORITY_NO_ENEMY_ONLY均WIN（56/56、0漏、0死、剩余生命5）。policy、dt、max_time与C7基线一致。
因此R8-1在这个双变体范围内为robust roadblock-targeting simulator WIN；客户端导航/真实游戏仍UNKNOWN。

## 2026-10-14 — Seven-stage batch blocked before static checks

The generic stage extractor and CLI runner covered R8-2, R8-4, and R8-7. R8-3/R8-5 remained blocked by
`DISAPPEAR`; R8-6 remained blocked by `WAIT_CURRENT_WAVE_TIME`. This continuation consumed six new CLI
starts: R8-2 V1/V2/V3 = 3, R8-4 V1/V2 = 2, R8-7 V1 = 1. Combined with the prior R8-1 batch, the seven
stage report now totals nine CLI starts. All six continuation plans failed schema/contract validation
before static compile and simulation: 0 valid plans and 0 simulations. Evidence is under
`output/r8_1_r8_7_batch_v1/`.
# 2026-10-14 Recovery loop and four bounded GPT revisions

- Feedback compression fix commit: `7288339...`; targeted tests 2/2 PASS. The
  compact summaries excluded full result event timelines; R8-4 feedback was
  about 2.6 KB and R8-7 feedback about 6.4 KB.
- CLI starts: R8-4-R1 (cumulative 10), R8-7-R1 (11), R8-4-R2 (12),
  R8-7-R2 (13). Internal model requests: UNKNOWN_CLI_INTERNAL. No automatic
  retry, resume, model change, or endpoint change.
- R8-4-R1: input tokens 344,055 (cached 288,896), output 11,150
  (reasoning 5,985). R8-7-R1: input 548,992 (cached 486,656), output 15,432
  (reasoning 9,132). R8-4-R2: input 328,971 (cached 279,040), output 7,776
  (reasoning 3,176). R8-7-R2: input 350,005 (cached 296,320), output 18,086
  (reasoning 11,999).
- Simulations: four new original-action diagnostics, one per candidate. Results
  are `PARTIAL_MECHANICS_DIAGNOSTIC_LOSS`: R8-4-R1 43/11/1/life -9; R8-4-R2
  36/18/5/life -16; R8-7-R1 17/16/7/life -14; R8-7-R2 1/32/6/life -29.
  These are ordered kills/leaks/deaths. No full-mechanism WIN, robust WIN, or
  real-game claim is issued.

# 2026-10-14 Civilian mechanics correction and bounded revisions

The corrected R8-2 V1 simulation is 8 kills / 28 leaks / 0 deaths / life -26; its
first objective failure is frame 1889 (`ENEMY_LEAK`), and frame 4604 records the
first source-backed civilian death. R8-2 V3 is 11/25/0/life -23. R8-4 V1 and V2
are both 20/34/life -31 (0 and 1 deaths respectively). R8-7 V1 is 4/29/5/life
-26. The obsolete `PARTIAL_MECHANICS_DIAGNOSTIC_WIN` result is therefore
contradicted, while all old artifacts remain in `recovery_v2_diagnostics/`.

Three new Codex CLI starts produced R8-2 V4, R8-4 V3, and R8-7 V2. R8-2 V4 and
R8-4 V3 passed schema/contract but were blocked from simulation by static DP/SP,
deployment limit and redeploy declaration conflicts. R8-7 V2 required only a
recorded parent-hypothesis metadata mapping and then passed static checks; its
single diagnostic improved V1 to 13/20/2/life -17 but still lost at frame 1532.
The batch has 16 cumulative CLI starts; internal request count remains
`UNKNOWN_CLI_INTERNAL`. Observed input/output token totals are 2,147,541 and
38,833.

## 2026-10-14 Ghost-block fix and original-action revalidation

The parent run had 32 pytest failures in the same environment; the fix has 31,
with 0 new and 1 resolved. A new non-overwriting directory revalidated four
saved action timelines. R8-2 V1/V3 each reached 36 kills, 0 leaks, 0 operator
deaths, and life 2, but civilian `enemy_3001_upeopl#11` was still blocked by
roadblock #2 at the final frame, so neither is WIN. R8-4 V2 reached 50 kills,
4 leaks, 1 death, and life -1; its first leak was frame 3269 and first objective
failure frame 5010. R8-7 V2 reached 29 kills, 4 leaks, 2 deaths, and life -1;
its first leak was frame 1289 and first objective failure frame 1532. R8-1 C7
passed both saved roadblock-targeting replays under the fixed code with 56 kills,
0 leaks, and life 5.

## 2026-10-14 R8-2 clearance CLI was infrastructure-blocked

A compact roadblock-#2 evidence package was prepared from fixed GameData, a
separate user observation, and V1/V3 events. Two new non-overwriting Codex CLI
attempts (cumulative starts 17 and 18) launched the same frozen R8-2-V5 prompt
and budget. Both failed at `workspace routing discovery failed`; no GPT-C5 was
received and no simulation was run. The failure after bounded proxy repair was
saved verbatim and treated as infrastructure, not tactical evidence.

## 2026-10-14 Codex entry recovered and R8-2 V5 won once

After verifying interactive and runner proxy variables were identical, the
service-side endpoint returned HTTP 451 `no_biscuit_no_service` with
`x-oai-request-id`; direct access timed out. One minimal Codex probe then
succeeded with `READY` (input 14,223 / cached 12,288 / output 5). The frozen
R8-2-V5 prompt (`b7331b3d81680b5aa48eacc4d99c97682e3bb15a931bd75a77f8a315654480c4`)
was reused in attempt3. Its schema/contract and static checks passed with 0
conflicts, and the single fixed simulation WON: 36 kills, 0 leaks, 0 operator
deaths, life 2. Roadblock #2 was damaged 15 times and destroyed at frame 6633;
civilian #11 safely arrived at frame 6956. This is a simulator WIN, not perfect
completion, because civilian #6 died at frame 4604. A V6 revision attempt failed
at `workspace routing discovery timed out` without producing a plan.
