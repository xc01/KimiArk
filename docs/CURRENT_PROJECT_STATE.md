# Current Project State

更新时间：2026-10-09；最新独立审查基线 f1a1c7db72f7912b30ca7edae7fc5a239d98d386。下列首轮数字保留为历史快照，由末尾最新状态覆盖。

## CONFIRMED_FROM_CODE

- 实际 clone GitHub 成功，master / remote HEAD 等于基线；23 个 tracked 文件，其中 18 份保存的 V3 artifacts。
- 保存的三份计划均选择 route-3:FIRE；保存的前缀证书均在 295 记录冲突（22/21/22 vs 19.8333）。这确认文件内容与共同调用路径，不确认真实关卡期限。
- 新输出文本有 merged anchor、upstream/downstream dam、delayed upgrade 等结构变化；不能证明已消除旧冲突。
- 源证据恢复完成：`src/`、repair/search/audit 依赖、context/catalog、旧 ledgers/certificates/trace、V3 request/response/completion 已纳入审查交付。见 `review/evidence_index.json`。
- GameData 不提交 1.1 GB 树；`review/gamedata_source.json` 固定 archive SHA-256、upstream commit `0ef7f95...`、data version `rel77.0` 与恢复命令。23.9 MB V3 SSE response 以 gzip + manifest 交付。
- `output/r8_1_v3_source_evidence_reverification_v1/` 确认 295 是 route-3 最早接敌事件；三个 V3 fire 槽的 plan-specific FIRE establishment deadline 为 UNKNOWN。295 不再作为开火硬期限。
- 本轮定向 unittest 29/29 PASS；compileall PASS。完整 unittest 94 项中 87 项 PASS，7 个模块因系统缺少 `pytest` 在导入阶段 BLOCKED，未标为通过。
- 确认并修复诊断升级为 proof、unknown→spawn fallback、退款条件小写漏报、后处理依赖失败先覆盖 artifacts 四类问题。补丁后的状态 UNKNOWN，未生成真实动作或完成机制复验。
- 新回归 5/5 PASS，传输 10/10 PASS，compileall/diff-check PASS；全套 20/23 PASS，余下三项是原交付缺件故障，不隐藏。
- 历史 18 份 JSON 原样保留，不运行 postprocess 或 prepare，未调用 Kimi，模拟次数零。历史 final_status/learning_progress 已被本次审查限制，不是当前权威状态。

## REPORTED_BY_PREVIOUS_WORKER

数百次搜索无 WIN；667/170 旧 fidelity 不完整；111 numeric hallucinations 为错误分类；五份旧计划的 deadline/DP 冲突；成功一次 Kimi-K3 V3 调用与 PARTIAL 学习。这些均需各自源代码和原 artifacts 才能独立确认。全部关键数字及理念保留于 PROJECT_CHARTER，不丢弃历史但不升格证据。

## HYPOTHESIS

旧 HYPOTHESIS 已消歧：恢复的 establishment_deadline 的 FIRE 分支取 earliest_operator_contact_frame，295 来源已确认，不是 spawn fallback。新 blocker/queue 能否允许更晚开火仍 UNKNOWN，400–600 叙述也不自动成为合法期限。

## 当前决定

审查补丁 `59add38` 已合入；fidelity/census 表已恢复。Plan A 有界复验完成：qualified opening 组合为 0，未生成 witness，未模拟，未调用 Kimi。原因是 A03 无支持的高 DPS anchor、部分 trait 语义不可用，且退款 UNKNOWN。这是 scoped conflict，不是全局战术失败。

## 最新独立审查：f1a1c7d

CONFIRMED_FROM_CODE：remote master 与 HEAD 核实；12 个 manifest 文件 hash/bytes 匹配；pinned GameData level 及目标 enemy 实际取得并与交付一致；真实路线几何与 source clock 得到接敌 295、最晚可拦截到达 431。三份 FIRE 建立时间和可行性仍 UNKNOWN。

保存的 23.9 MB 原 SSE 实际重放为 response.completed，无 parser error，envelope/structured/prompt/request fingerprints 匹配。可确认保存的一条响应，不可证明不存在其他历史调用。

纠正“所有证据已恢复”：fresh checkout 仍缺 all_operator_fidelity/all_operator_census；原 loader 静默空表导致每个 anchor pool 从记录的21变22，新增 char_4211_snhunt。source-reverification 已最小修复为缺表 BLOCKED/候选 UNKNOWN，并支持只读测试不写历史输出。

