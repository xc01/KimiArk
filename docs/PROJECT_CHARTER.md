# KimiArk / Arknights Auto Planner 完整研发交接

记录时间：2026-10-09（Asia/Shanghai）。来源：本轮用户完整交接。此记录在获取源码前建立。
证据状态：目标与授权为用户明确要求；所有历史代码、实验与提交报告均为 REPORTED_BY_PREVIOUS_WORKER，尚未独立核实。CONFIRMED_FROM_CODE 只能在获取真实源码并检查相应证据后使用；推测标为 HYPOTHESIS。

## 一、项目目标
GitHub：https://github.com/xc01/KimiArk
先前报告的最新提交：5d31ce04693837b5909537a4fcb7c68ea4a2fbd8。必须实际获取仓库并核实最新 commit，不能将此报告视为已核实。
最终目标：让大语言模型真正理解《明日方舟》的关卡，利用游戏事实和模拟器不断修正战术，最终自动生成能够通关的操作方案：
DEPLOY(operator, tile, direction, frame)
ACTIVATE_SKILL(operator, frame)
RETREAT(operator, frame)
部署必须包含方向。WIN 是硬性目标。仅在获得 WIN 后依次优化：干员数量、干员星级总和、时间安排的脆弱性、外部操作数量、可选通关时间。模拟器 WIN 不等于真实游戏通关。

## 二、最重要的设计理念与角色
我们要培养能够从失败中修正战术的自动规划系统，不是不断增加硬编码、只会证明方案不可行的程序，也不是内置大量固定打法的脚本。
Kimi-K3 是战术大脑：理解关卡、提出战术假设、选择战略结构、安排阶段职责，根据失败证据主动改变打法。
Deterministic System 负责事实、计算与执行验证：GameData、精确数值、部署经济、路线、攻击范围、阻挡、时间、几何、合法性、候选生成和模拟器。不能代替 Kimi 决定战术。
GPT / Work 负责研发管理与技术审查：读代码、识别架构问题、审查实验、修复确认的程序缺陷、决定下一研发阶段。
原开发 GLM-5.3 主要负责代码实现，不能擅自替代 Kimi-K3 的战术决策角色。

## 三、确定的架构
Arknights GameData → Mechanics / Stage Facts → Deterministic Battlefield Analysis → Affordance Catalog → Kimi-K3 StageUnderstanding → Kimi-K3 TacticalRequirements → Kimi-K3 StrategicHypotheses → Kimi-K3 OperationalPlans → OperationalPlanCompilerContract → Deterministic Feasibility Verification → Roster / Assignment / Geometry / Timing → Operational Fidelity Certificates → Simulator → Failure Evidence / Counterexamples → Kimi-K3 Tactical Revision。
OperationalPlan 中间层必须保留开局结构、路线职责、压力窗口、阵型演化、技能意图、临时阻挡、火力共享、治疗、撤退和移交的具体战术决策。
不同 OperationalPlans 若被编译成相同通用部署策略而丢失原战术含义，属于错误。动作合法不代表完整执行了战术。

## 四、不可行也是资产
允许 Kimi 起初不理解游戏，希望它通过失败反例持续修正理解。例如计划要求 frame 729 前建立指定防线，但 Required minimum DP 45、Available DP upper bound 40.3，结果 INFEASIBLE。
此结果不能仅用于拒绝方案，应保存为条件性的失败经验反馈 Kimi：哪些职责必须同时成立？哪个截止时间引起冲突？是否错误假设独立部署？能否通过阶段变化重排职责？是否需改变开局经济结构？哪些战术思想仍值得保留？
Python 提供可验证约束与反例，不指定新战术；Kimi 自己理解原因并决定如何调整。
维护可复用 FeasibilityExperienceMemory，每条包括适用条件、证据、约束来源、失败原因及局限性。不能把某份方案的不可行推广成整个战略不可行。

