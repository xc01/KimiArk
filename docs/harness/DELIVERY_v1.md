# 交付说明 v1 —— KimiArk 可复用战术实验 harness

## 1. 它是什么

一个**薄封装**层，复用已跑通的生产闭环，不新建第二套模拟器、不新建认证系统、不自己做模型客户端。

```
scripts/tactical_harness/
  prepare_harness.py            参数化批次准备（父项注册 / 证据派生 / 账本 / 预算 / 授权）
  tactical_harness_service_v1.py  stdio JSON-RPC 服务：转发生产门禁 + 新增一批 Astra 工具
  run_demo_fake_backend.py       假后端端到端验收驱动
tests/test_tactical_harness_v1.py  TEST_ONLY_FAKE 回归测试
docs/harness/ASTRA_OPERATING_MANUAL_v1.md  Astra 照做手册
docs/harness/DELIVERY_v1.md        本文件
```

**复用而非重写**：

- 检查/冻结/运行/查询：直接转发 `scripts/kimiark_tactical_stdio_service_v1.py`（`check_plan` / `run_simulation` / `query_events` / `get_session_status`）。生产计数语义（去重、静态只扣 check、PASS 才占候选、STARTED 计模拟）**原样保留**。
- 认证/模型请求：留给远端已登录的官方 Codex。Pi/GLM **不读取、不复制、不转发**任何登录凭据，不静默切付费 API。`prepare_harness.py` 生成的 `model_authorization_v1.json` 只是声明 `provider=openai` + `extra_config_values`，真正的 Codex 启动链仍是既有的
  `scripts/run_kimiark_real_tool_closed_loop_v1.py` / `run_r8_1_gpt_c4_codex_cli_v1.py` / `codex_model_authorization_v1.py`。
- 经验/知识库：复用 `codex_experience_selector_v1.load_store` 的数据与字段，新增只读检索工具 `inspect_evidence(kind="kb"|"experience")`。**知识库此前未接入任何服务**，这里首次接上。

## 2. 需求对照

| 需求 | 实现 |
| --- | --- |
| 1 订阅接入 | 不碰凭据；`prepare` 只写授权声明；模型不可用/额度尽时服务 `status.blocker` + `stopped` 保存现场并报告，不自动 retry/resume。第一版不要求 Pi 充当模型客户端。 |
| 2 Astra 操作说明 | `docs/harness/ASTRA_OPERATING_MANUAL_v1.md`：查事实/能力/旧实验/原始事件、提搜索、读结果、追单局、复验，含完整小例子。经验/机制条目带 `applicable_conditions` / `source_url` / `sim_check_points` / 反例线索。 |
| 3 批量一等操作 | `search_variants`：父项 + 问题 + 可变操作（deploy/retreat/skill/frame/tile/direction/返场，`changes` 类型 set/remove/add/replace）+ 参数网格 + 可选整套 `actions`；`dry_run` 先给规模；粗扫后缩区间；无需为每个组合重写 JSON。 |
| 4 结果指导下一轮 | 返回 `attempted/dedup/static_fail/real_runs`；每变体 `observed`（漏怪 ID、双保护到达、炮兵/`#19`、死亡、complete_win）；有父项时给 `leak_delta`（消掉/新增哪些漏怪）；`complementary_by_leak_set` 按漏怪 ID 集合保留互补方案。原始事件默认不灌上下文，按需 `inspect_evidence`。 |
| 5 计数分离 | 轮 = 问题→跑一批→据证据决定下一步（`record_round`，默认上限 5）。`dry_run` 按剩余预算给 `usable_simulations` 并预留复验；超出即 `TRUNCATED_BY_BUDGET` + `skipped`；静态拒绝只计 check；重复输入 `DEDUP`；中断后 `get_session_status` 读回已完成组合。 |

## 3. 假后端已验证（全部在 TEST_ONLY_FAKE 下）

`scripts/tactical_harness/run_demo_fake_backend.py`（27 项断言）+ `tests/test_tactical_harness_v1.py`（3 项），实测通过。

