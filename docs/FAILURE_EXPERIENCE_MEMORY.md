# Failure Experience Memory

## 既有五份条件经济冲突与一次战斗失败

REPORTED_BY_PREVIOUS_WORKER：保留 `output/r8_1_constraint_informed_revision_v3/feasibility_experience_memory.json` 的 EXP-001…006 和 PROJECT_CHARTER 历史记录；确认保存文件确实存在，但引用的旧 ledgers、unsat certificates、历史 trace 未交付。不得把来源恢复前的内容标为 independently proven，不得扩大到整个战略不可行。

每条仍保持 stage/main_08-01、mechanics/m18.9-stage-device-runtime-v1、source plan、deadline、mandatory distinct capability/responsibility、最低成本与可用收入、证据路径、适用条件、失败原因和局限。旧冲突集不保证 minimal UNSAT core；历史早期死亡不要求所有新结构采用同一 pocket fire。

## REVIEW-295-001：简化前缀诊断不可升级为战术失败

- 状态：CONFIRMED_FROM_CODE（分析程序与保存内容）；真实关卡 deadline 和成本来源 UNKNOWN。
- 条件：现有 V3 A/B/C 的 fire 槽均选择 route-3:FIRE；分析器仅用 route/kind deadline、不同干员指派和 10+frame/30。
- 证据：review/FRAME295_REVIEW.md；review/evidence_index.json 的三条 JSON pointers、SHA-256；V3 feasibility_analysis、plan_capability_pool。
- 诊断：保存值 22/21/22 DP 在 295 与自然 DP 19.8333 冲突。
- 约束来源：295 的 repair 函数/context 缺失；不是已确认的不可放宽游戏规则。A/C 的队列要求和 B 的上游分流可能改变 fire deadline，仍待验证。
- 失败原因：确定性系统尚未证明 deadline、共享/条件/阶段与完整经济保持战术语义，却标 proven 并计为已替换旧冲突。
- 可复用经验：先恢复、验证 contract；只把真实且具适用范围的反例交给 Kimi，由 Kimi 决定改战术。
- 局限：不证明三份计划可行、不证明 295 错误、不证明退款能救前缀，不指定新打法。禁止把 synthetic regression 当作真实游戏复验。

## REVIEW-RETREAT-002：待验证条件漏报

- 状态 CONFIRMED_FROM_CODE；适用于非空小写 retreat_basis / must_vacate_slot。
- 证据：原 V3 L982–988 的 uppercase RETREAT 判断与真实三个计划；原 certificates 的 unverified list 全空；新增回归。
- 原因：大小写字面匹配漏掉真实小写文本。
- 修复：依据字段存在性列待验证退款/安全交接条件；不授权任何 refund 数额、时机或机制。

## REVIEW-CONTACT-295-003：接敌事件不是开火 establishment deadline

- 状态：CONFIRMED_FROM_CODE；适用于 main_08-01 route-3、`enemy_1107_uoffcr`、mechanics `m18.9-stage-device-runtime-v1`。
- 事实：spawn frame 240，speed 1.1，earliest operator contact distance 2，formula `ceil(240 + 2 / 1.1 * 30) = 295`；route-3 BLOCK 事实是 431。
- 修正：295 是最早可能接敌事件，不是 FIRE establishment deadline。V3 A/B/C 的 plan-specific FIRE deadline 保持 UNKNOWN；400–600 叙述是战术目标，不自动升格为游戏事实。
- 保留限制：22/21/22 DP vs 19.8333 的前缀算术只是自然-only、distinct-unit、无退款/技能收入假设下的诊断冲突集。它不证明计划不可行，也不证明退款能解决冲突。
- 可复用经验：区分 CONTACT、BLOCK、FIRE establishment 和 KILL-by target；只有计划/机制显式要求时才把事件转为 deadline。

## REVIEW-PLAN-A-OPENING-004：合并 anchor 与 trait/退款语义不可暂视为已建立

- 状态：CONFIRMED_FROM_CODE（当前候选/几何/DP 计算）；战斗结果 UNKNOWN。
- 条件：仅限 `R8OP-A-MERGED-ANCHOR-REFUND-LATTICE` frame 0–941、当前 fidelity 表、当前 [3,3]/[8,5]/[9,2]/[5,1]/[6,1] 结构与最多 3 候选/槽、16 组合预算。
- 事实：A03 三个候选 effective DPS 均低于 450 vs 150 DEF；`char_4211_snhunt` 的 skill-only DPS 可达下限，但 ammo/trait `atk_scale` unsupported。A02 trait 说明技能未开时 block 0；A04/A05 的 merchant trait interval/cost decision-critical unsupported。
- 退款：来源与到账时刻 UNKNOWN，当前模拟器为 no refund。无退款时 A05 缺 5.7 DP；假设 full-cost refund 仍缺 0.7 DP。
- 结论：没有 faithful opening witness，因此 0–941 模拟 0 次。这是 scoped conflict；不能推为全战略不可行，也不能用假设退款或放行 trait 制造 witness。