## 五、历史报告（均待实际代码及 artifacts 核实）
1. 静态战术与搜索阶段产生数百条方案，未获 R8-1 WIN；增加搜索数量不能解决战术结构问题。
2. 引入 Kimi TacticalRequirements 与 StrategicHypotheses；高层假说直接到动作会丢失语义，因此引入 OperationalPlans。
3. 曾有 667 条被当时验证器认为 faithful 的方案、无 WIN；后发现 fidelity 不完整，旧结果不能当作严格验证过的战术失败。
4. Kimi-K3 调用已证实可行；Codex 自动续接可能使用不兼容 assistant-message prefill，改为 direct streaming Responses 后完成大规模结构化战术输出。
5. 曾报告 111 个 numeric hallucinations，逐项审计全部是旧校验器错误分类。必须区分游戏数值事实、确定性推导值、合法战术设计数量、标识符、非关键描述。
6. 保真度曾发现并修复 OP-05 route-specific triage/concession 语义丢失、OP-04 干员技能检查过严、EARLIEST_PHASE 未影响部署时间、关键职责 deadline 未正确检查。重验原 170 条 faithful 执行记录均存在 deadline 问题。
7. 五份修订计划在各自硬约束下发生经济冲突：
OP-01 deadline 941，Minimum DP 49，Available DP 47.367；
OP-02 deadline 805，Minimum DP 47，Available DP 42.833；
OP-03 deadline 941，Minimum DP 49，Available DP 47.367；
OP-04 deadline 729，Minimum DP 45，Available DP 40.300；
OP-05 deadline 941，Minimum DP 49，Available DP 47.367。
这是有证据支持的冲突约束集合，未证明是最小 UNSAT Core。
8. Constraint-Informed Tactical Revision V3：Kimi 收到上述证据，恰好一次 Kimi-K3 调用产生三个新 OperationalPlans。旧职责组合改变，但三个计划均在 frame 295 产生新 DP 冲突，未进入战术模拟，学习进度报告 PARTIAL。

## 六、当前必须审查的核心
不是直接让 Kimi 再想三个方案，而是查明为什么三个不同的新计划均在 frame 295 冲突：
- frame 295 是否来自真实关卡压力 deadline？
- 是否共享一条被错误硬化的编译约束？
- 是否要求开局职责过早同时建立？
- 经济下界是否考虑真实干员选择、职责共享及合法技能？
- Kimi 是否真正理解并改变旧不可行假设？
- 新 OperationalPlans 是否被忠实编译？
不能预设是 Kimi 或编译器问题；读实际代码、测试、实验 artifacts 后判断。

## 七、机制与证据纪律
主要关卡 main_08-01 / R8-1、main_08-04 / R8-4；机制版本 m19.1-local-device-target-v1。
GameData 是主要事实源，PRTS、客户端及其他可核实机制证据作补充。禁止猜测修改机制以使战术通过。
R8-1 曾有两种具证据支持的 roadblock targeting 解释。若获得模拟器 WIN，必须用完全相同动作时间线在两种解释下重验，才能声称 robust WIN。真实游戏验证独立处理。

## 八、长期工作方式
每完成重大里程碑，GPT / Work 必须审查真实代码后再决定下一轮：
Worker 完成 → 检查 GitHub 最新 commit → 读实际代码和 diff → 读测试及 artifacts → 核实报告 → 有 bug 则最小修复加回归测试 → 重评瓶颈 → 决定下一个有界里程碑。
不要仅凭 worker 总结生成下一份大型指令，避免无限增设审计层、验证器、工程指标而没有可执行战术。
真正进展包括：消化旧反例、消除旧经济冲突、生成新合法战术结构、忠实编译后进入模拟、战斗失败原因有意义地改变、最终 WIN。
失败需说明新增知识以及它如何改变下一次战术决策。

## 九、长期项目资料
先建立本交接的上下文记录，再获取 GitHub；接管仓库后优先检查已有文档并合并维护，避免重复创建：
PROJECT_CHARTER：目标、用户理念及不可变约束。
ARCHITECTURE_DECISIONS：Kimi、编译器、模拟器职责边界与重大决策。
EXPERIMENT_LEDGER：里程碑输入、代码版本、结果和失效结论。
FAILURE_EXPERIENCE_MEMORY：具有证据和适用范围的可复用失败经验。
CURRENT_PROJECT_STATE：最新已验证进展、未证实假设和当前阻塞。
NEXT_MILESTONE：审查后确定的唯一下一项有界工作及验收条件。
全部记录区分 CONFIRMED_FROM_CODE、REPORTED_BY_PREVIOUS_WORKER、HYPOTHESIS。未核实历史报告不能标为独立确认事实。

## 十、现在执行的第一项任务
1. 实际获取 GitHub 仓库并核对最新提交。
2. 阅读已有项目文档、V3 实现及关键依赖。
3. 建立并维护上述长期上下文，保留全部关键理念和证据状态。
4. 审查三个计划共享的 frame 295 冲突，给出可定位的代码和 artifacts 证据。
5. 若确认通用编译器 bug，做最小修复与回归测试。
6. 判断现有反例能否直接反馈 Kimi，还是应先修复确定性系统。
7. 给出唯一一个有界下一阶段研发计划及验收条件。
完成审查前不得启动 V4 战术推理或扩大模拟搜索。