原定向29/29重现，修复后31/31；compileall/diff-check PASS。fresh 基线 unittest Ran67，32 PASS、1 failure、34 errors；除 pytest 外还缺 GameData/fidelity/若干历史 outputs，不把worker87/94认作fresh clone结果。日志及证据见 review/f1a1c7d/。

下一阶段只做现有 Plan A 的0–941开局 witness，预算与验收见 NEXT_MILESTONE。无 Kimi/新增计划/阶段计划模拟/新 WIN。

## 最新独立审查：23a623a（覆盖前述当前决定）

CONFIRMED_FROM_CODE：实际 fetch/ls-remote 核实 master=23a623ae4960c0095d71f1f28ca5d3d782e642c1；两表真实存在、hash 与305项匹配。Plan A 是候选 gate audit，12为数量乘积，未枚举执行；无 witness/模拟。

## 2026-10-10：一次有界 Kimi-K3 Plan A 修订

CONFIRMED_FROM_CODE：审查修复已合入为 `8a2a0d3`。Kimi-K3 恰好调用一次并返回 `response.completed`，model 字段为 `kimi-k3`。新计划 `R8OP-A1-BLOCK1-COOP-ANCHOR390` 显式拒绝把 250 当作通用 deadline，移除 wscoot 的无技能 dam 职责，假设退款为 0，默认省略 A05/route-6，并把 [9,2] roadblock、cooperation、upkeep 和 target ordering 留作条件分支。

有界确定性校验实际生成 2 个 distinct opening 组合和 1 条方向完整动作候选；0 次阶段模拟。当前模拟器公式下：strong route-2 于 357 击杀；caper-only route-1 最晚 474 开火、804 击杀；talr+caper 在“两目标持续被挡且按当前 target ordering”的假设下 route-1 431、route-3 600。这些是条件性局部证书，不是完整 witness。`[9,2]` 部署合法性、退款、merchant upkeep、真实 targeting/timing 仍 UNKNOWN。

fresh checkout 缺 build_operator_runtime_fidelity.py，原7项Plan A测试在初始化失败。最小修复为来源缺失显式UNKNOWN；定向41/41通过。DPS公式不是有限窗口伤害上/下界；15-DP账本不是实际候选经济下界；A05条件让路未计算。caper能覆盖[8,5]，不能声称全部几何不覆盖。历史artifacts保持不变，失效结论由本段与review报告约束。

wscoot技能未开阻挡0的description与计划无技能依赖dam矛盾；merchant upkeep/ammo/refund等运行时仍未证实。不能把未支持机制推广成战术失败。先完成NEXT_MILESTONE中的固定候选契约计算，无Kimi/V4/扩搜。worker全量96/103仅REPORTED_BY_PREVIOUS_WORKER；本轮无完整测试通过声明。

## 最新有界计算：Plan A 固定候选开局契约

CONFIRMED_FROM_CODE：审查补丁已合入为 `491a9a0`；真实 `scripts/build_operator_runtime_fidelity.py` 已确认存在，SHA-256 `ab63a4e52f9d5ef3e6bd4c0be53af812eff67dcf9849b8200942adead50b7212`，并随本轮上传。原始表生成 commit 仍为 `UNKNOWN_ORIGINAL_GENERATION_COMMIT`。

CONFIRMED_FROM_CODE（当前模拟器公式与确定性上下文）：只使用旧候选 1/1/3/2/2 并实际枚举 12 个结构组合。caper 从 [9,2] DOWN 可覆盖 [8,5]；angel/aprl 不可覆盖。caper 逐击、attack-SP 计算在 450 帧部署时 route-1 第 12 击于 780 帧完成；随后 route-3 于 810 开火、1140 帧完成，错过 941。若两个目标均被持续挡在 [8,5]，双期限要求 route-1 最晚 250 帧开火，route-3 在 610–940 完成。

CONFIRMED_FROM_CODE（base-cost model）：frame-250 前缀 A01+A02 后可用 DP 5.333；aprl 11 成本缺 5.667，caper/angel 12 成本缺 6.667。无退款、base-cost 分支中 A04 在 725 可支付；A05 在 729 不可支付，因此保留 COND_ROUTE6 false 分支：省略 A05 并让 route-6。退款与 merchant 实际经济仍 UNKNOWN。`trap_020_roadblock#2` 占据 [9,2]，anchor 部署合法性 UNKNOWN。没有 faithful witness，阶段模拟 0 次；这不是全战略不可行。

