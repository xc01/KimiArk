# Architecture Decisions

来源与不可变约束：PROJECT_CHARTER（用户明确要求）。代码事实、历史报告、推测分别标 CONFIRMED_FROM_CODE、REPORTED_BY_PREVIOUS_WORKER、HYPOTHESIS。

1. 用户明确要求：Kimi-K3 决定战术；deterministic system 提供事实、计算、合法候选与验证；GPT / Work 管理审查；GLM 实现代码。任何确定性修复不得替 Kimi 选打法。
2. 用户明确要求：OperationalPlan 保留开局、路线职责、压力窗口、阵型演化、技能意图、暂时阻挡、共享火力、治疗、撤退和移交。合法动作不等于忠实战术。
3. 2026-10-09 CONFIRMED_FROM_CODE：当前 V3 是前缀诊断，不是完整 OperationalPlanCompilerContract 或 fidelity verifier。保留诊断数值，撤回自动 proven classification；没有替换为另一个固定打法或人为放宽 deadline。
4. 2026-10-09 CONFIRMED_FROM_CODE：未知 deadline 不得自动转成 spawn frame；自然-only 收入没有证明是完整经济上界；共享/条件/阶段语义缺失不得升级为全计划不可行。
5. 用户明确要求：机制 m18.9-stage-device-runtime-v1；GameData 主源；机制不能为让计划通过而猜改。两种 roadblock targeting 的 robust WIN 必须相同动作时间线；模拟器 WIN 和真实游戏通关分别记录。
6. 用户明确要求：失败经验必须具有条件、证据、来源与局限，冲突集合不称最小 UNSAT core；旧不完整 fidelity 结果不作为严格战术失败。
7. 2026-10-09 CONFIRMED_FROM_CODE：`EARLIEST_OPERATOR_CONTACT_FRAME` 不能自动成为 FIRE establishment deadline。A/B/C 的 route-3 FIRE deadline 保持 UNKNOWN；不发明替代期限。
8. 2026-10-09 CONFIRMED_FROM_CODE：selected-usage fidelity 仍必须检查实际依赖的 trait；ammo `atk_scale`、“技能未开时 block 0”、merchant cost/interval 都是 decision-critical 时不得因 aggregate selected-skill metadata 一刀切放行。缺表导致的 pool 数量差异不能通过人工增删干员抹平。

7.2026-10-09 CONFIRMED_FROM_CODE：source-reverification的candidate pool须具fidelity/census输入证据；缺失时BLOCKED，测试不得覆盖历史artifact。接敌事实与plan-specific FIRE deadline分离；下一阶段用一个现有计划的有限局部witness推进，不继续增加泛化审查层。

- 23a623a independent review: capability averages and cost caps cannot serve as finite-window damage certificates or economic lower bounds. Preserve conditional concession branches; record missing provenance without inventing files/hash; runtime UNSUPPORTED is an evidence gap, not game impossibility.

- d9304bb review: test execution results must come from actual runner logs, not literals in validators. DP credits persist across events and conditional omissions change executable ledger rows. Conditional derived deadlines stay tied to roster/targeting/damage assumptions. Next tactical revision belongs to Kimi-K3, one bounded call.

- 2026-10-10 CONFIRMED_FROM_CODE：d9304bb 审查补丁合入后允许唯一 Kimi-K3 修订。模型返回一个 Plan A 开局修订；确定性系统只生成 2 个 distinct opening 组合、1 条动作候选和条件证书，0 次阶段模拟。Python 不替 Kimi 发明新战术，也不把 conditional model conflict 升格为通用期限。

- 51e0410 review: continuous SP/attack state must cross target handoffs; per-plan literal certificates do not prove semantic compilation. UNKNOWN execution guards block faithful prefix validation; simulator omissions cannot certify those guards. Candidate-set absence remains scoped to actually supplied roster.