迁移前状态：项目目标、理念、架构与历史经验已整理；Work 交接曾尝试但尚未成功，GitHub 获取与审查尚未执行。请实际开展上述接管与首轮审查，不只回复确认收到。

## 十一、当前边界（2026-10-09）

`R8_1_PLAN_A_OPENING_WITNESS_V1` 是有界复验：Plan A qualified opening 组合为 0，stage-prefix 模拟为 0。295 仍是 route-3 最早接敌事实，不是 FIRE establishment deadline。退款与关键 trait 语义保持 UNKNOWN/UNSUPPORTED；结论只约束当前 Plan A 开局 witness，不升格为全战略不可行。

## 十二、当前边界（2026-10-10）

`R8OP-A1-BLOCK1-COOP-ANCHOR390` 是唯一一次授权 Kimi-K3 修订的产物。有界校验只产生条件性动作候选，不产生 faithful witness，不运行阶段模拟。WIN 仍为硬目标；任何局部通过都不等于 WIN。

## 十三、当前边界（2026-10-10 执行前提）

公共 merchant upkeep 与 active stage-device occupancy 已最小实现。原5动作固定候选在 frame 207 出现0.1 DP upkeep 缺口，frame 390 caper 缺9 DP且被 roadblock 占格拒绝。这是局部战术反例；是否修订战术由后续 Kimi 决定，当前不执行前缀模拟、不新增候选、不宣称 WIN。

## 用户新增不可变约束（2026-10-10）

普通模式R8-1不得考虑或使用模式专属预备干员，包括“预备干员-特种”“预备干员-特种（卫戍协议）”及同类临时单位。该限制覆盖Kimi输入、候选生成、显式干员指派、动作及证书。保留这些GameData记录用于事实查询，不将其存在当作普通模式可用性。普通可获得低星干员不因属于预备行动组而排除。来源：用户明确修正；实现核实见review/48fa985/。

## 用户新增调试范围（2026-10-10）

当前调试只使用普通模式可用的1～3星干员；用户希望检验模型战术思考，不能用高星强度代替。4星及以上不得进入调试候选、Kimi显式选择或动作，不自动放宽。该约束限定当前调试域；未证明低星方案可行时报告限定范围结果，不宣称全战略不可行。WIN仍先于优化；不得为求WIN自行解除调试约束。
## 当前边界（2026-10-10 低星修订）

普通模式1～3星候选域已完整建立为34名；4星及以上和模式专属预备干员被资格入口拒绝。Kimi产生了一个低星计划，但当前只有结构编译候选，不是faithful executable timeline。0–941阶段模拟未运行，WIN为NOT_RUN；任何局部DP/占格通过不等于战术成功。


## 2026-10-10 Work独立审查1e92747（覆盖冲突旧结论）

用户新增不编造要求持续有效。CONFIRMED_FROM_CODE：本轮完成34人事实覆盖及17名三星枚举；未完成所有三星运行时机制。未知必须分开标注，不能由计划自述认证。

## 当前边界（2026-10-10固定前缀诊断）

B2六动作已经完成一次公共模型诊断，但结果只属于 `DIAGNOSTIC_MODEL_PREFIX`。客户端前摇、取整、若干unsupported天赋和AoE几何仍未支持，不得把模型击杀帧、0漏怪或生命5当作真实游戏结果或WIN。下一决策属于Work；未获批准不得调用Kimi、改变战术或扩大搜索。


## 2026-10-10 Work审查bc14455（覆盖冲突旧结论）

既定目标、普通1～3星约束与不编造纪律不变。CONFIRMED_FROM_CODE：bc14455发现源路线/装置row误翻转。旧模型结果不能当作真实战术失败；先纠正事实再让Kimi思考。

## 当前边界（2026-10-10 开局路线事实）

七条开局路线静态事实已重建并推送审查。静态无阻挡/拦截时刻只在公共折线路径、固定GameData速度和WAIT模型内成立；客户端寻路、精确几何与部署后条件时序保持UNKNOWN。route-6直连段与FLY_ONLY格不一致，不升格为真实路线。旧B2六动作不改，不据此宣布战术失败。普通1～3星约束、Kimi0、真实关卡模拟0、WIN NOT_RUN继续有效。


## 2026-10-11 Work审查1223c03（覆盖冲突旧结论）