- **教师提示原样到达战术端**：`record_teacher_prompt` 存原文并回显 `sha256`；断言与教师侧计算一致。
- **战术端查出一条相关经验 + 一条机制**：`inspect_evidence(kind="experience")` 返回 `applicable_conditions`/`responsible_paths`/`selector_verdict`；`kind="kb"` 返回 `summary`/`source_url`/`sim_check_points`。
- **提交多组合实验**：`dry_run` 报告组合数与剩余额度（不花钱）；正式跑经**真实生产 `check_plan`**：一条 PASS → 冻结 `candidate-001` → 真跑一次；另一条得到**真实静态拒绝** `SP_NOT_READY available_sp=44.7 required_sp=45.0`，只扣一次 check。
- **计数语义**：静态拒绝不占候选/模拟；`PASS` 占一个候选；`reserved_for_verification` 正确从可用模拟中扣除；预算截断批返回 `TRUNCATED_BY_BUDGET` 与 `skipped`；重复提交报 `DEDUP`（不重跑）。
- **据第一轮实际返回选第二轮**：第二轮 `record_round` 记录观测与 `next_reason`，改换机制（格子而非帧）后跑第二批，`candidate-002` 被假后端判 WIN 并写 `WIN_PENDING_VERIFICATION.json`。
- **复验诚实**：fake 模式下 `independent_verify` 返回 `CACHE_HIT_NOT_INDEPENDENT`（假后端对已完成候选返回 `IDEMPOTENT_COMPLETED`），`counts_as_independent_verification=false`——不把缓存命中当独立复验。
- **教学三分**：`record_teaching` 分别落 `teaching/user_quotes_v1.jsonl`、`astra_interpretations_v1.jsonl`、`observations_v1.jsonl`。
- **可回答"谁提出什么/实际跑了什么/为什么改方向"**：`batch_state.json` 的 `rounds`（expected/observed/next_reason/decision）+ `variants`（changes/status/candidate_id/observed）+ `teacher_prompts_v1.jsonl`。
- **事件口径**：`observe` 用**真实归档事件的字段约定**验证过（漏怪 ID 在 `ENEMY_LEAK.source_id`，损失在 `details.amount`），合成用例断言它不会把带漏怪的运行判成 complete_win。
- **无覆盖地保留原件**：每变体改父项前把派生上下文存档到 `input_bundle/evidence_by_parent/<parent>.json` 并记 sha，父项自身文件不被覆盖。

（另：`prepare_harness.py` 与一次性实证均使用 **R129 的真实完整 facts**（含 34 人目录、`stage_active_facts`、正确的 capability source hash、`m58_open_roster_policy`），因此上述 PASS 是**真实生产门禁**的 PASS，不是被 mock 掉的门禁。仅模拟执行器是 fake。）

## 4. 仍待真实联调（假后端无法覆盖）

- **真实 Codex 会话冒烟**：用既有启动链实际拉起 `gpt-6.2-astra`（或其他已授权模型）会话，喂 `ASTRA_OPERATING_MANUAL_v1.md`，确认它真能按手册调用工具。
- **真实完整模拟**：`execution_backend=CONTROLLED_RUNNER` 下跑一次真关卡，替换 fake executor；确认 `observe`/`leak_delta` 在真实漏怪集合上的分组。
- **`independent_verify` 真实路径**：真实后端下的新 run id 独立复跑 + 预算计费（fake 模式被诚实地短路为 cache hit）。
- **代理/额度/路由故障路径**：模拟真实网络/额度故障，确认 `blocker` + `stopped` 保存现场、不自动重试。
- **Pi / MCP 接线**：把 `tactical_harness_service_v1.py` 挂进既有 MCP 配置（`extra_config_values.mcp_servers.kimiark`），确认 Codex 侧可见 `tools/list`。
- **完整证据父项接入**：把 R129 式完整父 bundle（含 `diagnostic_events.json`）经 `--parent` 注册后，跨谱系对照（如 R106 vs R107 恢复版）在真实事件上跑通。
- **教学经验导入器接跨关规则**：把 `teaching/records_v1.jsonl` 里 `scope=CROSS_STAGE_PENDING` 的抽象规则，按需导入经验库并保留适用条件/反例。

## 5. 已验证 vs 待联调边界一览

| 环节 | 状态 |
| --- | --- |
| prepare（父项注册/证据派生/账本/预算/授权） | 已用真实 facts 验证 |
| 生产 check/去重/静态拒绝/PASS 冻结 | 已用真实生产服务代码验证（fake 执行器） |
| 预算截断 / 预留复验 / DEDUP | 已验证 |
| 事件口径（漏怪 ID / 保护到达 / 炮兵 / 死亡） | 已用真实归档事件验证 |
| 教师提示原样到达 / 教学三分 | 已验证 |
| 复验诚实性（cache hit ≠ 独立复验） | 已验证（fake 语义） |
| 真实模型会话 / 真实完整模拟 / 真实复验 | 待联调 |
| 代理/额度故障路径 | 待联调（离线不可复现真实故障） |
| MCP 挂载 / Pi 侧 | 待联调 |

## 6. 边界声明

- 全部结论仅限**当前固定模拟器**；不宣称实机、faithful、robust、概率 WIN、更少人数无解或全局最少。
- 本任务**未推送**；是否提交由用户决定。
- 未修改任何模拟机制、门禁、权限或既有权重；旧账本、原件、M70/R106 等分支与无关脏文件保持不动。