## 最新独立审查：d9304bb
CONFIRMED_FROM_CODE：实际fetch及remote HEAD核对；生成脚本hash与12个manifest输入一致；原定向48/48复现。780/1140与条件性250推导复算成立，但非通用FIRE期限。确认退款只在一行入账后丢失、A05省略仅文字、测试PASS硬编码三类程序缺陷并最小修复；定向52/52通过。hypothetical5退款在12-cost开局729为+2.3（不含upkeep），仍不是事实可行证书。12结构tuple中6个全部署分支重复duelist。历史artifacts保持，纠正计算在review/d9304bb/。无Kimi/关卡模拟；下一阶段一次Kimi-K3开局修订，详NEXT_MILESTONE。

## 最新独立审查：51e0410
CONFIRMED_FROM_CODE：remote HEAD核实；14manifest条目匹配；11.13MB SSE重放为kimi-k3 completed，与structured/request/prompt指纹一致。确认保存一份响应，不独立证明不存在其他历史调用。Kimi实际改变block1协同/让路/条件分支，学习进度为计划层进展。

协同算式漏掉caper450攻击但480继续放技能；最小修复保留连续攻击/SP序列，条件性431/600击杀时间不变，伤害trace纠正。定向baseline59、修复62通过。固定动作不落实占格/upkeep/生存分支；添加明确prefix_simulation_ready=false。模拟器未处理active device占格及merchant upkeep，不能以模拟通过消除这些UNKNOWN。原prompt只供应7个干员，“无第三duelist”只对供应集合成立。历史output保持；下一步仅核实A1经济/占格执行前提，无Kimi/新计划/模拟。

## 最新执行前提结论：A1固定候选

CONFIRMED_FROM_CODE/GAMEDATA：`output/r8_1_plan_a1_execution_prerequisites_v1/execution_prerequisites.json` 将固定候选标记为 `INFEASIBLE_UNDER_CONFIRMED_EXECUTION_PREREQUISITES`。strong、talr、nothin 的 merchant trait 确认为每3秒扣3 DP，DP不足按描述自动撤退；首扣帧仍UNKNOWN。活跃 roadblock 占据部署格，`trap_020_roadblock#2` 在 [9,2] 使 caper@390 非法。

修复后的账本在 frame 207 记录 strong 的3 DP upkeep 只剩2.9 DP（缺口0.1）；frame 390 caper 前余额3.0，部署12 DP缺9 DP，同时 roadblock 非法。关卡模拟0次、Kimi调用0次、新计划0次。这是固定候选局部反例，不是 R8-1 战略不可能，也不是 WIN/失败终局。

## 最新独立审查48fa985及用户修正
CONFIRMED_FROM_CODE：实际remote HEAD核实；下载固定character_table，hash/bytes与manifest一致。13个模式预备char均isNotObtainable；原census/context305项无重叠；自动池已有可获得过滤。用户禁止普通模式使用模式专属预备干员，所有后续显式选择亦必须满足。A1的孑/裁度/乌有是普通可获得行商。

维护费3秒3DP/不足自动撤退/不返费有源描述；路障格子重写不可部署得到PRTS支持。首扣仍UNKNOWN，207缺0.1及390缺9仅deploy+90假设的模型数字。COND_UPKEEP FALSE不可解读为费用不存在。pytest初始67PASS1FAIL为列表与元组断言，最小测试修正后68PASS，无公共机制改动。历史output保持。本轮无Kimi/关卡模拟；下一阶段为普通模式候选事实下的一次开局修订，无扩搜。

用户追加调试硬约束：普通模式1～3星。A1的孑/跃跃4星、裁度/乌有5星不再合法调试人选。固定GameData资格集合34名，历史305表仅覆盖17名三星，不能把表缺项视为不能上场。事实清单在review/48fa985/normal_debug_1_to_3_star_roster.json；下一阶段一次低星开局修订，无4星以上自动放宽。
## 2026-10-10：普通模式1～3星事实与一次Kimi修订

CONFIRMED_FROM_CODE：审查补丁已合入为 `8cc612e`。固定GameData `0ef7f952dfd018392200157a5c79a6511ba69122` 下普通模式1～3星为34名（1星12、2星5、3星17），完整目录见 `output/normal_low_star_facts_v1/normal_low_star_facts.json`。3星基准为E1/最高源键、技能7级、潜能1、信赖0；1/2星为phase 0/最高源键。Kimi-K3恰好调用一次并成功返回一个计划 `R8OP-B2-FANG43-FRSTON85-CROSSFIRE-OPEN0941`。

CONFIRMED_FROM_CODE：计划中6个DEPLOY动作在30 FPS映射、真实DP账本和占格检查下均合法：Fang[4,3]@0、Friston-3[8,5]@90、GALLUS²[9,5]@180、Kroos[7,5]@510、Lancet-2[6,5]@570、夜刀[5,1]@630。全部避开活跃roadblock格，无行商/upkeep/退款，账本以0 DP结束。Kimi的“约17 DP banked”叙事与实际0不一致，已单独保留为范围性叙事错误，不修改原计划。

