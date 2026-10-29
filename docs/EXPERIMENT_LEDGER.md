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

## 2026-10-14 R8-2 V6/V8 bounded tactical closure

With `features.apps=false`, the frozen R8-2 V6 input (SHA-256
`30882fb15d4c5180663adb52cf127bc90bbc62a1021c93421815168985a1f8a1`) succeeded on
CLI start 22. Usage: input 298,104 / cached 252,672 / output 8,837 /
reasoning 4,302. Schema/contract and static checks passed; the original fixed
simulation was 34 kills / 2 leaks / 0 deaths / life 0, #6 died at frame 4844, and
roadblock #2 was destroyed at frame 8733.

R8-2 V7 was CLI start 23: input 382,822 / cached 329,984 / output 8,864 /
reasoning 3,872. Schema/contract passed but the only static conflict was
`INSUFFICIENT_DP` for Popukar at frame 2763 (13.1/19); no simulation was run.
R8-2 V8 was CLI start 24: input 584,192 / cached 526,592 / output 12,200 /
reasoning 6,343. It passed static checks and was simulated once: 24 kills / 12
leaks / 1 death / life -10; the first objective failure was leak at frame 2369,
#6 died at frame 4604, and roadblock #2 was still destroyed at frame 7233.
V5 remains the zero-leak simulator-WIN baseline; V8 is not a tactical improvement.
Internal model requests remain `UNKNOWN_CLI_INTERNAL`.

## 2026-10-14 V9–V13 structural protection closure

CLI starts 25–29 ran with `features.apps=false` and medium reasoning. V9 usage:
input 482,346 / cached 421,888 / output 8,519 / reasoning 2,730. Its original
simulation was 35 kills / 1 leak / 0 deaths / life 1; deployment errors 0,
roadblock #2 destroyed at frame 8943, #11 arrived at 9266, but #6 died at 5294
and Uterer #37 leaked at 5228. V10 usage: input 539,030 / cached 475,904 /
output 13,508 / reasoning 6,503. Its simulation was 35 / 1 / 1 death / life 1;
Popukar died at 5264 and Officer #38 leaked at 5512, while #6 still died at 5294.

V11 usage: input 549,199 / cached 487,296 / output 11,331 / reasoning 4,399;
it was rejected for Hibiscus DP 16.1/17 at frame 2373. V12 usage: input 268,196 /
cached 219,136 / output 9,216 / reasoning 3,582; it fixed that conflict but was
rejected for Midnight DP 15.1/16 at frame 2823. V13 usage: input 384,938 /
cached 333,952 / output 7,537 / reasoning 2,004; it repeated V12's conflict with
no information increment, so the loop stopped. V5 remains the best zero-leak
simulator-WIN baseline.

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

## 2026-10-14 Feedback repair, V14/V15 WINs, and V16 hang

A global-assignment bug prevented `--tactical-feedback` and
`--static-conflict-summary` from reaching V11–V13. The runner now embeds static
conflicts with candidate ID, action index, required/available DP, prior economic
events, conditional-income conditions and `NO_SIMULATION`; diagnostic feedback
also records its source plan ID. V14 (CLI start 30, input 401,313 / cached
301,568 / output 13,629 / reasoning 6,758) passed all static checks and simulated
WIN with 36 kills / 0 leaks / 0 deaths / life 2; roadblock #2 was destroyed at
frame 6839 and #11 arrived at 7162, but #6 died at 5294. V15 (CLI start 31,
input 322,821 / cached 274,176 / output 8,926 / reasoning 3,115) also simulated
WIN with the same 36/0/0/life 2 metrics; it cleared roadblock #2 at 5911 but #6
died at 4994 and #11 took two attacks. V16 was CLI start 32, left no final
message, and was manually stopped after about 26 minutes without new session
output. Internal requests remain `UNKNOWN_CLI_INTERNAL`.
## 2026-10-14 Local device targeting replays

No GPT CLI call was made in this repair round. Two original R8-2 plans were
replayed once with unchanged action snapshots: V14 remained 36/0/0/life 2 with
#6 death at 5294 and #2 destroyed at 6354; V15 became a perfect conditional
simulator result at 36/0/0/life 3, 0 protected deaths, all protected arrivals,
and #2 destroyed at 2715. R8-1 C7 was replayed once under both historical
roadblock-targeting variants; both remained WIN. Simulation starts this round:
four (two R8-2 plans plus two R8-1 targeting variants).
## 2026-10-15 R8-4 m19.1 closure

Since `da1544b`, this round used 2 new CLI process starts (V3 and V4) and 4 new
R8-4 diagnostics: accidental R2 source replay, correct V2 original replay, V3
revision, and V4 revision. V3 was 47/7/3/life -4; V4 was 54/0/0/life 3 with all
three protected targets safely arriving. The V4 result is current-model
perfect simulator WIN only. Internal model request count remains
UNKNOWN_CLI_INTERNAL.
## 2026-10-15 R8-7 m19.1 revision loop

Since `e4a33d0`, R8-7 used nine new CLI starts (V3, V4, V5, V6, V7, V8, V9,
V10, V11). V4 and V6 were static-conflict candidates without simulation. V7 and V11
failed contract validation. Fixed diagnostics were started for V3, V5, V9, V10,
plus one same-plan V5 re-evaluation after correcting the runner's retreat-redeploy
gate. V5: 21/12/7/life -9 and both protected arrivals. V9: 24/9/4/life -6 and
both arrivals. V10: 28/5/3/life -2 and only #3 arrival. Internal model requests
remain `UNKNOWN_CLI_INTERNAL`. Later V11 failed lineage, V12 was static-only,
and high-effort V13 achieved both protected arrivals but regressed to
17/16/8/life -13. V10 remains best under m19.1.

## 2026-10-15 m21 roadblock radius validation

CONFIRMED_FROM_CODE: PRTS `roadblock.html` gives 0.4472 blocking radius. The
runtime now blocks a civilian whose route enters that radius even without
passing the device tile center, stops at the first radius intersection, releases
the civilian when the roadblock is destroyed, and no longer emits repeated
blocks. A one-star operator is excluded from the deployment-slot count.

CONFIRMED_FROM_SIMULATION: m21 replayed frozen V15, V4 and V13 actions once
each; action snapshot hashes stayed unchanged. R8-2 V15 remained WIN
(36/0/0/life 3), R8-4 V4 remained WIN (54/0/0/life 3), and R8-7 V13 remained
LOSS (18/15/10/life -14). The two C7 roadblock-targeting variants were each
replayed once and both lost (55/1/0/life 4), so R8-1 requires a new m21 tactical
revision. Total m21 full-stage simulations: 5. Synthetic regression tests are
not full-stage counts.

CLI: cumulative start count is 46. The 46th start reused the frozen V14 prompt
after the read-only-home fix, reached a thread, then failed server-side at
`workspace routing discovery failed` after five reconnect attempts. No automatic
retry/resume was used; internal model requests remain `UNKNOWN_CLI_INTERNAL`.
## 2026-10-15 m22 mechanism repair run

- Mechanics version: `m22-deep-mechanics-partial-v1`.
- Code changes: static DP ledger generations/refund/99 cap, zero-duration AUTO
  scheduling, selected low-rarity skills/talents/targeting, delayed area artillery,
  and friendly device effects.
