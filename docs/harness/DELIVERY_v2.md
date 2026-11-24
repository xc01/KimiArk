# 交付说明 v2 —— tactical harness 审查修复（基线 `0a342f12`）

基线 `0a342f12` 之后只做了代码修复与离线测试：**没有启动战术模型、没有真实模拟、没有新实验账本、没有推送**。旧账本、原件、M70/R106 分支与无关脏文件不动。

## 五项修复对照表

| # | 原行为（基线 0a342f12） | 修复后行为 | 对应测试 | 仍须真实联调 |
|---|---|---|---|---|
| 1 | `search_variants` 把所有非 PASS 一律 `break`（基线 495–523 行）；候选输入异常（如 `build_payload` 抛错）直接整批崩溃 | `RECOVERABLE_CHECK_STATUSES={FAIL,INPUT_REJECTED…}` 继续下一组合；`build_payload` 异常→记 `INPUT_REJECTED_BEFORE_PRODUCTION_CHECK` 仅此组合；`FATAL_CHECK_STATUSES`（check/候选预算耗尽）按 `fatal_stop_kind` 停止并写 `check_budget_exhausted` blocker；服务异常经 `classify_check_fault` 分为 `check_service_fault` / `ledger_inconsistency`；模拟侧同理分 `simulation_service_fault` / `simulation_ledger_fault` | demo: 第一组合非法第二组合照跑（`real_runs==1`）；单元: `test_recoverable_and_fatal_statuses_are_disjoint_and_explicit`、`test_check_fault_classification_separates_ledger_from_service` | 真实服务故障的区分（网络断 vs 账本损） |
| 2 | 去重只看 `action_key`；中断恢复不存在；`IDEMPOTENT_RECHECK`/`IDEMPOTENT_COMPLETED` 被当致命停止 | 恢复取决于**执行状态**：`candidate_execution_state` 读生产账本+`_simulation_output_state`；COMPLETED→复用结果；NOT_STARTED→同候选重跑；STARTED_UNKNOWN/非空输出→`INTERRUPTED_UNKNOWN_RESULT` 停止不盲跑。新增三层对账：(a) state 里有候选→恢复；(b) state 行丢失但 check 返回 `IDEMPOTENT_RECHECK`→按 PASS 行恢复；(c) 连 check 都没跑到→`frozen_candidate_by_sha(payload_candidate_sha256)` 用生产账本 `candidate_sha256` 找回冻结候选。恢复/复用的 observed 与 leak_delta 都持久化写回 `batch_state.json`；不再重复占候选位或重复花 check | demo: 故障注入 A（冻结未启动→resumed 1 次、预算+1）、B（跑完未写回→reused 1 次、预算+0）、C（写回全丢→按账本 sha 找回，候选位+0、check+0、模拟+1）；单元: `test_payload_hash_matches_production_check_hash` | 真实账本损坏（人工删 attempt 行）下的对账 |
| 3 | `itertools.product(...)` 先物化整张网格再 `len()`；8 维×10 值直接 OOM | `plan_grid` 只算维度与乘积；`iter_grid` 惰性；`MAX_COMBINATIONS_PER_CALL=60` 超限返回 `COMBINATION_CAP_EXCEEDED`+`planned_total`，不分配不执行；`dry_run` 只回 `MAX_PREVIEW_ROWS=20` 行预览；skipped 预览惰性截断 | demo: 8 维×10 值报 `10**8` 且状态 `COMBINATION_CAP_EXCEEDED`；单元: `test_plan_grid_reports_huge_grid_without_allocating`、`test_iter_grid_is_lazy_and_ordered` | 无（纯逻辑） |
| 4 | `observe` 读 `PROTECTED_TARGET_REACHED.target_id`（真实事件里是 null → 永远 0 到达）；无验收分层；无 per-stage 声明 | `observe` 改读 `source_id`（与生产归档一致）；新增 `stage_profiles_v1.json` 声明 R8-7 保护目标 `#14`/`#3`（按真实 spawn/route 修正了基线写反的归属）、炮兵 `enemy_1112_emppnt#0`、重点 `enemy_1107_uoffcr#19`；`_completion_evidence` 分离缺失字段；`evaluate_stage_acceptance` 分 `failures`（确定矛盾）与 `gaps`（证据不足）→ `COMPLETE_WIN` / `NOT_WIN` / `INSUFFICIENT_EVIDENCE`；同 ID 重复到达不满足两个目标；fake 结果→`ARTIFACT_PROJECTION_NOT_REAL_WIN` | demo: 真实 M70 归档判 `COMPLETE_WIN`（两个不同到达 ID、炮兵/`#19` 击杀可见）；3 漏+缺 remaining → `NOT_WIN` 而非只报证据不足；同 ID 到两次不满足两目标；fake win 永不认证；单元 8 项（含真实 M70 gzip 重放） | 真实 CONTROLLED_RUNNER 全关上的验收 |
| 5 | `record_teaching` 只有单文件、无说话者 ID、无运行溯源 | `record_teacher_prompt` 先存原文+稳定 `message_id`（重复文本复用同一 ID）；Astra 引用 `teacher_message_id` 保存解释；`user_quote` 与存储原文不一致→`ASTRA_QUOTE_DIVERGES_FROM_STORED_TEACHER_MESSAGE`（不伪称教师原文）；观察带 `candidate_id`/`run_id`/`event_log`/`event_locator`，候选 ID 自动解析出确定性事件日志路径；三分文件 append-only；`source_capability` 标注来源能力；`search_variants` 接受并落 `teacher_message_id` | demo: 教师消息稳定 ID、逐字引用解析、分歧引用标记；单元: `test_teacher_message_id_is_stable_and_content_addressed`、`test_astra_paraphrase_is_flagged_not_labelled_verbatim`、`test_resolved_teacher_quote_uses_stored_text` | Astra 真实会话里引用教师消息的习惯 |

