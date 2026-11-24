# Astra 操作手册 v1（可复用战术实验 harness）

本手册描述怎样在这个 harness 里提出假设、跑一批实验、读结果、决定下一步。全部工具都是**只转发生产门禁**：战术决定由你（Astra）做，harness 不做战术、不做第二套模拟器、不碰认证。

## 0. 你会拿到什么

启动时 harness 会告诉你：

- 本批**父项**（例如 `A`、`M70`）以及一个空协议容器 `T`（无战术、无事件，只用来从零编排）。
- **名单模式**：`open`（34 个合法普通 1–3 星都可评估）或 `fixed:<ids>`（只能恰好用这些 ID）。
- `max_unique_deployed_operators`（K）。`selected` 与所有 `DEPLOY` 的 `operator_id` 并集必须 ≤ K；同 ID 再部署只计一次；机器人计入。
- 预算：`check`（静态/合同检查次数）、`candidate`（合法冻结候选数）、`full_simulation`（真实完整模拟次数）。
- 轮的次数上限（默认 5）。**一轮 = 一个问题 → 跑一批 → 据证据决定下一步**，不是一次模拟。

## 1. 开局先读证据，不要凭空猜

```
get_session_status()                     # 预算、已记录轮、父项、名单模式
inspect_evidence(kind="facts")           # 关卡事实：active facts / routes / spawn timeline
inspect_evidence(kind="catalog")         # 34 人能力目录（带 qualification/rarity/position）
inspect_evidence(kind="plan", source="A")        # 父项完整计划
inspect_evidence(kind="actions", source="A")     # 父项动作表 + validation card
inspect_evidence(kind="outcome", source="A")     # 父项真实结局：leaks/kills/arrivals/deaths/devices
inspect_evidence(kind="events", source="A", event_types=["ENEMY_LEAK"], ids=["enemy_..."] , aggregate=false)
inspect_evidence(kind="diff", source="A", other="M70")   # 两个父项的动作差异（不拼接成功时窗）
```

机制与历史经验：

```
inspect_evidence(kind="kb", query="索敌", topic="targeting")
   # 返回 summary/details/source_url/sim_check_points；每条都要求你对当前模拟器再核对一次
inspect_evidence(kind="experience", tags=["ARTILLERY_KILL","CENTRAL_INTERCEPT"])
   # 归档经验：带 applicable_conditions / responsible_paths / 反例线索
   # 注意 selector_verdict：若显示 MECHANICS_NOT_CURRENT，说明该记录的 mechanics_version 不是当前版本，
   # 只能当跨关参考，不能直接当作本关事实。
```

**规则**：经验/机制条目只给"看到什么迹象值得检查什么"，不直接给动作。本关有效的经验是 **THIS_STAGE_ONLY**，不能自动升级为跨关规则；写回经验库时标 `CROSS_STAGE_PENDING`（见第 5 节）。

## 2. 提出一轮（先记录假设，再花钱）

```
record_round(
  round=1,
  expected="我预测哪个战斗事件会变（写具体事件：谁、哪一帧、什么受击/治疗/命中）",
  decision="我要怎么实现（换谁/换格/换朝向/改帧/撤退/返场）",
)
```

`record_round` 只保存文字，不花钱。之后才用 `search_variants` 把它变成一批组合。

## 3. 批量实验 `search_variants`

一个组合 = 参数网格的笛卡尔积作用在 `changes` 上。支持的动作变化：

- `{"type":"set","operator":<id>,"action":"DEPLOY|ACTIVATE_SKILL|RETREAT","frame":<原帧>,"fields":{...}}`：按 `(operator, action, frame)` 唯一定位一条动作，改它的字段。
- `{"type":"remove","operator":...,"action":...,"frame":...}`：删除该条动作。
- `{"type":"add","value":{完整动作}}`：新增一条完整动作。
- `{"type":"replace","operator":<旧>,"replacement":<新>}`：把某人的动作整体换成另一人。

`parameters` 里的 `$name` 会被网格值替换。例：

```
search_variants(
  round=1, name="r1_falco", parent="A",
  hypothesis="延后 Falco 部署与技能帧，改变他首个炮兵窗口的输出（≥20 字）",
  changes=[{"type":"set","operator":"char_192_falco","action":"DEPLOY","frame":31,"fields":{"frame":"$d"}},
           {"type":"set","operator":"char_192_falco","action":"ACTIVATE_SKILL","frame":1382,"fields":{"frame":"$s"}}],
  parameters={"d":[31,91],"s":[1382,1442]},
)
```