- Focused tests: 59 passed (`test_deep_mechanism_regressions.py`,
  `test_normal_low_star_mechanics.py`, `test_neutral_protected_target.py`,
  `test_local_device_targeting.py`, `test_architecture.py`, `test_real_search.py`).
- Full tests: 496 passed / 31 failed / 2 skipped (529 collected); 31-failure count matches the
  prior parent observation. Focused parent comparison is
  `docs/review/fc77177/m22_full_test_comparison_v1.json`.
- New full-stage simulations: 0. New tactical CLI calls: 0. This run was
  mechanism-repair only; historical V15/V4/C7/V13 claims remain version-scoped.

## 2026-10-15 m23 behavior regression closure

- New tactical CLI calls: 0. New full-stage simulations: 0.
- Work's 13 behavioral regressions plus the compiler CLI regression pass; no
  test was deleted or weakened to force green.
- Full tests: 497 passed / 31 failed / 2 skipped (530 collected). Parent
  `4ced50e9ea6d70abfb4c7a6967ea5a9b7c6bebf2` in the same venv/artifact snapshot
  had 34 failures; exact JUnit IDs show no new current failure and three fewer.

## 2026-10-15 m24 deployment-slot replay run

- Code checkpoint: `4073c511f214ae291ea4508af84db521254cf689`.
- New tactical CLI calls: 0. New full-stage simulation starts: 5.
- R8-1 C7 targeting A: LOSS, 54/2/0/life 3. R8-1 C7 targeting B: LOSS, 54/2/0/life 3.
- R8-2 V15: WIN, 36/0/0/life 3; 4 protected arrivals, 0 protected deaths.
- R8-4 V4: WIN, 54/0/0/life 3; 3 protected arrivals, 0 protected deaths, Ansel death frame 5304.
- R8-7 V13: LOSS, 17/16/life -15; 11 operator deaths and 2 protected deaths.
- Focused tests: 5 compiler deployment-slot cases and 17 deep mechanism cases pass.
- Full tests after the fix: 497 passed / 31 failed / 2 skipped; exact failure IDs match m23 with no additions.

## 2026-10-19 M26 deterministic-feedback R8-7 loop

- New authorization: 4 tactical CLI starts and 6 full fixed simulations.
- Actual usage: 4 CLI starts (cumulative 61) and 1 full fixed simulation.
- Attempt01: contract invalid (`parent_hypothesis_id` did not reference a declared
  strategic hypothesis); no simulation.
- Attempt02: real CLI start, then operator abort because it used `medium` rather
  than authorized `high`; no model output was accepted as a plan.
- Attempt03: schema/contract PASS, static FAIL at Midnight SP 69.5/70 on frame
  2490; no simulation.
- Attempt04: schema/contract PASS, static PASS, one fixed simulation LOSS. Result:
  16 kills / 17 leaks / 10 operator deaths / remaining life -16 / 2 protected
  deaths / 0 protected arrivals. The hypothesis expected `enemy_1112_emppnt#0`
  death by frame 3419, but it leaked at frame 5759. Twelve later skill/retreat
  commands encountered an absent source operator, first Midnight's frame-2520
  skill after frame-1680 death.
- Evidence and hashes: `docs/review/fc77177/m26_loop_results_v1.json`,
  `docs/review/fc77177/m26_attempt04_feedback_v1.json`, and the attempt04 gzip
  events/summary under `docs/review/fc77177/`.
- Full tests: 538 collected, 497 passed, 31 failed, 2 skipped. The stored JUnit
  is `docs/review/fc77177/m26_full_test_junit.xml`; exact-ID comparison with the
  m23 baseline has zero current-only failures and 31 unchanged historical
  failures.
# M27 offline verification ledger — 2026-10-19

- New tactical Codex CLI starts: 0. New full-stage simulations: 0.
- `M26-EXP-0007` is `INVALIDATED`; `M26-EXP-0008` records the corrected last-hit
  chain from saved events: #3 at frame 3180 was last hit by artillery, while #14
  at frame 3966 was last hit by `enemy_1107_uoffcr#18`.
- The M27 offline replay is
  `docs/review/fc77177/m27_r8_7_attempt04_offline_replay_v1.json`; it records
  Midnight's pre-death damage and absence of healing, the artillery lifecycle,
  both protected-target chains, first leak and 12 absent-source commands.
- Same-environment full pytest comparison: parent 34 failures, M27 child 31
  failures, zero child-only failures; two architecture failures no longer occur.
  Evidence: `docs/review/fc77177/m27_full_test_parent_child_comparison_v1.json`.

# M29 phase-plan iteration ledger — 2026-10-20

- Real Codex CLI starts: 4 of 4. V1 (`attempt_01_cli`, cumulative 65), V2
  (`attempt_04_cli`, 66), and V3 (`attempt_06_cli`, 67) completed. V4
  (`attempt_08_cli`, 68) completed a contract-valid plan but was not statically
  checked or simulated. The earlier no-output intermediate check is preserved
  and superseded in
  `docs/review/fc77177/m29_attempt08_infrastructure_failure_v1.json`. The
  non-starting `attempt_03_cli` is explicitly reconciled and not counted.
- Full-stage simulations: 2 of 4. Both completed legal battles. V2 lost at
  19 kills/14 leaks/13 operator deaths/life -12 with protected target #3 dead and
  #14 arrived. V3 lost at 8 kills/25 leaks/11 operator deaths/life -23 with #3
  arrived and #14 killed by artillery at frame 3930.
- V1 had no simulation because Gallus redeployed at frame 5250 while still in
  cooldown. V4 is not a tactical failure; it was a received but unadvanced plan.
- Evidence and hashes: `docs/review/fc77177/m29_simulation_reconciliation_v1.json`,
  `docs/review/fc77177/m29_attempt05_causal_feedback_v1.json`, and
  `docs/review/fc77177/m29_attempt07_causal_feedback_v1.json`.
- Full same-environment parent/child pytest run: child 547 passed, 31 failed,
  2 skipped; parent 529 passed, 47 failed, 2 skipped. ID-level comparison has
  zero M29-only failures and 31 shared historical failures. The 16 parent-only
  failures are local untracked-output availability differences. Evidence:
  `docs/review/fc77177/m29_full_test_parent_child_comparison_v1.json`.
- M29 simulation budget remains 2/4, but its real-model budget is exhausted.
- Phase replay of the two saved legal losses is
  `docs/review/fc77177/m29_phase_replay_v2_v3.json`; raw prompt/command/output/
  action/event/summary material is indexed by
  `docs/review/fc77177/m29_iteration_raw_manifest_v1.json`.

# M32 mechanism restoration ledger — 2026-10-21

- New tactical CLI starts: 0 of 0. New full-stage simulations: 2 of 4; 2 remain reserved.
- Fixed the static conditional-redeploy defect: another occupant now conflicts, self-occupancy
  remains conditional on observed exit/cooldown/tile/slot/DP, future death is not assumed, and
  conditional DP is not bypassed. Explicit retreat keeps deterministic cooldown and a new
  deployment generation.
- Re-verified M30 V2 and M31 V3 from copied source directories. Their action snapshot hashes and
  tactical results were unchanged. M30 V2 remains 23/10/10/life -7 with both civilians arriving;
  M31 V3 remains 22/11/10/life -9 with #3 dead and #14 arriving. Both artillery instances leaked
  at frame 5759.
