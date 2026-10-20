# KimiArk M29 final report — 2026-10-20, V4/V5 evaluation supplement

## 结果与预算

- 本次补充的父提交：`01920d8a741cbef1801ff70acc1c72e80f94b7b7`。
- 该父提交已在远端 `refs/heads/master`；本轮提交后的实际远端SHA见最终交付报告。
- R8-7：未通关；V2/V3 是当前模型固定模拟下的合法战斗 LOSS。
- M29历史真实战术CLI：4/4。V1、V2、V3、V4均收到完整输出并完成contract。
- 2026-10-20追加战术修订授权：新增Codex CLI 1/2，attempt09真实启动；无第二次CLI启动。
- M29共享固定模拟：4/4。V2/V3/V4/V5各一次，均COMPLETED；V1静态冲突未模拟。
- 内部模型请求数：`UNKNOWN_CLI_INTERNAL`。

## 逐次执行

| 计划 | CLI/contract | 静态 | 模拟 | 结果 |
|---|---|---|---|---|
| V1 | 收到，contract PASS | Gallus frame5250再部署冷却冲突 | 未运行 | B_STATIC_CONFLICT |
| V2 | 收到，contract PASS | PASS | COMPLETED LOSS | 19杀、14漏、13干员死亡、life -12、#3死亡、#14到达 |
| V3 | 收到，contract PASS | PASS | COMPLETED LOSS | 8杀、25漏、11干员死亡、life -23、#3到达、#14死亡 |
| V4 | 收到，contract PASS | PASS（0冲突） | COMPLETED LOSS | 21杀、12漏、10干员死亡、life -10、#3死亡、#14到达 |
| V5 | 收到，contract/谱系PASS | PASS（0冲突） | COMPLETED LOSS | 24杀、9漏、9干员死亡、life -8、两保护目标均死亡、0到达；预期Melantha击杀#4成立 |

关键事件与哈希见：

- `docs/review/fc77177/m29_attempt05_causal_feedback_v1.json`
- `docs/review/fc77177/m29_attempt07_causal_feedback_v1.json`
- `docs/review/fc77177/m29_attempt08_infrastructure_failure_v1.json`
- `docs/review/fc77177/m29_simulation_reconciliation_v1.json`

原始材料与离线回放见：

- `docs/review/fc77177/m29_iteration_raw_manifest_v1.json`：169个输入/过程/计划/动作/模拟/反馈记录的路径、字节数、SHA-256和压缩索引。
- `docs/review/fc77177/m29_phase_replay_v2_v3.json`：V2/V3每个声明phase的职责、条件、直接事件、解释和UNKNOWN。
- `docs/review/fc77177/m29_v4_causal_feedback_v1.json`：V4原始输出/静态/动作/manifest哈希、阶段回放、十名干员死亡、14条失效命令和保护目标证据。
- `docs/review/fc77177/m29_v4_next_revision_feedback_compact_v1.json`：V5发送使用的紧凑事实；完整V4反馈保留在`m29_v4_causal_feedback_v1.json`。
- `output/r8_1_r8_7_batch_v1/main_08-07/m29_iteration_v1/attempt_09_cli/`：V5完整prompt、argv、进程、响应、contract和静态材料。
- `docs/review/fc77177/m29_v5_causal_feedback_v1.json`：V5阶段回放、预测核验、保护目标损失、炮兵伤害和14条失效命令。
- V2/V3的`diagnostic_events.json`与`diagnostic_summary.json`以`gzip -9`入库，原文件哈希和解压后哈希均记录在manifest中。
- attempt08的`llm_structured_output.json` SHA-256为`3a1ae2458ac566e94d59464cf0eb953abc2dff6d1397a4800c0e3ab16adfa09e`；contract PASS，静态结果UNKNOWN（未运行）。
- V4离线评估的静态结果SHA-256为`8e56d9153b41bf52aef6cee4dd667f44eb65945752f74d697d7b8d0cba3b32f4`；动作SHA-256为`3f8fc800dfdd85c38ee6a37fa355ceb3466410a894a1ba57fb755a5b69c886e3`。事件与summary均以gzip -9保存，manifest记录原文件和压缩文件哈希。

测试复现条件：

```bash
PYTHONPATH=src:scripts .venv/bin/python -m pytest -q \
  tests/test_m29_raw_and_phase_replay_v1.py \
  tests/test_gpt_tactical_stage_session_v1.py \
  tests/test_tactical_experience_loop_v1.py \
  tests/test_tactical_evaluation_gate_v1.py \
  test_behavioral_regressions.py test_robot_compiler.py test_review_regressions.py
```

新增的raw/phase测试会验证manifest哈希、gzip解压哈希、计划phase绑定和保存事件中的关键反例。大事件通过压缩文件自包含；不影响本测试但可能影响部分历史全库测试的本地未跟踪output依赖。