## 假后端完整 walkthrough（48 项检查全 PASS）

```
教师提示 → record_teacher_prompt（稳定 message_id）
        → Astra 引用该 ID 提出参数网格（search_variants, teacher_message_id=…）
        → dry_run 报告组合数与剩余额度（不花钱）
        → 8 维×10 值网格被拒（COMBINATION_CAP_EXCEEDED, 10**8, 不分配）
        → 正式跑：第一组合非法（INPUT_REJECTED, 只计 check）→ 第二组合合法
        → check PASS → 冻结 candidate-001 → 假 runner 一次完整模拟
        → observed 提取漏怪/到达/炮兵/死亡 + leak_delta
        → 故障注入：冻结未启动→恢复；跑完未写回→复用；写回全丢→按账本 sha 找回
        → 预算截断（usable 上限）→ skipped 报告
        → 真实 M70 归档经 observe() → COMPLETE_WIN 认证
        → record_teaching：逐字引用 vs 分歧引用 → 三分文件
        → 第二轮根据第一轮证据换机制 → candidate-002 假 WIN → WIN_PENDING_VERIFICATION
        → independent_verify（fake 模式诚实报 cache hit）
```

命令：`.venv/bin/python scripts/tactical_harness/run_demo_fake_backend.py output/tactical_harness_demo`（48 项断言）；
回归：`.venv/bin/python -m pytest tests/test_tactical_harness_v1.py tests/test_tactical_harness_review_fixes_v1.py -q`（19 项）。

## 仍须真实联调（假后端无法覆盖）

- **真实 Codex 会话冒烟**：用既有启动链拉起真实模型会话，喂 `ASTRA_OPERATING_MANUAL_v1.md`，确认它按手册调工具。
- **真实 CONTROLLED_RUNNER 全关**：`execution_backend=CONTROLLED_RUNNER` 下跑一次真关卡，确认 `observe`/`leak_delta`/`stage_acceptance` 在真实漏怪集合上分组正确。
- **`independent_verify` 真实路径**：真实后端下的新 run id 独立复跑 + 预算计费（fake 模式诚实短路为 cache hit）。
- **代理/额度/路由故障路径**：真实网络/额度故障下 `blocker` 分类（service vs ledger vs budget）是否与实际一致。
- **MCP 挂载 / Pi 侧**：把 harness 服务挂进既有 MCP 配置，确认 Codex 侧可见 `tools/list`。
- **完整证据父项接入**：R129 式完整父 bundle（含 `diagnostic_events.json`）经 `--parent` 注册后的跨谱系对照。

## 边界声明

- 全部结论仅限当前固定模拟器；不宣称实机、faithful、robust、概率 WIN、更少人数无解或全局最少。
- 本任务未推送；是否提交由用户决定。
- 未修改模拟机制、门禁、权限或既有权重；旧账本、原件、M70/R106 分支与无关脏文件保持不动。