- Evidence: `docs/review/fc77177/m32_final_report_v1.md`,
  `docs/mechanics/R8_7_MECHANISM_COVERAGE_V1.md`,
  `docs/review/fc77177/m32_simulation_budget_v1.json`, and
  `output/r8_1_r8_7_batch_v1/main_08-07/m32_mechanism_reverification_v1/m32_reverification_manifest_v1.json`.
- Full pytest: current 31 failure IDs versus parent 47 failure IDs; zero current-only failures.

# M34 manifest decode ledger — 2026-10-21

- New tactical CLI starts: 0. New full-stage simulations: 0; M32's reserve remains 2/4.
- Recovered the build-2771 `FlatBufferSignedConverter` path: `EnableCodeOpts=SIGN`, so the
  `.idx` payload is a 128-byte RSA signature followed directly by FlatBuffer data. No AES
  key/IV, padding, or decompression is required for these manifests.
- Decoded `main.idx` to 2,528 bundles and 56,001 asset mappings; decoded the committed
  small fixture to 35 bundles and 365 mappings. The existing 15,166/194,002-entry
  GameData manifest is a separate reference, not build-2771 equivalence.
- The decoded initial manifest contains `projectile_enemy_emppnt`; it does not contain the
  artillery body prefab. The larger reference manifest names `battle/enm_pfb_6.ab` plus
  four missing dependencies, but that remote set is not yet confirmed for build 2771.
- Focused M32/M33/M34 tests: 11/11 PASS. Evidence is under
  `docs/review/fc77177/m34_manifest_decoder_v1/`; the reproducible decoder is
  `scripts/decode_build2771_resource_manifest_idx_v1.py`.

# M35 artillery resource ledger — 2026-10-22

- New tactical CLI starts: 0. New full-stage simulations: 0; M32's reserve remains 2/4.
- The manifest decoder now treats a missing optional field beyond the complete
  two-byte vtable slot as absent, records `signature_verification=NOT_PERFORMED`,
  and supersedes the M33 allocated-block sizes with logical sizes.
- The 2.7.81 hot list resource version is `26-10-14-13-45-10-99469376`. Its body
  bundle `battle/enm_pfb_6.ab` binds `enemy_1112_emppnt.prefab` to an attack
  object with `_projectileKey='projectile_enemy_emppnt'`, destination
  `INPUT_VECTOR3`, target timing `BEFORE_SPELL_START`, a hatred-descending
  post-filter, and taunt-last sorting. Its projectile has the saved 3-second
  delay, fixed position, 10-second lifetime, one hit, and 1.2 collider radius.
- `HitBehaviour.OnProjectileReached` calls `Box2dPhysicsUtil.FindTargets_DISPOSE`;
  `RangedAttack.CreateProjectile` calls `BattleController.CreateProjectile`.
  This is a migration-candidate chain, not build-2771 proof.
- Build-2771 body binding remains unavailable. No runtime change was made.
- Evidence: `docs/review/fc77177/m35_artillery_resource_v1/` and
  `scripts/build_m35_artillery_resource_behavior_evidence_v1.py`. Focused
  M32/M33/M34/M35 resource tests: 14/14 PASS.

# M42 retreat/redeploy tactical ledger — 2026-10-23

- New tactical CLI starts: 4 of 4. New fixed simulations: 3 of 4; one simulation remains but cannot be paired with a new tactical CLI. Historical M39–M41 budgets were not reset or borrowed.
- Attempt 1 was initially recorded as an infrastructure interruption after it produced no immediate output; it later returned normally. The start remains counted and the late branch was retained as `R8_7_GPT_M42_V1_ALT`. It lost 10/23/9/life -22.
- `R8_7_GPT_M42_V1` lost 16/17/8/life -16. Its opening died because Wyvern and Medic2 were inside artillery splash geometry around Beagle; first leak was frame 961. The first Beagle retreat/refund and Noir Corne replacement did execute.
- `R8_7_GPT_M42_V2` passed schema but was correctly `STATIC_BLOCKED_NOT_SIMULATED` for exact DP conflicts at frames 2070 and 3000.
- `R8_7_GPT_M42_V3` passed static checks and was the best local branch: 19/14/9/life -13. Steward dealt 23 hits / 6850.25 to artillery, seven successful retreat refunds executed, but only one roadblock was destroyed and both protected targets were killed by artillery.
- No WIN was obtained. Evidence, hashes, causal feedback and budget reconciliation are under
  `docs/review/fc77177/m42_retreat_redeploy_artillery_window_v1/`; the full report is `m42_tactical_report_v1.md`.

# M43 joint responsibility ledger — 2026-10-23

- New tactical CLI starts: 3 of 3. New fixed simulations: 1 of 3. M42's reserved simulation was not carried forward.
- Raw M42 and M43 prompt/output/static/simulation evidence was archived under their milestone evidence directories with raw/compressed SHA-256 values and MISSING markers for absent V2 artifacts.
- Raw-event replay corrected M42 causality: V1's first leak at frame 961 followed Wyvern's frame-820 death/unblock, while Medic2 died at frame 970; V3's first leak at 1661 followed Friston's frame-1513 death/unblock. M42 V3 destroyed only roadblock #2 and only its pre-civilian-death Steward damage is a safe-output window.
- M43 V1 was static-blocked by an active Gallus cooldown at frame 4710. M43 V2 was contract-blocked by `OPERATOR_RETREAT`. M43 V3 passed static checks but lost 6/27/10/life -26, far below M42 V3's 19/14 result.
- Fixed deterministic prediction evaluation so illegal `DEPLOY`/`RETREAT` events are not VERIFIED; equivalent direct-function regressions passed. M43 V3's prediction evaluation is therefore `EVENT_NOT_OBSERVED`.
- No WIN. Full report: `docs/review/fc77177/m43_joint_responsibility_closure_v1/m43_tactical_report_v1.md`.

# M44 prediction validation and fact correction ledger — 2026-10-23

- Validation fix: explicitly illegal `SKILL_ACTIVATE` no longer matches. The M44
  V1 `char_281_popka@3240` prediction changes from `VERIFIED` to
  `EVENT_NOT_OBSERVED`; missing `details.legal` remains compatible. Focused
  regression: `PYTHONPATH=scripts:src .venv/bin/python -m pytest
  tests/test_tactical_experience_loop_v1.py -q` — 21/21 passed.
- Fact correction: V2 and V3 have 31 actions, not 35; source plans, action
  snapshots and simulation attempts support these counts. V2's `DEPLOY@1500` was
  command-successful but its handoff failed because Friston had died at 1457.
- V3 fact chain: legal Popukar `DEPLOY@1440` and `BLOCK` against
  `enemy_1108_uterer#5` established that one handoff, with a kill at 1692. The
  later first leak was Beagle's `BLOCK@1467` of `enemy_1107_uoffcr#7`, death from
  artillery at 1663, release, then leak at 1881. V3 remains 19 kills / 14 leaks /
  7 operator deaths / life -13, with both civilians killed by artillery and zero
  safe arrivals; roadblock #4 was destroyed by Melantha at 4320.
- Budget/provenance: 3/3 M44 simulations are evidenced by the budget file and
  three simulation attempts; 0/3 separate CLI starts is only a ledger declaration
  and no `cli_process_attempt.json` was found. Current-session GPT made the real
  tactical edits in the three build scripts; original prompt/response records are
  `NOT_OBTAINED`. M42/M43 residual budgets remain non-stackable.