- 2026-10-10 CONFIRMED_FROM_CODE：公共运行时新增 generic merchant upkeep 与 active stage-device occupancy 检查。GameData description/trait blackboard 确认 strong/talr/nothin 每3秒扣3 DP且不足自动撤退；首扣帧仍未独立确认。`trap_020_roadblock#2` 活跃时占据 [9,2]，销毁（`hp <= 0` 后从 `active_devices` 移除）才释放部署格。机制版本不变，但不把这两个修复解释为战术通过。

- 用户2026-10-10：模式专属预备干员不得进入普通模式规划。复用GameData obtainability过滤，在LLM显式指派处也校验；基础事实记录不删除。候选资源范围必须明示，不能用旧7人集合缺项证明全普通 roster缺项。
- 48fa985审查：区分源确认的费用量/周期与未确认首扣相位；模型数字不升级为客户端精确观测。优先修正证据说明，禁止再造计划专用计算层。

- 用户约束：当前debug只用普通模式1～3星。资源资格与机制支持独立，资格在输入/显式选择/动作入口均需校验；不擅自放宽星级。旧高星阵型不约束新低星战术结构，战略决策仍属于Kimi。
## 低星目录与公共运行时边界（2026-10-10）

普通模式资格、1～3星限制、基准配置和运行时支持分别记录。`NormalLowStarQualification`是Kimi显式选择与动作校验共享入口；34名事实由固定GameData重建。只实现了有源且行为测试覆盖的最小通用机制：deployment SP、deployment global heal和redeploy-time delta。AoE splash几何缺失时不能把splashcaster/aoesniper当作已支持，Kimi计划中它们的unsupported天赋只作未计入事实。


## 2026-10-10 Work独立审查1e92747（覆盖冲突旧结论）

CONFIRMED_FROM_CODE：DP叙事比较必须同一时间点；账本以窗口终点输出且注明战斗存活收入条件。未支持机制不承重需要执行依赖证据，catalog存在/模型承诺均不足。允许显式省略机制的固定候选模型诊断，但其结果不得升格faithful。

## 固定前缀诊断观测边界（2026-10-10）

固定前缀诊断复用公共GameData读取、adapter和Simulator，不新增伤害/费用公式。Simulator的合法DEPLOY事件现在包含实付成本和DP余额；该字段只增强观测，不改变部署/经济规则。为了保存941而不是942循环尾，入口使用legacy loop特性把 `max_time` 设为 `(941-1)/30`。完整事件、参数、机制省略和manifest一起保存。


## 2026-10-10 Work审查bc14455（覆盖冲突旧结论）

CONFIRMED_FROM_CODE：serialized map数组行需翻转；路线和predefines场地row不需翻转。共享adapter分清来源而非统一翻row；runtime普通高台不能承担地面阻挡；固定时钟从整数tick推导。路线压力事实必须包含MOVE/WAIT并与公共runtime同源，不能只用distance/speed。

## 公共路线与方向契约（2026-10-10）

CONFIRMED_FROM_CODE：`Route.distances_at`保存每个到达同一格的折线距离，仅合并相邻重复；`time_at_distance`只累加严格早于目标距离的WAIT。这避免把一次经过的距离误用于重复阶段，也不把目标处等待当作已到达。`ApproximateRealRangeTransformer`使用bottom-left field坐标；`CanonicalSyntheticRangeTransformer`继续保持自身y-down约定。两套约定分开测试，不互相伪装。


## 2026-10-11 Work审查1223c03（覆盖冲突旧结论）

CONFIRMED_FROM_CODE：Route.distances_at不能只用于新目录，公共威胁与模拟器须使用全部访问。旧latest_safe_blocker_frame在本批数据只是条件格中心到达摘要，不是真实部署硬期限。通行检查必须覆盖连续路径，不能以tile中心枚举证明WALK可走；真实阻挡半径未建模时不得认证无拦截。


- 2026-10-11 CONFIRMED_FROM_CODE：新增公共 `WalkNavigator`，在 adapter 中仅对 `motionMode=WALK` 使用四方向 SPFA 和客户端 Bresenham/Segment 平滑；FLY/E_NUM 仍走既有转换。`StageRouteData` 保留源 `motionMode` 与 `allowDiagonalMove`。不建 R8 专用物理模型。
- UNKNOWN：动态 roadblock 是否参与/如何参与 SPFA、实际碰撞半径和 WAIT 阻挡规则。未实现猜测性 roadblock 导航规则。