## REVIEW-FIDELITY-003：缺表静默扩大候选池

CONFIRMED_FROM_CODE；适用于load_fidelity_tables缺任一表的fresh checkout。证据review/f1a1c7d/：无fidelity/census时已保存21候选变22，新增char_4211_snhunt；原测试仅非空断言仍通过。原因是缺表静默跳过trait/talent检查，不能把其pool当忠实候选。修复本轮reverification缺表BLOCKED并保持候选UNKNOWN。局限：不证明新增干员不合法，也不证明计划不可行；必须恢复原表并逐职责核对selected usage。

## EXP-23A-REVIEW: 限定前轮反例
CONFIRMED_FROM_CODE: DPS原始平均公式非逐击有限窗口伤害界；账本15为A03成本上限而候选11/12；COND_ROUTE6有让路分支。旧低于450与0.7/5.7缺口仅诊断，不能作为计划不可行。适用范围为该公式与示例成本/退款分支；不证明任何候选可行。wscoot未开技能阻挡0与无技能dam职责冲突仅适用于该实例；merchant运行时未支持是验证缺口，不等于真实战术不可行。

## PLAN-A-FIXED-CONTRACT-001: 有限窗口与固定候选经济

- 状态：CONFIRMED_FROM_CODE for simulator/base-cost model；真实游戏结果 UNKNOWN。
- 条件：仅限 Plan A 固定候选、[9,2] origin、[8,5] 目标、route-1/route-3 当前确定性上下文、1 秒攻击、attack-SP cycle、模拟器 target ordering 和 A02 持续阻挡假设。若目标不停留在 [8,5]，caper 也不能同时完成两个 3300 HP 契约。
- 事实：caper 在 450 帧部署时 route-1 780 帧击杀，但 route-3 810–1140 帧击杀，超过 941。双期限模型要求 A03 最晚 250 帧开火；该前缀可用 DP 5.333，aprl 缺 5.667，caper/angel 缺 6.667。angel/aprl 缺少 [8,5] 覆盖。
- 限制：[9,2] roadblock 部署、退款、merchant 成本/upkeep、真实 target ordering、技能调度和 Exact GameData timing 未证实；当前 UNSUPPORTED 是证据缺口，不是游戏不可行证明。该经验只用于条件性反馈，不触发无授权 V4。

## EXP-D930-CAPER（条件性模型经验）
CONFIRMED_FROM_CODE: 344ATK/1s/3normal+1skill(2.3x), two3300HP/150DEF continuously held, no intervening targets/fire, instant hits: first450->kills780/1140; strict805/941 requires first<=250. No-refund/no-upkeep fixed13DPprefix leaves5.333 at250 versuscaper12. Applies only to stated assumptions; not generaldeadline/minimalUNSAT/globalstrategyfailure. Wscootblock0 under inactive skill undermines holding assumption; support/occupancy/targeting/timing unknown. Refund ledger bug corrected: hypothetical5 refund persists,729balance+2.3 for12-costanchor; not game proof. Kimi should revise assumptions, not blindly satisfy250.

## PLAN-A1-REVISION-001: 修订开局的条件共享与让路

- 状态：Kimi 调用与新计划内容 CONFIRMED_FROM_CODE；战斗结果和真实机制 UNKNOWN。
- 可复用经验：若 block-2 依赖未开技能，则不能同时承担“无技能阻挡”和“火力合作”。当同一 live duelist 无法占两个槽时，条件让路必须实际省略部署和成本，而不是只改文字。退款金额未确认时，自然 DP 前缀和假设退款账本必须分开。
- 条件事实：在当前模拟器逐击公式、两目标持续被挡、当前 target ordering 和 talr+caper 同时开火的假设下，route-1 431、route-3 600 完成；这不是通用 FIRE deadline。若 cooperation、roadblock 部署或 merchant upkeep 未证实，计划必须回落到显式 concession。

## EXP-51-A1：条件协同与执行前提
CONFIRMED_FROM_CODE：连续源攻击流纠正450漏击，理想双目标handoff条件下route1=431/route3=600，非实际runtime证书。390零余量经济为无upkeep模型；任何未补偿的正费用会打破固定候选支付条件。设备占格与费用缺失不能通过当前模拟器结果自行排除。适用范围限该主候选和上述条件；no third duelist只针对prompt提供7干员，不是全游戏结论。新知识应反馈Kimi考虑维护费/合法位置/条件职责，Python不指定新打法。