也支持整套重写：给 `actions=<完整时间线>`，再让 `changes` 打补丁。**不需要为每个组合重新生成完整 JSON**：只给可变部分，harness 机械展开。

先看规模再花钱：

```
search_variants(..., dry_run=true)
# 返回 planned_total + capability(check/candidate/simulation 剩余, usable_simulations)
```

`dry_run` 不消耗任何额度。正式调用时会：

1. 机械展开组合，对每个组合构造 payload 并做**动作去重**（含历史归档），重复的报 `DEDUP`，不重跑。
2. 走生产 `check_plan`（合同/静态/执行输入/人数/谱系门禁）。
   - **静态拒绝只消耗一次 check**，不建候选、不跑模拟。
   - `PASS` 才冻结一个候选，并可跑**一次**完整模拟。
3. 组合数若超过可用模拟，会在剩余预算处停止，返回 `TRUNCATED_BY_BUDGET` 和 `skipped` 列表（本批默认预留 1 次模拟用于最终复验）。

返回默认包含（足以决定下一轮）：

- `attempted / dedup / static_fail / real_runs` 四个计数，分开算 check、候选、模拟。
- 每个变体：`status`、`candidate_id`、`observed{leaks, leak_ids, protected_arrivals, artillery_kill, enemy19_kill, operator_deaths, complete_win}`。
- 若父项有事件：`leak_delta{parent_leaks, variant_leaks, resolved, new}` —— **消掉了哪些漏怪、又新增了哪些**。
- `complementary_by_leak_set`：按漏怪 ID 集合分组的互补方案（不只留总击杀最高者）。

原始事件默认**不灌进上下文**，需要时再 `inspect_evidence(kind="events"|"outcome")` 追。

## 4. 看结果、追单局、决定第二轮

```
inspect_evidence(kind="outcome", source="<candidate_id>")     # 该候选的真实结局
inspect_evidence(kind="events", source="<candidate_id>", event_types=["ENEMY_LEAK"], earliest_frame=..., latest_frame=...)
inspect_evidence(kind="events", source="<candidate_id>", event_types=["DAMAGE"], ids=["char_...","enemy_..."], aggregate=true)
query_events(candidate_id=..., candidate_sha256=..., event_type="...")   # 生产只读查询（一次一种事件类型）
```

然后 `record_round(round=2, observed={...}, next_reason="...", decision="...")`，再 `search_variants(round=2, ...)`。
`search_variants` 要求该轮先被 `record_round` 记录，否则报错——保证"先写假设、后跑"。

## 5. 教学闭环与三分记录

收到教师提示时：

- `record_teacher_prompt(text=<原样文本>, source="user", received_by="tactical_side")` —— 原样存档并回显 `sha256`，用于审计"提示是否原样到达战术端"。不重写、不改方向。
- 每条被"听取"的提示用 `record_teaching` 分开记三件事，并用 `record_teacher_prompt` 返回的
  `teacher_message_id` 引用原话（不要凭记忆复述教师原话）：
  - `teacher_message_id`：指向存档原文的稳定 ID。
  - `user_quote`：只在需要单独引述时给；与存档原文不一致会被标记 `ASTRA_QUOTE_DIVERGES_FROM_STORED_TEACHER_MESSAGE`，**不会被当作教师原话**。省略时自动用存档原文。
  - `astra_interpretation`：**你**的解释（提示改变了你什么判断；没改变也可以）。
  - `simulation_observation` + `candidate_id`（或 `run_id`/`event_locator`）：实际模拟观察；给 `candidate_id` 就会自动解析出该候选的确定性事件日志路径。
  - 另可给 `abstract_rule`（可检索的判断方法）、`counterexample`（反例）、`scope`。
- **不要把"听取了提示"当成"提示已被证实"**。三者分别落 `teaching/user_quotes_v1.jsonl`、`astra_interpretations_v1.jsonl`、`observations_v1.jsonl`，可回读。
- 抽象规则写经验时：本关标的用 `THIS_STAGE_ONLY`；跨关待验用 `CROSS_STAGE_PENDING`。

## 6. 复验与收尾

- 找到可能是完整 WIN 的候选时，`search_variants` 返回 `WIN_MUST_VERIFY`，并写 `WIN_PENDING_VERIFICATION.json`。
- `independent_verify(candidate_id=...)`：用新 run id、同一冻结输入真实复跑。
  - **真实后端**：会另起一次生产模拟，`counts_as_independent_verification=true`。
  - **TEST_ONLY_FAKE 后端**：诚实返回 `CACHE_HIT_NOT_INDEPENDENT`（假后端对已完成候选返回 `IDEMPOTENT_COMPLETED`，这是缓存命中，不是独立复验）。