## Work review 2026-10-11 — 4b1b523

CONFIRMED_FROM_CODE: terrain navigation model exists; manifest 11/11 matches; review pytest 8 PASS / 3 FAIL (contradictory tests). Client algorithm equivalence is UNKNOWN; binary addresses/hash and extraction conclusions remain REPORTED_BY_PREVIOUS_WORKER until reproducible excerpts are supplied. This qualification supersedes earlier wording that independently confirmed client semantics. No new runtime bug or tactical impossibility is established. Next bounded task: reproducible active-roadblock navigation evidence; Kimi and real-stage simulations remain zero. See [review](review/4b1b523/REVIEW.md).

## 2026-10-12 No guessed roadblock runtime layer

不新增计划专用物理模型或审计框架。已保留公共 `WalkNavigator`，只提交 focused disassembly、hash、claim-to-evidence 映射和 artifact-integrity 回归。因为 roadblock prefab payload 不可解码，不修改导航默认规则；现有 `roadblock_navigation_effect=UNKNOWN` 分类继续生效。

## 2026-10-12 Keep roadblock navigation conditional

V2 提取到确切 payload 后仍不把路障实现为无条件全阻隔。已确认的两个分支是：keep-current passableMask 使 WALK/FLY mask 保持不变；但 `avoidObstacleLike=true` 的 SPFA reachability 检查会把该格视为 obstacle-like。在普通路径请求是否设置该标志得到确认前，公共导航层不改变战术判定。

## 2026-10-12 Preserve the missing Route-to-SPFA boundary

V3 保留 SPFA/Tile 的静态语义，但不在公共导航层补写 `Route.ReconstructNextMap -> SPFA`。Route 方法体在当前静态字节中不可解码；该边保持 `UNKNOWN_MISSING_STATIC_EDGE`。V2 的两条概括分别由 moveCost 变化位和 `cached_distance - tile_moveCost < 1000` 的条件算式取代。下一步只允许针对这一条边获取可复核客户端证据。

## 2026-10-12 Keep decoder failures narrowly scoped

V4 将默认 Capstone 空流分类为 `ENTRY_DECODE_FAILED`，非空前缀分类为
`PARTIAL_DECODE`，完整消费分类为 `COMPLETE_DECODE`。四字节重同步与 skipdata 结果
只作为候选线索，不能直接表示真实代码、函数边界或调用边。V4 在创建输出前校验固定
binary SHA-256，避免错误输入覆盖证据。公共导航层继续没有 `Route -> SPFA` 的
实现或补写。

## 2026-10-12 Keep LLM input and transport observable

完整战术闭环入口改为在 prepare 阶段保存 `llm_request.json`，并把 compact evidence JSON
嵌入唯一用户消息；call phase 不再从另一份 prompt 隐式重建请求。SSE 解析在收完原始流后
执行，避免分块边界切断事件；空 `response.incomplete` 不覆盖 `response.created` envelope。
响应必须完成且 JSON 可解析后才能进入确定性编译。

## 2026-10-12 — 最终请求门禁与传输预算

决策：最终POST必须使用已固化的canonical body；`llm_request.json`只是结构化缓存，不能在call
时从旧prompt重建。固化和stream序列化统一使用
`ensure_ascii=False, sort_keys=True, separators=(',',':')`，避免写入key顺序差异。
`validate_final_payload`检查嵌入evidence与prepared evidence相等、schema相等、模型/流、固定
路障、历史B2边界和body哈希。

决策：`start_attempt`必须在`urlopen`之前落盘；HTTPError保留状态和request ID，超时/中断保留
已收字节；`finish_attempt`后返回统一失败。不存在terminal事件时补`NO_TERMINAL_EVENT`，不把
`response.completed`当作HTTP 200反推。本地验收用mock urlopen检查`Request.data`。

## 2026-10-13 — 有界Responses工具循环