## EXP-A1-EXEC-BLOCK
CONFIRMED_FROM_CODE/GAMEDATA：仅限 R8OP-A1 固定 strong@27、talr@191、caper@390 前缀时，confirmed 3 DP/3秒 merchant upkeep 使 zero-slack caper 前缀失败；[9,2] 的活跃 roadblock 也独立拒绝 caper。不使用退款/upkeep收益/未授权拆路障。不可推广为“merchant 不可用”“[9,2] 永不可部署”或 A1 战略概念全局不可能。首扣帧未知，但任何确认的正周期费用都足以否定该固定前缀。

## EXP-48-A1费用与资格范围
普通模式不可用的模式专属预备干员不是合法战术资源；存在于character_table不代表可选。305原池无13reserve实例，但显式选择仍需资格检查。行商孑/裁度/乌有可用且有3秒3DP维护费、不返费、不足自动撤退描述。207/390失败数字限deploy+90首扣及不足不扣费策略；不能当精确客户端反例。可复用经验是390无余量账本不能承受未补偿的正维护费；活跃路障格不可部署。费用条件为真而支付失败，不把COND_UPKEEP artifact FALSE误解为费用不存在。

当前调试域普通1～3星与历史高星实验隔离：历史A1四名4/5星不是新调试候选，其费用/占格经验可复用。34名资格事实不等于34名已实现runtime；旧表仅覆盖17三星不证明1/2星不可用。
## 2026-10-10 低星修订经验

CONFIRMED_FROM_CODE：旧A1的4/5星干员不进入当前1～3星域。活跃roadblock占格与merchant upkeep仍是确认机制经验；Kimi的新计划通过改用[8,5]地面阻挡和[7,5]/[9,5]远程火力避免[9,2]，并且不使用行商。编译账本确认该结构在固定动作帧下DP和占格合法。

CONDITIONAL/UNKNOWN：Friston-3、GALLUS²、Kroos的unsupported天赋不作为承重；AoE splash、概率、召唤、状态、目标排序和客户端攻击时序仍不可验证。Kimi声称的约17 DP余量与0 DP账本冲突，不能作为经济余量经验。


## 2026-10-10 Work独立审查1e92747（覆盖冲突旧结论）

CONFIRMED_FROM_CODE：B2所谓941余额0反例失效，原0属于630；条件模型941为10.3667，成本37而非计划30。不能向Kimi反馈为无法支付新反例。GALLUS²天赋带目标排序，不具备“删天赋自然保守”的证明；效果依赖UNKNOWN。敌人基础间隔2.0/1.5及MELEE已有固定源，本轮输入遗漏不是游戏机制UNKNOWN。

## 2026-10-10 固定前缀执行经验

CONFIRMED_FROM_CODE：在公共近似模型和显式省略指定unsupported天赋下，B2六动作到941没有造成漏怪；route-1/2/3分别于691/576/881击杀，route-4于887接敌，route-6/7/8仍活跃。事件证实芬于570获得6 DP，941剩余约10.3667。

CONDITIONAL/UNKNOWN：以上时刻依赖模型时序、目标选择、instant projectile、zero windup、量化spawn与省略机制，不能当作真实客户端击杀帧。Friston-3减伤、GALLUS²减抗/优先目标和Kroos概率效果省略；客户端前摇与取整仍UNKNOWN。不能把0漏怪/生命5升格为WIN或真实战术证明。


## 2026-10-10 Work审查bc14455（覆盖冲突旧结论）

CONFIRMED_FROM_CODE：暂停旧翻转坐标及漏WAIT时序衍生的战略/经济截止时间失败经验；适用域仅旧程序条件，不向Kimi反馈为完整GameData约束。正确roadblock位置[5,3],[9,4],[7,2],[1,2],[3,5]；旧[9,2]占路障结论撤销，但活跃装置真实占格规则保留。旧0漏怪不证明route7延迟执行，事件里它没有BLOCK；route4移交主体错误。

## 2026-10-10 B2旧空间输入失效经验

`OLD_INPUT_INVALID`：route-1和route-4不在[8,5]，其可用拦截路径在y=1，且新静态最晚拦截分别是461/941帧@[8,1]。`OLD_DEADLINE_NOT_SOURCE_BACKED`：route-2在frame27逮捕没有源路线时序支持；route-2无阻挡静态拦截为147帧@[3,3]。`OLD_MODEL_VALUE_INVALID`：route-6约768和route-8约803依赖未证的客户端寻路；route-7不在[5,1]上。这些限制只作用于旧B2输入/模型解释，不证明Kimi战略全局不可行，也不替Kimi改动作。