UNKNOWN/UNVERIFIED：route-1/route-3有限窗口击杀、route-4 handoff和漏怪生命账本未模拟；GALLUS²/Friston-3/Kroos的unsupported天赋未计入；AoE splash几何仍缺失。因此没有faithful executable timeline，阶段模拟0次，WIN声明为NOT_RUN。定向直接函数测试47/47通过；pytest不可用。


## 2026-10-10 Work独立审查1e92747（覆盖冲突旧结论）

最新独立审查基线1e92747，详review/1e92747/REVIEW.md。CONFIRMED_FROM_CODE：低星34人事实目录含17三星；公共机制尚未全支持。B2六部署局部候选，faithful=0。旧941余额0结论被更正为条件模型10.3667；仍非17。敌人基础间隔2.0/1.5及MELEE有源。下一项仅同一候选一次固定前缀诊断，不再调用Kimi或新增战术。

## 2026-10-10 固定前缀模型诊断

CONFIRMED_FROM_CODE：审查补丁已合入为 `23482f7`。固定GameData中 `enemy_1107_uoffcr` level0基础攻击间隔2.0秒、`enemy_1108_uterer` level0为1.5秒；attackSpeed均为100、applyWay均为MELEE，`level_main_08-01` 两项 `overwrittenData=null`。已保存B2六动作通过公共adapter/runtime运行到941边界：0漏怪、3击杀、生命5、剩余DP约10.3667、4名活跃敌人、0干员死亡。route-2/route-1/route-3分别于576/691/881模型击杀；route-4于887被接敌；route-6/7/8到941未漏但仍在场。

MODEL_LIMITATION：本次只分类为 `DIAGNOSTIC_MODEL_PREFIX`，不是faithful executable timeline，也不是WIN。Friston-3减伤、GALLUS²减抗/优先目标、Kroos概率暴击均省略；客户端攻击前摇和精确取整UNKNOWN。事件时间取1/30秒公共模拟tick，不是客户端观测帧。定向直接函数测试48/48通过；pytest不可用。

BUDGET_CORRECTION：实际main_08-01执行共4次，超出“最多一次”限制：1次未保存探查、2次脚本在保存前崩溃、1次最终保存运行。仅最终3563事件用于结论；不能宣称整体预算合规。


## 2026-10-10 Work审查bc14455（覆盖冲突旧结论）

最新独立审查bc14455，详review/bc14455/REVIEW.md。旧保存前缀仅旧程序诊断：坐标翻转、漏WAIT时序、高台地面阻挡、晚1帧污染其战术解释。前三次运行缺证且预算FAIL。已修坐标/阻挡/时钟，55定向PASS，尚未真实关卡重验；历史坐标独立确认结论撤销。唯一下一项先重建七条开局公共源事实，Kimi0/真实关卡模拟0。

## 2026-10-10 七条开局路线静态事实重建

CONFIRMED_FROM_CODE：bc14455审查补丁已合入为 `a207aad`。main_08-1 serialized地图数组row翻转、源路线/预置装置row不再翻转；route-3端点为[1,1]->[9,1]，route-6端点为[0,5]->[8,6]。五个roadblock位于[5,3]、[9,4]、[7,2]、[1,2]、[3,5]。`Route.distances_at`保留重复经过格，WAIT-before-target计入、target处WAIT不计入到达时刻。真实场地bottom-left朝向与synthetic y-down约定分离。

静态同源时刻（条件：公共折线路径、最慢敌人、无部署阻挡）为route-1最晚合法拦截461帧@[8,1]、route-2为147帧@[3,3]、route-3为431帧@[8,1]、route-4为941帧@[8,1]；route-6/7/8在公共路线精确tile中心上没有可部署地面拦截格。无阻挡到终点模型值为488/856/458/968/1068/1351/1643帧。这些不是客户端寻路或真实执行证明；route-6的WALK直连段穿过[1,4]、[4,4]、[6,5]三处FLY_ONLY候选，客户端寻路保持UNKNOWN。

B2旧输入失效范围：route-1 191@[8,5]与route-4 941@[8,5]空间不成立；route-2 27逮捕期限无源；route-6约768、route-8约803是旧模型值；route-7不在[5,1]路径上。原六动作保持未改动，也未因此重跑模拟。预算：Kimi0、真实关卡模拟0、新计划0、新动作0、扩搜0。