决策：工具白名单只含三个只读查询。SSE accumulator保留`function_call`的call_id/name/arguments；
`requires_tool_execution`用于工具轮，`complete`仍要求assistant final text。工具续接通过把
`function_call_output`追加到初始user input实现；不使用`previous_response_id`，不伪造assistant
消息，不自动重试。

决策：每轮模型请求和每个工具调用都先预算计数；结果必须与call_id一一对应。工具轮没有最终文本
不算战术输出失败；incomplete/failed/JSON截断/参数不完整不执行或终止。`text.format`的最终计划
schema保留。当前provider组合的tool兼容性保持UNVERIFIED，不能由离线mock证明。

## 2026-10-13 — 只读工具续接与预算修复

决策：Responses式续接保留完整上下文：原user input，随后每个`function_call`及其对应
`function_call_output`。`item_id`只用于SSE内部关联；不发送`previous_response_id`，也不把
assistant prefill伪装成续接。模型+endpoint兼容性保持UNVERIFIED。

决策：工具批次先做重复call_id、剩余预算和JSON Schema预检，预检失败不执行任何工具。最终计划
必须经过现有jsonschema与OperationalPlan contract；外部验证回调只能追加错误，不能替代或绕过。
同帧部署扣款必须显式关联或顺序明确；否则DP结果是UNKNOWN，不允许同一检查同时PASS和冲突。

## 2026-10-13 — 最小真实工具续接

决策：先比较流式function_call与terminal envelope最终function_call的call_id、name、arguments
和status，再检查response与每个调用是否completed；malformed或未完成的调用绝不执行。DP账本
按关联扣款条目在声明顺序中的实际位置计算前后余额，不足是CONFLICT，顺序未知是UNKNOWN。

决策：真实协议探测只发送非战术提示、全部白名单工具和显式`max_output_tokens=1024`。最多2次
请求、1次工具；第一次原生调用，本地执行一次，第二次携带匹配`function_call_output`。不使用
previous_response_id或assistant prefill。探测成功只确认非战术工具轮，不授权真实C2或放宽战术
入口schema/contract。

## 2026-10-13 — C2工具使用门禁

决策：即使最终文本是合法JSON，若整个会话没有至少一个已执行的原生只读工具调用，也不返回
`COMPLETE`。文字声称调用工具、计划JSON有效或schema通过都不能替代Kimi主动查询；这防止模型
用普通文本冒充工具轮并直接交出战术计划。真实C2会话中的每个请求、续接和失败仍计数。

## 2026-10-13 — C2紧凑两阶段修订

决策：查询阶段复用已验证的原生function工具协议，不绑定最终OperationalPlan的`text.format`，
`max_output_tokens`上限4096。收到真实工具结果后，续接同时保留原user上下文、
function_call、function_call_output和新的显式最终指令；此后才绑定32768上限的最终JSON schema。
普通文本声称调用工具不等于工具结果。每个请求正文在联网前不得高于140,000字节。

决策：响应terminal分类必须准确。`response.incomplete`不能写成`NO_TERMINAL_EVENT`；它会占用
请求预算并终止会话，但缺少工具调用或最终计划时也不能被修补或续接为战术成功。

## 2026-10-13 — C2 V2长度与续接门禁

决策：查询与最终输出阶段都可显式设置32768输出预算；`text.format`仍只在最终续接绑定。续接体
必须在联网前按同一140,000字节上限预检，超限时停止并保留完整载荷哈希；不降级、不截断工具结果、
不猜测服务端限制。

决策：原生function_call完成且参数Schema有效才计入工具执行。参数不完整的调用必须标
`INVALID_NOT_EXECUTED`，不能在文档中概括成“6个工具全部使用”。

## 2026-10-13 — C2保存调用恢复

决策：修复配置校验后，只重验已保存的原生function_call；不重放第一轮推理，不重复执行时序查询，
不改operator、位置、方向、目标或call_id。已保存的失败结果保留，新结果另存并标明是确定性系统
修复后的重验。初始140,000字节预检不变；最终续接上限为200,000字节。第三次模型请求是唯一
HTTP续接，失败后不自动重试。