## 2026-10-11 Work审查1223c03（覆盖冲突旧结论）

CONFIRMED_FROM_CODE：route2最晚147失效，修后条件公共格中心最后到达589@[4,3]；589不是客户端硬deadline，等待/阻挡语义仍待证。route6/7/8无中心相交只适用失效直连折线，不能反馈为整个战略不可行或强制让路。route2与route8格中心PASS不能证明连续通行。route1/3/4的461/431/941保留条件模型到达值范围。


## 2026-10-11 导航失效知识更新

CONFIRMED_FROM_CODE：旧 route-2/6/7/8 “直连无中心拦截”的结论失效，不能用于真实不可阻挡或必须让路的判断。地形级 SPFA 路径已恢复且不穿 FLY_ONLY 内部；但活跃 roadblock 影响与阻挡半径仍 UNKNOWN，因此所有时间/机会仍为条件模型，不是硬 deadline。


## Work review 2026-10-11 — 4b1b523

CONFIRMED_FROM_CODE: terrain navigation model exists; manifest 11/11 matches; review pytest 8 PASS / 3 FAIL (contradictory tests). Client algorithm equivalence is UNKNOWN; binary addresses/hash and extraction conclusions remain REPORTED_BY_PREVIOUS_WORKER until reproducible excerpts are supplied. This qualification supersedes earlier wording that independently confirmed client semantics. No new runtime bug or tactical impossibility is established. Next bounded task: reproducible active-roadblock navigation evidence; Kimi and real-stage simulations remain zero. See [review](review/4b1b523/REVIEW.md).

## 2026-10-12 Roadblock inference lesson

LESSON：不能用客户端 `Token`/`Tile` 的 generic rewrite-and-restore 机制推出 `trap_020_roadblock` 必然重写地块；也不能用部署占格推出普通 WALK 不可通行。当前证据仅支持这些机制存在，roadblock prefab payload 和普通敌人分支仍 UNKNOWN。

适用条件：仅限 build 2771 提取的二进制与固定GameData commit；跨版本适用性 UNKNOWN。后续若得到 roadblock prefab 或 skill payload，必须先关联到 `Tile.Options` 或 `Enemy.SpecialBlockCondition`，再分普通 WALK、乌萨斯平民和塔露拉三类结论。

## 2026-10-12 Roadblock parser failure was not a game-fact proof

前一次 V1 的“prefab 不可解码”只说明当时缺少 Arknights 自定义 LZ4AK 支持，不能推出路障没有导航影响。Work 审查已确认 generic chain 有分支；V2 进一步证明该路障启用 rewrite、保留旧 passableMask，并把 `overrideObstacleLikeMoveCost` 置 1。

可复用教训：容器解析失败只能阻断对应证书，不能把 UNKNOWN 硬化为全阻隔或无影响。新边界是：passability mask 不变；`avoidObstacleLike=true` 时该格不可达；默认路径生成的实际调用仍 UNKNOWN。

V3 更正（覆盖上一段两条硬化分类）：

- `NOT_TRIGGERED_FOR_UNCHANGED_WALK_FLY_MASK` 不再作为可复用失败经验。moveCost-only 变化也会产生 dirty bit。
- `FALSE_IF_AVOID_OBSTACLE_LIKE_IS_TRUE` 只能保留为算术条件，不是逐格规则，也不是 R8-1 普通路线证明。
- 不得把这些条件推给 Kimi 作为已证战术失败；仍缺少 `Route.ReconstructNextMap -> SPFA` 的直接客户端证据。

## 2026-10-12 Route decoder failure lesson

LESSON：函数入口解码失败不等于整个字节范围没有有效 A64 指令，也不等于加密。
可复用边界只是 `ENTRY_DECODE_FAILED`：默认 Capstone 在固定静态二进制的
`Route..ctor`、`Route.ReconstructRoute` 和 `Route.ReconstructNextMap` 入口未消费字节。
四字节重同步找到的候选词没有函数边界/控制流证明，不能作为调用边。

适用条件：仅限固定 `libil2cpp.so`
（SHA-256 `3ece1e7b34165233fe8c3c919cf55dfcb4406b6bbc2725def2b1242b4c0a6259`）；
跨版本适用性 UNKNOWN。禁止把 `Route.ReconstructNextMap -> SPFA`、加密、运行时变换
或数据误分类写成结论。V3 的 `NO_VALID_A64_INSTRUCTIONS` 分类失效。证据：
`output/r8_1_route_navigation_decodability_v4/`。

## 2026-10-12 LLM evidence embedding lesson