- No WIN or tactical progress claim. Correction:
  `docs/review/fc77177/m44_joint_responsibility_iteration_v1/m44_prediction_correction_v1.json`.

# M45 joint artillery continuity ledger — 2026-10-23

- Budget: **3/3** real tactical CLI starts and **2/3** fixed simulations.
  Attempt 1 completed V1; attempt 2 timed out at 3600 seconds with no plan;
  attempt 3 completed V3. One M45 simulation remains but cannot create a V4
  without a new CLI. M42/M43/M44 balances remain non-transferable.
- `R8_7_GPT_M45_V1` passed contract/static checks and simulated as
  12 kills / 21 leaks / 11 deaths / life -19. Friston blocked #5 at 1141, died
  and released it at 1453, and it leaked at 1594; Popukar was scheduled at 3000.
  Hibiscus and Ansel later died, causing absent-operator/DP runtime errors.
  The declared Ansel-to-Wyvern heal was `EVENT_NOT_OBSERVED`.
- `R8_7_GPT_M45_V3` passed contract/static checks and simulated as
  18 / 15 / 4 / life -13. Its declared Melantha `BLOCK@1071` on
  `enemy_1108_uterer#5` was verified and #5 died at 1251. Fang blocked
  `enemy_1107_uoffcr#6` at 1208, died and released it at 1449, and #6 leaked at
  1791. Roadblocks #4/#3/#1 were destroyed; #2 remained.
- V3 protected #3 reached at 3776, but #14 died at 6314 after repeated 280-damage
  officer hits from #16/#18/#24/#26/#32. The artillery leaked at 5759. This is a
  LOSS, not WIN, real-game, faithful, robust or probabilistic evidence.
- Raw prompt/response/start/static/simulation evidence and hashes are under
  `docs/review/fc77177/m45_joint_artillery_continuity_v1/evidence/`; absent V2
  materials are explicitly MISSING.

# M46 opening survival economy ledger — 2026-10-23

- Budget: **3/3** real tactical CLI starts and **2/3** fixed simulations.
  V1 and V2 each produced one static-clean plan and one completed simulation;
  V3 timed out at 3600 seconds without a plan. The remaining simulation is not
  transferable and cannot be spent without a new CLI.
- `R8_7_GPT_M46_V1` lost 16/17/12/life -15. It repaired the M45 route-4
  `enemy_1107_uoffcr#6` failure with BLOCK@1208 and ENEMY_DEATH@1703, and kept
  Melantha's #5 block/kill. The new first failure was route-17: Midnight blocked
  #15 at 3548, died at 3789, and #15 leaked at 4176.
- `R8_7_GPT_M46_V2` lost 31/2/7/life 1. It repaired route 17 and #3 reached at
  4991, but artillery leaked at 5759 after 5817.58 damage, #14 remained
  restrained by roadblock #2 with no arrival, and route-29 #34 leaked at 6996
  after 704.85 damage. Lancet's retreat failed because it died at 2980.
- Raw prompt/response/start/static/simulation evidence and hashes are under
  `docs/review/fc77177/m46_opening_survival_economy_v1/evidence/`.

# M47 remaining gaps closure ledger — 2026-10-23

- Budget: **3/3** real tactical CLI starts and **1/3** fixed simulations.
  Attempt 1 was a real start but contract-invalid because `DEVICE_DAMAGE` was
  undeclared; attempt 2 was a real 3600-second timeout with no plan; attempt 3
  completed V2 and was then statically checked and simulated once. M42 residual
  simulations and earlier stage balances remain non-transferable.
- Focused regression now supports explicit `DEVICE_DAMAGE` and
  `DEVICE_DESTROYED` predictions without treating a missing `legal` field as
  failure. `PYTHONPATH=src:scripts uv run --frozen pytest -q
  tests/test_tactical_experience_loop_v1.py` passed 22/22.
- `R8_7_GPT_M47_V2` passed contract and static checks with 0 conflicts, then
  lost 23 / 10 / 8 / life -7. Gallus damaged roadblock #2 starting at 2490 and
  destroyed it at 4698; protected #3 and #14 reached at 4862 and 5030 with no
  protected deaths. This verified the declared first observable event only.
- The independent late failure was real: all eight operator deaths preceded the
  first leak, and four of eleven scheduled failures occurred before it (4410,
  4650, 4680, 4710). Spot blocked `enemy_1107_uoffcr#20`, but #21 killed Spot at
  4668; #20 and armored #21 leaked together at 5046, and #22 leaked at 5196 to
  reduce life to zero. Steward dealt 12006.62 artillery damage before dying at
  4120, leaving 993.38 HP, and #0 leaked at 5759. Route-29 #34 had zero recorded
  damage or block and leaked at 6996. The 5759/6996 frames are archived-timeline
  evidence, not universal deadlines; all 53 source actions match the original
  GPT JSON and frozen action snapshot.
- Raw prompt/response/start/static/simulation evidence and hashes are under
  `docs/review/fc77177/m47_remaining_gaps_closure_v1/evidence/`; compact causal
  feedback is `m47_v2_tactical_feedback_v1.json`.

# M48 joint survival interception ledger — 2026-10-24

- Budget: **1/3** real tactical CLI starts and **1/3** fixed simulations. The
  internal model-request count remains `UNKNOWN_CLI_INTERNAL`. The remaining
  2/3 CLI and 2/3 simulation balances are frozen because the full hard target
  was reached; no historical balance was transferred.
- `R8_7_GPT_M48_V1` came from Codex runner
  `openai/gpt-6.1-sol/high/features.apps=false`, parent `R8_7_GPT_M47_V2`, and
  thread `01a16e56-5228-78d0-9b87-04b932821aef`. Its plan/action hashes are
  `c2a96e30588f1a68cda40550e0ed37d371bd180d7eb52574b28218749117e783` and
  `34eb59f48384e85ff6eaef7464d75405e1d7df573811430a0f966025813c7042`.
- The 53-action V1 had 0 static conflicts and 0 runtime action errors. It won
  33/0/0 with remaining life 3, two protected arrivals, zero protected deaths,
  and zero operator deaths.
- Actual duty closure is recorded in `m48_v1_win_feedback_v1.json`: Hibiscus
  healed Ansel at 3079; Steward killed artillery #0 at 4273; Gallus destroyed
  roadblock #2 at 4698 before #14 and #3 reached at 5030/5033; #20/#21/#22 were
  blocked and killed; and #34 was blocked by Spot at 6596 then killed by Lava at
  7848.
- Raw and gzip-compressed evidence, with raw/archive hashes, is under
  `docs/review/fc77177/m48_joint_survival_interception_v1/evidence/`. The
  result is current-model simulator WIN only, not real-game, faithful, robust,
  or probabilistic WIN.

# M49 roster reduction ledger — 2026-10-25

- Budget: **3/3** real tactical CLI starts and **3/3** fixed simulations.
  Internal request count is `UNKNOWN_CLI_INTERNAL`. No M48 or earlier balance
  was transferred. The original runtime limit was not active because
  `configure()` omitted the required global declaration; post-run reconciliation
  confirmed all three unions were exactly ten. A focused runner hard check now
  propagates the limit and rejects a declared/deployed union above it.