当前仍普通模式1～3星、排除模式预备干员。CONFIRMED_FROM_CODE：重复经过已接入公共威胁与阻挡消费者；直连路径无中心拦截不是真实不可阻挡知识。未知导航不由模型自述或断言替代。


## 当前边界（2026-10-11 WALK导航）

地形级公共 WALK 导航已按源恢复；客户端精确路径与活跃 roadblock 导航语义保持 UNKNOWN。不得把静态格中心、连续地形交叉或条件模型时间升格为真实战术 deadline。普通模式1～3星约束继续有效。


## Work review 2026-10-11 — 4b1b523

CONFIRMED_FROM_CODE: terrain navigation model exists; manifest 11/11 matches; review pytest 8 PASS / 3 FAIL (contradictory tests). Client algorithm equivalence is UNKNOWN; binary addresses/hash and extraction conclusions remain REPORTED_BY_PREVIOUS_WORKER until reproducible excerpts are supplied. This qualification supersedes earlier wording that independently confirmed client semantics. No new runtime bug or tactical impossibility is established. Next bounded task: reproducible active-roadblock navigation evidence; Kimi and real-stage simulations remain zero. See [review](review/4b1b523/REVIEW.md).

## Work review 2026-10-12 — b60c48c and V3 correction

CONFIRMED_FROM_CODE: Work verified b60c48cd28383d3058f290ee2d0b434086b8c6da with 12/12 targeted PASS and matching raw-disassembly hashes; this reviewed saved evidence, not a fresh APK extraction. V3 supersedes the two V2 hardening labels. A moveCost-only change participates in refresh signal construction, and avoidObstacleLike is the conditional arithmetic `cached_distance - tile_moveCost < 1000`, not a universal per-tile rule. `Route.ReconstructNextMap -> SPFA` remains UNKNOWN because the supplied Route method bytes are not statically decodable. Cross-version applicability remains UNKNOWN.

## 当前边界（2026-10-12 Route解码诊断）

CONFIRMED_FROM_CODE：V4 核实固定 binary 的 ELF PT_LOAD 映射、`.eh_frame` 方法边界、
metadata 地址和原始字节。三个 Route 方法默认 Capstone 入口解码失败；对齐重同步只
能提供候选线索。UNKNOWN：`Route.ReconstructNextMap -> SPFA`、入口失败的真实原因、
跨版本适用性和兼容的完整调用体。历史 V1/V2/V3 artifacts 原样保留；V3 的
`NO_VALID_A64_INSTRUCTIONS` 分类失效。普通 1～3 星约束、Kimi 0、真实关卡模拟 0、
新计划/候选 0、战术扩搜 0 继续有效。

## 当前边界（2026-10-12 低星完整闭环）

普通模式 1～3 星约束不变。本轮唯一 Kimi-K3 调用失败为 `response.incomplete`，根因是
原请求未嵌入已准备 evidence context 且输出在 32,768 token 截断。因此没有有效新计划、
动作候选或模拟证据；不得用部分输出代替战术。原始流和 forensics 已保存。修复已针对
未来入口生效，但不构成新调用授权。下一步由 Work 审查后决定是否批准新请求。

## 2026-10-12 边界增补

Kimi只能在Work批准的新预算内重新调用。任何POST前必须保存并校验最终body；失败也算预算，
不得重试。历史战术诊断必须显式失效范围，不能复述为活跃事实。普通模式1～3星、排除模式专属
预备干员、不编造数值/机制/测试结果的规则继续生效。

## 2026-10-13 工具边界

确定性工具只做白名单事实、几何和条件约束计算；不得推荐位置、改朝向、生成战术、运行模拟或开放
shell/文件写入。工具轮、续接请求和失败都计入预算。UNKNOWN必须保留；mock成功不能冒充当前
kimi-k3 endpoint兼容性。

## 2026-10-13 只读工具执行边界

工具续接必须包含原user上下文、对应`function_call`和`function_call_output`；不使用
`previous_response_id`或assistant prefill。重复call_id、非法参数、超预算和参数未完成的
工具批次不得执行。最终计划必须强制通过现有schema/contract；外部回调不能替代校验。
同帧DP扣款未显式关联或顺序不明时必须UNKNOWN。

## 2026-10-13 真实工具探测边界

最小真实工具探测最多2次请求、1次只读调用，只允许非战术上下文和简短确认。它确认的兼容范围
仅限观察到的原生工具轮；不能授权完整战术会话、C2、模拟或扩大搜索。战术入口仍必须强制现有
schema/contract校验。

## 2026-10-13 战术模型可替换边界