LESSON：仅把证据保存到 artifact 不等于 Kimi 收到了证据。未来战术调用必须在用户
消息中嵌入完整 evidence context，并在 response forensics 中检查模型是否能引用关键事实。
`response.incomplete` 截断不能被解析成计划，也不能让 Python 补写或恢复战术语义。

本轮的 40,059 字符部分输出只保留为失败证据。它包含大量模型自述假设，不能用于
编译、模拟或反馈为战术事实。一次调用后禁止重试；下一轮由 Work 决定是否允许新调用。

## 2026-10-12 V2失败经验转化

V1的失败不是“需要更多战术候选”，而是请求入口丢失证据上下文且输出预算耗尽。V2规则：只读取
当前`llm_request.json`；POST前必须比较最终serialized body、evidence、schema、模型和固定路障；
历史B2的941零漏只是失效诊断，不允许prompt复述成活跃事实。`response.incomplete`和本地契约失败
只能作取证，不能编译为战术。传输失败在网络开始前记账，失败后不得重试。这些是入口工程规则，
不是游戏机制事实。

## 2026-10-13 工具失败经验

工具结果只回答已声明的只读事实、几何或条件账本；返回UNKNOWN不能被补成事实。错误call_id、
非白名单工具、参数不完整或截断JSON不执行。超预算即使没有HTTP成功也算实际请求/工具调用。
Provider兼容性未实测时，mock成功不能升格为真实协议兼容。工具不允许Python替代Kimi决定战术。

## 2026-10-13 只读工具V2失败经验

只给模型`function_call_output`不足以表达可继续的调用上下文；对应`function_call`及其参数必须
随原user上下文一起保留。参数、预算和call_id必须在执行前预检，否则第一批错误结果会造成不可
恢复的歧义。同帧扣款若没有关联ID或明确顺序，不能从余额反推；此时账本只能是UNKNOWN，不能
同时报告PASS和经济冲突。最终计划回调返回空错误不代表计划合法。

## 2026-10-13 工具完成状态与真实续接经验

`response.completed`不足以证明function_call可执行；还要比对流式与最终调用，并检查response和
每个call的完成状态。同帧扣款如果有关联条目，余额必须按该条目在声明顺序中的实际位置计算；
不足直接CONFLICT，顺序未知保持UNKNOWN。真实endpoint确认了非战术原生工具续接，但这不自动
证明完整战术上下文、长输出或C2会成功。

## 2026-10-13 C2工具失败经验

模型可以用最终文本声称已调用工具；这种声明不是原生`function_call`。必须在会话级要求至少一次
已执行的原生只读工具调用，否则拒绝返回计划。接口`response.completed`、HTTP 200、完整推理和
大量输出token都不是工具执行、计划有效或反例消化的证明。

若最终文本被当成计划，普通JSON对象可以完全不符合根schema并缺少核心战术字段。应保存原始
响应、最终文本、usage、request ID、工具计数和精确schema错误；不要把失败压缩成“调用失败”。
本例中的失败占1次模型请求，0次工具执行，不能重试或让Python补写C2。

## 2026-10-14 C4诊断失败经验

CLI入口成功不能替代战斗结果。C4无干员死亡且静态检查全绿，但仍漏7个：route-10帧2179、
route-12帧2184、route-11帧2629、route-13帧2634、route-23帧4555、route-33帧4879/4903。首漏是
route-10第15个敌人，1950帧出生后229帧内无受伤或阻挡事件；route-12只晚5帧。因此“个人静态合法性+
无干员死亡”不等于阻挡容量或击杀吞吐满足波次压力。

下一次战术反馈应保留完整路线漏怪清单，避免只修最早一条路线。不得把该条件模型LOSS外推为实机
机制或整个低星战略不可行；也不能因未做两种路障targeting重验而称robust WIN。

## 2026-10-14 C5-C7批次经验

C5输出战术内容完整但漏provenance，被本地contract正确拒绝；不要把这个当作战术失败，也不要跳过
contract。离线只补一个metadata对象后获得51/5。C6把C5的末段5漏收敛到route-8单漏；C7再针对
route-8 frame-1730决定性缺口得到0漏。失败反馈的价值不是“继续重试”，而是把完整路线漏怪状态和
唯一新瓶颈逐轮压缩成GPT可直接修订的因果输入。

WIN不自动等于robust：R8-1 C7仍需同时间线在两种roadblock targeting解释下复验。通用runner后续必须
把provenance要求写入prompt，避免同类可预防格式消耗。

复验必须保持C7的policy、dt、max_time、动作契约与快照哈希。旧robust脚本中的m11 policy没有问题，但
不能混用0.1秒/240秒配置；R8-1 C7 replay明确复用30FPS/600秒。只有双变体都WIN时才允许roadblock
targeting robust声明，不能外推到客户端导航或实机。