- V1: 10 IDs, 44 actions, 0 static conflicts, 21/12/5/life -10. Beagle died at
  5038 and released #21; Fang died at 5206; #21 leaked at 5437.
- V2: 10 IDs, 45 actions, 0 static conflicts, 23/10/4/life -8. It improved the
  roadblock/#14 chain and is the best loss, but Vanilla's 4173 release let #18
  leak at 4421; Steward died at 2593; artillery #0 leaked at 5759 after only
  2466.09 damage; Beagle/Spot released #21/#22; #3 died at 5353; #34 received
  four hits totaling 631.70 damage, had zero BLOCK, and leaked at 6996.
- V3: 10 IDs, 47 actions, 0 static conflicts, 22/11/6/life -9. It verified the
  predicted Hibiscus→Ansel heal but did not convert survival into closure; #22
  first leaked at 5553 and the objective failed at 5637.
- All candidates used the same ten-ID union: Hibiscus, Lava, Beagle, Fang,
  Melantha, Steward, Ansel, Vanilla, Midnight, and Spot. The objective is NOT
  MET; the evidence does not prove ten IDs impossible. Archive:
  `docs/review/fc77177/m49_roster_reduction_win_v1/evidence/`.

# M50 ten-operator full-WIN ledger — 2026-10-25

- Budget: **3/3** real tactical CLI starts and **3/3** fixed simulations.
  Internal request count is `UNKNOWN_CLI_INTERNAL`. No M48/M49 balance was
  transferred. Each candidate passed the repaired configured hard ten-ID gate,
  contract validation, and static checks with 0 conflicts/0 UNKNOWN.
- V1: 10 IDs, 37 actions, 14/19/8/life -17. Wyvern's verified `BLOCK@656` did
  not prevent its death/release at 792; the later skill/Ansel deploy income
  dependency failed. #2 leaked at 986.
- V2: 10 IDs, 30 actions, 28/5/4/life -3. It repaired the V1 opening and is the
  best loss, but Fang's death released #21 at 4786; #21, #27, #29, #33, and
  artillery #0 leaked, while #3 died and #14 arrived.
- V3: 10 IDs, 32 actions, 19/14/7/life -12. A verified early Lancet heal did not
  prove the whole survival chain; Friston died at 2111 and the runtime DP chain
  broke, causing #11's first leak at 3065.
- All results are current fixed-model LOSS. Evidence and hashes are under
  `output/r8_1_r8_7_batch_v1/main_08-07/m50_ten_operator_full_win_v1/` and
  `docs/review/fc77177/m50_ten_operator_full_win_v1/`.

# M51 ten-operator WIN ledger — 2026-10-25

- Authorization was 3 real Codex CLI starts and 3 fixed simulations. Actual
  usage is CLI 2/3 and simulations 2/3; V2 reached the hard goal and the unused
  remainder was frozen. Internal request count is `UNKNOWN_CLI_INTERNAL`. No
  M48/M49/M50 balance was transferred.
- V1: 10 IDs, 29 actions, static-clean, 28/5/2/life -2. Five leaks were
  #11@3065, #13@3425, #28@6101, #31@6292, and #34@6996. Steward killed artillery
  #0 at 4273, proving the old M50 survival failure was repaired but not the
  whole route set.
- V2: 10 IDs, 29 actions, static-clean, 33/0/0/life 3 with both protected
  targets safe. GPT moved Lancet-2 from 2162 to 1962, delayed Steward from 2071
  to 2132, and changed the invalid dead-Melantha tail to a live Fang retreat and
  redeploy. No runtime action error occurred.
- Frozen artifact is
  `output/r8_1_r8_7_batch_v1/main_08-07/m51_ten_operator_full_win_v2/attempt_02_cli/`.
  Closeout and hashes:
  `docs/review/fc77177/m51_ten_operator_full_win_v2/m51_closeout_v1.json`.

# M52 minimum-count ledger — 2026-10-25

- Authorization was 3 real Codex CLI starts and 3 fixed simulations; all were
  used. M51 remained frozen at CLI 2/3 and simulation 2/3. Internal request
  count is `UNKNOWN_CLI_INTERNAL`.
- M51 V2 was verified from local source/plan/action artifacts before use:
  10 IDs, 33/33 hostile kills, zero leaks, both protected targets reached.
- V1: parent M51 V2, 9 IDs, 27 actions, static-clean, WIN at 33/0/0/life 3.
  It removed Lava while preserving opening, artillery survival, late Uterer,
  armor #34, and both protected targets. This is `best_verified_win`.
- V2: parent V1, 8 IDs, 28 actions, static-clean, LOSS at 20/13/8/life -11.
  Steward died at 2561 before the first 4625 leak; #20 had zero damage/BLOCK.
- V3: parent V1 with V2 feedback, 8 IDs, 27 actions, static-clean, LOSS at
  19/14/6/life -12. Friston died at 2111 and #11 leaked at 3065.
- Closeout:
  `docs/review/fc77177/m52_minimum_operator_reduction_v1/m52_closeout_v1.json`.

## 2026-10-25 — M53 closes at limits without an 8-ID WIN

M53 used its own 3/3 real tactical CLI starts and 3/3 fixed simulations. V1,
V2, and V3 each used exactly 8 distinct IDs and passed static checks.
V1 lost 20/13/5/life -11; V2 lost 21/12/6/life -10; V3 lost 19/14/8/life -12.
The local M52 V1 baseline remains the best verified 9-ID current-model
simulator WIN. No global minimum, real-game, faithful, robust, or probabilistic
claim is made. Closeout:
`docs/review/fc77177/m53_eight_operator_joint_revision_v1/m53_closeout_v1.json`.

## 2026-10-25 — M54 closes at limits without an 8-ID WIN

M54 used its own 3/3 real tactical CLI starts and 3/3 fixed simulations. V1,
V2, and V3 each used exactly 8 distinct IDs and passed static checks.
V1 lost 15/18/8/life -17; V2 improved to 23/10/7/life -8; V3 regressed to
19/14/8/life -12. The local M52 V1 baseline remains the best verified 9-ID
current-model simulator WIN. No global minimum, real-game, faithful, robust,
or probabilistic claim is made. Closeout:
`docs/review/fc77177/m54_minimum_operator_continuation_v1/m54_closeout_v1.json`.

## 2026-10-26 — M55 closes at the one-call limit

M55 used 1/1 real tactical CLI starts and 1/1 fixed simulations. V1 was a
32-action, static-clean, exactly-8-ID fresh fusion. It lost 12/21/6/life -19
after Melantha's 1888 death, #9's 2121 leak, and later artillery/#34 leaks.
Closeout:
`docs/review/fc77177/m55_eight_operator_fusion_v1/m55_closeout_v1.json`.

## 2026-10-26 — M58 closes on the open-roster comparison contract