用户可以授权替换战术模型，但GLM仍是研发实现方，确定性工具与本地schema/contract校验不可替代。
GPT只通过普通模式1–3星资格、只读工具和C2失败证据决定战术；Python不代写阵容、位置、方向或
时刻。Sub2API/GPT项目兼容性在项目请求验证前保持UNKNOWN，Codex自身可用不作为兼容证明。

项目兼容性只按实际入口证据限定：观察到完成的普通文本、原生function_call、确定性工具执行与完整
续接，不推断所有tool schema、输出格式、截断或计费行为都已兼容。失败、超预算和请求日志不一致必须
按日志对账，不能因最终HTTP完成而改写为0或成功。

恢复历史输出必须保持来源边界：`parent_hypothesis_id`是模型假说谱系，旧计划谱系保存在provenance。
无损整理只允许显式规范化并保存diff；未通过contract的输出不能进入模拟。模拟结果必须保留完整事件
和参数，manifest或后处理故障不得自动重跑，也不能将diagnostic LOSS升级为实机结论。

## 2026-10-14 七关连续批次边界

用户授权第一阶段推进R8-1至R8-7普通模式。WIN是硬目标；只能使用实际解析为`main_08-01`到
`main_08-07`的固定GameData事实，普通1–3星资格不变。每个DEPLOY必须有[行,列]和方向。GPT决定
战术；Python执行事实、合法性和模拟。WIN先于减员；减员先从人数开始，只在第一阶段全部WIN后启动。

条件模型WIN、PROBABILISTIC_WIN、robust WIN和实机通关是不同声明。R8-1需要同一动作时间线在
两种roadblock targeting解释下复验才能称robust。概率依赖必须来自GameData，联合概率不得低于0.0001；
依赖不独立或无法证明时保持UNKNOWN。

## 2026-10-14 恢复优先与失败闭环止损

跨关卡校验不得回退到R8-1事实。已保存候选先通过阶段本地的schema/contract、假说谱系与静态检查，
再执行原样诊断。若连续同形状GPT修订反而恶化战斗结果，必须停止该修订方向并保存失败证据；不得让
Python挪格、改帧或自行替模型重排战术。

## 2026-10-14 七关批次调用纪律

通用七关入口必须使用每个关卡实际解析的事实，不复制R8-1路线或截止时间。每条CLI启动、每个计划
与模拟都必须计入持久预算。无效计划不能无损改成有效战术；尤其不能把路障格重命名或移动动作。
已解析但不被当前模拟器支持的关卡必须标BLOCKED，不得以紧凑事实隐藏缺失机制。

## 2026-10-14 平民目标与生命边界

R8-2的旧“PARTIAL_MECHANICS_DIAGNOSTIC_WIN”已由机制修正重验反证。Simulator必须要求
`remaining_life > 0`；乌萨斯平民是中立单位，普通干员不攻击也不阻挡；安全到达不扣生命、
不计漏怪，死亡扣1且不计歼灭。选择器对平民的1.2攻击半径是 enemies 侧特殊能力，不推广到全部敌人。
路障只按已核实规则阻止平民，不成为普通干员阻挡。以上仅限定当前模拟，不等于实机结论。

## 2026-10-14 死亡释放阻挡为模拟器最低正确性

统一致死链必须在删除活跃敌人前释放其阻挡名额。死亡后残留的`blocked_enemy_ids`会造成幽灵容量，
使存活干员放过后续敌人；任何战术失败结论都必须先排除这类确定性程序污染。历史模拟不能因后续修复
自动改写，只在新目录重验并把旧结果标注适用范围。

## 2026-10-14 模拟WIN与完美通关分开判定

R8-2的当前模拟WIN只要求零漏怪、正生命、出生耗尽且无活跃敌人。用户目标进一步要求保护目标零损失；
因此保护目标死亡不能被WIN抹去。报告中必须分开记录`SIMULATOR_WIN`、`PROTECTED_TARGET_LOSS`与
`PERFECT_COMPLETION`，不能把前者升级为后者或实机结论。

## 2026-10-15 m21机制边界

路障阻挡必须使用PRTS给出的0.4472连续半径，不能只在路线穿过装置格中心时生效；路障摧毁时释放
被它停住的平民。普通干员格中心接触在当前模型保留，但精确客户端连续接触半径仍为UNKNOWN。
一星干员不计部署位但仍计编队人数。再部署费用增长、R8-5/6友方装置效果、斗士塔露拉完整语义和
概率联合下界仍未实现；涉及这些机制的通关不能升级为完整机制通关。