## 2026-10-14 Codex CLI输出schema经验

Codex `--output-schema`使用OpenAI strict response format，不只是本地JSON Schema。根对象必须显式
`additionalProperties=false`。OpenAI的400 schema错误已经是网络越过路由的强信号，但不等于模型turn完成
或战术计划有效。此时不得重跑，也不能把本地Draft 7通过当作response_format通过。

## 2026-10-14 Codex CLI环境继承经验

交互shell的`~/.bashrc`代理导出不会自动进入Python subprocess。CLI进程必须在启动前显式记录并提供
`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`和`NO_PROXY`；否则即使mihomo节点是新加坡，Codex仍可能直连并
在网络路由阶段失败。失败一次就停止；不能把环境修复后的新启动伪装成同一进程的续接。

## 2026-10-13 C4服务失败经验

HTTP 503是provider可用性失败，不是计划失败、工具失败或战术不可行证明；但它确实消耗请求预算。
必须在网络前持久记录STARTED，失败后保留request ID和原始错误，不重置预算。剩余请求是否手动
使用应由Work决定，不能自动重试或重开目录变相重置。

恢复入口必须在HTTP前证明：同一实验、同一序列化body、attempt1确实是已计数空503、预算为1且工具
为0。第二次相同503不能变成第三次自动机会；也不能把重复503推断为请求体或协议缺陷。

## 2026-10-13 保存C2执行阻断经验

不要把schema可修复的包装问题误认为整份C2无效，也不要因包装问题消失就宣称战术成功。必须保存
无损转换位置和深度差异。编译器字段名或目标对象形态错误会产生假UNKNOWN；修复后要重放静态检查，
不能把“没有编译错误”当作战斗可行。

frame600 Noirc需要14 DP而余额9，是原样C2的真实执行反例。此时不得移动部署、改帧、删干员或用
退款/收入假设补足；正确输出是具体冲突并将0/1次模拟保持未启动。

## 2026-10-13 自动收入与战斗生存经验

静态经济账本即使正确建模自动技能，也只能在“存活、保持部署、正常回SP”条件下成立。芬在
frame570确实给了6 DP，但frame890死亡；后续周期和frame1680芙蓉部署都因此失效。不要把
修复后的静态账本当作执行证明。

一次完整模拟的第一失败要关联阻挡、解除阻挡、死亡与漏怪。C2的route-6敌人在frame1076被
Vanilla阻挡，frame1243因Vanilla死亡解除，frame1295漏怪；比frame1680部署失败更早。报告
LOSS时必须保留这个先后关系，不能只说后期人手不足。

## 2026-10-13 C3 reasoning-only截断经验

HTTP 200和`tool_choice`字段被接受不等于强制工具调用被执行。C3两次请求都耗尽32,768输出预算于
hidden reasoning，没有assistant消息或原生function_call。不要把推理摘要中的战术设想当作Kimi
计划，也不要用它继续编译或模拟。

紧凑证据本身不能解决“模型把全部输出预算用于推理”的协议问题。第二次显式`tool_choice=required`
没有观察到预期语义时，应停止并保留原始响应；不要把第三次请求当成必然成功的机会。

## 2026-10-13 C2紧凑查询失败经验

查询阶段的4096上限不是“使用量”; 它是显式配置上限。本例4096实际输出中4093是reasoning，没有
assistant文本或原生function_call。上限不足导致的`response.incomplete`会消耗一次真实请求，但不
能视为协议成功，也不能人为补造工具调用。

`response.incomplete`必须保留精确语义；把它误标为`NO_TERMINAL_EVENT`会掩盖服务器截断原因。
压缩证据本身没有恢复本轮战术进展：模型在推理中手工推演范围，而不是先生成原生工具调用。下一步
审查应区分“上下文太长/推理太多/指令不够强”等假设，不得把假设写成已确认原因。

## 2026-10-13 C2 V2续接体超限经验

提高输出预算解决了第一阶段长度截断，但不自动解决续接体长度。6个工具输出、6个function_call、
原user上下文、最终schema和新用户指令叠加后，请求体可从127KB升至149KB。必须在每次HTTP前统一
执行140KB预检，超限时停止，不截断工具结果或schema。

模型给出的configuration若缺少固定配置字段，只读工具必须拒绝；这不是工具执行失败，也不是
游戏不可行。成功执行的时序结果只是条件模型计算，不能替代C2、战斗模拟或反例吸收证明。

## 2026-10-13 C2 V2恢复失败经验