- 完整 WIN 判定要求：合法 ≤K、零漏、双保护安全到达、全敌结算（`enemies_remaining==0`）且模拟器判 WIN。fake 后端打出的 WIN 只是产物，标注 `artifact_projection=true`，不算真实结果。
- 中断后重连：`get_session_status` 可读回已记录轮、已尝试变体（`frozen_candidates` 含每个冻结候选的执行状态）、教学记录、剩余预算。
- **恢复由执行状态决定，不由动作 key 决定**：已完成→复用结果（不重跑）；已冻结未启动→同一候选继续跑（不重占候选位）；启动结果未知（`STARTED_UNKNOWN` / 非空输出）→harness 停止并报告 `INTERRUPTED_UNKNOWN_RESULT`，**不要盲目重跑**。
- 即使 harness 自己的 `batch_state.json` 写回丢失，也能按生产账本的 `candidate_sha256` 找回冻结候选；候选位和 check 不会被重复消耗。
- **坏组合只影响自己**：一个组合非法（`INPUT_REJECTED_BEFORE_PRODUCTION_CHECK`）或静态拒绝（`FAIL`）只会记下该组合并继续下一组合；预算耗尽、账本不一致或服务不可用才停止整批。
- **大网格先看规模**：单次调用上限 60 个组合；8 维×10 值这类大网格会返回 `COMBINATION_CAP_EXCEEDED` 与真实总数（不分配、不执行）；先 `dry_run=true`。

## 7. 一个从提问到结果的完整小例子

```
# 教师提示
record_teacher_prompt(text="先别猜能不能夹住炮兵，去看 1382 是不是 SP 还没转好。", source="user")

# 查一条相关经验 + 一条机制
inspect_evidence(kind="experience", tags=["ARTILLERY_KILL"], limit=2)
inspect_evidence(kind="kb", query="技能")

# 记录第 1 轮假设
record_round(round=1, expected="去掉 Falco 的 1382 技能（改帧）会改变他首个炮兵窗口的输出",
             decision="枚举 Falco DEPLOY 帧 {31,91}")

# 先看规模
search_variants(round=1, name="r1", parent="A", hypothesis="延后 Falco 部署以改变首个炮兵窗口的输出时机",
  changes=[{"type":"set","operator":"char_192_falco","action":"DEPLOY","frame":31,"fields":{"frame":"$d"}}],
  parameters={"d":[31,91]}, dry_run=true)

# 正式跑
search_variants(round=1, name="r1", parent="A", hypothesis="延后 Falco 部署以改变首个炮兵窗口的输出时机",
  changes=[{"type":"set","operator":"char_192_falco","action":"DEPLOY","frame":31,"fields":{"frame":"$d"}}],
  parameters={"d":[31,91]})
# => r1_0 PASS(candidate-001, 真跑) ; r1_1 FAIL(static: SP_NOT_READY available_sp=44.7 required_sp=45.0)

# 据第 1 轮证据改方向
record_round(round=2, observed={...}, next_reason="改部署帧会撞 SP 阈值，改看格子/朝向更直接",
             decision="改 Midnight 的落点")
search_variants(round=2, name="r2", parent="A", hypothesis="移动 Midnight 落点以打开中路窗口而不动 Falco",
  changes=[{"type":"set","operator":"char_283_midn","action":"DEPLOY","frame":1021,"fields":{"tile":"$t"}}],
  parameters={"t":[[3,3],[4,3]]})

# 记录教学三分（引用 record_teacher_prompt 返回的 message_id）
record_teaching(round=1, teacher_message_id=<teacher_message_id>,
  astra_interpretation="1382 的技能可能因为 SP 未满被拒；先验证充能窗口再谈夹击",
  candidate_id="candidate-001",
  simulation_observation={"r1_1":"FAIL","error":"SP_NOT_READY available_sp=44.7 required_sp=45.0"},
  abstract_rule="技能被拒时，先查该帧充能/SP 是否就绪，再判断技能时机是不是杠杆",
  scope="CROSS_STAGE_PENDING",
  counterexample="被拒也可能只是同帧顺序问题，而非充能不足")
```

## 8. 边界

- 只对当前固定模拟器作结论；不宣称实机、faithful、robust、概率 WIN、更少人数无解或全局最少。
- 服务/额度/路由故障：harness 会**停止并保存现场**，不自动 retry/resume、不换模型账号地区。看到 `status.blocker` 就报告，不要反复重试。
- 不为每个组合重写完整 JSON；用 `changes` + `parameters` 表达可变面。