## 因果结论

- V2将#14护送到frame11624安全到达，但Lancet在frame1380死亡；Ansel/Steward在3180死亡，Hibiscus/Lava在3780死亡。幸存炮兵继续施压， officers/armor从frame4731开始漏出。#3在frame3330被炮兵最后一击。
- V3反转了保护目标结局：#3在frame2867到达，#14在frame3930被炮兵击杀。但开局失败更早：Fang在1269、香草（char_240_wyvern）在1599死亡，首漏发生在1611。
- V2更正：frame1860只有Kroos对路障#3的`DEVICE_DAMAGE`，没有`DEVICE_DESTROYED`；路障#3整个V2运行未摧毁。frame3030平民#3受炮击的是`DAMAGE`事件；同帧Ansel/Steward的`ENEMY_ABILITY_HIT`也存在。
- V4将预期`enemy_1108_uterer#4`在900–1260死亡兑现：Kroos在frame1080最后一击。但Lancet在630死亡，Hibiscus虽在1680部署，两医疗前提已失效。路障#3从未摧毁，炮兵未击杀且5759漏出。#3先受officer #8三次280伤害，再受炮兵2880/3030/3180三次950伤害并在3180死亡。#14在3620被路障#2挡住，8442释放，8774到达。
- V1的再部署冷却静态冲突不是战术失败，不得进入战斗经验；V4是合法战斗LOSS。
- V5吸收了V4的两项教训：路障#3在1815实际摧毁，两名常规医疗建立并实际治疗；但炮兵死亡门未成立，Steward/Durin伤害不足，#14在3930死亡，#3在5430死亡。它同时说明“清掉一处路障”或“局部击杀兑现”都不等于完整保护链成立。V5将漏怪从12降到9、击杀从21升到24，但保护目标结局退到0到达、2死亡，因此只能作为有明确结构差异的探索分支，不能覆盖M25最佳。

V4属于合法战斗LOSS。它的14条后续命令因“operator is not deployed”失效，说明早期医疗/承伤失败导致原阶段移交链不可执行；这不能推广为整个低星战略不可行。

V5也属于合法战斗LOSS。它的14条后续命令同样因干员未部署失效；这证实指令链必须绑定干员实际存活，而不是只修正前段经济。

## 工程与测试

- `battle_phases`纳入强制计划契约，推动GPT显式声明阶段目标、开始/完成条件、职责、存活依赖、移交和失效后果。
- 模拟门禁区分`FAILED_BEFORE_START`、`FAILED_AFTER_START_WITHOUT_SAVED_RESULT`、`FAILED_AFTER_START`和`COMPLETED`。
- 候选档案修正跨关卡归属，保留M25/M28有价值分支，未宣称唯一最佳。
- 重点回归：`tests/test_gpt_tactical_stage_session_v1.py` + `tests/test_m29_raw_and_phase_replay_v1.py` + `tests/test_tactical_experience_loop_v1.py` + `tests/test_tactical_evaluation_gate_v1.py`，33项通过。
- 修复runner在模拟已完成但分支状态文件缺失时的后处理失败；新增自包含回归，并创建`m29_branch_state_v1.json`保留M25 current best、M28探索分支及M29 V4/V5。
- 行为/机器人/审查回归：22项通过。
- 全库同环境父/子pytest对照：子`547 passed / 31 failed / 2 skipped`；父`529 passed / 47 failed / 2 skipped`。逐ID对照M29-only失败为0，31项为父/子共同历史失败；父多出的16项来自隔离worktree缺少未跟踪output artifacts。机器可查对照：`docs/review/fc77177/m29_full_test_parent_child_comparison_v1.json`。

## 状态边界

- simulator WIN：R8-1 C7/M25、R8-2 V15、R8-4 V4冻结保留。
- R8-7 perfect target：未达到；要求WIN、零漏、保护目标零死亡且全部安全到达。
- 干员死亡单独记录；未把零干员死亡加入硬目标。
- faithful、robust、实机通关：`NOT_EVALUATED`，不得因当前模拟结果升级。
- 概率联合下界未实现；不得宣称概率通关达标。
- R8-3/5/6：机制BLOCKED，本轮未扩关。

## 下一步

R8-7的M29模拟额度已耗尽；本轮新增CLI还剩1/2，但无模拟额度可验证新候选，因此不启动。V5确认的新约束是：炮兵击杀、两处后续路障清除和指挥存活性必须同时闭合；V4的单一“医疗建立”判断和V5的“首目标击杀/单路障清除”都不足以推出完整通关。下一轮若同时获得CLI与模拟授权，必须要求GPT重新设计炮兵处理与保护目标暴露的并发结构，而不是平移V5时间或拼接局部成功。