严格配置校验修复后，五条已保存范围查询能原样重验；这恢复了几何事实，但不自动修复最终计划契约。
`response.completed`、assistant文本、大量推理和15,862实际输出token都不等于有效C2。最终JSON的
`verification_questions`类型错误足以阻断静态编译和模拟。

恢复路径应在HTTP前把代码错误、请求体阻断和实际模型失败分开记录。本次NameError未发送HTTP、未计入
模型请求，但五个工具已成功重验；修正后必须复用保存结果，不能重复执行或伪造“一次恢复”。

## 2026-10-13 C2工具失败经验

模型可以用最终文本声称已调用工具；这种声明不是原生`function_call`。必须在会话级要求至少一次
已执行的原生只读工具调用，否则拒绝返回计划。接口`response.completed`、HTTP 200、完整推理和
大量输出token都不是工具执行、计划有效或反例消化的证明。

若最终文本被当成计划，普通JSON对象可以完全不符合根schema并缺少核心战术字段。应保存原始
响应、最终文本、usage、request ID、工具计数和精确schema错误；不要把失败压缩成“调用失败”。
本例中的失败占1次模型请求，0次工具执行，不能重试或让Python补写C2。

## 2026-10-14 七关GPT计划失败经验

GPT能读取事实，但三次R8-2计划在显式路障数组后仍选择`[row,col]=[5,3]`或`[2,1]`；第三次已明确
解释`[col,row]`到`[row,col]`的反转，仍不改。R8-4 V2同样选择路障。这不是坐标格式解析缺陷的唯一
假设；更像模型把roadblock tile当作可部署/支援位。Python不得替它挪格或删干员。必须把这类计划拒在
静态前，并保留invalid plan、prompt版本与usage。
## 2026-10-14 Cross-stage rejection correction

The previous memory claiming six saved plans failed because GPT ignored
roadblock discipline was contradicted by the stage-local recovery run. All six
plans passed schema/contract and parent-hypothesis checks, and five passed
static checks. Do not feed that invalid lesson into future tactical prompts.
The remaining deterministic static failure is R8-2 V2 Beagle SP 39.9667/40 at
frame 4440.

## 2026-10-14 Repeated loss revisions can degrade

Failure summaries alone did not lead to stable structural improvement. R8-4
degraded from 44 kills/10 leaks/2 deaths in the recovered V2 to 43/11/1 in R1
and 36/18/5 in R2. R8-7 degraded from 6 kills/27 leaks/5 deaths in the recovered
V1 to 17/16/7 in R1 and 1/32/6 in R2. Stop the loop and reanalyze the tactical
bottleneck instead of issuing another same-shape revision request.

## 2026-10-14 Civilian behavior changed the R8-2 baseline

Treating enemy-stored Ursus Civilians as ordinary targets made the old R8-2 V1
false-positive WIN. The corrected model removes those operator attacks and
consequently exposes 28 leaks, though civilian scoring and roadblock handling are
now source-backed. Do not reintroduce civilian kills, ordinary blocking, or a
life-zero WIN to recover that old result.

## 2026-10-14 Ghost block invalidated the six prior loss windows

The unified death path omitted `_unblock`, so dead enemies remained in
`blocked_enemy_ids` and could consume block capacity. The six simulations in
`civilian_mechanics_corrected_v1/` are therefore potentially ghost-polluted
historical observations; do not use their loss windows as reliable tactical
feedback. Use the death-unblock-fixed revalidation instead: R8-2 V1/V3 leave an
active civilian at roadblock #2 despite zero leaks, R8-4 V2 first leaks at frame
3269, and R8-7 V2 loses two guards and first fails at frame 1532.

## 2026-10-14 Infrastructure failure is not tactical feedback

The first two R8-2 clearance CLI attempts both failed at
`workspace routing discovery failed`. Save the thread/error logs and stop; do
not turn this into evidence that the model misunderstood the stage. The frozen
R8-2-V5 prompt includes the user-confirmed permanent roadblock stop, roadblock
#2 attributes, zero prior attack events, civilian #11, and civilian #6 death.

## 2026-10-14 R8-2 V5 clears the final roadblock but loses civilian #6

V5's clearance handoff successfully destroyed roadblock #2 and delivered #11.
The remaining perfect-completion defect is earlier: #6 remained blocked from
frame 1730 while Infected Patrol Officers attacked it 13 times, with the 13th
attack killing it at frame 4604. This is not license to ignore the civilian;
the next tactical version must remove the officer pressure while preserving
V5's zero-leak outcome. A V6 transport failure is infrastructure and must not be
recorded as model tactical disagreement.

## 2026-10-14 V6/V8 show the protection-clearance coupling