The user revoked M58's dynamic-evidence prerequisite and supplied
`USER_CONFIRMED_TACTICAL_PREMISE`; this authorized tactical exploration but did
not convert the still-unexecuted S0-S3 client UNKNOWNs into client facts. M58
used 1/1 real GPT tactical CLI starts and 0/1 fixed simulations. The 30-action,
exactly-8-ID A_SPOT_FUSION candidate was the selected contender, but contract
validation failed because the raw model comparison used `contenders`,
candidate-level `contender_id`, and no top-level `selected_structure_id` instead
of the enforced `candidates`, `structure_id`, and `selected_structure_id`
fields. Per the no-retry rule, it was saved and stopped before static compile or
simulation. A later no-model-call protocol recovery preserved the plan/actions,
passed the same contract, and passed static checks with 0 conflicts; a focused
range check found that returned Steward at [5,6] DOWN does not cover returned
Fang at [4,4]. The best verified WIN remains M52 V1 at 9 IDs. Closeout and
failure feedback:
`docs/review/fc77177/m58_user_premise_open_roster_v1/m58_closeout_v1.json` and
`docs/review/fc77177/m58_user_premise_open_roster_v1/m58_v1_contract_failure_feedback_v1.json`.
Protocol recovery:
`docs/review/fc77177/m58_user_premise_open_roster_v1/m58_protocol_recovery_report_v1.json`.

## 2026-10-26 — M59 verifies the frozen M58 8-ID candidate and loses

M59 used its own authorization with 0/0 new tactical CLI calls and 1/1 fixed
full-stage simulation. It did not transfer M58's closed simulation balance or
reopen M58. The normalized M58 candidate was audited losslessly against the
original `contenders` output, passed the original contract with the 8-ID gate,
and passed static compilation with 0 conflicts.

The unchanged 30-action A_SPOT_FUSION run lost at 15 kills / 18 leaks / 8
operator deaths / life -16. Fang's living retreat at 2430 refunded 5 DP and Spot
deployed at 2431, but Fang held no block at retreat, so it released no enemy.
Spot's 2882–3632 healing window did heal Hibiscus at 3038 and 3155, but Hibiscus
died at 4363 after the window ended. Steward died at 4061, so the 4800 retreat
failed; his 6901 return had no post-return damage. Artillery #0 received
11757.52 damage across 40 hits, was not blocked, and leaked at 5759. Armored #34
spawned at 6330, received no damage or block, and leaked at 6996. Protected #3
died at 3311; protected #14 reached at 10219.

The best verified current-model simulator WIN remains M52 V1 at 9 IDs. This one
loss does not prove 8 IDs impossible. No faithful, real-game, robust, or global
minimum claim is made. Closeout and evidence:
`docs/review/fc77177/m59_frozen_m58_spot_fusion_v1/m59_closeout_v1.json` and
`docs/review/fc77177/m59_frozen_m58_spot_fusion_v1/evidence/attempt_01/`.

## 2026-10-27 — M60 stops at the one-call contract gate

M60 used its own 1/1 real tactical CLI start and 0/1 fixed simulations. Its
prompt was 131,678 bytes and supplied the full low-star catalog, routes, M59
causal feedback, current Spot/Ansel limits, the eight-ID gate, and the corrected
`candidates`/`structure_id`/`selected_structure_id` contract. The model returned
three comparison candidates but placed `selected_structure_id` at the JSON root
instead of inside the comparison and emitted only one revised strategic
hypothesis. Validation failed on exactly those two errors. Because inventing two
hypotheses is semantic repair, not an outer-field recovery, Python stopped
before static compile and simulation.

The model's raw comparison preferred `M60_DUAL_ARTS_SHARED_MEDIC`; it retained
`M60_SPOT_LOCAL_FUSION` and `M60_YATO_LOCK_ROTATION` as alternatives, with the
Yato pre-strike behavior marked not expressible. No M60 simulation result exists
and the failed 35-action plan is not a tactical WIN or LOSS. The best verified
current-model simulator WIN remains M52 V1 at 9 IDs. Evidence:
`docs/review/fc77177/m60_m59_feedback_revision_v1/m60_closeout_v1.json` and
`docs/review/fc77177/m60_m59_feedback_revision_v1/evidence/attempt_01_cli/`.

The post-closeout protocol audit found that the stale prompt itself asked for a
top-level selected ID while the validator required the nested comparison path,
and that the three-hypothesis requirement was a hidden runner gate. Under the
future contract, a read-only recheck moves only that selected field; the plan and
35 actions remain hash-identical and the one referenced hypothesis passes. The
alleged roster violation is a name confusion: M60 used `char_209_ardign`
(`卡缇` / Cardigan, 3-star), not `char_328_cammou` (`卡达` / Click). M60's
original contract failure and no-simulation result remain unchanged; see
`m60_contract_repair_recheck_v1.json` in the same M60 review directory.

## 2026-10-27 — M61 stops after one simulation-start input mismatch

M61 made its own single GPT revision call from M60's static conflict and the
M59 event feedback. The prompt was 133,010 bytes, used the nested selected path,
and passed the no-model fixture. The model compared reciprocal medicine/Spot
rotation, dual arts with Cardigan/Durin, and Yato pre-swing locking; it selected
the first as current-model checkable. The 34-action plan used
芬/Friston-3/月见夜/玫兰莎/安赛尔/芙蓉/斑点/史都华德 and had an 8-ID union.

The original static compiler passed with zero conflicts and zero unknowns. The
one authorized simulation was therefore started and consumed, but the diagnostic
loader immediately failed before the simulation model ran with
`KeyError: 'debug_configuration'`; the compact prompt-facts omitted that
diagnostic-only field. This is an executor input mismatch, not a tactical WIN or
LOSS and not a MODEL_GAP. No action was repaired and no retry was made. The M52
nine-ID WIN remains best verified. Evidence and closeout are under
`docs/review/fc77177/m61_m60_static_revision_v1/`.

