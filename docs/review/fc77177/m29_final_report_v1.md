# KimiArk M29 final report — 2026-10-20

## 结果与预算

- 本地 HEAD：`243a45665bb224884a52041757ccf949afd808b3`。
- 推送后远端 `refs/heads/master`：`243a45665bb224884a52041757ccf949afd808b3`。
- R8-7：未通关；V2/V3 是当前模型固定模拟下的合法战斗 LOSS。
- M29真实战术CLI：4/4。V1、V2、V3、V4均收到完整输出并完成contract；仅V1/V2/V3进入静态/模拟路径。
- M29固定模拟：2/4。V2/V3各一次，均COMPLETED；V1静态冲突未模拟，V4 contract PASS后未静态检查、未模拟。
- 内部模型请求数：`UNKNOWN_CLI_INTERNAL`。

## 逐次执行

| 计划 | CLI/contract | 静态 | 模拟 | 结果 |
|---|---|---|---|---|
| V1 | 收到，contract PASS | Gallus frame5250再部署冷却冲突 | 未运行 | B_STATIC_CONFLICT |
| V2 | 收到，contract PASS | PASS | COMPLETED LOSS | 19杀、14漏、13干员死亡、life -12、#3死亡、#14到达 |
| V3 | 收到，contract PASS | PASS | COMPLETED LOSS | 8杀、25漏、11干员死亡、life -23、#3到达、#14死亡 |
| V4 | 收到，contract PASS | 未运行/UNKNOWN | 未运行 | 完整计划未推进 |

关键事件与哈希见：

- `docs/review/fc77177/m29_attempt05_causal_feedback_v1.json`
- `docs/review/fc77177/m29_attempt07_causal_feedback_v1.json`
- `docs/review/fc77177/m29_attempt08_infrastructure_failure_v1.json`
- `docs/review/fc77177/m29_simulation_reconciliation_v1.json`

原始材料与离线回放见：

- `docs/review/fc77177/m29_iteration_raw_manifest_v1.json`：104个输入/过程/计划/动作/模拟记录的路径、字节数、SHA-256和压缩索引。
- `docs/review/fc77177/m29_phase_replay_v2_v3.json`：V2/V3每个声明phase的职责、条件、直接事件、解释和UNKNOWN。
- V2/V3的`diagnostic_events.json`与`diagnostic_summary.json`以`gzip -9`入库，原文件哈希和解压后哈希均记录在manifest中。
- attempt08的`llm_structured_output.json` SHA-256为`3a1ae2458ac566e94d59464cf0eb953abc2dff6d1397a4800c0e3ab16adfa09e`；contract PASS，静态结果UNKNOWN（未运行）。

测试复现条件：

```bash
PYTHONPATH=src:scripts .venv/bin/python -m pytest -q \
  tests/test_m29_raw_and_phase_replay_v1.py \
  tests/test_tactical_experience_loop_v1.py \
  tests/test_tactical_evaluation_gate_v1.py \
  test_behavioral_regressions.py test_robot_compiler.py test_review_regressions.py
```

新增的raw/phase测试会验证manifest哈希、gzip解压哈希、计划phase绑定和保存事件中的关键反例。大事件通过压缩文件自包含；不影响本测试但可能影响部分历史全库测试的本地未跟踪output依赖。

## 因果结论

- V2将#14护送到frame11624安全到达，但Lancet在frame1380死亡；Ansel/Steward在3180死亡，Hibiscus/Lava在3780死亡。幸存炮兵继续施压， officers/armor从frame4731开始漏出。#3在frame3330被炮兵最后一击。
- V3反转了保护目标结局：#3在frame2867到达，#14在frame3930被炮兵击杀。但开局失败更早：Fang在1269、Wyvern在1599死亡，首漏发生在1611。
- V1的再部署冷却静态冲突和V4的启动后无输出都不是战术失败，不得进入战斗经验。

## 工程与测试

- `battle_phases`纳入强制计划契约，推动GPT显式声明阶段目标、开始/完成条件、职责、存活依赖、移交和失效后果。
- 模拟门禁区分`FAILED_BEFORE_START`、`FAILED_AFTER_START_WITHOUT_SAVED_RESULT`、`FAILED_AFTER_START`和`COMPLETED`。
- 候选档案修正跨关卡归属，保留M25/M28有价值分支，未宣称唯一最佳。
- 重点回归：`tests/test_tactical_experience_loop_v1.py` + `tests/test_tactical_evaluation_gate_v1.py`，20项通过。
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

R8-7的M29模型预算耗尽。唯一有界下一步是由Work批准新的R8-7预算后，以V2的#14清障/到达成果和V3的#3到达线索为分支，同时解决早期医疗/承伤层与幸存炮兵；下一轮必须检验阶段声明的关键生存或清障事件，而不是只复述阶段文本。