V6 proved that Apps connector isolation restored transport, but its upstream
interception/officer-throughput balance leaked `enemy_1107_uoffcr#23` and
`#30` at frame 5033; these were exactly part of the pressure pool that had killed
#6 in V5. V8 overcorrected by weakening the opening line, producing 12 leaks by
frame 5228 and life -10 before the late roadblock destruction. Thus preserving
#6 cannot be solved by merely delaying clearance or removing early line pressure.
The next revision must treat officer throughput, protected-target exposure, road
hold time, and clearance handoff as one coupled structure. Do not reuse V6/V8 as
successful knowledge; use them as evidence that one-variable timing changes are
insufficient.

## 2026-10-14 V9 improved survival but exposed clearance timing

V9 disproves the V8 conclusion that the tactical family could not recover from
the opening: Popukar actually deployed and blocked, no operator died, leaks fell
to one, and roadblock #2 was destroyed. Its real failure was that #6 stayed held
by roadblock #2 until frame 5293 while the destruction happened at frame 8943,
so 13 officer attacks killed #6 at frame 5294. V10 shifted the late leak but did
not change this exposure and lost Popukar. Static DP revisions V11–V13 also show
that repairing one conditional deployment can move the deficit to the next
deploy. Treat protection, clearance, route throughput, and conditional economy as
one plan; do not call any unresolved dependency a DP formula bug.

## 2026-10-14 V14/V15 bracket the protection-clearance coupling

V14 reached zero leaks, zero operator deaths, and roadblock clearing, but #6
still died at frame 5294. V15 cleared the roadblock earlier and retained a
zero-leak WIN, yet #6 died earlier at frame 4994 and #11 took two attacks. These
bracketing results prove that moving destruction earlier is insufficient; the
release path and officer pressure must be protected together. V9/V10 and
V14/V15 are plan-specific current-model observations, not general disproof of
interception. V11–V13 have no battle result.

## 2026-10-14 Global device gate invalidated earlier clearance interpretation

CONFIRMED_FROM_CODE_AND_SOURCE: `_target_device_for` treated any active
non-neutral enemy anywhere as a global reason not to select a device. The PRTS
roadblock/selector pages and fixed GameData support a low-taunt filtered
candidate, not a map-wide prohibition. The correction in
`m19.1-local-device-target-v1` uses local operator candidates only.

LESSON: do not infer “must wait for every map enemy to disappear” from the old
global runtime gate. This invalidates the strong claim that V14/V15 excluded
clearance timing; it also changes their conditional results. The unchanged V15
timeline now clears #2 at frame 2715, saves #6, keeps life 3, and safely
delivers all protected targets. V14 still loses #6 at 5294, so the comparison
is plan-specific and remains non-robust. Historical global-gate events are
historical-only, not client evidence.
## 2026-10-15 R8-4 stale failure and civilian-clearance coupling

R8-4 V2's old 50/4/1 result was m19.0 and dropped to 48/6/1/life -3 after
original replay under m19.1; V2's six leaks therefore cannot be reused as the
current tactical failure. V3 regressed to 47/7/3/life -4 and exposed that three
civilians remained blocked behind roadblock #1 until the cap, so a zero-leak
enemy plan still cannot be a WIN. V4 resolved both route throughput and civilian
clearance: WIN, 54/0/0/life 3, all three civilians arrived at 5336, no
protected-target damage, and both roadblocks destroyed.
## 2026-10-15 R8-7 separates survival from civilian clearing

V5 and V9 prove that complete roadblock clearing and protected-target arrival are
achievable, but the opening survival and route-throughput cost was too high. V10
recovered most throughput yet left #14 behind roadblock #4, so civilian clearing
cannot be implicit. Opening deaths remain coupled to later deployment errors; a
missing interceptor invalidates downstream conditional retreats and skills.
Contract-only V7/V11 and static-only V12 have no tactical result. V13 shows that
solving both protected arrivals by broadening clearance/redeployment can collapse
route defense; the next structure must preserve V10's line and selectively clear
#4.

## 2026-10-15 m21 invalidates R8-1 C7 as a robust current result

The center-line roadblock approximation was too weak. Under m21's radius model,
the unchanged C7 timeline leaks `enemy_1108_uterer#54` at frame 5282 in both
targeting variants. Historical WIN artifacts remain valid only for their recorded
mechanics versions. The next R8-1 feedback must preserve prior successful roles
but account for the new continuous clearance geometry and late route leak.

## 2026-10-15 nested CLI infrastructure boundary

The earlier V14 failure was a read-only host `CODEX_HOME` initialization issue,
not a tactical rejection. A writable gitignored runtime home recovered CLI
startup, but the next attempt failed at service-side workspace routing. Stop the
entry after the recorded failure; do not retry the same request or infer a model
tactical conclusion from it.