The post-closeout input repair restored only the omitted
`normal_low_star_catalog[*].debug_configuration` from the hash-matched M60 full
facts. The execution-ready context and the original M61 plan/34 actions are
deep-equal; a new preflight and static recheck both pass without starting the
simulator. This repair does not refund or change M61's `CLI 1/1, simulation
1/1` ledger or turn the started-but-pre-battle attempt into a WIN/LOSS.

M62 reran that repaired candidate unchanged with no new GPT call. Contract,
preflight, 8-ID union, and static checks passed; the one authorized simulation
completed as a current-model LOSS at 24 kills, 9 leaks, 4 operator deaths,
protected #3 killed, #14 arrived, and life -7. Steward died at 4393 before the
4800 retreat; artillery #0 and #34 both leaked at 5759/6996, while the later
Steward return killed other inner enemies but never hit #34. M52 V1 remains the
best verified 9-ID WIN. Evidence is under
`docs/review/fc77177/m62_m61_execution_ready_validation_v1/`.

After committing the protocol repair (`c415941`), a static-only check used the
same failed M60 plan after the audited outer-field move. Protocol validation
passed and all 35 actions remained hash-identical, but the existing static
compiler found one unique conflict site (reported twice): action 27 tries to
deploy Durin to `[5,5]` DOWN at 6901 while Ansel still occupies that tile, with
declaration mismatch. No simulation was started and no action was changed. The
failed plan remains available for later GPT revision, not a WIN/LOSS.

## 2026-10-27 — M63 stops when its sole CLI turn is externally aborted

M63 made one real GPT revision call from M62's causal feedback using the
correct nested `selected_structure_id` contract. The no-model protocol fixture
passed with three structures, one selected ID, one referenced hypothesis, an
8-ID union, and 34 executable operator configurations. The authorized CLI turn
started at 08:05:00 UTC and was externally interrupted at 08:45:55 UTC after
2,449,107 ms. It emitted only four intermediate progress summaries; it never
committed a final three-candidate comparison or complete plan.

Consequently, no plan was frozen, static compile did not run, no simulator
entered `Simulator.run`, and the fixed-simulation budget remains 0/1. Python
did not reconstruct missing tactics, candidate selection, or actions. The M52
V1 nine-ID current-model simulator WIN remains best verified. M63 is counted as
`CLI 1/1, simulation 0/1`, with no WIN/LOSS and no eight-operator conclusion.
Raw session, hashes, prompt/schema/context, and fixture evidence are under
`docs/review/fc77177/m63_m62_feedback_revision_v1/`.

After the first external abort, the user explicitly authorized reruns. A
second start was reclaimed by its tool-session process group before producing
output; a third `setsid`-detached call completed successfully. M63 is therefore
counted as `CLI 3/3, simulation 1/1`. The accepted V3 plan compared
split-medic/dual-arts, Spot-fusion reordering, and Yato/Cardigan rotation, then
selected `M63_SPLIT_MEDIC_DUAL_ARTS` with an 8-ID union and 25 actions.

Contract, execution-input gate, and static compile all passed. The fixed full
stage then completed as a current-model LOSS: 19 kills, 14 leaks, 8 operator
deaths, and life -12. The first leak was officer #13 at 3501; objective failure
began at 5046. Artillery #0 leaked at 5759 and killed protected #3 at 5341,
while #14 reached at 9919. Final armor #34 leaked at 6996. Midnight died at
4753, making the 6900 retreat illegal; Steward's later 6451 return was legal
but he died again at 6635. No WIN/LOSS claim extends beyond the fixed
simulator, and M52 V1 remains best verified. Evidence is under
`docs/review/fc77177/m63_m62_feedback_revision_v1/evidence/attempt_03/`.

## 2026-10-27 — M64 closes as an early-leak LOSS

M64 made its own single GPT revision call. It compared early Midnight/Spot with
two Fang returns, Vanilla/Durin stationary arts, and Cardigan/Yato bait; it
selected the first because its decisive actions were current-model checkable.
The accepted plan used 芬/Friston-3/月见夜/玫兰莎/芙蓉/安赛尔/史都华德/斑点,
had 36 actions and an 8-ID union, and passed contract, execution-input, and
static checks with zero conflicts and zero unknowns.

The one authorized fixed simulation completed as a LOSS at 20 kills, 13 leaks,
7 operator deaths, and life -11. The first leak was officer #20 at 4821, and
objective failure began at 5196. Artillery #0 again killed protected #3 at
5341 and leaked at 5759; #14 reached at 9618. Armor #34 still leaked at 6996.
Hibiscus, Ansel, Steward, Friston, Spot, Midnight, and Fang all died, with
illegal retreats at 4440/4770/6330 after respective death states. M52 V1
remains the best verified current-model simulator WIN. Evidence is under
`docs/review/fc77177/m64_m63_revision_v1/`.

## 2026-10-28 — M65 closes at its single-call and single-simulation limits

M65 made one real GPT revision call from M64's original events and the verified
M62 cross-branch facts. Its no-model protocol fixture passed the nested
`m58_open_roster_comparison` path, three distinct candidates, one selected ID,
one referenced hypothesis, and the 8-ID union gate. The model compared Spot
repair, permanent core with Durin rotation, and Cardigan/Yato bait; it
autonomously selected `M65_PERMANENT_CORE_DURIN_ROTATION` with
芬/Friston-3/月见夜/玫兰莎/安赛尔/芙蓉/史都华德/杜林 and 25 actions. Contract,
execution preflight, and static compile all passed with 0 conflicts/unknowns.

The one authorized full-stage simulation completed as a fixed-model LOSS:
20 kills, 13 leaks, 5 operator deaths, and life -11. The first leak was officer
#19 at 4507. Protected #3 passed roadblock #3 but remained blocked by roadblock
#1, took two artillery hits plus three officer hits, and died at 5384; #14
reached at 9619. Artillery #0 took 4105.78 damage without dying, hit #3 twice,
and leaked at 5759. #34 had zero operator damage and zero blocks, hit
Melantha/Hibiscus five times, and leaked at 6996. Steward, Ansel, Fang,
Midnight, and Friston died at 2743/3043/4180/4753/6127; later Ansel and
Midnight actions were illegal dead-state commands. M52 V1 remains the best
verified current-model 9-ID WIN, and no eight-ID impossibility or
operator-uselessness claim follows.

## 2026-10-28 — M66 closes three authorized iterative loops without an 8-ID WIN

M66 first compressed the M52 V1 nine-ID WIN into a read-only contribution table,
then used its authorized three CLI calls and three fixed full-stage simulations
as independent revision loops. No balance transferred and no automatic retry was
used. A V3 pre-STARTED authorization rejection for a missing
`features.apps=false` override entered no model process and was not counted.
Each valid loop compared at least three structures, selected one complete plan,
passed contract/execution/static gates, and then consumed one simulation.

V1 `M66_M52_MEDICAL_REDISTRIBUTION` lost 17/16/8/life -14; first leak
#15@4176 and protected #3 died@5191. V2 `M66_SPOT_OUTER_DELAYED_HEAL` lost
19/14/7/life -13; the declared Melantha-to-Spot BLOCK was absent, #9 leaked
@2007, and both protected targets died to artillery. V3
`M66_MIRRORED_OUTER_DUTIES` used 芬/Friston-3/月见夜/玫兰莎/安赛尔/芙蓉/米格鲁/
史都华德, 27 actions, and a valid 8-ID union; it passed 0-conflict/0-unknown
static checks but lost 19/14/6/life -12. Its expected Melantha BLOCK occurred
@921, yet #11 was never blocked and leaked @3065, life first reached zero @4627,
protected #3 died@5353, artillery leaked@5759, and #34 leaked@6996.

M66 therefore records no 8-ID WIN. M52 V1 remains the best verified
current-model fixed-simulator result. This does not prove 8-ID impossibility,
operator uselessness, or any real-game/robust claim. Full prompts, model
comparisons, snapshots, static/preflight results, gzipped original events,
budget, hashes, and closeout are under
`docs/review/fc77177/m66_nine_win_compression_v1/evidence/`.

## 2026-10-28 — M67 closes at three CLI calls with two completed simulations

M67 supplied the verified M52 V1 nine-operator contribution table and all three
M66 original-event loss chains, explicitly allowing GPT to replace or delete any
operator. V1 selected Spot outer-medical bridging and removed Lancet/Beagle from
the tested roster. Its 33-action, 8-ID plan passed contract, execution input,
and static gates with 0 conflicts/unknowns, then lost 26/7/6/life -4. It
improved on several old gaps: Ansel's expected early heal occurred, Friston
survived to 4869, Steward killed artillery#0 at 4453, and both protected targets
arrived. The remaining break was the central death cascade; #21 and #34 leaked.

V2 reserved the second-barrage medical skills. Its expected heal occurred@3647,
but Ansel and Steward died together@3793; the plan regressed to 21/12/7/life
-10, artillery killed protected #3@5353 and leaked@5759, and #34 leaked@6996
with zero operator damage/BLOCK. V3's real CLI start then failed without a
structured plan after repeated Codex model-refresh timeouts; it was counted as
CLI 3/3, was not retried, and did not start the remaining simulation.

M67 therefore records no 8-ID WIN and no 8-ID impossibility. M52 V1 remains the
best verified current-model fixed-simulator result. Evidence, hashes, gzip
round-trip manifests, and failure boundaries are under
`docs/review/fc77177/m67_contribution_replacement_v1/evidence/`.

## 2026-10-28 — M68 closes three CLI calls with two completed simulations

M68 used M67 V1's original events as the revision focus and allowed GPT to
replace or delete any operator. V1 selected
`M68_EARLY_HIBISC_RESERVED_SPOT_CASTER_ROTATION`. Its 31-action, 8-ID plan
passed contract, execution input, and static gates with 0 conflicts/unknowns,
then lost 24/9/5/life -7. Steward died@2593 after two 910 artillery hits;
Hibiscus, Friston, Fang, and Melantha died@4543/4768/4954/5356. Fang unblocked
#21 and Melantha unblocked #22 on death. Protected #3 died@5353, artillery
leaked@5759, and #34 leaked@6996 with zero BLOCK and only 49.7 Midnight damage.

V2 selected `M68_SEPARATED_EAST_EARLY_CASTER`. Its 30-action, 8-ID plan passed
all pre-run gates, then regressed to 19/14/9/life -13. The earliest break was
Spot: artillery splash 558@4060 plus officer ticks killed him@4119, releasing
#16/#18, which leaked at 4506/4491. Steward died@2743 after two 910 artillery
hits; artillery took only 3686.68 operator damage. Neither protected target
reached and roadblocks #1/#2 were not destroyed.

V3's real CLI start counted 3/3. GPT produced a structured 31-action, 8-ID plan,
but contract validation failed because the expected first observable event used
unsupported `PROJECTILE_BORN`. The plan was not normalized or rewritten, no
static gate or simulation followed, and no tactical LOSS was recorded. M68 ends
at CLI 3/3 and simulation 2/3 without an 8-ID WIN. M52 V1 remains the best
verified current-model fixed-simulator result. Evidence, gzip round-trip
manifests, and failure boundaries are under
`docs/review/fc77177/m68_m67_v1_causal_revision_v1/evidence/`.

## 2026-10-28 — M69 repairs projectile queries and closes five candidate attempts

M69 first repaired the read-only event contract before tactical work: the
existing exact `type/source/target/frame` matcher now accepts
`PROJECTILE_BORN`, without changing simulator mechanics or M68's historical
contract failure. Focused tests cover matching, wrong target/frame rejection,
and unchanged invalid-query semantics. This repair consumed no tactical budget.

Candidate 1 restored M68 V3 verbatim with no model call and simulated it once:
23/10/5/life -8. Candidate 2 then used one real CLI and became the best M69
result at 27/6/3/life -4; it killed #34 via Friston BLOCK@6596-7194, but Fang
died@4786 and released #21, while Steward died@2743 and artillery plus #3
remained open. Candidate 3 regressed to 19/14/7/life -12 after artillery killed
Hibiscus and Steward together@3073. Candidate 4 lost 23/10/5/life -8 despite
12753.92 artillery damage because artillery survived, protected #3 died@3343,
and #34 had no contact. Candidate 5 was closest but still a complete LOSS at
30/3/1/life 0 with zero runtime action errors and both protected targets safe:
Steward dealt 13227.21 and killed artillery@4273, but Friston died@6577 to
mixed #28/#31/#34 damage and released #28/#31; #28 leaked@6788, #31@6806, and
#34 leaked@6996 with only 722.39 damage and zero BLOCK.

M69 therefore ends at candidate attempts 5/5, real CLI 4/4, and full
simulations 5/5. No eight-ID WIN was found; M52 V1 remains the best verified
nine-ID current-model fixed-simulator result, and this does not prove eight-ID
impossibility or operator uselessness. Evidence, prompts/schema/replies,
candidate comparisons, frozen plans, preflight/static results, gzipped original
events, feedback, budget, protocol diff/tests, and 174 verified hashes are under
`docs/review/fc77177/m69_projectile_query_contract_v1/evidence/`.

## 2026-10-29 — M70 full-roster reassessment wins at eight IDs

M70 built a new independent ledger and required an original-event row for every
M69 C5 operator, explicitly stating that no role was mandatory. GPT compared
`M70_LOWER_EXCLUSIVE_ARTS`, `M70_SPOT_CENTRAL_BEAGLE_BACKUP`, and
`M70_YATO_WINDUP_ROTATION`, then selected the first structure. Its 29-action,
8-ID plan passed schema/semantic, execution-input, and static gates with 0
conflicts/unknowns, then won the first authorized full simulation: 33 kills,
zero leaks, zero operator deaths, life 3, and both protected targets safe.

Observed closure was Fang/Midnight/Melantha killing #21/#22/#33, Steward
killing artillery#0 after 13227.21 damage, and Fang/Friston/Midnight/Steward
combining for 5092.32 damage before Steward killed #34. The model stopped after
candidate 1, leaving candidate 4/5, CLI 4/5, and simulation 4/5 unused. M52 V1
is superseded as the best verified count by this current fixed-simulator M70
eight-ID WIN. Full evidence, hashes, prompts, comparisons, frozen plan, static/
preflight, gzipped events, and closeout are under
`docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/`.

## 2026-10-29 — M71 exhausts five shared slots without a seven-ID WIN

M71 initialized target K=7 with a shared budget of five candidates, five real
CLI starts, and five fixed simulations. All ordinary-1–3-star contracts, K=7
hard-limit fixtures, prompts, schemas, preflight, and static checks were kept
separate from M70/M69 ledgers. Candidates 1–3 each occupied one candidate slot
and one real CLI start, but failed after STARTED with
`Selected model is at capacity. Please try a different model.` They produced no
plan and were recorded as execution failures, not tactical LOSS.

Candidate 4 selected `CONTINUOUS_STEWARD_PERMANENT_MELANTHA`. Its 7-ID, 22-action
plan passed contract and static gates, then lost 11 kills / 22 leaks / 7 operator
death events / life -21. Hibiscus was hit by artillery 890@1421 and 890@1571 and
died before her planned skill; Ansel and Melantha died@2111, Steward@2411, and
the first protected failure was artillery#0 killing #3@3310. Artillery received
only 2216.99 Steward damage; #34/#28/#31 had zero operator DAMAGE.

Candidate 5 selected `EARLY_MIDNIGHT_CONTINUOUS_LOWER_CASTER`. Its 7-ID,
25-action plan passed contract and static gates, then lost 15 / 18 / 6 / life
-17. Melantha and Ansel died together@2111, Steward@2411, first leak was
officer#16@4070, #3 died@5384, #14 died@6314, and #34 still had zero operator
DAMAGE. Midnight@481 was deployed as the declared observable event, but that
single observation did not establish the full hypothesis.

M71 ends with candidate attempts 5/5, real CLI starts 5/5, simulations 2/5, and
no seven-ID WIN. M70 V1 remains the best verified current-model fixed-simulator
result at eight IDs. Seven-ID feasibility remains UNKNOWN; neither the two
tactical LOSS results nor three capacity failures prove infeasibility. Evidence,
prompts/schema/replies, frozen attempts, static/preflight, gzipped events,
feedback, budget, and 117 verified hashes are under
`docs/review/fc77177/m71_fewer_operator_search_v1/evidence/`.
